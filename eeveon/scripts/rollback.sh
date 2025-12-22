#!/bin/bash
#
# EEveon Rollback System
# Manages deployment history and rollback functionality
#

set -e

# Get project name and optional version from arguments
PROJECT_NAME="$1"
TARGET_VERSION="${2:-previous}"  # Default to previous version

if [ -z "$PROJECT_NAME" ]; then
    echo "Usage: $0 <project-name> [version]"
    exit 1
fi

# Base directory (Use ~/.eeveon for data)
EEVEON_HOME="$HOME/.eeveon"
CONFIG_FILE="$EEVEON_HOME/config/pipeline.json"
LOG_DIR="$EEVEON_HOME/logs"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(dirname "$SCRIPT_DIR")"

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
DEPLOY_PATH=$(jq -r ".\"$PROJECT_NAME\".deploy_path" "$CONFIG_FILE")
DEPLOYMENT_DIR=$(jq -r ".\"$PROJECT_NAME\".deployment_dir" "$CONFIG_FILE")

if [ "$DEPLOY_PATH" == "null" ]; then
    log "ERROR" "Project '$PROJECT_NAME' not found in configuration"
    exit 1
fi

BACKUP_DIR="$DEPLOYMENT_DIR/backups"
HISTORY_FILE="$DEPLOYMENT_DIR/deployment_history.json"

# Ensure backup directory exists
mkdir -p "$BACKUP_DIR"

# Initialize history file if it doesn't exist
if [ ! -f "$HISTORY_FILE" ]; then
    echo "[]" > "$HISTORY_FILE"
fi

# List available versions
list_versions() {
    log "INFO" "Available deployment versions:"
    
    if [ ! -f "$HISTORY_FILE" ]; then
        log "WARNING" "No deployment history found"
        return
    fi
    
    jq -r '.[] | "\(.version) - \(.timestamp) - \(.commit) - \(.status)"' "$HISTORY_FILE" | \
    while IFS= read -r line; do
        echo "  $line"
    done
}

# Get version to rollback to
get_rollback_version() {
    if [ "$TARGET_VERSION" == "previous" ]; then
        # Get the second-to-last successful deployment
        ROLLBACK_VERSION=$(jq -r '[.[] | select(.status == "success")] | .[-2].version // empty' "$HISTORY_FILE")
    else
        ROLLBACK_VERSION="$TARGET_VERSION"
    fi
    
    if [ -z "$ROLLBACK_VERSION" ]; then
        log "ERROR" "No previous version found to rollback to"
        list_versions
        exit 1
    fi
    
    echo "$ROLLBACK_VERSION"
}

# Perform rollback
perform_rollback() {
    local version="$1"
    local backup_path="$BACKUP_DIR/$version"
    
    if [ ! -d "$backup_path" ]; then
        log "ERROR" "Backup not found for version: $version"
        list_versions
        exit 1
    fi
    
    log "INFO" "Rolling back to version: $version"
    
    # Get version info
    local version_info=$(jq -r ".[] | select(.version == \"$version\")" "$HISTORY_FILE")
    local commit=$(echo "$version_info" | jq -r '.commit')
    local timestamp=$(echo "$version_info" | jq -r '.timestamp')
    
    log "INFO" "Version details:"
    log "INFO" "  Commit: $commit"
    log "INFO" "  Deployed at: $timestamp"
    
    # Confirm rollback
    echo ""
    read -p "Are you sure you want to rollback? (yes/no): " -r
    echo
    if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
        log "INFO" "Rollback cancelled"
        exit 0
    fi
    
    # Create backup of current deployment before rollback
    log "INFO" "Creating backup of current deployment..."
    CURRENT_BACKUP="$BACKUP_DIR/pre-rollback-$(date +%s)"
    mkdir -p "$CURRENT_BACKUP"
    rsync -a "$DEPLOY_PATH/" "$CURRENT_BACKUP/"
    
    # Perform rollback
    log "INFO" "Restoring files from backup..."
    rsync -a --delete "$backup_path/" "$DEPLOY_PATH/"
    
    if [ $? -eq 0 ]; then
        log "SUCCESS" "Rollback completed successfully!"
        log "INFO" "Restored to version: $version"
        
        # Send notification
        if [ -f "$SCRIPT_DIR/notify.sh" ]; then
            bash "$SCRIPT_DIR/notify.sh" "$PROJECT_NAME" "warning" \
                "Rolled back to version $version" "$commit" "Rollback performed"
        fi
        
        # Update deployment history
        local rollback_entry=$(cat <<EOF
{
    "version": "rollback-$(date +%s)",
    "commit": "$commit",
    "timestamp": "$(date -Iseconds)",
    "status": "rollback",
    "rollback_from": "current",
    "rollback_to": "$version"
}
EOF
)
        jq ". += [$rollback_entry]" "$HISTORY_FILE" > "$HISTORY_FILE.tmp"
        mv "$HISTORY_FILE.tmp" "$HISTORY_FILE"
        
    else
        log "ERROR" "Rollback failed!"
        
        # Restore from pre-rollback backup
        log "WARNING" "Attempting to restore previous state..."
        rsync -a --delete "$CURRENT_BACKUP/" "$DEPLOY_PATH/"
        
        exit 1
    fi
}

# Main logic
case "${2:-rollback}" in
    list)
        list_versions
        ;;
    *)
        ROLLBACK_VERSION=$(get_rollback_version)
        perform_rollback "$ROLLBACK_VERSION"
        ;;
esac

exit 0
