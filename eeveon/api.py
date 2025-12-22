from fastapi import FastAPI, HTTPException, BackgroundTasks, Header, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import os
import json
import subprocess
from datetime import datetime
from typing import Optional, List, Dict
from pydantic import BaseModel

# Try local imports first (when running as package)
try:
    from .cli import load_config, save_config, SCRIPTS_DIR, LOGS_DIR, CONFIG_DIR, EEVEON_HOME, SecretsManager, log, load_nodes, get_auth_token
except ImportError:
    # Fallback for local development
    import sys
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from cli import load_config, save_config, SCRIPTS_DIR, LOGS_DIR, CONFIG_DIR, EEVEON_HOME, SecretsManager, log, load_nodes, get_auth_token

app = FastAPI(title="EEveon Dashboard API")

# Add CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
