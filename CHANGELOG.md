# EEveon Changelog

## v0.4.0-stable (2025-12-23) - "Observability & Scale"

### 🎯 Overview
This release transforms EEveon from a silent background engine into a fully observable, enterprise-ready CI/CD platform with a real-time web dashboard, encrypted notification management, and true multi-node orchestration.

---

### ✨ Phase 1: Web Dashboard (COMPLETED)

#### Core Features
- **Real-time Dashboard**: Beautiful, glassmorphic web UI served directly from `eeveon dashboard`
- **Live System Metrics**: Terminal status bar showing Pipelines, Nodes, Uptime, and Memory usage
- **Interactive Pipeline Management**: Deploy, Rollback, Approve, and Remove projects from the browser
- **Professional Navigation**: Unified header with dynamic activity counters and "Last Updated" timestamp
- **Developer-First Design**: Equal-sized navigation topics, clean typography, and high-contrast status indicators

#### Technical Implementation
- FastAPI backend with CORS support
- Rich library integration for premium CLI experience
- Silenced Uvicorn access logs for clean terminal output
- Custom activity logging for all API interactions
- Zero-configuration setup (reads existing `~/.eeveon` data)

---

### 🔔 Phase 2: Notification Management (COMPLETED)

#### Multi-Channel Support
- **Slack Integration**: Webhook-based deployment alerts
- **MS Teams Integration**: Enterprise-grade notifications with MessageCard format
- **Discord Integration**: Community-friendly embed notifications
- **Telegram Integration**: Bot-based messaging support
- **Custom Webhooks**: Generic JSON payload delivery

#### Advanced Features
- **Status Mapping**: Granular control over which events (PASS, FAIL, WARN, INFO) trigger each channel
- **Encrypted Storage**: All webhook URLs and bot tokens encrypted with AES-128 via `SecretsManager`
- **Security Masking**: Encrypted values displayed as `****************` in the UI
- **Just-in-Time Decryption**: Secrets only decrypted when notifications are sent

#### UI Enhancements
- Grid-based notification configuration panel
- Per-channel event checkboxes for precise alert control
- Professional "SAVE CONFIGURATION" button with visual feedback

---

### 🌐 Phase 3: Multi-Node Orchestration (COMPLETED)

#### Edge Deployment
- **Node Registration**: `eeveon nodes add <ip> <user>` for SSH-based cluster setup
- **Two-Phase Deployment**: Sync all nodes first, then perform atomic traffic switch
- **Cluster-Wide Atomic Swap**: Simultaneous Blue-Green switching across all registered nodes
- **Failure Isolation**: Deployment aborts if any single node sync fails
- **Health Aggregation**: Dashboard displays status of every configured node

#### Technical Architecture
- Phase 5: Multi-Node Replication (Sync Phase) - rsync to all targets
- Phase 6: Multi-Node Atomic Swap (Switch Phase) - coordinated symlink updates
- SSH-based connectivity with timeout protection
- Real-time node health checks via dashboard

---

### 🔐 Phase 4: Security & Authentication (COMPLETED)

#### Dashboard Authentication
- **Token-Based Access**: Cryptographically secure 32-character hex tokens
- **Auto-Generation**: Token created on first dashboard launch
- **URL-Based Login**: `http://host:port/?token=<TOKEN>` for seamless access
- **localStorage Persistence**: Token stored client-side for session continuity
- **API Protection**: All endpoints require `X-EEveon-Token` header
- **401 Auto-Logout**: Invalid tokens trigger automatic session termination

#### Security Infrastructure
- `dashboard_auth.json` stores access token
- `verify_token` dependency applied to all API routes
- Terminal displays token and direct login URL on startup
- Access denied page for unauthorized users

---

### 🛠️ Technical Improvements

#### CLI Enhancements
- Added `eeveon system decrypt` for secure secret retrieval
- Integrated `rich` library for premium terminal experience
- Live status table with real-time metrics during dashboard operation
- Text-pure indicators ([PASS], [FAIL], [WARN]) replacing all emojis
- Professional logging with timestamp and color-coded levels

#### API Enhancements
- Custom activity logging for all deployment actions
- Unified `/api/status` endpoint with node count
- Encrypted notification settings via `NotificationSettings` model
- Rollback, Remove, and Node Health Check endpoints
- CORS middleware for local development

#### Deployment Engine
- Integrated `notify.sh` calls on success and failure
- Multi-node sync with failure detection
- Atomic cluster-wide traffic switching
- Post-deployment health check integration

---

### 📦 Dependencies

#### Required
- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `rich` - Terminal formatting
- `cryptography` - AES-128 encryption
- `jq` - JSON parsing in shell scripts

#### Optional
- `psutil` - Real-time memory metrics

---

### 🚀 Migration Guide

#### From v0.3.x to v0.4.0

1. **Install New Dependencies**:
   ```bash
   pip install fastapi uvicorn rich
   ```

2. **Launch Dashboard**:
   ```bash
   eeveon dashboard
   ```
   Copy the access token from terminal output.

3. **Configure Notifications** (Optional):
   - Navigate to "Notifications" tab in dashboard
   - Add webhook URLs for desired channels
   - Configure event mapping (PASS, FAIL, WARN)
   - Click "SAVE CONFIGURATION"

4. **Register Edge Nodes** (Optional):
   ```bash
   eeveon nodes add <server-ip> <ssh-user> --name production-1
   ```

---

### 📝 Breaking Changes

- **Dashboard Access**: Now requires authentication token (displayed in terminal)
- **API Endpoints**: All routes require `X-EEveon-Token` header
- **Notification Format**: Emojis replaced with text indicators ([PASS], [FAIL])

---

### 🐛 Bug Fixes

- Fixed duplicate `TEAMS_ENABLED` variable in `notify.sh`
- Corrected `load_nodes` import in `api.py`
- Resolved `NameError` in dashboard status table generation
- Fixed notification encryption logic for empty values

---

### 🎨 UI/UX Improvements

- Standardized navigation with equal font sizes
- Added active state underline with glow effect
- Implemented "ENGINE ACTIVE" status pill
- Added dynamic activity counters (Sites, Nodes)
- Introduced "Last Updated" timestamp
- Enhanced status badges with uppercase labels and glow effects
- Improved toast notifications with custom styling

---

### 📚 Documentation

- Updated `PLAN_V040.md` with implementation status
- Added inline code comments for security functions
- Documented authentication flow in dashboard
- Included notification channel setup examples

---

### 🔮 Future Roadmap (v0.5.0+)

- **Deployment History**: Commit-level rollback with visual timeline
- **AI-Powered Insights**: Intelligent deployment suggestions
- **Canary Deployments**: Gradual traffic shifting
- **Metrics Dashboard**: Grafana-style performance charts
- **Webhook Testing**: In-dashboard notification preview
- **Multi-User RBAC**: Team-based access control

---

### 👥 Contributors

- Core Development: EEveon Team
- UI/UX Design: Inspired by modern DevOps platforms
- Security Audit: Internal review

---

### 📄 License

MIT License - See LICENSE file for details

---

**Full Changelog**: https://github.com/eeveon/eeveon/compare/v0.3.0...v0.4.0
