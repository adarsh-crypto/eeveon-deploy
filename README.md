# EEveon - Lightweight CI/CD Pipeline

A bash-based continuous deployment system that automatically deploys code from GitHub to your production server.

## Features

- 🚀 **Automatic Deployment** - Polls GitHub every 2 minutes for new commits
- **Dashboard (v0.4.0)**: Real-time web management UI with live logs and remote controls.
- **Multi-Node**: Deploy to a cluster of servers from a single command.
- **Blue-Green Deployments**: Atomic traffic switching for zero downtime.
- 🔐 **Encrypted Secrets** - Securely manage environment variables using AES-128 encryption
- 🤝 **Manual Approvals** - Pause deployments for critical environments until authorized
- 📊 **RBAC & Auth** - Role-based access control for multiple users
- 🪝 **Post-Deploy Hooks** - Run custom scripts after deployment
- 📝 **Comprehensive Logging** - Track all deployments with automatic rotation
- 📦 **System Health** - Diagnostic tool to ensure server readiness
- 🤖 **AI Control Plane (v2)** - Validated AI requests, approvals, and audit trail
- 🪝 **GitHub Webhooks (v2)** - Instant commit detection without polling

## Installation

```bash
pip install ee-deploy
```

Install from source:

```bash
git clone https://github.com/adarsh-crypto/eeveon-deploy.git
cd eeveon-deploy
./install.sh
source ~/.bashrc
```

Primary CLI command: `ee-deploy`  
Compatibility alias: `eeveon`

## Quick Start

### 1. Initialize a Pipeline

```bash
ee-deploy init \
  --repo https://github.com/username/repo.git \
  --name myproject \
  --path /var/www/myproject \
  --branch main
```

### 2. Configure (Optional)

```bash
cd ~/Desktop/github/eeveon-deploy/deployments/myproject

# Create .deployignore
cat > .deployignore << EOF
.git
node_modules
*.log
EOF

# Create .env
cat > .env << EOF
NODE_ENV=production
DATABASE_URL=postgresql://localhost/db
EOF

# Create post-deploy hook
mkdir -p hooks
cat > hooks/post-deploy.sh << 'EOF'
#!/bin/bash
npm install --production
pm2 restart myapp
EOF
chmod +x hooks/post-deploy.sh
```

### 3. Start Monitoring

```bash
ee-deploy start myproject -f  # Run in foreground
# OR
ee-deploy start myproject     # Get systemd service instructions
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `ee-deploy init` | Initialize a new deployment pipeline |
| `ee-deploy list` | List all configured pipelines |
| `ee-deploy start <project>` | Start monitoring a pipeline |
| `ee-deploy stop <project>` | Stop a running pipeline |
| `ee-deploy deploy <project>` | Trigger immediate deployment |
| `ee-deploy logs [project]` | View deployment logs |
| `ee-deploy remove <project>` | Remove a pipeline configuration |
| `ee-deploy secrets set <p> <k> <v>` | Encrypt and store a secret |
| `ee-deploy approve <project>` | Authorize a pending deployment |
| `ee-deploy check` | Verify system dependencies |
| `ee-deploy vacuum` | Clean up old log files |
| `ee-deploy ai <request>` | Parse NL into a validated tool call |
| `ee-deploy ai-request <request>` | Queue a validated AI request |
| `ee-deploy ai-list` | List AI requests |
| `ee-deploy ai-approve <id>` | Approve and execute an AI request |
| `ee-deploy ai-config get|set` | Get or set LLM config |
| `ee-deploy seed-rollback <project>` | Seed rollback history from current deploy |
| `ee-deploy webhook <action>` | Manage GitHub webhook settings |

## How It Works

```
Developer → Git Push → GitHub → EEveon Monitor → Auto Deploy → Production
```

1. Developer pushes code to GitHub
2. Monitor script checks GitHub every 2 minutes
3. Detects new commits by comparing hashes
4. Automatically pulls and deploys to production
5. Respects `.deployignore` patterns
6. Copies `.env` file
7. Runs post-deploy hooks
8. Logs everything

## Configuration Files

### `.deployignore`

Specify files/patterns to exclude from deployment:

```
.git
.gitignore
node_modules
__pycache__
*.pyc
*.log
.env.template
```

### `.env`

Environment variables for your application:

```bash
NODE_ENV=production
DATABASE_URL=postgresql://user:pass@localhost/db
API_KEY=your-secret-key
PORT=3000
```

### `~/.eeveon/config/ai.json`

LLM and AI control plane configuration:

```json
{
  "provider": "ollama",
  "base_url": "https://ollama.eeveon.com/api/generate",
  "model": "qwen3-coder:480b-cloud",
  "timeout_s": 60,
  "auto_execute_safe": false,
  "api_key": null
}
```

Provider notes:
- `ollama` expects a `/api/generate` endpoint.
- `openai-compatible` expects a `/v1/chat/completions` endpoint and an API key.

Environment overrides: `EEVEON_LLM_PROVIDER`, `EEVEON_LLM_BASE_URL`,
`EEVEON_LLM_MODEL`, `EEVEON_LLM_TIMEOUT`, `EEVEON_LLM_API_KEY`.

### `hooks/post-deploy.sh`

Custom script to run after deployment:

```bash
#!/bin/bash
cd /var/www/myproject
npm install --production
pm2 restart myapp
```

## Examples

### Deploy a Node.js Application

```bash
ee-deploy init \
  --repo git@github.com:user/nodeapp.git \
  --name nodeapp \
  --path /var/www/nodeapp

# Create post-deploy hook
cat > ~/Desktop/github/eeveon-deploy/deployments/nodeapp/hooks/post-deploy.sh << 'EOF'
#!/bin/bash
cd /var/www/nodeapp
npm install --production
pm2 restart nodeapp || pm2 start server.js --name nodeapp
EOF
chmod +x ~/Desktop/github/eeveon-deploy/deployments/nodeapp/hooks/post-deploy.sh

ee-deploy start nodeapp -f
```

### Deploy a Static Website

```bash
ee-deploy init \
  --repo https://github.com/user/static-site.git \
  --name mysite \
  --path /var/www/html/mysite

ee-deploy start mysite -f
```

### Deploy a Python Flask App

```bash
ee-deploy init \
  --repo git@github.com:user/flaskapp.git \
  --name flaskapp \
  --path /var/www/flaskapp

# Create post-deploy hook
cat > ~/Desktop/github/eeveon-deploy/deployments/flaskapp/hooks/post-deploy.sh << 'EOF'
#!/bin/bash
cd /var/www/flaskapp
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart flaskapp
EOF
chmod +x ~/Desktop/github/eeveon-deploy/deployments/flaskapp/hooks/post-deploy.sh

ee-deploy start flaskapp -f
```

## Running as a Service

To run the monitor as a systemd service:

```bash
# Start the pipeline to generate service file
ee-deploy start myproject

# Install as systemd service
sudo cp /tmp/eeveon-myproject.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable eeveon-myproject
sudo systemctl start eeveon-myproject

# Check status
sudo systemctl status eeveon-myproject

# View logs
sudo journalctl -u eeveon-myproject -f
```

## Directory Structure

```
eeveon/
├── bin/
│   └── eeveon              # Main CLI tool
├── scripts/
│   ├── monitor.sh          # Monitoring script
│   └── deploy.sh           # Deployment script
├── config/
│   └── pipeline.json       # Pipeline configurations
├── deployments/
│   └── <project-name>/
│       ├── repo/           # Cloned repository
│       ├── .env            # Environment variables
│       ├── .deployignore   # Ignore patterns
│       └── hooks/
│           └── post-deploy.sh
├── logs/
│   └── deploy-YYYY-MM-DD.log
├── install.sh              # Installation script
└── README.md
```

## Requirements

- Git
- jq (JSON processor)
- rsync
- Python 3.6+
- Bash 4.0+

All dependencies will be installed by `install.sh` if missing.

## Troubleshooting

### Pipeline not detecting changes

```bash
# Check if monitor is running
ps aux | grep monitor.sh

# Check logs
ee-deploy logs myproject -n 50

# Manually trigger deployment
ee-deploy deploy myproject
```

### Permission issues

```bash
# Ensure deployment path is writable
sudo chown -R $USER:$USER /var/www/myproject

# Check script permissions
chmod +x ~/Desktop/github/eeveon-deploy/scripts/*.sh
chmod +x ~/Desktop/github/eeveon-deploy/bin/eeveon
```

### AI requests not executing

```bash
# Check pending AI requests
ee-deploy ai-list

# Approve a specific request
ee-deploy ai-approve <request_id>

# View AI audit log
tail -n 50 ~/.eeveon/config/ai_audit.jsonl
```

### Git authentication issues

For private repositories, set up SSH keys:

```bash
# Generate SSH key
ssh-keygen -t ed25519 -C "your_email@example.com"

# Add to GitHub
cat ~/.ssh/id_ed25519.pub
# Copy and add to GitHub Settings > SSH Keys

# Use SSH URL in pipeline
ee-deploy init --repo git@github.com:username/repo.git ...
```

## Advanced Usage

### GitHub Webhooks (Instant Deploy Triggers)

Enable webhooks to avoid polling and trigger deploys instantly.

```bash
# Enable webhooks and set repo + secret
ee-deploy webhook enable myproject
ee-deploy webhook repo myproject owner/repo
ee-deploy webhook secret myproject <webhook_secret>

# Optional: restrict webhook branches
ee-deploy webhook branches myproject main,release
```

Configure your GitHub webhook:
- Payload URL: `http://<host>:<dashboard-port>/api/webhooks/github`
- Content type: `application/json`
- Secret: same as `webhook secret`
- Events: `push` and `release`

Webhook delivery dedupe + event log is stored in:
- `~/.eeveon/config/webhook_dedupe.json`
- `~/.eeveon/config/webhook_events.jsonl`

#### Stable Webhook URL (Cloudflare Tunnel)

For production, use a named Cloudflare Tunnel with a stable hostname so GitHub
does not rely on a temporary URL. See `config/cloudflared/README.md`.

### Multiple Environments

```bash
# Production
ee-deploy init --repo https://github.com/user/app.git \
  --name app-prod --path /var/www/app --branch main

# Staging
ee-deploy init --repo https://github.com/user/app.git \
  --name app-staging --path /var/www/app-staging --branch develop
```

### Custom Poll Interval

```bash
# Check every 30 seconds
ee-deploy init --interval 30 ...

# Check every 5 minutes
ee-deploy init --interval 300 ...
```

### Disable Multi-Node Sync

```bash
ee-deploy config myproject nodes_enabled false
```

## Security Notes

- ⚠️ Never commit `.env` files to Git
- ⚠️ Use SSH keys for private repositories
- ⚠️ Ensure deployment paths have proper permissions
- ⚠️ Review post-deploy hooks before running

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT

## Author

Adarsh

## Support

For issues or questions, check the logs:
```bash
ee-deploy logs -n 100
```

Or open an issue on GitHub.
