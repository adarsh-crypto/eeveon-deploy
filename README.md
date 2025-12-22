# EEveon - Lightweight CI/CD Pipeline

A bash-based continuous deployment system that automatically deploys code from GitHub to your production server.

## Features

- 🚀 **Automatic Deployment** - Polls GitHub every 2 minutes for new commits
- 🌈 **Blue-Green Strategy** - Zero-downtime deployments with health checks and atomic swapping
- 🔐 **Encrypted Secrets** - Securely manage environment variables using AES-128 encryption
- 🤝 **Manual Approvals** - Pause deployments for critical environments until authorized
- 📊 **RBAC & Auth** - Role-based access control for multiple users
- 🪝 **Post-Deploy Hooks** - Run custom scripts after deployment
- 📝 **Comprehensive Logging** - Track all deployments with automatic rotation
- 📦 **System Health** - Diagnostic tool to ensure server readiness

## Installation

```bash
git clone https://github.com/adarsh-crypto/eeveon.git
cd eeveon
./install.sh
source ~/.bashrc
```

## Quick Start

### 1. Initialize a Pipeline

```bash
eeveon init \
  --repo https://github.com/username/repo.git \
  --name myproject \
  --path /var/www/myproject \
  --branch main
```

### 2. Configure (Optional)

```bash
cd ~/Desktop/github/eeveon/deployments/myproject

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
eeveon start myproject -f  # Run in foreground
# OR
eeveon start myproject     # Get systemd service instructions
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `eeveon init` | Initialize a new deployment pipeline |
| `eeveon list` | List all configured pipelines |
| `eeveon start <project>` | Start monitoring a pipeline |
| `eeveon stop <project>` | Stop a running pipeline |
| `eeveon deploy <project>` | Trigger immediate deployment |
| `eeveon logs [project]` | View deployment logs |
| `eeveon remove <project>` | Remove a pipeline configuration |
| `eeveon secrets set <p> <k> <v>` | Encrypt and store a secret |
| `eeveon approve <project>` | Authorize a pending deployment |
| `eeveon check` | Verify system dependencies |
| `eeveon vacuum` | Clean up old log files |

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
eeveon init \
  --repo git@github.com:user/nodeapp.git \
  --name nodeapp \
  --path /var/www/nodeapp

# Create post-deploy hook
cat > ~/Desktop/github/eeveon/deployments/nodeapp/hooks/post-deploy.sh << 'EOF'
#!/bin/bash
cd /var/www/nodeapp
npm install --production
pm2 restart nodeapp || pm2 start server.js --name nodeapp
EOF
chmod +x ~/Desktop/github/eeveon/deployments/nodeapp/hooks/post-deploy.sh

eeveon start nodeapp -f
```

### Deploy a Static Website

```bash
eeveon init \
  --repo https://github.com/user/static-site.git \
  --name mysite \
  --path /var/www/html/mysite

eeveon start mysite -f
```

### Deploy a Python Flask App

```bash
eeveon init \
  --repo git@github.com:user/flaskapp.git \
  --name flaskapp \
  --path /var/www/flaskapp

# Create post-deploy hook
cat > ~/Desktop/github/eeveon/deployments/flaskapp/hooks/post-deploy.sh << 'EOF'
#!/bin/bash
cd /var/www/flaskapp
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart flaskapp
EOF
chmod +x ~/Desktop/github/eeveon/deployments/flaskapp/hooks/post-deploy.sh

eeveon start flaskapp -f
```

## Running as a Service

To run the monitor as a systemd service:

```bash
# Start the pipeline to generate service file
eeveon start myproject

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
eeveon logs myproject -n 50

# Manually trigger deployment
eeveon deploy myproject
```

### Permission issues

```bash
# Ensure deployment path is writable
sudo chown -R $USER:$USER /var/www/myproject

# Check script permissions
chmod +x ~/Desktop/github/eeveon/scripts/*.sh
chmod +x ~/Desktop/github/eeveon/bin/eeveon
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
eeveon init --repo git@github.com:username/repo.git ...
```

## Advanced Usage

### Multiple Environments

```bash
# Production
eeveon init --repo https://github.com/user/app.git \
  --name app-prod --path /var/www/app --branch main

# Staging
eeveon init --repo https://github.com/user/app.git \
  --name app-staging --path /var/www/app-staging --branch develop
```

### Custom Poll Interval

```bash
# Check every 30 seconds
eeveon init --interval 30 ...

# Check every 5 minutes
eeveon init --interval 300 ...
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
eeveon logs -n 100
```

Or open an issue on GitHub.
