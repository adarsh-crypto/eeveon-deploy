# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2025-12-16

### Added
- **Notifications & Alerts**
  - Slack webhook integration
  - Discord webhook integration
  - Telegram bot integration
  - Email notifications (SMTP)
  - Custom webhook support
  - Color-coded status messages
  
- **Rollback Capability**
  - Deployment history tracking
  - One-command rollback
  - Rollback to any previous version
  - Automatic rollback on deployment failure
  - Backup management system
  
- **Health Checks**
  - HTTP endpoint health checks
  - Custom script health checks
  - Retry mechanism with exponential backoff
  - Automatic rollback on failed health checks
  - Pre and post-deployment checks
  
- **Python Package Structure**
  - Proper Python package with `eeveon/` module
  - Modern `pyproject.toml` configuration
  - Updated `setup.py` for PyPI
  - Package metadata in `__init__.py`
  - CLI module structure
  
- **Testing & Development**
  - Comprehensive unit test suite (42 checks)
  - Integration test suite (10 tests)
  - Pre-commit hook for automatic testing
  - Build and publish script
  - Development guide (DEVELOPMENT.md)
  
- **Documentation**
  - Near-term roadmap (ROADMAP.md)
  - Long-term vision (FUTURE_ROADMAP.md)
  - Test documentation
  - Development workflow guide

### Changed
- Reorganized project structure for Python packaging
- Improved CLI implementation
- Enhanced error handling

### Fixed
- Script permissions
- JSON configuration handling

## [0.1.0] - 2025-12-16

### Added
- Initial release of EEveon CI/CD Pipeline
- CLI tool for managing deployment pipelines
- Automatic monitoring of GitHub repositories
- Support for `.deployignore` patterns
- Environment variable management with `.env` files
- Post-deployment hooks support
- Comprehensive logging system
- Multiple project support
- Systemd service integration
- Installation script with dependency checking

### Features
- Poll GitHub every 2 minutes (configurable)
- Automatic deployment on new commits
- rsync-based file synchronization
- Git-based version control integration
- Bash and Python implementation

### Documentation
- Complete README with examples
- Quick start guide
- Architecture documentation
- Troubleshooting guide
