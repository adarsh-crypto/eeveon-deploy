#!/bin/bash
#
# EEveon Notification System
# Sends deployment notifications to various channels
#

# Get project name and status from arguments
PROJECT_NAME="$1"
STATUS="$2"  # success, failure, warning, info
MESSAGE="$3"
COMMIT_HASH="${4:-}"
COMMIT_MSG="${5:-}"

# Base directory (Use ~/.eeveon for data)
EEVEON_HOME="$HOME/.eeveon"
CONFIG_FILE="$EEVEON_HOME/config/pipeline.json"
NOTIFY_CONFIG="$EEVEON_HOME/config/notifications.json"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(dirname "$SCRIPT_DIR")"

# Decrypt helper to avoid relying on an old eeveon binary
decrypt_value() {
    local val="$1"
    if [ -z "$val" ]; then
        echo ""
        return
    fi
    if command -v python3 >/dev/null 2>&1; then
        python3 -m eeveon.cli system decrypt "$val"
    elif command -v python >/dev/null 2>&1; then
        python -m eeveon.cli system decrypt "$val"
    elif command -v eeveon >/dev/null 2>&1; then
        eeveon system decrypt "$val"
    else
        echo "$val"
    fi
}

# Load notification configuration
if [ ! -f "$NOTIFY_CONFIG" ]; then
    # No notifications configured
    exit 0
fi

# Extract notification settings
SLACK_ENABLED=$(jq -r '.slack.enabled // false' "$NOTIFY_CONFIG")
SLACK_WEBHOOK_ENC=$(jq -r '.slack.webhook_url // ""' "$NOTIFY_CONFIG")
SLACK_WEBHOOK=$(decrypt_value "$SLACK_WEBHOOK_ENC")

DISCORD_ENABLED=$(jq -r '.discord.enabled // false' "$NOTIFY_CONFIG")
DISCORD_WEBHOOK_ENC=$(jq -r '.discord.webhook_url // ""' "$NOTIFY_CONFIG")
DISCORD_WEBHOOK=$(decrypt_value "$DISCORD_WEBHOOK_ENC")

EMAIL_ENABLED=$(jq -r '.email.enabled // false' "$NOTIFY_CONFIG")
EMAIL_TO=$(jq -r '.email.to // ""' "$NOTIFY_CONFIG")
EMAIL_FROM=$(jq -r '.email.from // ""' "$NOTIFY_CONFIG")
SMTP_HOST=$(jq -r '.email.smtp_host // ""' "$NOTIFY_CONFIG")
SMTP_PORT=$(jq -r '.email.smtp_port // 587' "$NOTIFY_CONFIG")

TELEGRAM_ENABLED=$(jq -r '.telegram.enabled // false' "$NOTIFY_CONFIG")
TELEGRAM_BOT_TOKEN_ENC=$(jq -r '.telegram.bot_token // ""' "$NOTIFY_CONFIG")
TELEGRAM_BOT_TOKEN=$(decrypt_value "$TELEGRAM_BOT_TOKEN_ENC")
TELEGRAM_CHAT_ID=$(jq -r '.telegram.chat_id // ""' "$NOTIFY_CONFIG")

WEBHOOK_ENABLED=$(jq -r '.webhook.enabled // false' "$NOTIFY_CONFIG")
WEBHOOK_URL=$(jq -r '.webhook.url // ""' "$NOTIFY_CONFIG")

TEAMS_ENABLED=$(jq -r '.teams.enabled // false' "$NOTIFY_CONFIG")
TEAMS_WEBHOOK_ENC=$(jq -r '.teams.webhook_url // ""' "$NOTIFY_CONFIG")
TEAMS_WEBHOOK=$(decrypt_value "$TEAMS_WEBHOOK_ENC")


# Function to check if a channel should be notified for this status
check_channel() {
    local channel="$1"
    local status="$2"
    # Status mapping from config (default to true if not specified)
    jq -e ".${channel}.events.${status} // true" "$NOTIFY_CONFIG" >/dev/null 2>&1
}

# Determine color/emoji based on status
case "$STATUS" in
    success)
        COLOR="#36a64f"
        EMOJI="[PASS]"
        DISCORD_COLOR=3066993
        ;;
    failure)
        COLOR="#ff0000"
        EMOJI="[FAIL]"
        DISCORD_COLOR=15158332
        ;;
    warning)
        COLOR="#ff9900"
        EMOJI="[WARN]"
        DISCORD_COLOR=16776960
        ;;
    *)
        COLOR="#0099ff"
        EMOJI="[INFO]"
        DISCORD_COLOR=255
        ;;
esac

# Send Slack notification
if [ "$SLACK_ENABLED" = "true" ] && [ -n "$SLACK_WEBHOOK" ] && check_channel "slack" "$STATUS"; then
    SLACK_PAYLOAD=$(cat <<EOF
{
    "username": "EEveon CI/CD",
    "icon_emoji": "",
    "attachments": [{
        "color": "$COLOR",
        "title": "$EMOJI Deployment $STATUS",
        "fields": [
            {
                "title": "Project",
                "value": "$PROJECT_NAME",
                "short": true
            },
            {
                "title": "Status",
                "value": "$STATUS",
                "short": true
            },
            {
                "title": "Message",
                "value": "$MESSAGE",
                "short": false
            },
            {
                "title": "Commit",
                "value": "${COMMIT_HASH:0:7}",
                "short": true
            },
            {
                "title": "Commit Message",
                "value": "$COMMIT_MSG",
                "short": false
            },
            {
                "title": "Time",
                "value": "$(date '+%Y-%m-%d %H:%M:%S')",
                "short": true
            }
        ]
    }]
}
EOF
)
    curl -X POST -H 'Content-type: application/json' \
        --data "$SLACK_PAYLOAD" \
        "$SLACK_WEBHOOK" &>/dev/null
fi

# Send Discord notification
if [ "$DISCORD_ENABLED" = "true" ] && [ -n "$DISCORD_WEBHOOK" ] && check_channel "discord" "$STATUS"; then
    DISCORD_PAYLOAD=$(cat <<EOF
{
    "username": "EEveon CI/CD",
    "avatar_url": "https://cdn-icons-png.flaticon.com/512/919/919827.png",
    "embeds": [{
        "title": "$EMOJI Deployment $STATUS",
        "color": $DISCORD_COLOR,
        "fields": [
            {
                "name": "Project",
                "value": "$PROJECT_NAME",
                "inline": true
            },
            {
                "name": "Status",
                "value": "$STATUS",
                "inline": true
            },
            {
                "name": "Message",
                "value": "$MESSAGE",
                "inline": false
            },
            {
                "name": "Commit",
                "value": "${COMMIT_HASH:0:7}",
                "inline": true
            },
            {
                "name": "Commit Message",
                "value": "$COMMIT_MSG",
                "inline": false
            }
        ],
        "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%S.000Z)"
    }]
}
EOF
)
    curl -X POST -H 'Content-type: application/json' \
        --data "$DISCORD_PAYLOAD" \
        "$DISCORD_WEBHOOK" &>/dev/null
fi

# Send Telegram notification
if [ "$TELEGRAM_ENABLED" = "true" ] && [ -n "$TELEGRAM_BOT_TOKEN" ] && [ -n "$TELEGRAM_CHAT_ID" ] && check_channel "telegram" "$STATUS"; then
    TELEGRAM_MESSAGE="$EMOJI *Deployment $STATUS*

*Project:* $PROJECT_NAME
*Status:* $STATUS
*Message:* $MESSAGE
*Commit:* ${COMMIT_HASH:0:7}
*Commit Message:* $COMMIT_MSG
*Time:* $(date '+%Y-%m-%d %H:%M:%S')"

    curl -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
        -d "chat_id=$TELEGRAM_CHAT_ID" \
        -d "text=$TELEGRAM_MESSAGE" \
        -d "parse_mode=Markdown" &>/dev/null
fi

# Send MS Teams notification
if [ "$TEAMS_ENABLED" = "true" ] && [ -n "$TEAMS_WEBHOOK" ] && check_channel "teams" "$STATUS"; then
    TEAMS_PAYLOAD=$(cat <<EOF
{
    "@type": "MessageCard",
    "@context": "http://schema.org/extensions",
    "themeColor": "${COLOR#\#}",
    "summary": "EEveon Deployment Notification",
    "sections": [{
        "activityTitle": "$EMOJI Deployment $STATUS: $PROJECT_NAME",
        "activitySubtitle": "$MESSAGE",
        "facts": [
            {"name": "Project", "value": "$PROJECT_NAME"},
            {"name": "Status", "value": "$STATUS"},
            {"name": "Commit", "value": "${COMMIT_HASH:0:7}"},
            {"name": "Message", "value": "$COMMIT_MSG"}
        ],
        "markdown": true
    }]
}
EOF
)
    curl -X POST -H 'Content-type: application/json' \
        --data "$TEAMS_PAYLOAD" \
        "$TEAMS_WEBHOOK" &>/dev/null
fi

# Send custom webhook
if [ "$WEBHOOK_ENABLED" = "true" ] && [ -n "$WEBHOOK_URL" ] && check_channel "webhook" "$STATUS"; then
    WEBHOOK_PAYLOAD=$(cat <<EOF
{
    "project": "$PROJECT_NAME",
    "status": "$STATUS",
    "message": "$MESSAGE",
    "commit": "$COMMIT_HASH",
    "commit_message": "$COMMIT_MSG",
    "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%S.000Z)"
}
EOF
)
    curl -X POST -H 'Content-type: application/json' \
        --data "$WEBHOOK_PAYLOAD" \
        "$WEBHOOK_URL" &>/dev/null
fi

# Send email notification
if [ "$EMAIL_ENABLED" = "true" ] && [ -n "$EMAIL_TO" ]; then
    # Simple email using sendmail or mail command
    if command -v mail &> /dev/null; then
        echo "Project: $PROJECT_NAME
Status: $STATUS
Message: $MESSAGE
Commit: $COMMIT_HASH
Commit Message: $COMMIT_MSG
Time: $(date '+%Y-%m-%d %H:%M:%S')" | \
        mail -s "[$STATUS] EEveon Deployment: $PROJECT_NAME" "$EMAIL_TO"
    fi
fi

exit 0
