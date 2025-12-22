#!/bin/bash
#
# EEveon Health Check System
# Performs health checks after deployment
#

set -e

# Get arguments
PROJECT_NAME="$1"
CHECK_TYPE="${2:-post}"  # pre or post deployment
TARGET_PATH="$3"         # Specific path to check (useful for blue-green)

if [ -z "$PROJECT_NAME" ]; then
    echo "Usage: $0 <project-name> [pre|post] [target-path]"
    exit 1
fi

# Base directory (Use ~/.eeveon for data)
EEVEON_HOME="$HOME/.eeveon"
CONFIG_FILE="$EEVEON_HOME/config/pipeline.json"
HEALTH_CONFIG="$EEVEON_HOME/config/health_checks.json"
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

# Load health check configuration
if [ ! -f "$HEALTH_CONFIG" ]; then
    log "INFO" "No health check configuration found, skipping"
    exit 0
fi

# Extract health check settings for this project
HEALTH_ENABLED=$(jq -r ".\"$PROJECT_NAME\".enabled // false" "$HEALTH_CONFIG")

if [ "$HEALTH_ENABLED" != "true" ]; then
    log "INFO" "Health checks disabled for this project"
    exit 0
fi

# Get health check configuration
HTTP_URL=$(jq -r ".\"$PROJECT_NAME\".http_url // \"\"" "$HEALTH_CONFIG")
HTTP_METHOD=$(jq -r ".\"$PROJECT_NAME\".http_method // \"GET\"" "$HEALTH_CONFIG")
HTTP_EXPECTED_CODE=$(jq -r ".\"$PROJECT_NAME\".http_expected_code // 200" "$HEALTH_CONFIG")
HTTP_TIMEOUT=$(jq -r ".\"$PROJECT_NAME\".http_timeout // 10" "$HEALTH_CONFIG")

SCRIPT_PATH=$(jq -r ".\"$PROJECT_NAME\".script_path // \"\"" "$HEALTH_CONFIG")

MAX_RETRIES=$(jq -r ".\"$PROJECT_NAME\".max_retries // 3" "$HEALTH_CONFIG")
RETRY_DELAY=$(jq -r ".\"$PROJECT_NAME\".retry_delay // 5" "$HEALTH_CONFIG")
ROLLBACK_ON_FAILURE=$(jq -r ".\"$PROJECT_NAME\".rollback_on_failure // true" "$HEALTH_CONFIG")

log "INFO" "Starting $CHECK_TYPE-deployment health checks..."

# HTTP Health Check
http_health_check() {
    local url="$1"
    local method="$2"
    local expected_code="$3"
    local timeout="$4"
    
    log "INFO" "Checking HTTP endpoint: $url"
    
    local response_code=$(curl -s -o /dev/null -w "%{http_code}" \
        -X "$method" \
        --max-time "$timeout" \
        "$url" 2>/dev/null || echo "000")
    
    if [ "$response_code" == "$expected_code" ]; then
        log "SUCCESS" "HTTP health check passed (code: $response_code)"
        return 0
    else
        log "ERROR" "HTTP health check failed (expected: $expected_code, got: $response_code)"
        return 1
    fi
}

# Script Health Check
script_health_check() {
    local script="$1"
    
    if [ ! -f "$script" ]; then
        log "ERROR" "Health check script not found: $script"
        return 1
    fi
    
    log "INFO" "Running health check script: $script"
    
    # Run script relative to target path if available
    if [ -n "$TARGET_PATH" ]; then
        cd "$TARGET_PATH"
    fi

    if bash "$script"; then
        log "SUCCESS" "Script health check passed"
        return 0
    else
        log "ERROR" "Script health check failed"
        return 1
    fi
}

# Retry mechanism with exponential backoff
retry_health_check() {
    local check_function="$1"
    shift
    local args=("$@")
    
    local attempt=1
    local delay="$RETRY_DELAY"
    
    while [ $attempt -le $MAX_RETRIES ]; do
        log "INFO" "Health check attempt $attempt of $MAX_RETRIES"
        
        if $check_function "${args[@]}"; then
            return 0
        fi
        
        if [ $attempt -lt $MAX_RETRIES ]; then
            log "WARNING" "Health check failed, retrying in ${delay}s..."
            sleep "$delay"
            # Exponential backoff
            delay=$((delay * 2))
        fi
        
        attempt=$((attempt + 1))
    done
    
    log "ERROR" "All health check attempts failed"
    return 1
}

# Main health check logic
HEALTH_CHECK_PASSED=true

# HTTP health check
if [ -n "$HTTP_URL" ]; then
    if ! retry_health_check http_health_check "$HTTP_URL" "$HTTP_METHOD" "$HTTP_EXPECTED_CODE" "$HTTP_TIMEOUT"; then
        HEALTH_CHECK_PASSED=false
    fi
fi

# Script health check
if [ -n "$SCRIPT_PATH" ]; then
    if ! retry_health_check script_health_check "$SCRIPT_PATH"; then
        HEALTH_CHECK_PASSED=false
    fi
fi

# Handle health check result
if [ "$HEALTH_CHECK_PASSED" = "false" ]; then
    log "ERROR" "Health checks failed!"
    
    # Send notification
    if [ -f "$SCRIPT_DIR/notify.sh" ]; then
        bash "$SCRIPT_DIR/notify.sh" "$PROJECT_NAME" "failure" \
            "Health checks failed after deployment" "" "Health check failure"
    fi
    
    # Trigger rollback if enabled
    if [ "$ROLLBACK_ON_FAILURE" = "true" ] && [ "$CHECK_TYPE" = "post" ]; then
        log "WARNING" "Triggering automatic rollback..."
        
        if [ -f "$SCRIPT_DIR/rollback.sh" ]; then
            bash "$SCRIPT_DIR/rollback.sh" "$PROJECT_NAME"
        fi
    fi
    
    exit 1
else
    log "SUCCESS" "All health checks passed!"
    
    # Send notification
    if [ -f "$SCRIPT_DIR/notify.sh" ]; then
        bash "$SCRIPT_DIR/notify.sh" "$PROJECT_NAME" "success" \
            "Health checks passed" "" "Deployment healthy"
    fi
    
    exit 0
fi
