# EEveon v0.3.0 Implementation Plan: "Advanced Operations"

## 🎯 Goal
Transform EEveon from a basic deployment tool into a sophisticated orchestration engine with high-availability and security features.

---

## 🏗️ Phase 1: Blue-Green Deployment Strategy
**Objective:** Zero-downtime deployments with instant traffic switching.

### Tasks:
- [x] **Symlink-Based Orchestration**: Modify the deployment logic to manage `active` vs `inactive` directory states.
- [x] **Atomic Swap**: Implement a symlink swap that occurs *only after* health checks pass.
- [x] **Cli Toggle**: Add `--strategy blue-green` flag to the deploy command.
- [x] **Persistence**: Ensure `.deploy_history` correctly tracks which color is currently active.

---

## 🔐 Phase 2: Secret Management & Encryption
**Objective:** Securely handle sensitive environment variables without plain-text exposure.

### Tasks:
- [x] **Encryption Helper**: Integrate `age` (now using `cryptography`/Fernet for better portability).
- [x] **Secrets Command**: Add `eeveon secrets set <key> <value>` and `eeveon secrets encrypt/decrypt`.
- [x] **Runtime Injection**: Update `deploy.sh` to decrypt secrets into a temporary buffer during the transfer/build phase.
- [x] **Safety**: Ensure decrypted files are never written to persistent storage in plain text.

---

## 🤝 Phase 3: Deployment Approvals (Human-in-the-loop)
**Objective:** Prevent accidental deployments to critical environments.

### Tasks:
- [x] **Approval State**: Add a `pending_approval` state to the monitor daemon.
- [x] **Notification Hook**: Send interactive buttons or links (where supported) for one-click approval.
- [x] **Approval CLI**: Implement `eeveon approve <site_name>` to release the deployment lock.
- [x] **Timeouts**: Define expiration for pending approvals to avoid stale code releases.

---

## 📊 Phase 4: RBAC (Role-Based Access Control)
**Objective:** Control who can do what.

### Tasks:
- [x] **User Config**: Define `admin` vs `deployer` roles in the global config.
- [x] **Command Restrictions**: Block `rollback` and `approve` for limited users.
- [x] **Sudo Integration**: Leverage system-level permissions to enforce boundaries.

---

## 🛠️ Technical Debt & Polish
- [x] **Log Rotation**: Implement automated log cleanup for the monitor daemon via `eeveon vacuum`.
- [x] **Dependency Check**: Ensure `rsync`, `git`, and `cryptography` are present via `eeveon check`.
- [x] **Performance**: Optimize the git-polling logic to reduce CPU usage on low-end servers.

---

## 📅 Timeline
- **Week 1-2**: Blue-Green Implementation.
- **Week 3**: Secret Management.
- **Week 4**: Approval Workflow & RBAC.
- **Week 5**: Testing, Bug-Fixing, and Documentation update.
