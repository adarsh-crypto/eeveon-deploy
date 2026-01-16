# EEveon Development Guide

Complete guide for developing, testing, and publishing EEveon.

## 🏗️ Project Structure

```
eeveon/
├── eeveon/                 # Python package
│   ├── __init__.py        # Package initialization
│   └── cli.py             # CLI implementation
├── bin/
│   └── eeveon             # CLI entry point
├── scripts/
│   ├── monitor.sh         # GitHub monitoring
│   ├── deploy.sh          # Deployment logic
│   ├── notify.sh          # Notifications
│   ├── rollback.sh        # Rollback system
│   └── health_check.sh    # Health checks
├── tests/
│   ├── run_tests.sh       # Unit tests
│   ├── integration_test.sh # Integration tests
│   └── README.md          # Test documentation
├── hooks/
│   └── pre-commit         # Pre-commit hook template
├── config/                # (Created on install)
├── deployments/           # (Created per project)
├── logs/                  # (Created on first run)
├── setup.py               # Python package setup
├── pyproject.toml         # Modern Python packaging
├── requirements.txt       # Dependencies
├── build_and_publish.sh   # Build & publish script
├── install.sh             # Installation script
├── README.md              # Main documentation
├── CHANGELOG.md           # Version history
├── CONTRIBUTING.md        # Contribution guide
├── LICENSE                # MIT License
├── ROADMAP.md             # Near-term roadmap
└── FUTURE_ROADMAP.md      # Long-term vision
```

## 🚀 Development Workflow

### 1. Setup Development Environment

```bash
# Clone the repository
git clone https://github.com/adarsh-crypto/eeveon.git
cd eeveon

# Install in development mode
pip install -e .

# Or use the installer
./install.sh
```

### 2. Make Changes

```bash
# Create a feature branch
git checkout -b feature/my-feature

# Make your changes
# Edit files...

# Make scripts executable
chmod +x scripts/*.sh tests/*.sh
```

### 3. Test Your Changes

```bash
# Run unit tests
./tests/run_tests.sh

# Run integration tests
./tests/integration_test.sh

# Or run both
./tests/run_tests.sh && ./tests/integration_test.sh
```

### 4. Commit Changes

```bash
# Add files
git add .

# Commit with descriptive message
git commit -m "feat: Add awesome feature"

# Our pre-commit hook will run tests automatically
# (if you've installed it)
```

### 5. Push and Create PR

```bash
# Push to your fork
git push origin feature/my-feature

# Create Pull Request on GitHub
```

## 🧪 Testing

### Our Own Testing System

We use **our own bash-based testing system** - no external CI/CD needed!

**Unit Tests:**
```bash
./tests/run_tests.sh
```

**Integration Tests:**
```bash
./tests/integration_test.sh
```

### AI Control Plane Tests (Lightweight)

```bash
python -m eeveon.cli ai-config get
python -m eeveon.cli ai-request "Explain what will happen if I run eeveon deploy now."
python -m eeveon.cli ai-list
```

**Install Pre-Commit Hook:**
```bash
# Copy pre-commit hook
cp hooks/pre-commit .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit

# Now tests run automatically before each commit!
```

### Adding New Tests

**Unit Test:**
Edit `tests/run_tests.sh` and add:

```bash
test_my_feature() {
    test_start "Testing my feature"
    
    if [ condition ]; then
        test_pass "Feature works"
    else
        test_fail "Feature broken"
    fi
}
```

**Integration Test:**
Edit `tests/integration_test.sh` and add:

```bash
echo -e "${BLUE}[TEST N]${NC} Testing my feature..."
# Test logic
if [ success ]; then
    echo -e "${GREEN}✓ PASS${NC} Feature works"
else
    echo -e "${RED}✗ FAIL${NC} Feature failed"
    exit 1
fi
```

## 📦 Building & Publishing

### Build Package

```bash
# Run our build script
./build_and_publish.sh

# Or manually:
python3 setup.py sdist bdist_wheel
```

### Test Package Locally

```bash
# Install from wheel
pip install dist/eeveon-*.whl

# Test it
eeveon --help
```

### Publish to PyPI

```bash
# Install twine
pip install twine

# Upload to TestPyPI (for testing)
twine upload --repository testpypi dist/*

# Upload to PyPI (production)
twine upload dist/*

# Or use our script (interactive)
./build_and_publish.sh
```

## 🔧 Code Style

### Bash Scripts

- Use `#!/bin/bash` shebang
- Add comments for complex logic
- Use UPPERCASE for variables
- Check return codes
- Use `set -e` for error handling

Example:
```bash
#!/bin/bash
set -e

# Description of what this does
MY_VAR="value"

if command; then
    echo "Success"
else
    echo "Failed"
    exit 1
fi
```

### Python Code

- Follow PEP 8
- Use meaningful names
- Add docstrings
- Keep functions focused

Example:
```python
def my_function(arg):
    """
    Brief description.
    
    Args:
        arg: Description
        
    Returns:
        Description
    """
    return result
```

## 📝 Commit Messages

Use conventional commits:

```
feat: Add new feature
fix: Bug fix
docs: Documentation
test: Tests
refactor: Code refactoring
chore: Maintenance
```

Examples:
```
feat: Add Slack notification support
fix: Rollback not working on Ubuntu 22.04
docs: Update installation guide
test: Add health check integration tests
```

## 🔄 Release Process

### 1. Update Version

Edit `eeveon/__init__.py`:
```python
__version__ = "0.3.0"
```

Edit `pyproject.toml`:
```toml
version = "0.3.0"
```

### 2. Update Changelog

Add to `CHANGELOG.md`:
```markdown
## [0.3.0] - 2025-XX-XX

### Added
- New feature X
- New feature Y

### Fixed
- Bug Z
```

### 3. Run Tests

```bash
./tests/run_tests.sh && ./tests/integration_test.sh
```

### 4. Build & Publish

```bash
./build_and_publish.sh
```

### 5. Create Git Tag

```bash
git tag -a v0.3.0 -m "Release v0.3.0"
git push origin v0.3.0
```

### 6. Create GitHub Release

- Go to GitHub Releases
- Create new release
- Tag: v0.3.0
- Copy changelog content
- Publish

## 🐛 Debugging

### Enable Verbose Logging

```bash
# In scripts, add:
set -x  # Print commands

# Or run with:
bash -x scripts/deploy.sh
```

### Check Logs

```bash
# View deployment logs
tail -f ~/Desktop/github/eeveon/logs/deploy-$(date +%Y-%m-%d).log

# Or use eeveon CLI
eeveon logs myproject -n 100
```

### Test Individual Scripts

```bash
# Test syntax
bash -n scripts/deploy.sh

# Test execution
bash scripts/deploy.sh test-project
```

## 🤝 Contributing

1. Fork the repository
2. Create feature branch
3. Make changes
4. Add tests
5. Run tests
6. Commit changes
7. Push to fork
8. Create Pull Request

## 📚 Resources

- **Main README**: [README.md](README.md)
- **Changelog**: [CHANGELOG.md](CHANGELOG.md)
- **Roadmap**: [ROADMAP.md](ROADMAP.md)
- **Future Vision**: [FUTURE_ROADMAP.md](FUTURE_ROADMAP.md)
- **Contributing**: [CONTRIBUTING.md](CONTRIBUTING.md)
- **Tests**: [tests/README.md](tests/README.md)

## 💡 Tips

- Always run tests before committing
- Use the pre-commit hook
- Write descriptive commit messages
- Update documentation
- Add tests for new features
- Keep scripts simple and focused

## 🎯 Our Philosophy

**We own everything:**
- ✅ Our own testing system (no GitHub Actions)
- ✅ Our own build pipeline
- ✅ Our own deployment logic
- ✅ No external dependencies
- ✅ Complete control

**This is OUR platform!** 🚀

---

Happy coding! If you have questions, open an issue on GitHub.
