"""
EEveon - Lightweight CI/CD Pipeline
A bash-based continuous deployment system for automatic deployment from GitHub.
"""

__version__ = "0.4.0"
__author__ = "Adarsh"
__license__ = "MIT"
__email__ = "sinha.adarsh200@gmail.com"

from pathlib import Path

# Package metadata
PACKAGE_NAME = "ee-deploy"
PACKAGE_DIR = Path(__file__).parent
BASE_DIR = PACKAGE_DIR.parent

# Version info
VERSION_INFO = {
    "major": 0,
    "minor": 4,
    "patch": 0,
    "release": "stable"
}

def get_version():
    """Get the current version string."""
    return __version__

def get_version_info():
    """Get detailed version information."""
    return VERSION_INFO

# Package description
DESCRIPTION = "Lightweight bash-based CI/CD pipeline for automatic deployment from GitHub"

LONG_DESCRIPTION = """
EEveon is a comprehensive CI/CD platform with real-time observability and enterprise-grade security.

Features:
- 🖥️ Real-time Web Dashboard with live metrics
- 🔔 Multi-channel notifications (Slack, MS Teams, Discord, Telegram)
- 🌐 Multi-node orchestration with atomic deployments
- 🔐 AES-128 encryption for all secrets
- 🔒 Token-based authentication
- 🔄 Blue-Green deployments with zero downtime
- 📊 Live terminal status with Rich library
- ⚡ Instant rollback capability
- 🏥 Automated health checks
- 📝 Comprehensive logging and monitoring
- 🎯 .deployignore support
- 🔧 Post-deployment hooks
- 📦 Multiple project support

Perfect for developers who want a powerful, observable deployment solution without the complexity
of enterprise CI/CD platforms.
"""

# Export public API
__all__ = [
    "__version__",
    "__author__",
    "__license__",
    "get_version",
    "get_version_info",
    "PACKAGE_NAME",
    "DESCRIPTION",
]
