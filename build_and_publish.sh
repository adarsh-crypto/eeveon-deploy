#!/bin/bash
#
# EEveon Build & Publish Script
# Build and publish to PyPI - Our own deployment pipeline!
#

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║         EEveon Build & Publish Pipeline                         ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Step 1: Run tests
echo -e "${BLUE}[1/6]${NC} Running tests..."
if ! ./tests/run_tests.sh; then
    echo -e "${RED}✗ Tests failed!${NC}"
    exit 1
fi

if ! ./tests/integration_test.sh; then
    echo -e "${RED}✗ Integration tests failed!${NC}"
    exit 1
fi

echo -e "${GREEN}✓ All tests passed${NC}"
echo ""

# Step 2: Clean previous builds
echo -e "${BLUE}[2/6]${NC} Cleaning previous builds..."
rm -rf build/ dist/ *.egg-info eeveon.egg-info
echo -e "${GREEN}✓ Cleaned${NC}"
echo ""

# Step 3: Build package
echo -e "${BLUE}[3/6]${NC} Building package..."
python3 setup.py sdist bdist_wheel
echo -e "${GREEN}✓ Package built${NC}"
echo ""

# Step 4: Check package
echo -e "${BLUE}[4/6]${NC} Checking package..."
if command -v twine &> /dev/null; then
    twine check dist/*
    echo -e "${GREEN}✓ Package check passed${NC}"
else
    echo -e "${YELLOW}⚠ twine not installed, skipping check${NC}"
    echo -e "${YELLOW}  Install with: pip install twine${NC}"
fi
echo ""

# Step 5: Test installation locally
echo -e "${BLUE}[5/6]${NC} Testing local installation..."
python3 -m pip install --user --force-reinstall dist/*.whl
echo -e "${GREEN}✓ Local installation successful${NC}"
echo ""

# Step 6: Publish (optional)
echo -e "${BLUE}[6/6]${NC} Ready to publish to PyPI"
echo ""
read -p "Do you want to publish to PyPI? (yes/no): " -r
echo

if [[ $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
    if command -v twine &> /dev/null; then
        echo "Publishing to PyPI..."
        echo ""
        echo "Choose repository:"
        echo "  1) TestPyPI (for testing)"
        echo "  2) PyPI (production)"
        read -p "Enter choice (1 or 2): " choice
        
        if [ "$choice" == "1" ]; then
            echo "Uploading to TestPyPI..."
            twine upload --repository testpypi dist/*
        elif [ "$choice" == "2" ]; then
            echo "Uploading to PyPI..."
            twine upload dist/*
        else
            echo "Invalid choice. Skipping upload."
        fi
    else
        echo -e "${RED}✗ twine not installed${NC}"
        echo "Install with: pip install twine"
        exit 1
    fi
else
    echo "Skipping PyPI upload"
fi

echo ""
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║                    Build Complete!                               ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""
echo "Package files:"
ls -lh dist/
echo ""
echo "To install locally:"
echo "  pip install dist/eeveon-*.whl"
echo ""
echo "To publish to TestPyPI:"
echo "  twine upload --repository testpypi dist/*"
echo ""
echo "To publish to PyPI:"
echo "  twine upload dist/*"
echo ""
