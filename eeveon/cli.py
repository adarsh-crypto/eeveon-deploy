#!/usr/bin/env python3
"""
Eeveon CI/CD Pipeline CLI Tool
Manages continuous deployment from GitHub to production server
"""

import os
import sys
import json
import subprocess
import argparse
from pathlib import Path
from datetime import datetime

# Configuration paths
BASE_DIR = Path(__file__).parent.parent
CONFIG_DIR = BASE_DIR / "config"
SCRIPTS_DIR = BASE_DIR / "scripts"
LOGS_DIR = BASE_DIR / "logs"
DEPLOYMENTS_DIR = BASE_DIR / "deployments"

# Ensure directories exist
for dir_path in [CONFIG_DIR, SCRIPTS_DIR, LOGS_DIR, DEPLOYMENTS_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

CONFIG_FILE = CONFIG_DIR / "pipeline.json"
ENV_FILE = CONFIG_DIR / ".env"


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
    log("Initializing new CI/CD pipeline...", "INFO")
    
    # Get repository details
    repo_url = args.repo or input(f"{Colors.CYAN}GitHub repository URL: {Colors.END}")
    branch = args.branch or input(f"{Colors.CYAN}Branch to deploy (default: main): {Colors.END}") or "main"
    deploy_path = args.path or input(f"{Colors.CYAN}Deployment path on server: {Colors.END}")
    project_name = args.name or input(f"{Colors.CYAN}Project name: {Colors.END}")
    
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
        "poll_interval": args.interval or 120,  # 2 minutes default
        "enabled": True,
        "last_commit": None,
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
        print(f"{Colors.BOLD}{name}{Colors.END}")
        print(f"  Repository: {pipeline['repo_url']}")
        print(f"  Branch: {pipeline['branch']}")
        print(f"  Deploy Path: {pipeline['deploy_path']}")
        print(f"  Poll Interval: {pipeline['poll_interval']}s")
        print(f"  Status: {status}")
        print(f"  Last Commit: {pipeline.get('last_commit', 'Never deployed')}")
        print()


def start_pipeline(args):
    """Start monitoring a pipeline"""
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
WorkingDirectory={BASE_DIR}
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
    project_name = args.project
    log(f"Stopping pipeline '{project_name}'...", "INFO")
    
    # Stop systemd service if running
    result = run_command(f"sudo systemctl stop eeveon-{project_name} 2>/dev/null")
    log(f"Pipeline '{project_name}' stopped", "SUCCESS")


def deploy_now(args):
    """Trigger immediate deployment"""
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
    init_parser.add_argument('--interval', type=int, help='Poll interval in seconds (default: 120)')
    init_parser.add_argument('--gitignore', help='Comma-separated patterns to ignore')
    init_parser.set_defaults(func=init_pipeline)
    
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
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    args.func(args)


if __name__ == '__main__':
    main()
