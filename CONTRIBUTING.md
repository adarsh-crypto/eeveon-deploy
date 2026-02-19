# Contributing to EEveon

First off, thank you for considering contributing to EEveon! It's people like you that make EEveon such a great tool.

## Code of Conduct

This project and everyone participating in it is governed by our Code of Conduct. By participating, you are expected to uphold this code.

## How Can I Contribute?

### Reporting Bugs

Before creating bug reports, please check the existing issues as you might find out that you don't need to create one. When you are creating a bug report, please include as many details as possible:

* **Use a clear and descriptive title**
* **Describe the exact steps which reproduce the problem**
* **Provide specific examples to demonstrate the steps**
* **Describe the behavior you observed after following the steps**
* **Explain which behavior you expected to see instead and why**
* **Include logs from `ee-deploy logs`**

### Suggesting Enhancements

Enhancement suggestions are tracked as GitHub issues. When creating an enhancement suggestion, please include:

* **Use a clear and descriptive title**
* **Provide a step-by-step description of the suggested enhancement**
* **Provide specific examples to demonstrate the steps**
* **Describe the current behavior and explain which behavior you expected to see instead**
* **Explain why this enhancement would be useful**

### Pull Requests

* Fill in the required template
* Do not include issue numbers in the PR title
* Follow the Python and Bash style guides
* Include thoughtfully-worded, well-structured tests
* Document new code
* End all files with a newline

## Development Setup

1. Fork the repo
2. Clone your fork:
   ```bash
   git clone https://github.com/your-username/eeveon-deploy.git
   cd eeveon-deploy
   ```

3. Create a branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```

4. Make your changes

5. Test your changes:
   ```bash
   ./install.sh
   ee-deploy --help
   ```

6. Commit your changes:
   ```bash
   git add .
   git commit -m "Add some feature"
   ```

7. Push to your fork:
   ```bash
   git push origin feature/your-feature-name
   ```

8. Create a Pull Request

## Style Guides

### Git Commit Messages

* Use the present tense ("Add feature" not "Added feature")
* Use the imperative mood ("Move cursor to..." not "Moves cursor to...")
* Limit the first line to 72 characters or less
* Reference issues and pull requests liberally after the first line

### Python Style Guide

* Follow PEP 8
* Use meaningful variable names
* Add docstrings to functions
* Keep functions focused and small

### Bash Style Guide

* Use `#!/bin/bash` shebang
* Add comments for complex logic
* Use meaningful variable names in UPPERCASE
* Check return codes with `if [ $? -eq 0 ]`

## Testing

Before submitting a pull request, please test your changes:

1. Test the installation:
   ```bash
   ./install.sh
   ```

2. Test basic commands:
   ```bash
   ee-deploy --help
   ee-deploy list
   ```

3. Test with a real repository (if applicable)

## Questions?

Feel free to open an issue with your question or reach out to the maintainers.

Thank you for contributing! 🎉
