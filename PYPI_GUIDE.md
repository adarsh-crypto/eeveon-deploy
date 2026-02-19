# 📦 EEveon v0.4.0 - PyPI Publishing Guide

## ✅ Pre-Publishing Checklist

- [x] Version updated to `0.4.0` (stable)
- [x] GitHub repository pushed
- [x] Git tag `v0.4.0` created
- [x] All tests passed
- [x] Documentation complete
- [x] Optional dependencies configured (rich, psutil)

---

## 🚀 Publishing to PyPI

### Step 1: Install Build Tools

```bash
pip install --upgrade build twine
```

### Step 2: Clean Previous Builds

```bash
cd /home/adarsh/Desktop/github/eeveon-deploy
rm -rf dist/ build/ *.egg-info
```

### Step 3: Build Distribution Packages

```bash
python3 -m build
```

This creates:
- `dist/ee_deploy-0.4.0-py3-none-any.whl` (wheel)
- `dist/ee_deploy-0.4.0.tar.gz` (source)

### Step 4: Verify Package Contents

```bash
tar -tzf dist/ee_deploy-0.4.0.tar.gz | head -20
```

Check that it includes:
- ✅ `eeveon/cli.py`
- ✅ `eeveon/api.py`
- ✅ `eeveon/dashboard/index.html`
- ✅ `eeveon/dashboard/static/style.css`
- ✅ `eeveon/scripts/*.sh`
- ✅ `README.md`
- ✅ `CHANGELOG.md`

### Step 5: Test Installation Locally

```bash
# Create test environment
python3 -m venv test_env
source test_env/bin/activate

# Install from local build
pip install dist/ee_deploy-0.4.0-py3-none-any.whl

# Test basic commands
ee-deploy --version
ee-deploy --help

# Deactivate and cleanup
deactivate
rm -rf test_env
```

### Step 6: Upload to Test PyPI (Recommended)

```bash
# Upload to test.pypi.org first
python3 -m twine upload --repository testpypi dist/*

# Test installation from TestPyPI
pip install --index-url https://test.pypi.org/simple/ ee-deploy==0.4.0
```

### Step 7: Upload to Production PyPI

```bash
python3 -m twine upload dist/*
```

You'll be prompted for:
- **Username**: `__token__`
- **Password**: Your PyPI API token (starts with `pypi-`)

---

## 🔑 PyPI API Token Setup

If you don't have a token:

1. Go to: https://pypi.org/manage/account/token/
2. Click "Add API token"
3. Name: `ee-deploy-v0.4.0`
4. Scope: `Project: ee-deploy` (or "Entire account" for first upload)
5. Copy the token (starts with `pypi-`)
6. Store securely (you won't see it again!)

### Save Token for Future Use

```bash
# Create .pypirc file
cat > ~/.pypirc << 'EOF'
[pypi]
username = __token__
password = pypi-YOUR_TOKEN_HERE

[testpypi]
username = __token__
password = pypi-YOUR_TEST_TOKEN_HERE
EOF

chmod 600 ~/.pypirc
```

---

## 📋 Installation Options for Users

After publishing, users can install with:

### Basic Installation
```bash
pip install ee-deploy
```

### With Premium CLI (Rich library)
```bash
pip install ee-deploy[premium]
```

### Individual Extras
```bash
pip install ee-deploy[rich]        # Premium terminal UI
pip install ee-deploy[monitoring]  # Memory/CPU metrics
```

### Development Installation
```bash
pip install ee-deploy[dev]
```

---

## ✅ Post-Publishing Verification

### 1. Check PyPI Page
Visit: https://pypi.org/project/ee-deploy/

Verify:
- ✅ Version shows `0.4.0`
- ✅ Description renders correctly
- ✅ Dependencies listed
- ✅ Project links work
- ✅ Classifiers accurate

### 2. Test Fresh Installation

```bash
# In a new environment
python3 -m venv fresh_test
source fresh_test/bin/activate

pip install ee-deploy[premium]
ee-deploy --version  # Should show: 0.4.0

# Test dashboard
ee-deploy dashboard
# Verify token authentication works

deactivate
rm -rf fresh_test
```

### 3. Update GitHub Release

1. Go to: https://github.com/adarsh-crypto/eeveon-deploy/releases/tag/v0.4.0
2. Edit release
3. Add PyPI badge:
   ```markdown
   [![PyPI version](https://badge.fury.io/py/ee-deploy.svg)](https://badge.fury.io/py/ee-deploy)
   ```
4. Add installation instructions
5. Update release notes

---

## 📊 Package Statistics

After publishing, monitor:
- **Downloads**: https://pypistats.org/packages/ee-deploy
- **Dependencies**: https://libraries.io/pypi/ee-deploy
- **Security**: https://pypi.org/project/ee-deploy/#security

---

## 🐛 Troubleshooting

### Issue: "File already exists"
**Solution**: Version already published. Bump to `0.4.1` or use TestPyPI

### Issue: "Invalid distribution"
**Solution**: 
```bash
rm -rf dist/ build/ *.egg-info
python3 -m build
```

### Issue: "README not rendering"
**Solution**: Check `long_description_content_type="text/markdown"` in setup.py

### Issue: "Missing files in package"
**Solution**: Check `MANIFEST.in` and `package_data` in setup.py

---

## 📝 MANIFEST.in (If Needed)

If files are missing, create `MANIFEST.in`:

```
include README.md
include CHANGELOG.md
include LICENSE
recursive-include eeveon/scripts *.sh
recursive-include eeveon/dashboard *.html *.css
```

---

## 🎯 Success Criteria

Publishing is successful when:

- ✅ Package appears on PyPI
- ✅ `pip install ee-deploy` works
- ✅ Dashboard launches with `ee-deploy dashboard`
- ✅ All scripts included and executable
- ✅ Dependencies install correctly
- ✅ README renders on PyPI page
- ✅ Version matches `0.4.0`

---

## 🔄 Future Updates

For v0.4.1 or v0.5.0:

1. Update version in `eeveon/__init__.py`
2. Update `CHANGELOG.md`
3. Commit and tag
4. Build: `python3 -m build`
5. Upload: `python3 -m twine upload dist/*`

---

## 📞 Support

- **PyPI Help**: https://pypi.org/help/
- **Packaging Guide**: https://packaging.python.org/
- **Twine Docs**: https://twine.readthedocs.io/

---

**Ready to publish EEveon v0.4.0 to PyPI!** 🚀

Run the commands in order and verify each step before proceeding to the next.
