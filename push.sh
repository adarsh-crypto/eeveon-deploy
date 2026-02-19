#!/bin/bash
# Quick push script for EEveon v0.4.0

echo "🚀 Pushing EEveon v0.4.0 to GitHub..."
echo ""
echo "Current commits to push:"
git log origin/main..HEAD --oneline
echo ""

# Try to push
git push origin main

if [ $? -eq 0 ]; then
    echo "✅ Successfully pushed to GitHub!"
    echo ""
    echo "📦 Next steps:"
    echo "1. Build package: python3 -m build"
    echo "2. Upload to PyPI: python3 -m twine upload dist/*"
    echo ""
    echo "See PYPI_GUIDE.md for detailed instructions"
else
    echo "❌ Push failed. You may need to authenticate."
    echo ""
    echo "Try one of these:"
    echo "1. Use GitHub CLI: gh auth login"
    echo "2. Use SSH: git remote set-url origin git@github.com:adarsh-crypto/eeveon-deploy.git"
    echo "3. Use token: git push https://TOKEN@github.com/adarsh-crypto/eeveon-deploy.git main"
fi
