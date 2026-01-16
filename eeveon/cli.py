#!/usr/bin/env python3
"""
Eeveon CI/CD Pipeline CLI Tool
Manages continuous deployment from GitHub to production server
"""

import os
import json
import subprocess
import shutil
import argparse
import secrets
from pathlib import Path
from datetime import datetime
from cryptography.fernet import Fernet

START_TIME = datetime.now()
try:
    from rich.console import Console
    from rich.logging import RichHandler
    from rich.live import Live
    from rich.table import Table
    from rich.panel import Panel
    from rich.layout import Layout
    from rich.text import Text
    import logging
    RICH_AVAILABLE = True
    console = Console()
except ImportError:
    RICH_AVAILABLE = False

# Configuration and Data paths (Use user's home directory for portability)
EEVEON_HOME = Path.home() / ".eeveon"
CONFIG_DIR = EEVEON_HOME / "config"
LOGS_DIR = EEVEON_HOME / "logs"
DEPLOYMENTS_DIR = EEVEON_HOME / "deployments"
KEYS_DIR = EEVEON_HOME / "keys"
AI_REQUESTS_FILE = CONFIG_DIR / "ai_requests.json"
AI_AUDIT_FILE = CONFIG_DIR / "ai_audit.jsonl"

# Package paths (where scripts are located)
PACKAGE_DIR = Path(__file__).parent
SCRIPTS_DIR = PACKAGE_DIR / "scripts"

# Ensure data directories exist
for dir_path in [CONFIG_DIR, LOGS_DIR, DEPLOYMENTS_DIR, KEYS_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

CONFIG_FILE = CONFIG_DIR / "pipeline.json"
AUTH_FILE = CONFIG_DIR / "auth.json"
GLOBAL_FILE = CONFIG_DIR / "global.json"
ENV_FILE = CONFIG_DIR / ".env"


def get_global_config():
    if not GLOBAL_FILE.exists():
        return {"log_retention_days": 7, "admin_user": os.getenv('USER')}
    with open(GLOBAL_FILE, 'r') as f:
        return json.load(f)


def check_dependencies(args):
    """Check for required system dependencies"""
    deps = {
        "rsync": "File synchronization",
        "jq": "JSON processing",
        "git": "Version control",
        "age": "Encryption (optional, using cryptography instead)",
        "ssh": "Remote access"
    }
    
    print(f"\n{Colors.BOLD}EEveon Dependency Check:{Colors.END}\n")
    all_ok = True
    
    for dep, desc in deps.items():
        result = subprocess.run(f"command -v {dep}", shell=True, capture_output=True)
        if result.returncode == 0:
            print(f"  {Colors.GREEN}[PASS] {dep.ljust(10)}{Colors.END} {desc}")
        else:
            if dep == "age":
                print(f"  {Colors.YELLOW}[INFO] {dep.ljust(10)}{Colors.END} {desc} (Using internal cryptography)")
            else:
                print(f"  {Colors.RED}[FAIL] {dep.ljust(10)}{Colors.END} {desc} [MISSING]")
                all_ok = False
                
    # Check Python packages
    try:
        import cryptography
        print(f"  {Colors.GREEN}[PASS] cryptography{Colors.END} Python library found")
    except ImportError:
        print(f"  {Colors.RED}[FAIL] cryptography{Colors.END} Python library NOT found")
        all_ok = False
        
    if all_ok:
        log("Environment is ready for production", "SUCCESS")
    else:
        log("Some dependencies are missing. System might be unstable.", "WARNING")


def rotate_logs(args):
    """Remove old logs to save space"""
    retention = args.days or get_global_config().get("log_retention_days", 7)
    log(f"Cleaning up logs older than {retention} days...", "INFO")
    
    count = 0
    now = datetime.now()
    for log_file in LOGS_DIR.glob("*.log"):
        mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
        if (now - mtime).days > retention:
            log_file.unlink()
            count += 1
            
    log(f"Removed {count} old log files", "SUCCESS")


def has_permission(required_role="deployer"):
    """Check if the current user has the required permission level"""
    current_user = os.getenv('USER')
    admin_user = get_global_config().get("admin_user")
    
    if current_user == admin_user:
        return True
        
    if not AUTH_FILE.exists():
        return False
        
    with open(AUTH_FILE, 'r') as f:
        auth_data = json.load(f)
        
    user_data = auth_data.get(current_user)
    if not user_data:
        return False
        
    role = user_data.get("role")
    if required_role == "admin":
        return role == "admin"
    if required_role == "deployer":
        return role in ["admin", "deployer"]
    
    return True


def verify_admin():
    if not has_permission("admin"):
        admin_user = get_global_config().get("admin_user")
        log(f"Permission Denied: Admin role required (Global Admin: {admin_user})", "ERROR")
        return False
    return True


def verify_deployer():
    if not has_permission("deployer"):
        log(f"Permission Denied: Deployer role required", "ERROR")
        return False
    return True


def manage_auth(args):
    """Manage user permissions and roles"""
    if not verify_admin(): return
    
    auth_data = {}
    if AUTH_FILE.exists():
        with open(AUTH_FILE, 'r') as f:
            auth_data = json.load(f)

    if args.action == 'add':
        auth_data[args.user] = {"role": args.role or "deployer", "added_at": datetime.now().isoformat()}
        with open(AUTH_FILE, 'w') as f:
            json.dump(auth_data, f, indent=2)
        log(f"User '{args.user}' added as {args.role or 'deployer'}", "SUCCESS")
        
    elif args.action == 'list':
        print(f"\n{Colors.BOLD}Configured Users & Roles:{Colors.END}")
        admin = get_global_config().get("admin_user")
        print(f"  {admin}: admin (Global)")
        for user, data in auth_data.items():
            print(f"  {user}: {data['role']}")
        print()


def manage_webhook(args):
    """Manage GitHub webhook configuration for a project."""
    if not verify_admin():
        return

    config = load_config()
    project_name = args.project
    if project_name not in config:
        log(f"Pipeline '{project_name}' not found", "ERROR")
        return

    pipeline = config[project_name]

    if args.action == "enable":
        pipeline["webhook_enabled"] = True
        log(f"Webhooks enabled for '{project_name}'", "SUCCESS")
    elif args.action == "disable":
        pipeline["webhook_enabled"] = False
        log(f"Webhooks disabled for '{project_name}'", "WARNING")
    elif args.action == "secret":
        if not args.value:
            log("Usage: eeveon webhook secret <project> <secret>", "ERROR")
            return
        encrypted = SecretsManager.encrypt("_system_", args.value)
        pipeline["webhook_secret"] = f"ENC:{encrypted}"
        log(f"Webhook secret updated for '{project_name}'", "SUCCESS")
    elif args.action == "repo":
        if not args.value:
            log("Usage: eeveon webhook repo <project> <owner/repo>", "ERROR")
            return
        pipeline["webhook_repo"] = args.value
        log(f"Webhook repo set for '{project_name}'", "SUCCESS")
    elif args.action == "branches":
        if not args.value:
            log("Usage: eeveon webhook branches <project> <branch1,branch2>", "ERROR")
            return
        branches = [b.strip() for b in args.value.split(",") if b.strip()]
        pipeline["webhook_branches"] = branches
        log(f"Webhook branches set for '{project_name}'", "SUCCESS")
    else:
        log("Unknown webhook action", "ERROR")
        return

    config[project_name] = pipeline
    save_config(config)
class SecretsManager:
    """Handles encryption and decryption of secrets using Fernet"""
    
    @staticmethod
    def get_key(project_name):
        key_file = KEYS_DIR / f"{project_name}.key"
        if not key_file.exists():
            key = Fernet.generate_key()
            with open(key_file, 'wb') as f:
                f.write(key)
            return key
        with open(key_file, 'rb') as f:
            return f.read()

    @classmethod
    def encrypt(cls, project_name, value):
        f = Fernet(cls.get_key(project_name))
        return f.encrypt(value.encode()).decode()

    @classmethod
    def decrypt(cls, project_name, encrypted_value):
        f = Fernet(cls.get_key(project_name))
        try:
            return f.decrypt(encrypted_value.encode()).decode()
        except:
            return None


class Colors:
    """ANSI color codes"""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'


def manage_system(args):
    """Handle system-level security/ops"""
    if args.action == 'decrypt':
        val = args.value
        if val.startswith("ENC:"):
            dec = SecretsManager.decrypt("_system_", val[4:])
            if dec:
                print(dec, end='')
            else:
                print(val, end='')
        else:
            print(val, end='')


def load_nodes():
    """Load remote nodes configuration"""
    nodes_file = CONFIG_DIR / "nodes.json"
    if nodes_file.exists():
        with open(nodes_file, 'r') as f:
            try:
                return json.load(f)
            except:
                return {}
    return {}


def log(message, level="INFO"):
    """Log message with timestamp"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    
    if RICH_AVAILABLE:
        color = {
            "INFO": "cyan",
            "SUCCESS": "green",
            "WARNING": "yellow",
            "ERROR": "red"
        }.get(level, "cyan")
        console.print(f"[bold {color}][{timestamp}] [{level}][/bold {color}] {message}")
    else:
        color = {
            "INFO": Colors.CYAN,
            "SUCCESS": Colors.GREEN,
            "WARNING": Colors.YELLOW,
            "ERROR": Colors.RED
        }.get(level, Colors.CYAN)
        print(f"{color}[{timestamp}] [{level}]{Colors.END} {message}")
    
    # Also log to file
    log_file = LOGS_DIR / f"deploy-{datetime.now().strftime('%Y-%m-%d')}.log"
    with open(log_file, 'a') as f:
        f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [{level}] {message}\n")


def run_command(command, cwd=None, capture=True):
    """Run shell command and return output"""
    try:
        if capture:
            result = subprocess.run(
                command,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        else:
            subprocess.run(command, shell=True, cwd=cwd, check=True)
            return None
    except subprocess.CalledProcessError as e:
        log(f"Command failed: {command}", "ERROR")
        log(f"Error: {e.stderr if hasattr(e, 'stderr') else str(e)}", "ERROR")
        return None


def load_config():
    """Load pipeline configuration"""
    if not CONFIG_FILE.exists():
        return {}
    
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        log("Invalid config file, creating new one", "WARNING")
        return {}


def save_config(config):
    """Save pipeline configuration"""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)
    log("Configuration saved", "SUCCESS")


def init_pipeline(args):
    """Initialize a new deployment pipeline"""
    if not verify_admin(): return
    log("Initializing new CI/CD pipeline...", "INFO")
    
    # Get repository details
    repo_url = args.repo or input(f"{Colors.CYAN}GitHub repository URL: {Colors.END}")
    branch = args.branch or input(f"{Colors.CYAN}Branch to deploy (default: main): {Colors.END}") or "main"
    deploy_path = args.path or input(f"{Colors.CYAN}Deployment path on server: {Colors.END}")
    project_name = args.name or input(f"{Colors.CYAN}Project name: {Colors.END}")
    strategy = args.strategy or "standard"
    
    if not all([repo_url, deploy_path, project_name]):
        log("All fields are required!", "ERROR")
        return
    
    # Create deployment directory
    deployment_dir = DEPLOYMENTS_DIR / project_name
    deployment_dir.mkdir(parents=True, exist_ok=True)
    
    # Create configuration
    config = load_config()
    config[project_name] = {
        "repo_url": repo_url,
        "branch": branch,
        "deploy_path": deploy_path,
        "deployment_dir": str(deployment_dir),
        "strategy": strategy,
        "approval_required": args.approve or False,
        "poll_interval": args.interval or 120,
        "nodes_enabled": not args.disable_nodes,
        "enabled": True,
        "last_commit": None,
        "approved_commit": None,
        "pending_commit": None,
        "created_at": datetime.now().isoformat()
    }
    
    save_config(config)
    
    # Create .gitignore if specified
    if args.gitignore:
        gitignore_path = deployment_dir / ".deployignore"
        with open(gitignore_path, 'w') as f:
            f.write(args.gitignore.replace(',', '\n'))
        log(f"Created .deployignore with patterns: {args.gitignore}", "INFO")
    
    # Create .env template
    env_template = deployment_dir / ".env.template"
    with open(env_template, 'w') as f:
        f.write("# Environment variables for deployment\n")
        f.write("# Copy this to .env and fill in your values\n\n")
    
    log(f"Pipeline '{project_name}' initialized successfully!", "SUCCESS")
    log(f"Deployment directory: {deployment_dir}", "INFO")
    log(f"Next steps:", "INFO")
    log(f"  1. Edit {env_template} if needed", "INFO")
    log(f"  2. Run: eeveon start {project_name}", "INFO")


def set_config(args):
    """Update pipeline configuration"""
    if not verify_admin(): return
    config = load_config()
    project_name = args.project
    
    if project_name not in config:
        log(f"Project '{project_name}' not found", "ERROR")
        return
    
    key = args.key
    value = args.value
    
    # Handle health check keys specially
    if key in ["health-url", "health-enabled", "health-rollback"]:
        health_file = CONFIG_DIR / "health_checks.json"
        health_config = {}
        if health_file.exists():
            with open(health_file, 'r') as f:
                try: health_config = json.load(f)
                except: health_config = {}
        
        if project_name not in health_config:
            health_config[project_name] = {"enabled": True}
            
        mapping = {
            "health-url": "http_url",
            "health-enabled": "enabled",
            "health-rollback": "rollback_on_failure"
        }
        
        real_key = mapping[key]
        # Type conversion
        if value.lower() == 'true': value = True
        elif value.lower() == 'false': value = False
        
        health_config[project_name][real_key] = value
        with open(health_file, 'w') as f:
            json.dump(health_config, f, indent=2)
        log(f"Updated health config: {key} to {value}", "SUCCESS")
        return

    # Standard config (pipeline.json)
    if value.lower() == 'true': value = True
    elif value.lower() == 'false': value = False
    elif value.isdigit(): value = int(value)
    
    config[project_name][key] = value
    save_config(config)
    log(f"Updated {key} to {value} for {project_name}", "SUCCESS")


def list_pipelines(args):
    """List all configured pipelines"""
    config = load_config()
    
    if not config:
        log("No pipelines configured yet", "WARNING")
        log("Run 'eeveon init' to create one", "INFO")
        return
    
    print(f"\n{Colors.BOLD}Configured Pipelines:{Colors.END}\n")
    
    for name, pipeline in config.items():
        status = f"{Colors.GREEN}[ENABLED]{Colors.END}" if pipeline.get('enabled') else f"{Colors.RED}[DISABLED]{Colors.END}"
        approval = f"{Colors.YELLOW}Manual Required{Colors.END}" if pipeline.get('approval_required') else f"{Colors.GREEN}Auto{Colors.END}"
        print(f"{Colors.BOLD}{name}{Colors.END}")
        print(f"  Repository: {pipeline['repo_url']}")
        print(f"  Strategy: {pipeline.get('strategy', 'standard')}")
        print(f"  Branch: {pipeline['branch']}")
        print(f"  Approval: {approval}")
        
        pending = pipeline.get('pending_commit')
        if pending:
            print(f"  {Colors.YELLOW}! Pending Commit: {pending[:7]}{Colors.END}")
            
        approved = pipeline.get('approved_commit')
        if approved:
            print(f"  {Colors.GREEN}* Approved (Ready): {approved[:7]}{Colors.END}")
            
        print(f"  Status: {status}")
        print()


def start_pipeline(args):
    """Start monitoring a pipeline"""
    if not verify_deployer(): return
    config = load_config()
    project_name = args.project
    
    if project_name not in config:
        log(f"Pipeline '{project_name}' not found", "ERROR")
        return
    
    pipeline = config[project_name]
    
    # Create systemd service
    service_content = f"""[Unit]
Description=Eeveon CI/CD Pipeline for {project_name}
After=network.target

[Service]
Type=simple
User={os.getenv('USER')}
WorkingDirectory={EEVEON_HOME}
ExecStart={SCRIPTS_DIR}/monitor.sh {project_name}
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
"""
    
    service_file = f"/tmp/eeveon-{project_name}.service"
    with open(service_file, 'w') as f:
        f.write(service_content)
    
    log(f"Starting pipeline '{project_name}'...", "INFO")
    log(f"To install as systemd service, run:", "INFO")
    log(f"  sudo cp {service_file} /etc/systemd/system/", "INFO")
    log(f"  sudo systemctl daemon-reload", "INFO")
    log(f"  sudo systemctl enable eeveon-{project_name}", "INFO")
    log(f"  sudo systemctl start eeveon-{project_name}", "INFO")
    
    # For now, run in foreground
    if args.foreground:
        log("Running in foreground mode (Ctrl+C to stop)...", "INFO")
        monitor_script = SCRIPTS_DIR / "monitor.sh"
        subprocess.run([str(monitor_script), project_name])


def stop_pipeline(args):
    """Stop a running pipeline"""
    if not verify_deployer(): return
    project_name = args.project
    log(f"Stopping pipeline '{project_name}'...", "INFO")
    
    # Stop systemd service if running
    result = run_command(f"sudo systemctl stop eeveon-{project_name} 2>/dev/null")
    log(f"Pipeline '{project_name}' stopped", "SUCCESS")


def manage_secrets(args):
    """Manage encrypted secrets for a project"""
    if not verify_admin(): return
    project_name = args.project
    config = load_config()
    
    if project_name not in config:
        log(f"Project '{project_name}' not found", "ERROR")
        return

    secrets_file = Path(config[project_name]['deployment_dir']) / "secrets.json"
    secrets = {}
    if secrets_file.exists():
        with open(secrets_file, 'r') as f:
            secrets = json.load(f)

    if args.action == 'set':
        if not args.key or not args.value:
            log("Usage: eeveon secrets set <project> <key> <value>", "ERROR")
            return
        encrypted_val = SecretsManager.encrypt(project_name, args.value)
        secrets[args.key] = encrypted_val
        with open(secrets_file, 'w') as f:
            json.dump(secrets, f, indent=2)
        log(f"Secret '{args.key}' set and encrypted successfully", "SUCCESS")
    
    elif args.action == 'list':
        if not secrets:
            log("No secrets found", "WARNING")
            return
        print(f"\n{Colors.BOLD}Secrets for {project_name}:{Colors.END}")
        for k in secrets:
            print(f"  {k}: [ENCRYPTED]")
        print()
    
    elif args.action == 'remove':
        if args.key in secrets:
            del secrets[args.key]
            with open(secrets_file, 'w') as f:
                json.dump(secrets, f, indent=2)
            log(f"Secret '{args.key}' removed", "SUCCESS")
        else:
            log(f"Secret '{args.key}' not found", "ERROR")


def decrypt_env(args):
    """Output decrypted secrets as ENV variable lines (used by deploy.sh)"""
    project_name = args.project
    config = load_config()
    
    if project_name not in config:
        return

    secrets_file = Path(config[project_name]['deployment_dir']) / "secrets.json"
    if not secrets_file.exists():
        return

    with open(secrets_file, 'r') as f:
        secrets = json.load(f)
        for k, v in secrets.items():
            decrypted = SecretsManager.decrypt(project_name, v)
            if decrypted:
                print(f"{k}={decrypted}")


def approve_deployment(args):
    """Approve a pending deployment"""
    if not verify_deployer(): return
    project_name = args.project
    config = load_config()
    
    if project_name not in config:
        log(f"Project '{project_name}' not found", "ERROR")
        return

    pending = config[project_name].get('pending_commit')
    if not pending:
        log(f"No pending deployment for {project_name}", "WARNING")
        return

    config[project_name]['approved_commit'] = pending
    config[project_name]['pending_commit'] = None
    save_config(config)
    log(f"Deployment approved for commit {pending[:7]}. Monitor will deploy it shortly.", "SUCCESS")


def reject_deployment(args):
    """Reject and clear a pending deployment"""
    if not verify_deployer(): return
    project_name = args.project
    config = load_config()
    
    if project_name not in config:
        log(f"Project '{project_name}' not found", "ERROR")
        return

    pending = config[project_name].get('pending_commit')
    if not pending:
        log(f"No pending deployment to reject", "WARNING")
        return

    config[project_name]['pending_commit'] = None
    save_config(config)
    log(f"Deployment rejected and cleared.", "SUCCESS")


def deploy_now(args):
    """Trigger immediate deployment"""
    if not verify_deployer(): return
    config = load_config()
    project_name = args.project
    
    if project_name not in config:
        log(f"Pipeline '{project_name}' not found", "ERROR")
        return
    
    log(f"Triggering deployment for '{project_name}'...", "INFO")
    
    deploy_script = SCRIPTS_DIR / "deploy.sh"
    subprocess.run([str(deploy_script), project_name])


def show_logs(args):
    """Show deployment logs"""
    project_name = args.project
    lines = args.lines or 50
    
    log_file = LOGS_DIR / f"deploy-{datetime.now().strftime('%Y-%m-%d')}.log"
    
    if not log_file.exists():
        log("No logs found for today", "WARNING")
        return
    
    if project_name:
        # Filter logs for specific project
        result = run_command(f"grep '{project_name}' {log_file} | tail -n {lines}")
    else:
        result = run_command(f"tail -n {lines} {log_file}")
    
    if result:
        print(result)


def load_ai_requests():
    if not AI_REQUESTS_FILE.exists():
        return {}
    try:
        with open(AI_REQUESTS_FILE, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}


def save_ai_requests(requests):
    with open(AI_REQUESTS_FILE, 'w') as f:
        json.dump(requests, f, indent=2)


def log_ai_event(event, request_id=None, tool=None, status=None, actor=None, detail=None):
    record = {
        "timestamp": datetime.now().isoformat(),
        "event": event,
        "request_id": request_id,
        "tool": tool,
        "status": status,
        "actor": actor,
        "detail": detail,
    }
    AI_AUDIT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(AI_AUDIT_FILE, 'a') as f:
        f.write(json.dumps(record) + "\n")


def resolve_project_name(config, identifier):
    if not identifier:
        return None, "missing_identifier"
    if identifier in config:
        return identifier, ""
    matches = [
        name for name in config.keys()
        if identifier.lower() in name.lower() or name.lower().endswith(identifier.lower())
    ]
    if len(matches) == 1:
        return matches[0], ""
    if len(matches) > 1:
        return None, f"ambiguous_identifier:{matches}"
    return None, "no_project_match"


def resolve_compose_path(pipeline):
    candidates = []
    if pipeline.get("docker_compose_file"):
        candidates.append(pipeline.get("docker_compose_file"))
    deploy_path = pipeline.get("deploy_path") or ""
    deployment_dir = pipeline.get("deployment_dir") or ""
    if deploy_path:
        candidates.append(os.path.join(deploy_path, "docker-compose.yml"))
    if deployment_dir:
        candidates.append(os.path.join(deployment_dir, "repo", "docker-compose.yml"))
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate)
        if not path.is_absolute():
            path = Path(deployment_dir) / path
        if path.exists():
            return path.resolve()
    return None


def run_docker_compose(args, cwd):
    docker_bin = shutil.which("docker")
    docker_compose_bin = shutil.which("docker-compose")
    if docker_bin:
        result = subprocess.run(["docker", "compose"] + args, cwd=cwd)
        if result.returncode == 0:
            return result
        # Fall through to docker-compose if available
    if docker_compose_bin:
        return subprocess.run(["docker-compose"] + args, cwd=cwd)
    return None

def execute_ai_action(tool_call, approved=False):
    safety = tool_call.get("safety", {})
    if safety.get("requires_confirmation") and not approved:
        return False, "requires_confirmation"

    tool = tool_call.get("tool")
    args = tool_call.get("args", {})
    config = load_config()

    if tool == "deploy":
        project, error = resolve_project_name(config, args.get("environment"))
        if not project:
            return False, f"deploy_project_resolution_failed:{error}"
        if args.get("dry_run"):
            return True, "deploy_dry_run_not_supported"
        configured_branch = config.get(project, {}).get("branch")
        if args.get("branch") and configured_branch and args["branch"] != configured_branch:
            return False, f"branch_mismatch:configured={configured_branch}"
        deploy_script = SCRIPTS_DIR / "deploy.sh"
        if not deploy_script.exists():
            return False, "deploy_script_not_found"
        result = subprocess.run([str(deploy_script), project])
        if result.returncode != 0:
            return False, f"deploy_failed:{result.returncode}"
        return True, f"deploy_started:{project}"

    if tool == "rollback":
        project, error = resolve_project_name(config, args.get("service"))
        if not project:
            return False, f"rollback_project_resolution_failed:{error}"
        target_version = args.get("target_version") or "previous"
        rollback_script = SCRIPTS_DIR / "rollback.sh"
        if not rollback_script.exists():
            return False, "rollback_script_not_found"
        result = subprocess.run([str(rollback_script), project, target_version, "--yes"])
        if result.returncode != 0:
            return False, f"rollback_failed:{result.returncode}"
        return True, f"rollback_started:{project}"

    if tool == "scale":
        project, error = resolve_project_name(config, args.get("service"))
        if not project:
            return False, f"scale_project_resolution_failed:{error}"
        if args.get("dry_run"):
            return True, "scale_dry_run"

        pipeline = config.get(project, {})
        compose_file = resolve_compose_path(pipeline)
        if not compose_file:
            return False, "scale_compose_file_not_found"

        service = pipeline.get("docker_service") or args.get("service") or project
        compose_dir = pipeline.get("docker_compose_dir")
        if compose_dir:
            compose_dir = Path(compose_dir)
            if not compose_dir.is_absolute():
                compose_dir = Path(pipeline.get("deployment_dir", "")) / compose_dir
        else:
            compose_dir = compose_file.parent

        cmd_args = ["-f", str(compose_file), "up", "-d", "--scale", f"{service}={args.get('replicas')}"]
        result = run_docker_compose(cmd_args, cwd=str(compose_dir))
        if result is None:
            return False, "docker_compose_not_found"
        if result.returncode != 0:
            return False, f"docker_compose_failed:{result.returncode}"

        config[project]["desired_replicas"] = args.get("replicas")
        config[project]["desired_replicas_updated_at"] = datetime.now().isoformat()
        if args.get("region"):
            config[project]["desired_replicas_region"] = args.get("region")
        save_config(config)
        log(f"Docker scale applied for '{project}' to {args.get('replicas')} replicas", "SUCCESS")
        return True, f"scale_applied:{project}"

    if tool == "pause_automation":
        project, error = resolve_project_name(config, args.get("service") or args.get("environment"))
        if not project:
            return False, f"pause_project_resolution_failed:{error}"
        config[project]["enabled"] = False
        config[project]["paused_at"] = datetime.now().isoformat()
        config[project]["paused_reason"] = "ai_request"
        save_config(config)
        log(f"Automation paused for '{project}'", "WARNING")
        return True, f"automation_paused:{project}"

    if tool == "resume_automation":
        project, error = resolve_project_name(config, args.get("service") or args.get("environment"))
        if not project:
            return False, f"resume_project_resolution_failed:{error}"
        config[project]["enabled"] = True
        config[project].pop("paused_at", None)
        config[project].pop("paused_reason", None)
        save_config(config)
        log(f"Automation resumed for '{project}'", "SUCCESS")
        return True, f"automation_resumed:{project}"

    if tool == "explain":
        return True, "explain_only"

    return False, "tool_not_supported"


def ai_assist(args):
    """Parse a natural language request into a validated tool call."""
    if not verify_deployer():
        return

    request = " ".join(args.request).strip() if args.request else ""
    if not request:
        log("Usage: eeveon ai \"<request>\"", "ERROR")
        return

    try:
        from .ai import run_nl_request
    except Exception as exc:
        log(f"AI module unavailable: {exc}", "ERROR")
        return

    result = run_nl_request(
        request,
        provider=args.provider,
        base_url=args.base_url,
        model=args.model,
        timeout_s=args.timeout,
        api_key=args.api_key,
    )

    if not result["ok"]:
        log(f"AI response failed validation: {result['error']}", "ERROR")
        if args.raw:
            print(result["raw"])
        return

    if args.raw:
        print(result["raw"])
    else:
        print(json.dumps(result["data"], indent=2))
    log(f"AI response validated in {result['latency_s']:.2f}s", "SUCCESS")


def ai_request(args):
    """Create a validated AI request and optionally execute."""
    if not verify_deployer():
        return

    request = " ".join(args.request).strip() if args.request else ""
    if not request:
        log("Usage: eeveon ai-request \"<request>\"", "ERROR")
        return

    try:
        from .ai import run_nl_request
    except Exception as exc:
        log(f"AI module unavailable: {exc}", "ERROR")
        return

    result = run_nl_request(
        request,
        provider=args.provider,
        base_url=args.base_url,
        model=args.model,
        timeout_s=args.timeout,
        api_key=args.api_key,
    )

    if not result["ok"]:
        log(f"AI response failed validation: {result['error']}", "ERROR")
        if args.raw:
            print(result["raw"])
        return

    requests = load_ai_requests()
    request_id = f"ai-{secrets.token_hex(4)}"
    record = {
        "id": request_id,
        "request": request,
        "tool_call": result["data"],
        "raw": result["raw"],
        "status": "pending",
        "created_at": datetime.now().isoformat(),
        "created_by": os.getenv("USER"),
        "approved_at": None,
        "executed_at": None,
        "error": None,
    }

    requests[request_id] = record
    save_ai_requests(requests)
    log(f"AI request queued: {request_id}", "INFO")
    log_ai_event(
        "ai_request_created",
        request_id=request_id,
        tool=record["tool_call"].get("tool"),
        status="pending",
        actor=os.getenv("USER"),
    )

    try:
        from .ai import load_ai_config
        ai_config = load_ai_config()
    except Exception:
        ai_config = {}

    auto_execute = args.auto or ai_config.get("auto_execute_safe", False)

    if auto_execute and not result["data"]["safety"].get("requires_confirmation"):
        ok, message = execute_ai_action(result["data"], approved=True)
        record["approved_at"] = datetime.now().isoformat()
        record["executed_at"] = datetime.now().isoformat()
        record["status"] = "executed" if ok else "failed"
        record["error"] = None if ok else message
        requests[request_id] = record
        save_ai_requests(requests)
        log_ai_event(
            "ai_request_executed",
            request_id=request_id,
            tool=record["tool_call"].get("tool"),
            status="success" if ok else "failed",
            actor=os.getenv("USER"),
            detail=message,
        )
        if ok:
            log(f"AI request executed: {message}", "SUCCESS")
        else:
            log(f"AI execution failed: {message}", "ERROR")
    elif auto_execute:
        log("AI request requires confirmation; use ai-approve", "WARNING")

    if args.raw:
        print(result["raw"])
    else:
        print(json.dumps(result["data"], indent=2))


def ai_list(args):
    """List AI requests and their statuses."""
    requests = load_ai_requests()
    if not requests:
        log("No AI requests found", "WARNING")
        return
    for request_id, record in requests.items():
        tool = record.get("tool_call", {}).get("tool", "unknown")
        status = record.get("status", "unknown")
        created = record.get("created_at", "n/a")
        print(f"{request_id}  {status}  {tool}  {created}")


def ai_approve(args):
    """Approve and execute a pending AI request."""
    if not verify_deployer():
        return
    requests = load_ai_requests()
    record = requests.get(args.request_id)
    if not record:
        log(f"AI request not found: {args.request_id}", "ERROR")
        return
    if record.get("status") in ["executed", "failed"]:
        log(f"AI request already completed: {args.request_id}", "WARNING")
        return

    log_ai_event(
        "ai_request_approved",
        request_id=args.request_id,
        tool=record.get("tool_call", {}).get("tool"),
        status="approved",
        actor=os.getenv("USER"),
    )

    ok, message = execute_ai_action(record["tool_call"], approved=True)
    record["approved_at"] = datetime.now().isoformat()
    record["executed_at"] = datetime.now().isoformat()
    record["status"] = "executed" if ok else "failed"
    record["error"] = None if ok else message
    requests[args.request_id] = record
    save_ai_requests(requests)
    log_ai_event(
        "ai_request_executed",
        request_id=args.request_id,
        tool=record.get("tool_call", {}).get("tool"),
        status="success" if ok else "failed",
        actor=os.getenv("USER"),
        detail=message,
    )

    if ok:
        log(f"AI request executed: {message}", "SUCCESS")
    else:
        log(f"AI execution failed: {message}", "ERROR")


def ai_config(args):
    """Get or update AI configuration."""
    try:
        from .ai import load_ai_config, save_ai_config
    except Exception as exc:
        log(f"AI module unavailable: {exc}", "ERROR")
        return

    config = load_ai_config()
    if args.action == "get":
        display = config.copy()
        if display.get("api_key"):
            display["api_key"] = "***"
        print(json.dumps(display, indent=2))
        return

    updated = config.copy()
    changed = False
    if args.provider is not None:
        updated["provider"] = args.provider
        changed = True
    if args.base_url is not None:
        updated["base_url"] = args.base_url
        changed = True
    if args.model is not None:
        updated["model"] = args.model
        changed = True
    if args.timeout is not None:
        updated["timeout_s"] = args.timeout
        changed = True
    if args.auto_execute is not None:
        updated["auto_execute_safe"] = args.auto_execute
        changed = True
    if args.api_key is not None:
        updated["api_key"] = args.api_key if args.api_key != "" else None
        changed = True

    if not changed:
        log("No changes provided. Use --provider/--base-url/--model/--timeout/--api-key/--auto-execute.", "ERROR")
        return

    saved = save_ai_config(updated)
    log("AI configuration updated", "SUCCESS")
    print(json.dumps(saved, indent=2))


def seed_rollback(args):
    """Seed rollback history from current deployed state."""
    if not verify_admin():
        return

    project_name = args.project
    config = load_config()
    if project_name not in config:
        log(f"Pipeline '{project_name}' not found", "ERROR")
        return

    pipeline = config[project_name]
    deploy_path = Path(pipeline.get("deploy_path", ""))
    if not deploy_path.exists():
        log(f"Deploy path not found: {deploy_path}", "ERROR")
        return

    deployment_dir = Path(pipeline.get("deployment_dir", ""))
    backup_dir = deployment_dir / "backups"
    history_file = deployment_dir / "deployment_history.json"
    backup_dir.mkdir(parents=True, exist_ok=True)
    if not history_file.exists():
        history_file.write_text("[]\n")

    if not shutil.which("rsync"):
        log("rsync is required for seeding rollback history", "ERROR")
        return

    target_path = deploy_path.resolve()
    version = f"seed-{int(datetime.now().timestamp())}"
    backup_path = backup_dir / version
    backup_path.mkdir(parents=True, exist_ok=True)

    log(f"Seeding rollback history for '{project_name}' from {target_path}", "INFO")
    result = subprocess.run(["rsync", "-a", f"{target_path}/", f"{backup_path}/"])
    if result.returncode != 0:
        log(f"Seed backup failed with code {result.returncode}", "ERROR")
        return

    try:
        history = json.loads(history_file.read_text())
    except json.JSONDecodeError:
        history = []

    entry = {
        "version": version,
        "commit": pipeline.get("last_commit"),
        "timestamp": datetime.now().isoformat(),
        "status": "success",
        "source": "seed",
        "path": str(target_path),
    }
    history.append(entry)

    keep = args.keep or pipeline.get("rollback_keep", 5)
    removed_versions = []
    if keep and isinstance(keep, int) and len(history) > keep:
        removed = history[:-keep]
        history = history[-keep:]
        removed_versions = [item.get("version") for item in removed if item.get("version")]

    history_file.write_text(json.dumps(history, indent=2) + "\n")

    for version_id in removed_versions:
        old_path = backup_dir / version_id
        if old_path.exists():
            shutil.rmtree(old_path, ignore_errors=True)

    log(f"Rollback history seeded as {version}", "SUCCESS")


def get_auth_token():
    """Load or generate dashboard access token"""
    auth_file = CONFIG_DIR / "dashboard_auth.json"
    if auth_file.exists():
        with open(auth_file, 'r') as f:
            return json.load(f).get("token")
    
    token = secrets.token_hex(16)
    with open(auth_file, 'w') as f:
        json.dump({"token": token}, f)
    return token


def launch_dashboard(args):
    """Launch the web management dashboard"""
    token = get_auth_token()
    try:
        import uvicorn
        from .api import app
    except ImportError:
        log("Dashboard dependencies missing. Run: pip install fastapi uvicorn", "ERROR")
        return

    port = args.port or 8080
    host = args.host or "127.0.0.1"
    
    log(f"Starting EEveon Dashboard Engine on {host}:{port}", "INFO")
    log(f"Access Token: {token}", "WARNING")
    log(f"Direct Login: http://{host}:{port}/?token={token}", "SUCCESS")
    
    if RICH_AVAILABLE:
        import threading
        import time
        
        def run_server():
            # Use warning level to hide initial startup spam
            uvicorn.run(app, host=host, port=port, access_log=False, log_level="warning")

        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()

        log(f"EEveon Engine is running at http://{host}:{port}", "SUCCESS")
        
        def get_status_table():
            config = load_config()
            nodes_data = load_nodes()
            uptime = datetime.now() - START_TIME
            uptime_str = str(uptime).split('.')[0] # HH:MM:SS
            
            table = Table(box=None, padding=(0, 2))
            table.add_column("System Status", style="bold cyan")
            table.add_column("Pipelines", style="green")
            table.add_column("Nodes", style="blue")
            table.add_column("Uptime", style="magenta")
            table.add_column("Memory", style="yellow")
            
            p_count = len(config)
            n_count = len(nodes_data)
            
            # Use psutil if available, otherwise dummy
            try:
                import psutil
                mem = f"{psutil.virtual_memory().percent}%"
            except ImportError:
                mem = "N/A"
                
            table.add_row("RUNNING", f"{p_count} Active", f"{n_count} Configured", uptime_str, mem)
            return Panel(table, title="[bold white]EEveon Engine v0.4.0-alpha[/bold white]", border_style="green")

        with Live(get_status_table(), refresh_per_second=2) as live:
            while True:
                time.sleep(1)
                live.update(get_status_table())
    else:
        log(f"Launching dashboard at http://{host}:{port}", "SUCCESS")
        uvicorn.run(app, host=host, port=port)


def manage_nodes(args):
    """Manage remote server nodes for multi-node deployment"""
    if not verify_admin(): return
    
    nodes_file = CONFIG_DIR / "nodes.json"
    nodes_data = load_nodes()

    if args.action == 'add':
        if not args.ip or not args.user:
            log("Usage: eeveon nodes add <ip> <user> [--name name]", "ERROR")
            return
        node_id = args.name or f"node-{len(nodes_data) + 1}"
        nodes_data[node_id] = {
            "ip": args.ip,
            "user": args.user,
            "added_at": datetime.now().isoformat(),
            "status": "active"
        }
        with open(nodes_file, 'w') as f:
            json.dump(nodes_data, f, indent=2)
        log(f"Node '{node_id}' ({args.user}@{args.ip}) added successfully", "SUCCESS")
        
    elif args.action == 'list':
        if not nodes_data:
            log("No nodes configured", "WARNING")
            return
        print(f"\n{Colors.BOLD}Configured Remote Nodes:{Colors.END}")
        for node_id, data in nodes_data.items():
            print(f"  {node_id}: {data['user']}@{data['ip']} ({data['status']})")
        print()
        
    elif args.action == 'remove':
        if args.name in nodes_data:
            del nodes_data[args.name]
            with open(nodes_file, 'w') as f:
                json.dump(nodes_data, f, indent=2)
            log(f"Node '{args.name}' removed", "SUCCESS")
        else:
            log(f"Node '{args.name}' not found", "ERROR")


def remove_pipeline(args):
    """Remove a pipeline configuration"""
    if not verify_admin(): return
    config = load_config()
    project_name = args.project
    
    if project_name not in config:
        log(f"Pipeline '{project_name}' not found", "ERROR")
        return
    
    confirm = input(f"{Colors.YELLOW}Are you sure you want to remove '{project_name}'? (yes/no): {Colors.END}")
    
    if confirm.lower() == 'yes':
        del config[project_name]
        save_config(config)
        log(f"Pipeline '{project_name}' removed", "SUCCESS")
    else:
        log("Cancelled", "INFO")


def main():
    parser = argparse.ArgumentParser(
        description="Eeveon CI/CD Pipeline - Manage continuous deployment from GitHub",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  eeveon init --repo https://github.com/user/repo.git --name myproject --path /var/www/myproject
  eeveon list
  eeveon start myproject
  eeveon deploy myproject
  eeveon logs myproject
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Init command
    init_parser = subparsers.add_parser('init', help='Initialize a new pipeline')
    init_parser.add_argument('--repo', help='GitHub repository URL')
    init_parser.add_argument('--branch', default='main', help='Branch to deploy (default: main)')
    init_parser.add_argument('--path', help='Deployment path on server')
    init_parser.add_argument('--name', help='Project name')
    init_parser.add_argument('--strategy', choices=['standard', 'blue-green'], default='standard', help='Deployment strategy')
    init_parser.add_argument('--approve', action='store_true', help='Require manual approval for deployments')
    init_parser.add_argument('--interval', type=int, help='Poll interval in seconds (default: 120)')
    init_parser.add_argument('--gitignore', help='Comma-separated patterns to ignore')
    init_parser.add_argument('--health-url', help='HTTP URL for health check')
    init_parser.add_argument('--disable-nodes', action='store_true', help='Disable multi-node sync for this pipeline')
    init_parser.set_defaults(func=init_pipeline)

    # Approve/Reject commands
    approve_parser = subparsers.add_parser('approve', help='Approve a pending deployment')
    approve_parser.add_argument('project', help='Project name')
    approve_parser.set_defaults(func=approve_deployment)

    reject_parser = subparsers.add_parser('reject', help='Reject a pending deployment')
    reject_parser.add_argument('project', help='Project name')
    reject_parser.set_defaults(func=reject_deployment)

    # Config command
    config_parser = subparsers.add_parser('config', help='Update configuration')
    config_parser.add_argument('project', help='Project name')
    config_parser.add_argument('key', help='Config key to update (e.g., strategy, branch)')
    config_parser.add_argument('value', help='New value')
    config_parser.set_defaults(func=set_config)

    # List command
    list_parser = subparsers.add_parser('list', help='List all pipelines')
    list_parser.set_defaults(func=list_pipelines)
    
    # Start command
    start_parser = subparsers.add_parser('start', help='Start monitoring a pipeline')
    start_parser.add_argument('project', help='Project name')
    start_parser.add_argument('-f', '--foreground', action='store_true', help='Run in foreground')
    start_parser.set_defaults(func=start_pipeline)
    
    # Stop command
    stop_parser = subparsers.add_parser('stop', help='Stop a pipeline')
    stop_parser.add_argument('project', help='Project name')
    stop_parser.set_defaults(func=stop_pipeline)
    
    # Deploy command
    deploy_parser = subparsers.add_parser('deploy', help='Trigger immediate deployment')
    deploy_parser.add_argument('project', help='Project name')
    deploy_parser.set_defaults(func=deploy_now)
    
    # Logs command
    logs_parser = subparsers.add_parser('logs', help='Show deployment logs')
    logs_parser.add_argument('project', nargs='?', help='Project name (optional)')
    logs_parser.add_argument('-n', '--lines', type=int, help='Number of lines to show')
    logs_parser.set_defaults(func=show_logs)
    
    # Remove command
    remove_parser = subparsers.add_parser('remove', help='Remove a pipeline')
    remove_parser.add_argument('project', help='Project name')
    remove_parser.set_defaults(func=remove_pipeline)

    # Seed rollback history
    seed_parser = subparsers.add_parser('seed-rollback', help='Seed rollback history from current deploy')
    seed_parser.add_argument('project', help='Project name')
    seed_parser.add_argument('--keep', type=int, help='Keep last N backups (default: 5)')
    seed_parser.set_defaults(func=seed_rollback)

    # System command (Internal/Security)
    system_parser = subparsers.add_parser('system', help='System-level operations')
    system_parser.add_argument('action', choices=['decrypt'], help='Action')
    system_parser.add_argument('value', help='Value to decrypt')
    system_parser.set_defaults(func=manage_system)

    # Check command
    check_parser = subparsers.add_parser('check', help='Check system dependencies')
    check_parser.set_defaults(func=check_dependencies)

    # Vacuum command
    vacuum_parser = subparsers.add_parser('vacuum', help='Rotate and clean up logs')
    vacuum_parser.add_argument('--days', type=int, help='Retention period in days')
    vacuum_parser.set_defaults(func=rotate_logs)

    # Auth command
    auth_parser = subparsers.add_parser('auth', help='Manage user roles (Admin Only)')
    auth_parser.add_argument('action', choices=['add', 'list', 'remove'], help='Action to perform')
    auth_parser.add_argument('user', nargs='?', help='User OS name')
    auth_parser.add_argument('role', choices=['admin', 'deployer', 'user'], nargs='?', help='Role to assign')
    auth_parser.set_defaults(func=manage_auth)

    # Webhook command
    webhook_parser = subparsers.add_parser('webhook', help='Manage GitHub webhook settings (Admin Only)')
    webhook_parser.add_argument('action', choices=['enable', 'disable', 'secret', 'repo', 'branches'], help='Action to perform')
    webhook_parser.add_argument('project', help='Project name')
    webhook_parser.add_argument('value', nargs='?', help='Value for the action')
    webhook_parser.set_defaults(func=manage_webhook)

    # Dashboard command
    dashboard_parser = subparsers.add_parser('dashboard', help='Launch the web dashboard')
    dashboard_parser.add_argument('--port', type=int, default=8080, help='Port to run on (default: 8080)')
    dashboard_parser.add_argument('--host', default='127.0.0.1', help='Host to bind to (default: 127.0.0.1)')
    dashboard_parser.set_defaults(func=launch_dashboard)

    # Secrets command
    secrets_parser = subparsers.add_parser('secrets', help='Manage encrypted secrets')
    secrets_parser.add_argument('action', choices=['set', 'list', 'remove'], help='Action to perform')
    secrets_parser.add_argument('project', help='Project name')
    secrets_parser.add_argument('key', nargs='?', help='Secret key')
    secrets_parser.add_argument('value', nargs='?', help='Secret value (for set)')
    secrets_parser.set_defaults(func=manage_secrets)

    # Internal: Decrypt env for deployment
    decrypt_parser = subparsers.add_parser('decrypt-env', help=argparse.SUPPRESS)
    decrypt_parser.add_argument('project')
    decrypt_parser.set_defaults(func=decrypt_env)

    # Nodes command
    nodes_parser = subparsers.add_parser('nodes', help='Manage remote server nodes (Admin Only)')
    nodes_parser.add_argument('action', choices=['add', 'list', 'remove'], help='Action to perform')
    nodes_parser.add_argument('ip', nargs='?', help='Node IP address')
    nodes_parser.add_argument('user', nargs='?', help='SSH username')
    nodes_parser.add_argument('--name', help='Node friendly name')
    nodes_parser.set_defaults(func=manage_nodes)

    # AI command
    ai_parser = subparsers.add_parser('ai', help='Parse NL into a safe tool call (no execution)')
    ai_parser.add_argument('request', nargs='+', help='Natural language request')
    ai_parser.add_argument('--provider', help='LLM provider (ollama or openai-compatible)')
    ai_parser.add_argument('--model', help='LLM model name (default: EEVEON_LLM_MODEL)')
    ai_parser.add_argument('--base-url', help='LLM endpoint (default: EEVEON_LLM_BASE_URL)')
    ai_parser.add_argument('--timeout', type=int, help='Request timeout in seconds')
    ai_parser.add_argument('--api-key', help='LLM API key (overrides config)')
    ai_parser.add_argument('--raw', action='store_true', help='Print raw model response')
    ai_parser.set_defaults(func=ai_assist)

    # AI request workflow
    ai_request_parser = subparsers.add_parser('ai-request', help='Queue a validated AI request')
    ai_request_parser.add_argument('request', nargs='+', help='Natural language request')
    ai_request_parser.add_argument('--provider', help='LLM provider (ollama or openai-compatible)')
    ai_request_parser.add_argument('--model', help='LLM model name (default: EEVEON_LLM_MODEL)')
    ai_request_parser.add_argument('--base-url', help='LLM endpoint (default: EEVEON_LLM_BASE_URL)')
    ai_request_parser.add_argument('--timeout', type=int, help='Request timeout in seconds')
    ai_request_parser.add_argument('--api-key', help='LLM API key (overrides config)')
    ai_request_parser.add_argument('--raw', action='store_true', help='Print raw model response')
    ai_request_parser.add_argument('--auto', action='store_true', help='Execute if no confirmation required')
    ai_request_parser.set_defaults(func=ai_request)

    ai_list_parser = subparsers.add_parser('ai-list', help='List AI requests')
    ai_list_parser.set_defaults(func=ai_list)

    ai_approve_parser = subparsers.add_parser('ai-approve', help='Approve and execute an AI request')
    ai_approve_parser.add_argument('request_id', help='AI request id')
    ai_approve_parser.set_defaults(func=ai_approve)

    # AI config
    ai_config_parser = subparsers.add_parser('ai-config', help='Get or set AI configuration')
    ai_config_parser.add_argument('action', choices=['get', 'set'], help='Action to perform')
    ai_config_parser.add_argument('--provider', help='LLM provider (ollama or openai-compatible)')
    ai_config_parser.add_argument('--base-url', help='LLM endpoint')
    ai_config_parser.add_argument('--model', help='LLM model')
    ai_config_parser.add_argument('--timeout', type=int, help='Timeout in seconds')
    ai_config_parser.add_argument('--api-key', help='LLM API key (stored encrypted)')
    auto_group = ai_config_parser.add_mutually_exclusive_group()
    auto_group.add_argument('--auto-execute', dest='auto_execute', action='store_true', help='Auto-execute safe tools')
    auto_group.add_argument('--no-auto-execute', dest='auto_execute', action='store_false', help='Disable auto-execute')
    ai_config_parser.set_defaults(auto_execute=None, func=ai_config)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    args.func(args)


if __name__ == '__main__':
    main()
