#!/usr/bin/env python3
"""
EEveon Setup Script
Modern Python packaging with pyproject.toml support
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read version from package
version = {}
with open("eeveon/__init__.py") as f:
    for line in f:
        if line.startswith("__version__"):
            exec(line, version)

# Read README
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text(encoding="utf-8") if readme_file.exists() else ""

# Read requirements (system dependencies documented, no Python deps)
requirements = [
    "cryptography>=3.0.0",
    "fastapi>=0.100.0",
    "uvicorn>=0.20.0",
]

optional_requirements = {
    "rich": ["rich>=13.0.0"],
    "monitoring": ["psutil>=5.0.0"],
}

setup(
    name="ee-deploy",
    version=version.get("__version__", "0.2.0"),
    author="Adarsh",
    author_email="sinha.adarsh200@gmail.com",
    description="Lightweight bash-based CI/CD pipeline for automatic deployment from GitHub",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/adarsh-crypto/eeveon-deploy",
    project_urls={
        "Bug Reports": "https://github.com/adarsh-crypto/eeveon-deploy/issues",
        "Source": "https://github.com/adarsh-crypto/eeveon-deploy",
        "Documentation": "https://github.com/adarsh-crypto/eeveon-deploy#readme",
        "Changelog": "https://github.com/adarsh-crypto/eeveon-deploy/blob/main/CHANGELOG.md",
    },
    packages=find_packages(exclude=["tests", "tests.*"]),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "Topic :: Software Development :: Build Tools",
        "Topic :: System :: Systems Administration",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Unix Shell",
        "Operating System :: POSIX :: Linux",
        "Operating System :: Unix",
    ],
    python_requires=">=3.6",
    install_requires=requirements,
    extras_require={
        "premium": optional_requirements["rich"] + optional_requirements["monitoring"],
        "rich": optional_requirements["rich"],
        "monitoring": optional_requirements["monitoring"],
        "dev": [
            "black>=22.0.0",
            "isort>=5.0.0",
            "flake8>=4.0.0",
            "mypy>=0.950",
        ],
        "docs": [
            "sphinx>=4.0.0",
            "sphinx-rtd-theme>=1.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "ee-deploy=eeveon.cli:main",
            "eeveon=eeveon.cli:main",
        ],
    },
    include_package_data=True,
    package_data={
        "eeveon": [
            "scripts/*.sh",
            "dashboard/*.html",
            "dashboard/static/*.css",
        ],
    },
    data_files=[
        ("scripts", [
            "eeveon/scripts/monitor.sh",
            "eeveon/scripts/deploy.sh",
            "eeveon/scripts/notify.sh",
            "eeveon/scripts/rollback.sh",
            "eeveon/scripts/health_check.sh",
        ]),
    ],
    zip_safe=False,
    keywords="ci cd deployment automation github devops pipeline continuous-deployment",
)
