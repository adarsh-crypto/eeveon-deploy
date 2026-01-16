#!/bin/bash
#
# Eeveon CI/CD Deployment Script
# Deploys code from repository to production
#

set -e

# Get project name from argument
PROJECT_NAME="$1"

if [ -z "$PROJECT_NAME" ]; then
    echo "Usage: $0 <project-name>"
    exit 1
fi

# Base directory
# Base directory (Use ~/.eeveon for data)
EEVEON_HOME="$HOME/.eeveon"
CONFIG_FILE="$EEVEON_HOME/config/pipeline.json"
LOG_DIR="$EEVEON_HOME/logs"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(dirname "$SCRIPT_DIR")" # This is the package root

# Ensure log directory exists
mkdir -p "$LOG_DIR"

# Log function
log() {
    local level="$1"
    shift
    local message="$@"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    local log_file="$LOG_DIR/deploy-$(date '+%Y-%m-%d').log"
    
    echo "[$timestamp] [$level] [$PROJECT_NAME] $message" | tee -a "$log_file"
}

# Check if jq is installed
if ! command -v jq &> /dev/null; then
    log "ERROR" "jq is not installed. Please install it: sudo apt install jq"
    exit 1
fi

# Load project configuration
if [ ! -f "$CONFIG_FILE" ]; then
    log "ERROR" "Configuration file not found: $CONFIG_FILE"
    exit 1
fi

# Extract project configuration
REPO_URL=$(jq -r ".\"$PROJECT_NAME\".repo_url" "$CONFIG_FILE")
BRANCH=$(jq -r ".\"$PROJECT_NAME\".branch" "$CONFIG_FILE")
DEPLOY_PATH=$(jq -r ".\"$PROJECT_NAME\".deploy_path" "$CONFIG_FILE")
DEPLOYMENT_DIR=$(jq -r ".\"$PROJECT_NAME\".deployment_dir" "$CONFIG_FILE")
STRATEGY=$(jq -r ".\"$PROJECT_NAME\".strategy // \"standard\"" "$CONFIG_FILE")
NODES_ENABLED=$(jq -r ".\"$PROJECT_NAME\".nodes_enabled // true" "$CONFIG_FILE")

if [ "$REPO_URL" == "null" ]; then
    log "ERROR" "Project '$PROJECT_NAME' not found in configuration"
    if [ -f "$SCRIPT_DIR/notify.sh" ]; then
        bash "$SCRIPT_DIR/notify.sh" "$PROJECT_NAME" "failure" "Project not found in configuration"
    fi
    exit 1
fi

BACKUP_DIR="$DEPLOYMENT_DIR/backups"
HISTORY_FILE="$DEPLOYMENT_DIR/deployment_history.json"
mkdir -p "$BACKUP_DIR"
if [ ! -f "$HISTORY_FILE" ]; then
    echo "[]" > "$HISTORY_FILE"
fi

REPO_DIR="$DEPLOYMENT_DIR/repo"
DEPLOYIGNORE_FILE="$DEPLOYMENT_DIR/.deployignore"
ENV_FILE="$DEPLOYMENT_DIR/.env"

log "INFO" "Starting deployment for: $PROJECT_NAME"
log "INFO" "Strategy: $STRATEGY"

# Determine Target Path based on strategy
if [ "$STRATEGY" == "blue-green" ]; then
    # In blue-green mode, DEPLOY_PATH is a symlink
    # We check where it currently points to determine which one is inactive
    ACTIVE_PATH=""
    if [ -L "$DEPLOY_PATH" ]; then
        ACTIVE_PATH=$(readlink -f "$DEPLOY_PATH")
    fi

    if [[ "$ACTIVE_PATH" == *"_blue" ]]; then
        TARGET_COLOR="green"
    else
        TARGET_COLOR="blue"
    fi

    TARGET_PATH="${DEPLOY_PATH}_${TARGET_COLOR}"
    log "INFO" "Blue-Green mode: Target color is $TARGET_COLOR"
    log "INFO" "Target path: $TARGET_PATH"
else
    TARGET_PATH="$DEPLOY_PATH"
    log "INFO" "Standard mode: Target path: $TARGET_PATH"
fi

# Ensure target path exists
mkdir -p "$TARGET_PATH"

# Ensure repository exists
REPO_DIR="$DEPLOYMENT_DIR/repo"
if [ ! -d "$REPO_DIR/.git" ]; then
    log "INFO" "Repository not found at $REPO_DIR. Cloning..."
    mkdir -p "$DEPLOYMENT_DIR"
    git clone --branch "$BRANCH" "$REPO_URL" "$REPO_DIR"
    
    if [ $? -ne 0 ]; then
        log "ERROR" "Failed to clone repository"
        if [ -f "$SCRIPT_DIR/notify.sh" ]; then
            bash "$SCRIPT_DIR/notify.sh" "$PROJECT_NAME" "failure" "Failed to clone repository"
        fi
        exit 1
    fi
    log "SUCCESS" "Repository cloned successfully"
fi

# Pull latest changes
cd "$REPO_DIR"
log "INFO" "Pulling latest changes from $BRANCH..."

# Use fetch + reset to ensure we match remote exactly
git fetch origin "$BRANCH"
git reset --hard "origin/$BRANCH"

if [ $? -ne 0 ]; then
    log "ERROR" "Failed to fetch latest changes"
    exit 1
fi

CURRENT_COMMIT=$(git rev-parse HEAD)
COMMIT_MSG=$(git log -1 --pretty=format:"%s")
COMMIT_AUTHOR=$(git log -1 --pretty=format:"%an")

log "INFO" "Commit: ${CURRENT_COMMIT:0:7}"
log "INFO" "Message: $COMMIT_MSG"
log "INFO" "Author: $COMMIT_AUTHOR"

# Create rsync exclude file from .deployignore
RSYNC_EXCLUDE_FILE="/tmp/eeveon-exclude-$PROJECT_NAME.txt"
if [ -f "$DEPLOYIGNORE_FILE" ]; then
    cp "$DEPLOYIGNORE_FILE" "$RSYNC_EXCLUDE_FILE"
    log "INFO" "Using .deployignore patterns"
else
    # Default excludes
    cat > "$RSYNC_EXCLUDE_FILE" << 'EOF'
.git
.gitignore
.env.template
.deployignore
node_modules
__pycache__
*.pyc
.DS_Store
.vscode
.idea
EOF
    log "INFO" "Using default exclude patterns"
fi

# Always exclude .git directory
echo ".git" >> "$RSYNC_EXCLUDE_FILE"

# Sync files to target path
log "INFO" "Syncing files to $TARGET_PATH..."

rsync -av --delete \
    --exclude-from="$RSYNC_EXCLUDE_FILE" \
    "$REPO_DIR/" "$TARGET_PATH/"

if [ $? -ne 0 ]; then
    log "ERROR" "Failed to sync files"
    rm -f "$RSYNC_EXCLUDE_FILE"
    exit 1
fi

rm -f "$RSYNC_EXCLUDE_FILE"

rm -f "$RSYNC_EXCLUDE_FILE"

# Copy .env file if it exists and append encrypted secrets
log "INFO" "Generating environment variables..."
if [ -f "$ENV_FILE" ]; then
    cp "$ENV_FILE" "$TARGET_PATH/.env"
else
    touch "$TARGET_PATH/.env"
fi

# Inject encrypted secrets from EEveon store
eeveon decrypt-env "$PROJECT_NAME" >> "$TARGET_PATH/.env"

# Run post-deployment hooks if they exist
HOOKS_DIR="$DEPLOYMENT_DIR/hooks"
POST_DEPLOY_HOOK="$HOOKS_DIR/post-deploy.sh"

if [ -f "$POST_DEPLOY_HOOK" ]; then
    log "INFO" "Running post-deployment hook..."
    cd "$TARGET_PATH"
    bash "$POST_DEPLOY_HOOK"
    
    if [ $? -eq 0 ]; then
        log "SUCCESS" "Post-deployment hook completed"
    else
        log "WARNING" "Post-deployment hook failed"
    fi
fi

# Set proper permissions
log "INFO" "Setting permissions..."
find "$TARGET_PATH" -type f -exec chmod 644 {} \;
find "$TARGET_PATH" -type d -exec chmod 755 {} \;

# Make scripts executable if there's a bin directory
if [ -d "$TARGET_PATH/bin" ]; then
    chmod +x "$TARGET_PATH/bin/"* 2>/dev/null || true
fi

# PHASE 3: Health Checks (before swap in Blue-Green)
if [ -f "$SCRIPT_DIR/health_check.sh" ]; then
    log "INFO" "Running health checks..."
    # We pass the TARGET_PATH as the 3rd argument to health_check.sh
    if ! bash "$SCRIPT_DIR/health_check.sh" "$PROJECT_NAME" "post" "$TARGET_PATH"; then
        log "ERROR" "Health checks failed. Deployment aborted."
        if [ -f "$SCRIPT_DIR/notify.sh" ]; then
            bash "$SCRIPT_DIR/notify.sh" "$PROJECT_NAME" "failure" "Post-deployment health checks failed"
        fi
        # In Blue-Green, we just leave the target path as is, no symlink swap
        exit 1
    fi
fi

# PHASE 4: Atomic Swap (for Blue-Green)
if [ "$STRATEGY" == "blue-green" ]; then
    log "INFO" "Performing atomic swap to $TARGET_COLOR..."
    
    # Create temp symlink for atomic swap
    TEMP_LINK="${DEPLOY_PATH}_tmp"
    ln -sfn "$TARGET_PATH" "$TEMP_LINK"
    mv -Tf "$TEMP_LINK" "$DEPLOY_PATH"
    
    log "SUCCESS" "Traffic switched to $TARGET_COLOR"
fi

# PHASE 5: Multi-Node Replication (Sync Phase)
NODES_FILE="$EEVEON_HOME/config/nodes.json"
SUCCESSFUL_NODES=""
if [ "$NODES_ENABLED" != "true" ]; then
    log "INFO" "Node sync disabled for this pipeline"
elif [ -f "$NODES_FILE" ]; then
    log "INFO" "Checking for remote nodes..."
    NODE_IPS=$(jq -r 'keys[]' "$NODES_FILE" 2>/dev/null || echo "")

    if [ -n "$NODE_IPS" ]; then
        for NODE_ID in $NODE_IPS; do
            NODE_IP=$(jq -r ".\"$NODE_ID\".ip" "$NODES_FILE")
            NODE_USER=$(jq -r ".\"$NODE_ID\".user" "$NODES_FILE")

            log "INFO" "Syncing files to node $NODE_ID ($NODE_USER@$NODE_IP)..."

            # Create target dir on remote just in case
            ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no "$NODE_USER@$NODE_IP" "mkdir -p $TARGET_PATH"

            # Sync files (including .env and .deploy-info)
            if rsync -avz --delete -e "ssh -o StrictHostKeyChecking=no" \
                "$TARGET_PATH/" "$NODE_USER@$NODE_IP:$TARGET_PATH/"; then
                log "SUCCESS" "Sync to $NODE_ID complete"
                SUCCESSFUL_NODES="$SUCCESSFUL_NODES $NODE_ID"
            else
                log "ERROR" "Sync to $NODE_ID failed. Aborting atomic cluster swap."
                # Optionally rollback successful nodes or just stop
                exit 1
            fi
        done
    fi
fi

# PHASE 6: Multi-Node Atomic Swap (Switch Phase)
if [ -n "$SUCCESSFUL_NODES" ] && [ "$STRATEGY" == "blue-green" ]; then
    log "INFO" "Initiating Cluster-wide Atomic Swap..."
    for NODE_ID in $SUCCESSFUL_NODES; do
        NODE_IP=$(jq -r ".\"$NODE_ID\".ip" "$NODES_FILE")
        NODE_USER=$(jq -r ".\"$NODE_ID\".user" "$NODES_FILE")
        
        log "INFO" "Performing remote swap on $NODE_ID..."
        if ssh -o StrictHostKeyChecking=no "$NODE_USER@$NODE_IP" \
            "ln -sfn $TARGET_PATH ${DEPLOY_PATH}_tmp && mv -Tf ${DEPLOY_PATH}_tmp $DEPLOY_PATH"; then
            log "SUCCESS" "Traffic switched on $NODE_ID"
        else
            log "ERROR" "Traffic switch failed on $NODE_ID!"
        fi
    done
fi

# Record deployment history + backup
VERSION="deploy-$(date +%s)"
BACKUP_PATH="$BACKUP_DIR/$VERSION"
mkdir -p "$BACKUP_PATH"
if rsync -a "$TARGET_PATH/" "$BACKUP_PATH/"; then
    HISTORY_ENTRY=$(cat <<EOF
{
  "version": "$VERSION",
  "commit": "$CURRENT_COMMIT",
  "timestamp": "$(date -Iseconds)",
  "status": "success",
  "strategy": "$STRATEGY",
  "path": "$TARGET_PATH"
}
EOF
)
    jq ". += [$HISTORY_ENTRY]" "$HISTORY_FILE" > "$HISTORY_FILE.tmp" && mv "$HISTORY_FILE.tmp" "$HISTORY_FILE"

    MAX_HISTORY=$(jq -r ".\"$PROJECT_NAME\".rollback_keep // 5" "$CONFIG_FILE")
    if ! [[ "$MAX_HISTORY" =~ ^[0-9]+$ ]]; then
        MAX_HISTORY=5
    fi
    if [ "$MAX_HISTORY" -gt 0 ]; then
        COUNT=$(jq 'length' "$HISTORY_FILE")
        if [ "$COUNT" -gt "$MAX_HISTORY" ]; then
            REMOVE_VERSIONS=$(jq -r ".[0:-$MAX_HISTORY][] | .version" "$HISTORY_FILE")
            jq ".[-$MAX_HISTORY:]" "$HISTORY_FILE" > "$HISTORY_FILE.tmp" && mv "$HISTORY_FILE.tmp" "$HISTORY_FILE"
            for ver in $REMOVE_VERSIONS; do
                rm -rf "$BACKUP_DIR/$ver"
            done
        fi
    fi
else
    log "WARNING" "Backup creation failed; rollback history not updated"
fi

log "SUCCESS" "Deployment completed successfully!"
if [ -f "$SCRIPT_DIR/notify.sh" ]; then
    bash "$SCRIPT_DIR/notify.sh" "$PROJECT_NAME" "success" "Deployment successful on all nodes" "$CURRENT_COMMIT" "$COMMIT_MSG"
fi
log "INFO" "Deployed commit: ${CURRENT_COMMIT:0:7}"
log "INFO" "Active code path: $(readlink -f "$DEPLOY_PATH")"

# Create deployment marker file
DEPLOY_INFO="$TARGET_PATH/.deploy-info"
cat > "$DEPLOY_INFO" << EOF
{
  "project": "$PROJECT_NAME",
  "commit": "$CURRENT_COMMIT",
  "commit_message": "$COMMIT_MSG",
  "commit_author": "$COMMIT_AUTHOR",
  "deployed_at": "$(date -Iseconds)",
  "deployed_by": "$(whoami)",
  "branch": "$BRANCH",
  "strategy": "$STRATEGY",
  "color": "$TARGET_COLOR"
}
EOF

log "INFO" "Deployment info saved to $DEPLOY_INFO"

exit 0
