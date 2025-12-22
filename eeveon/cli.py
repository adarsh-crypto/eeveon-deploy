#!/usr/bin/env python3
"""
Eeveon CI/CD Pipeline CLI Tool
Manages continuous deployment from GitHub to production server
"""

import os
import json
import subprocess
import argparse
from pathlib import Path
from datetime import datetime
from cryptography.fernet import Fernet

# Configuration and Data paths (Use user's home directory for portability)
EEVEON_HOME = Path.home() / ".eeveon"
CONFIG_DIR = EEVEON_HOME / "config"
LOGS_DIR = EEVEON_HOME / "logs"
DEPLOYMENTS_DIR = EEVEON_HOME / "deployments"
KEYS_DIR = EEVEON_HOME / "keys"

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
            print(f"  {Colors.GREEN}✓ {dep.ljust(10)}{Colors.END} {desc}")
        else:
            if dep == "age":
                print(f"  {Colors.YELLOW}? {dep.ljust(10)}{Colors.END} {desc} (Using internal cryptography)")
            else:
                print(f"  {Colors.RED}✗ {dep.ljust(10)}{Colors.END} {desc} [MISSING]")
                all_ok = False
                
    # Check Python packages
    try:
        import cryptography
        print(f"  {Colors.GREEN}✓ cryptography{Colors.END} Python library found")
    except ImportError:
        print(f"  {Colors.RED}✗ cryptography{Colors.END} Python library NOT found")
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


def log(message, level="INFO"):
    """Log message with timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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
        f.write(f"[{timestamp}] [{level}] {message}\n")


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
        status = f"{Colors.GREEN}✓ Enabled{Colors.END}" if pipeline.get('enabled') else f"{Colors.RED}✗ Disabled{Colors.END}"
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
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    args.func(args)


if __name__ == '__main__':
    main()
