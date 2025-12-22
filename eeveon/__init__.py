"""
EEveon - Lightweight CI/CD Pipeline
A bash-based continuous deployment system for automatic deployment from GitHub.
"""

__version__ = "0.3.6"
__author__ = "Adarsh"
__license__ = "MIT"
__email__ = "sinha.adarsh200@gmail.com"

from pathlib import Path

# Package metadata
PACKAGE_NAME = "eeveon"
PACKAGE_DIR = Path(__file__).parent
BASE_DIR = PACKAGE_DIR.parent

# Version info
VERSION_INFO = {
    "major": 0,
    "minor": 3,
    "patch": 6,
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
EEveon is a comprehensive CI/CD pipeline that automatically deploys your code from GitHub to production.

Features:
- Automatic deployment from GitHub
- Multi-channel notifications (Slack, Discord, Telegram, Email)
- Instant rollback capability
- Health check automation
- .deployignore support
- Environment variable management
- Post-deployment hooks
- Multiple project support
- Comprehensive logging

Perfect for developers who want a simple, powerful deployment solution without the complexity
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
