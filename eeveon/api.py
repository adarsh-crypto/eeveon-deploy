from fastapi import FastAPI, HTTPException, BackgroundTasks, Header, Depends, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import os
import json
import subprocess
import hashlib
import hmac
from urllib.parse import urlparse
from datetime import datetime
from typing import Optional, List, Dict
import secrets
from pydantic import BaseModel

# Try local imports first (when running as package)
try:
    from .cli import (
        load_config,
        save_config,
        SCRIPTS_DIR,
        LOGS_DIR,
        CONFIG_DIR,
        EEVEON_HOME,
        SecretsManager,
        log,
        load_nodes,
        get_auth_token,
        load_ai_requests,
        save_ai_requests,
        execute_ai_action,
        log_ai_event,
    )
    from .ai import run_nl_request, load_ai_config, save_ai_config
except ImportError:
    # Fallback for local development
    import sys
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from cli import (
        load_config,
        save_config,
        SCRIPTS_DIR,
        LOGS_DIR,
        CONFIG_DIR,
        EEVEON_HOME,
        SecretsManager,
        log,
        load_nodes,
        get_auth_token,
        load_ai_requests,
        save_ai_requests,
        execute_ai_action,
        log_ai_event,
    )
    from ai import run_nl_request, load_ai_config, save_ai_config

app = FastAPI(title="EEveon Dashboard API")

# Add CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

WEBHOOK_DEDUPE_FILE = CONFIG_DIR / "webhook_dedupe.json"
WEBHOOK_EVENTS_FILE = CONFIG_DIR / "webhook_events.jsonl"


def append_webhook_event(record):
    WEBHOOK_EVENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(WEBHOOK_EVENTS_FILE, "a") as f:
        f.write(json.dumps(record) + "\n")


def load_webhook_dedupe():
    if not WEBHOOK_DEDUPE_FILE.exists():
        return []
    try:
        return json.loads(WEBHOOK_DEDUPE_FILE.read_text())
    except json.JSONDecodeError:
        return []


def save_webhook_dedupe(entries):
    WEBHOOK_DEDUPE_FILE.parent.mkdir(parents=True, exist_ok=True)
    WEBHOOK_DEDUPE_FILE.write_text(json.dumps(entries[-1000:], indent=2) + "\n")


def is_duplicate_delivery(delivery_id):
    if not delivery_id:
        return False
    entries = load_webhook_dedupe()
    seen = {entry.get("id") for entry in entries if isinstance(entry, dict)}
    if delivery_id in seen:
        return True
    entries.append({"id": delivery_id, "ts": datetime.now().isoformat()})
    save_webhook_dedupe(entries)
    return False


def extract_repo_full_name(url):
    if not url:
        return None
    if url.startswith("git@"):
        parts = url.split(":", 1)
        if len(parts) == 2:
            path = parts[1]
            if path.endswith(".git"):
                path = path[:-4]
            return path
        return None
    if url.startswith("http://") or url.startswith("https://") or url.startswith("ssh://"):
        parsed = urlparse(url)
        path = parsed.path.lstrip("/")
        if path.endswith(".git"):
            path = path[:-4]
        segments = path.split("/")
        if len(segments) >= 2:
            return "/".join(segments[:2])
    return None


def match_pipeline_for_repo(config, repo_full_name, clone_url, ssh_url):
    for name, pipeline in config.items():
        enabled = pipeline.get("webhook_enabled")
        if enabled is False:
            continue
        if enabled is None and not (pipeline.get("webhook_repo") or pipeline.get("webhook_secret")):
            continue

        if pipeline.get("webhook_repo") and repo_full_name:
            if pipeline["webhook_repo"].lower() == repo_full_name.lower():
                return name

        repo_url = pipeline.get("repo_url")
        if repo_url and repo_url in [clone_url, ssh_url]:
            return name

        repo_full = extract_repo_full_name(repo_url)
        if repo_full and repo_full_name and repo_full.lower() == repo_full_name.lower():
            return name
    return None


def get_allowed_branches(pipeline):
    branches = pipeline.get("webhook_branches")
    if branches is None:
        return [pipeline.get("branch")] if pipeline.get("branch") else []
    if isinstance(branches, list):
        return [b for b in branches if b]
    if isinstance(branches, str):
        return [b.strip() for b in branches.split(",") if b.strip()]
    return []


def get_webhook_secret(pipeline):
    secret = pipeline.get("webhook_secret")
    if not secret:
        return None
    if secret.startswith("ENC:"):
        return SecretsManager.decrypt("_system_", secret[4:])
    return secret


def verify_signature(secret, signature_header, payload_body):
    if not secret:
        return True
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode(), payload_body, hashlib.sha256).hexdigest()
    provided = signature_header.split("=", 1)[1]
    return hmac.compare_digest(expected, provided)


def run_deploy_and_update(project_name, commit_sha):
    deploy_script = SCRIPTS_DIR / "deploy.sh"
    if not deploy_script.exists():
        log("Deploy script not found", "ERROR")
        return False
    result = subprocess.run([str(deploy_script), project_name])
    if result.returncode != 0:
        log(f"Webhook deploy failed for {project_name}", "ERROR")
        return False
    config = load_config()
    if project_name in config:
        config[project_name]["last_commit"] = commit_sha
        config[project_name]["pending_commit"] = None
        config[project_name]["approved_commit"] = None
        config[project_name]["last_webhook_commit"] = commit_sha
        save_config(config)
    return True

# Security
async def verify_token(x_eeveon_token: str = Header(None)):
    expected = get_auth_token()
    if not x_eeveon_token or x_eeveon_token != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing access token")
    return x_eeveon_token

# Models
class SiteConfig(BaseModel):
    name: str
    repo_url: str
    branch: str
    deploy_path: str
    strategy: str = "standard"
    approve: bool = False
    interval: int = 120

class SecretInput(BaseModel):
    project: str
    key: str
    value: str

# API Endpoints
@app.get("/api/config", dependencies=[Depends(verify_token)])
async def get_full_config():
    return load_config()

@app.get("/api/status", dependencies=[Depends(verify_token)])
async def get_system_status():
    config = load_config()
    sites = []
    
    for name, data in config.items():
        sites.append({
            "name": name,
            "repo": data.get("repo_url"),
            "branch": data.get("branch"),
            "strategy": data.get("strategy", "standard"),
            "last_commit": data.get("last_commit", "N/A"),
            "pending_commit": data.get("pending_commit"),
            "status": "active" if data.get("enabled", True) else "disabled"
        })
        
    nodes = load_nodes()
    return {
        "home": str(EEVEON_HOME),
        "sites": sites,
        "node_count": len(nodes)
    }

@app.post("/api/deploy/{project}", dependencies=[Depends(verify_token)])
async def trigger_deploy(project: str):
    log(f"API: Triggering deployment for {project}", "INFO")
    deploy_script = SCRIPTS_DIR / "deploy.sh"
    if not deploy_script.exists():
        raise HTTPException(status_code=500, detail="Deploy script not found")
        
    # Run in background
    subprocess.Popen([str(deploy_script), project], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return {"message": f"Deployment triggered for {project}"}

@app.post("/api/approve/{project}", dependencies=[Depends(verify_token)])
async def approve_site(project: str):
    log(f"API: Approving pending commit for {project}", "SUCCESS")
    config = load_config()
    if project not in config:
        raise HTTPException(status_code=404, detail="Project not found")
        
    pending = config[project].get('pending_commit')
    if not pending:
        raise HTTPException(status_code=400, detail="No pending deployment")
        
    config[project]['approved_commit'] = pending
    config[project]['pending_commit'] = None
    save_config(config)
    return {"message": f"Approved commit {pending[:7]}"}

@app.get("/api/logs", dependencies=[Depends(verify_token)])
async def get_logs(lines: int = 100):
    log_file = LOGS_DIR / f"deploy-{datetime.now().strftime('%Y-%m-%d')}.log"
    if not log_file.exists():
        return {"logs": []}
        
    try:
        result = subprocess.run(["tail", "-n", str(lines), str(log_file)], capture_output=True, text=True)
        return {"logs": result.stdout.splitlines()}
    except Exception as e:
        return {"error": str(e)}

class ChannelConfig(BaseModel):
    enabled: bool = False
    webhook_url: Optional[str] = None
    bot_token: Optional[str] = None
    chat_id: Optional[str] = None
    events: Dict[str, bool] = {"success": True, "failure": True, "warning": True, "info": True}

class NotificationSettings(BaseModel):
    slack: Optional[ChannelConfig] = None
    teams: Optional[ChannelConfig] = None
    discord: Optional[ChannelConfig] = None
    telegram: Optional[ChannelConfig] = None


class AIParseRequest(BaseModel):
    request: str
    model: Optional[str] = None
    base_url: Optional[str] = None
    timeout: Optional[int] = None
    provider: Optional[str] = None
    api_key: Optional[str] = None


class AIRequestCreate(BaseModel):
    request: str
    model: Optional[str] = None
    base_url: Optional[str] = None
    timeout: Optional[int] = None
    provider: Optional[str] = None
    api_key: Optional[str] = None
    auto_execute: bool = False


class AIConfigUpdate(BaseModel):
    provider: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    timeout_s: Optional[int] = None
    auto_execute_safe: Optional[bool] = None
    api_key: Optional[str] = None

@app.get("/api/notifications", dependencies=[Depends(verify_token)])
async def get_notifications():
    notify_file = CONFIG_DIR / "notifications.json"
    if not notify_file.exists():
        return {"slack_enabled": False, "teams_enabled": False}
    with open(notify_file, 'r') as f:
        return json.load(f)

@app.post("/api/notifications", dependencies=[Depends(verify_token)])
async def update_notifications(settings: NotificationSettings):
    notify_file = CONFIG_DIR / "notifications.json"
    
    # We encrypt sensitive fields before saving
    config = settings.dict()
    
    for channel in ["slack", "teams", "discord"]:
        if config.get(channel) and config[channel].get("webhook_url"):
            val = config[channel]["webhook_url"]
            if val and not val.startswith("ENC:"):
                config[channel]["webhook_url"] = "ENC:" + SecretsManager.encrypt("_system_", val)
    
    if config.get("telegram"):
        if config["telegram"].get("bot_token"):
            val = config["telegram"]["bot_token"]
            if val and not val.startswith("ENC:"):
                config["telegram"]["bot_token"] = "ENC:" + SecretsManager.encrypt("_system_", val)
                
    with open(notify_file, 'w') as f:
        json.dump(config, f, indent=2)
    return {"message": "Notifications updated successfully"}


@app.post("/api/webhooks/github")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: str = Header(None),
    x_github_event: str = Header(None),
    x_github_delivery: str = Header(None),
):
    body = await request.body()
    try:
        payload = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    if not x_github_event:
        raise HTTPException(status_code=400, detail="Missing X-GitHub-Event")

    if is_duplicate_delivery(x_github_delivery):
        append_webhook_event({
            "timestamp": datetime.now().isoformat(),
            "delivery_id": x_github_delivery,
            "event": x_github_event,
            "status": "duplicate",
        })
        return {"status": "duplicate"}

    repo = payload.get("repository", {})
    repo_full_name = repo.get("full_name")
    clone_url = repo.get("clone_url")
    ssh_url = repo.get("ssh_url")
    config = load_config()
    project = match_pipeline_for_repo(config, repo_full_name, clone_url, ssh_url)

    if not project:
        append_webhook_event({
            "timestamp": datetime.now().isoformat(),
            "delivery_id": x_github_delivery,
            "event": x_github_event,
            "repo": repo_full_name,
            "status": "ignored_no_match",
        })
        return {"status": "ignored_no_match"}

    pipeline = config.get(project, {})
    secret = get_webhook_secret(pipeline)
    if not verify_signature(secret, x_hub_signature_256, body):
        append_webhook_event({
            "timestamp": datetime.now().isoformat(),
            "delivery_id": x_github_delivery,
            "event": x_github_event,
            "repo": repo_full_name,
            "project": project,
            "status": "invalid_signature",
        })
        raise HTTPException(status_code=401, detail="Invalid signature")

    if x_github_event == "ping":
        append_webhook_event({
            "timestamp": datetime.now().isoformat(),
            "delivery_id": x_github_delivery,
            "event": x_github_event,
            "repo": repo_full_name,
            "project": project,
            "status": "pong",
        })
        return {"status": "pong"}

    branch = None
    commit_sha = None
    commit_msg = ""
    action = payload.get("action")

    if x_github_event == "push":
        if payload.get("deleted"):
            append_webhook_event({
                "timestamp": datetime.now().isoformat(),
                "delivery_id": x_github_delivery,
                "event": x_github_event,
                "repo": repo_full_name,
                "project": project,
                "status": "ignored_deleted_ref",
            })
            return {"status": "ignored_deleted_ref"}
        ref = payload.get("ref", "")
        branch = ref.split("/")[-1] if ref else None
        commit_sha = payload.get("after")
        head_commit = payload.get("head_commit") or {}
        commit_msg = head_commit.get("message", "")
    elif x_github_event == "release":
        if action not in ["published", "released"]:
            append_webhook_event({
                "timestamp": datetime.now().isoformat(),
                "delivery_id": x_github_delivery,
                "event": x_github_event,
                "repo": repo_full_name,
                "project": project,
                "status": f"ignored_action:{action}",
            })
            return {"status": "ignored_action"}
        release = payload.get("release") or {}
        branch = release.get("target_commitish")
        commit_sha = release.get("tag_name") or ""
        commit_msg = release.get("name") or "release"
    else:
        append_webhook_event({
            "timestamp": datetime.now().isoformat(),
            "delivery_id": x_github_delivery,
            "event": x_github_event,
            "repo": repo_full_name,
            "project": project,
            "status": "ignored_event",
        })
        return {"status": "ignored_event"}

    allowed_branches = get_allowed_branches(pipeline)
    if allowed_branches and branch not in allowed_branches:
        append_webhook_event({
            "timestamp": datetime.now().isoformat(),
            "delivery_id": x_github_delivery,
            "event": x_github_event,
            "repo": repo_full_name,
            "project": project,
            "branch": branch,
            "status": "ignored_branch",
        })
        return {"status": "ignored_branch"}

    if pipeline.get("enabled") is False:
        append_webhook_event({
            "timestamp": datetime.now().isoformat(),
            "delivery_id": x_github_delivery,
            "event": x_github_event,
            "repo": repo_full_name,
            "project": project,
            "branch": branch,
            "status": "ignored_paused",
        })
        return {"status": "ignored_paused"}

    if pipeline.get("approval_required"):
        config[project]["pending_commit"] = commit_sha
        config[project]["last_webhook_commit"] = commit_sha
        save_config(config)
        notify_script = SCRIPTS_DIR / "notify.sh"
        if notify_script.exists():
            subprocess.Popen([
                str(notify_script),
                project,
                "warning",
                f"Webhook commit awaiting approval on {branch}",
                commit_sha or "",
                commit_msg,
            ])
        append_webhook_event({
            "timestamp": datetime.now().isoformat(),
            "delivery_id": x_github_delivery,
            "event": x_github_event,
            "repo": repo_full_name,
            "project": project,
            "branch": branch,
            "commit": commit_sha,
            "status": "pending_approval",
        })
        return {"status": "pending_approval"}

    append_webhook_event({
        "timestamp": datetime.now().isoformat(),
        "delivery_id": x_github_delivery,
        "event": x_github_event,
        "repo": repo_full_name,
        "project": project,
        "branch": branch,
        "commit": commit_sha,
        "status": "deploy_started",
    })

    background_tasks.add_task(run_deploy_and_update, project, commit_sha or "")
    return {"status": "deploy_started", "project": project}


@app.post("/api/ai/parse", dependencies=[Depends(verify_token)])
async def ai_parse(payload: AIParseRequest):
    result = run_nl_request(
        payload.request,
        provider=payload.provider,
        base_url=payload.base_url,
        model=payload.model,
        timeout_s=payload.timeout,
        api_key=payload.api_key,
    )
    if not result["ok"]:
        raise HTTPException(status_code=400, detail={
            "error": result["error"],
            "raw": result["raw"],
        })
    return result


@app.get("/api/ai/config", dependencies=[Depends(verify_token)])
async def get_ai_config():
    config = load_ai_config()
    if config.get("api_key"):
        config["api_key"] = None
    return config


@app.post("/api/ai/config", dependencies=[Depends(verify_token)])
async def update_ai_config(payload: AIConfigUpdate):
    config = load_ai_config()
    if payload.provider is not None:
        config["provider"] = payload.provider
    if payload.base_url is not None:
        config["base_url"] = payload.base_url
    if payload.model is not None:
        config["model"] = payload.model
    if payload.timeout_s is not None:
        config["timeout_s"] = payload.timeout_s
    if payload.auto_execute_safe is not None:
        config["auto_execute_safe"] = payload.auto_execute_safe
    if payload.api_key is not None:
        if payload.api_key == "":
            config["api_key"] = None
        else:
            if payload.api_key.startswith("ENC:"):
                config["api_key"] = payload.api_key
            else:
                config["api_key"] = "ENC:" + SecretsManager.encrypt("_system_", payload.api_key)
    return save_ai_config(config)


@app.post("/api/ai/request", dependencies=[Depends(verify_token)])
async def ai_request(payload: AIRequestCreate):
    result = run_nl_request(
        payload.request,
        provider=payload.provider,
        base_url=payload.base_url,
        model=payload.model,
        timeout_s=payload.timeout,
        api_key=payload.api_key,
    )
    if not result["ok"]:
        raise HTTPException(status_code=400, detail={
            "error": result["error"],
            "raw": result["raw"],
        })

    requests = load_ai_requests()
    request_id = f"ai-{secrets.token_hex(4)}"
    record = {
        "id": request_id,
        "request": payload.request,
        "tool_call": result["data"],
        "raw": result["raw"],
        "status": "pending",
        "created_at": datetime.now().isoformat(),
        "created_by": "api",
        "approved_at": None,
        "executed_at": None,
        "error": None,
    }

    log_ai_event(
        "ai_request_created",
        request_id=request_id,
        tool=record["tool_call"].get("tool"),
        status="pending",
        actor="api",
    )

    config = load_ai_config()
    auto_execute = payload.auto_execute or config.get("auto_execute_safe", False)

    if auto_execute and not result["data"]["safety"].get("requires_confirmation"):
        ok, message = execute_ai_action(result["data"], approved=True)
        record["approved_at"] = datetime.now().isoformat()
        record["executed_at"] = datetime.now().isoformat()
        record["status"] = "executed" if ok else "failed"
        record["error"] = None if ok else message
        log_ai_event(
            "ai_request_executed",
            request_id=request_id,
            tool=record["tool_call"].get("tool"),
            status="success" if ok else "failed",
            actor="api",
            detail=message,
        )

    requests[request_id] = record
    save_ai_requests(requests)
    return record


@app.get("/api/ai/requests", dependencies=[Depends(verify_token)])
async def list_ai_requests():
    requests = load_ai_requests()
    return list(requests.values())


@app.post("/api/ai/approve/{request_id}", dependencies=[Depends(verify_token)])
async def approve_ai_request(request_id: str):
    requests = load_ai_requests()
    record = requests.get(request_id)
    if not record:
        raise HTTPException(status_code=404, detail="AI request not found")
    if record.get("status") in ["executed", "failed"]:
        raise HTTPException(status_code=400, detail="AI request already completed")

    log_ai_event(
        "ai_request_approved",
        request_id=request_id,
        tool=record.get("tool_call", {}).get("tool"),
        status="approved",
        actor="api",
    )

    ok, message = execute_ai_action(record["tool_call"], approved=True)
    record["approved_at"] = datetime.now().isoformat()
    record["executed_at"] = datetime.now().isoformat()
    record["status"] = "executed" if ok else "failed"
    record["error"] = None if ok else message
    requests[request_id] = record
    save_ai_requests(requests)
    log_ai_event(
        "ai_request_executed",
        request_id=request_id,
        tool=record.get("tool_call", {}).get("tool"),
        status="success" if ok else "failed",
        actor="api",
        detail=message,
    )
    if not ok:
        raise HTTPException(status_code=400, detail=message)
    return record

@app.post("/api/rollback/{project}", dependencies=[Depends(verify_token)])
async def rollback_project(project: str):
    log(f"API: Rollback command received for {project}", "WARNING")
    config = load_config()
    if project not in config:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Simple rollback: re-deploy last known good commit if it's different
    # This is a placeholder for a more robust history system in Phase 2
    deploy_script = SCRIPTS_DIR / "deploy.sh"
    subprocess.Popen([str(deploy_script), project], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return {"message": f"Rollback initiated for {project}"}

@app.delete("/api/remove/{project}", dependencies=[Depends(verify_token)])
async def remove_project(project: str):
    log(f"API: Removing project {project} from configuration", "WARNING")
    config = load_config()
    if project in config:
        del config[project]
        save_config(config)
        return {"message": f"Project {project} removed"}
    raise HTTPException(status_code=404, detail="Project not found")

@app.get("/api/nodes/check/{node_id}", dependencies=[Depends(verify_token)])
async def check_node_health(node_id: str):
    nodes_file = CONFIG_DIR / "nodes.json"
    if not nodes_file.exists():
        return {"status": "error", "message": "No nodes configured"}
    
    with open(nodes_file, 'r') as f:
        nodes = json.load(f)
    
    if node_id not in nodes:
        return {"status": "error", "message": "Node not found"}
        
    node = nodes[node_id]
    log(f"API: Checking connectivity for node {node_id} ({node['ip']})", "INFO")
    try:
        # Quick SSH check
        cmd = ["ssh", "-o", "ConnectTimeout=3", "-o", "BatchMode=yes", f"{node['user']}@{node['ip']}", "exit"]
        res = subprocess.run(cmd, capture_output=True)
        status = "active" if res.returncode == 0 else "offline"
        return {"status": status, "id": node_id}
    except:
        return {"status": "offline", "id": node_id}
        
@app.get("/api/nodes", dependencies=[Depends(verify_token)])
async def get_nodes():
    nodes_file = CONFIG_DIR / "nodes.json"
    if not nodes_file.exists():
        return {}
    with open(nodes_file, 'r') as f:
        return json.load(f)

# Static files and frontend
DASHBOARD_DIR = Path(__file__).parent / "dashboard"
app.mount("/static", StaticFiles(directory=str(DASHBOARD_DIR / "static")), name="static")

@app.get("/")
async def get_dashboard():
    from fastapi.responses import FileResponse
    return FileResponse(DASHBOARD_DIR / "index.html")
