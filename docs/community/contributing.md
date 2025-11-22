# Contributing to RevitPy

Thank you for your interest in contributing to RevitPy! This guide will help you get started with contributing code, documentation, and community support to make RevitPy better for everyone.

## 🚀 Quick Start

### First-Time Contributors

New to open source? No problem! Follow these steps:

1. **🍴 Fork the Repository**
   - Go to [github.com/aj-geddes/revitpy](https://github.com/aj-geddes/revitpy)
   - Click the "Fork" button in the top right
   - Clone your fork locally

2. **🛠️ Set Up Development Environment**
   ```bash
   git clone https://github.com/YOUR_USERNAME/revitpy.git
   cd revitpy
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -e .
   pip install -r requirements-dev.txt
   ```

3. **🎯 Find Your First Issue**
   - Look for issues labeled [`good first issue`](https://github.com/aj-geddes/revitpy/labels/good%20first%20issue)
   - Check the [`help wanted`](https://github.com/aj-geddes/revitpy/labels/help%20wanted) label
   - Join our [Discord](https://discord.gg/revitpy) and ask in #contributing

4. **🔄 Make Your Contribution**
   - Create a new branch for your changes
   - Make your improvements
   - Test your changes thoroughly
   - Submit a pull request

## 📋 Types of Contributions

We welcome all types of contributions to RevitPy:

### 💻 Code Contributions

#### Core Framework
- **Bug fixes**: Fix issues in the core RevitPy framework
- **New features**: Add functionality that benefits the community
- **Performance improvements**: Optimize existing code for better performance
- **API enhancements**: Improve the developer experience

#### Examples and Templates
- **Example scripts**: Real-world examples for common use cases
- **Project templates**: Starter templates for different types of projects
- **Integration examples**: Show how RevitPy works with other tools

#### Developer Tools
- **CLI improvements**: Enhance the RevitPy command-line interface
- **VS Code extension**: Improve the development environment
- **Testing tools**: Better testing utilities and frameworks
- **Build and deployment**: Improve development workflows

### 📚 Documentation Contributions

#### Content Creation
- **Tutorial writing**: Step-by-step guides for various skill levels
- **API documentation**: Improve function and class documentation
- **Best practices guides**: Share expertise on effective patterns
- **Troubleshooting guides**: Help others solve common problems

#### Documentation Maintenance
- **Fix typos and errors**: Even small fixes make a big difference
- **Update outdated content**: Keep documentation current
- **Improve clarity**: Make complex topics easier to understand
- **Add examples**: Code examples make concepts clearer

### 🤝 Community Contributions

#### Support and Mentoring
- **Answer questions**: Help others in Discord, forums, and GitHub
- **Code reviews**: Provide thoughtful feedback on pull requests
- **Mentoring**: Guide new contributors through their first contributions
- **Issue triage**: Help organize and prioritize GitHub issues

#### Community Building
- **Event organization**: Help organize meetups and conferences
- **Content creation**: Write blog posts, create videos
- **Social media**: Help spread the word about RevitPy
- **Translation**: Help translate documentation to other languages

## 🛠️ Development Setup

### Prerequisites

- **Python 3.11+**: RevitPy requires modern Python
- **Git**: For version control
- **Revit 2022+**: For testing (optional - we have mocks)
- **VS Code**: Recommended IDE with RevitPy extension

### Detailed Setup Instructions

#### 1. Clone and Setup Repository

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/revitpy.git
cd revitpy

# Add upstream remote
git remote add upstream https://github.com/aj-geddes/revitpy.git

# Create development environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

#### 2. Install Dependencies

```bash
# Install RevitPy in development mode
pip install -e .

# Install development dependencies
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install
```

#### 3. Verify Installation

```bash
# Run tests to verify everything works
pytest tests/

# Check code quality
flake8 revitpy/
black --check revitpy/
mypy revitpy/

# Test CLI
revitpy --help
```

#### 4. Configure IDE

**VS Code Configuration** (`.vscode/settings.json`):
```json
{
    "python.defaultInterpreter": "./venv/bin/python",
    "python.linting.enabled": true,
    "python.linting.flake8Enabled": true,
    "python.formatting.provider": "black",
    "python.testing.pytestEnabled": true,
    "python.testing.pytestArgs": ["tests/"],
    "revitpy.development.mode": true
}
```

### Development Workflow

#### Branch Management

```bash
# Create feature branch
git checkout -b feature/amazing-new-feature

# Keep your fork updated
git fetch upstream
git checkout main
git merge upstream/main
git push origin main
```

#### Making Changes

1. **Write clean code**: Follow PEP 8 and our style guide
2. **Add tests**: Every new feature should have tests
3. **Update documentation**: Keep docs in sync with code changes
4. **Commit frequently**: Small, focused commits are easier to review

#### Testing Your Changes

```bash
# Run unit tests
pytest tests/unit/

# Run integration tests (requires Revit or mocks)
pytest tests/integration/

# Run specific test file
pytest tests/test_specific_feature.py

# Run with coverage
pytest --cov=revitpy tests/
```

#### Code Quality Checks

```bash
# Format code
black revitpy/

# Check linting
flake8 revitpy/

# Type checking
mypy revitpy/

# Sort imports
isort revitpy/

# All quality checks at once
pre-commit run --all-files
```

## 📝 Coding Standards

### Python Style Guide

We follow PEP 8 with these additional conventions:

#### Code Formatting
```python
# Use Black formatter for consistent code style
# Line length: 88 characters (Black default)
# Use double quotes for strings
# Use trailing commas in multi-line structures

# Good example
def process_elements(
    elements: List[Element],
    filter_func: Optional[Callable[[Element], bool]] = None,
    include_hidden: bool = False,
) -> List[Element]:
    """Process elements with optional filtering.

    Args:
        elements: List of elements to process
        filter_func: Optional function to filter elements
        include_hidden: Whether to include hidden elements

    Returns:
        List of processed elements
    """
    if filter_func is None:
        filter_func = lambda x: True

    return [
        element
        for element in elements
        if filter_func(element) or (include_hidden and element.is_hidden)
    ]
```

#### Type Annotations
```python
from typing import List, Optional, Dict, Any, Union
from revitpy.types import Element, ElementId

# Always use type annotations for public functions
def get_element_by_id(element_id: ElementId) -> Optional[Element]:
    """Get element by ID."""
    pass

# Use generic types for collections
def process_elements(elements: List[Element]) -> Dict[str, Any]:
    """Process elements and return summary."""
    pass

# Use Union for multiple possible types
def get_parameter_value(element: Element, param_name: str) -> Union[str, float, int, None]:
    """Get parameter value with proper typing."""
    pass
```

#### Documentation Strings
```python
def complex_function(
    param1: str,
    param2: Optional[int] = None,
    **kwargs
) -> Dict[str, Any]:
    """One-line summary of what the function does.

    Longer description of the function, including details about
    its behavior, algorithm, or important considerations.

    Args:
        param1: Description of the first parameter
        param2: Description of the second parameter with default value
        **kwargs: Additional keyword arguments:
            - special_option (bool): Enable special processing
            - timeout (int): Timeout in seconds

    Returns:
        Dictionary containing:
            - success (bool): Whether operation succeeded
            - data (List[Any]): Processed data
            - errors (List[str]): Any errors encountered

    Raises:
        ValueError: If param1 is empty
        RevitPyException: If Revit operation fails

    Example:
        >>> result = complex_function("test", param2=42)
        >>> print(result["success"])
        True

    Note:
        This function requires an active Revit context.
    """
    pass
```

#### Error Handling
```python
from revitpy.exceptions import RevitPyException, ElementNotFound

# Use specific exceptions
try:
    element = context.get_element_by_id(element_id)
except ElementNotFound as e:
    logger.warning(f"Element {element_id} not found: {e}")
    return None
except RevitPyException as e:
    logger.error(f"RevitPy error: {e}")
    raise

# Provide helpful error messages
if not isinstance(element_id, ElementId):
    raise ValueError(
        f"element_id must be an ElementId, got {type(element_id).__name__}. "
        f"Use ElementId.from_int() to convert from integer."
    )
```

### Testing Standards

#### Test Structure
```python
import pytest
from revitpy.testing import MockRevitContext, create_mock_element
from revitpy import RevitContext

class TestElementProcessing:
    """Test suite for element processing functionality."""

    def test_simple_element_query(self):
        """Test basic element querying."""
        with MockRevitContext() as context:
            # Arrange
            wall = create_mock_element('Wall', Height=10.0)
            context.add_element(wall)

            # Act
            walls = context.elements.of_category('Walls').to_list()

            # Assert
            assert len(walls) == 1
            assert walls[0].Height == 10.0

    def test_complex_filtering(self):
        """Test complex element filtering scenarios."""
        with MockRevitContext() as context:
            # Arrange
            elements = [
                create_mock_element('Wall', Height=8.0, Name='Short Wall'),
                create_mock_element('Wall', Height=12.0, Name='Tall Wall'),
                create_mock_element('Door', Height=7.0, Name='Door'),
            ]
            context.add_elements(elements)

            # Act
            tall_walls = (context.elements
                         .of_category('Walls')
                         .where(lambda w: w.Height > 10.0)
                         .to_list())

            # Assert
            assert len(tall_walls) == 1
            assert tall_walls[0].Name == 'Tall Wall'

    @pytest.mark.parametrize("height,expected_count", [
        (5.0, 3),   # All elements
        (8.0, 2),   # Walls and door
        (12.0, 1),  # Only tall wall
        (15.0, 0),  # No elements
    ])
    def test_height_filtering(self, height, expected_count):
        """Test height-based filtering with multiple scenarios."""
        with MockRevitContext() as context:
            elements = [
                create_mock_element('Wall', Height=8.0),
                create_mock_element('Wall', Height=12.0),
                create_mock_element('Door', Height=7.0),
            ]
            context.add_elements(elements)

            results = (context.elements
                      .where(lambda e: e.Height >= height)
                      .to_list())

            assert len(results) == expected_count
```

#### Performance Testing
```python
import pytest
import time
from revitpy.testing import performance_test

@performance_test(max_time=1.0)  # Must complete in under 1 second
def test_large_element_query_performance():
    """Test query performance with large datasets."""
    with MockRevitContext() as context:
        # Create large dataset
        elements = [
            create_mock_element('Wall', Height=i % 20)
            for i in range(10000)
        ]
        context.add_elements(elements)

        # Test query performance
        start_time = time.time()
        tall_walls = (context.elements
                     .of_category('Walls')
                     .where(lambda w: w.Height > 15.0)
                     .to_list())
        end_time = time.time()

        # Verify results and performance
        assert len(tall_walls) > 0
        assert (end_time - start_time) < 1.0
```

## 🔄 Pull Request Process

### Before Submitting

1. **✅ Self-Review Checklist**
   - [ ] Code follows our style guide
   - [ ] All tests pass
   - [ ] Documentation is updated
   - [ ] Type annotations are added
   - [ ] Performance impact considered

2. **🧪 Testing Checklist**
   - [ ] Unit tests added for new functionality
   - [ ] Integration tests pass
   - [ ] Manual testing completed
   - [ ] Performance benchmarks run (if applicable)

3. **📝 Documentation Checklist**
   - [ ] Docstrings added/updated
   - [ ] API documentation updated
   - [ ] Tutorial/guide updated (if applicable)
   - [ ] CHANGELOG.md updated

### Submitting Your Pull Request

#### PR Title Format
Use conventional commit format:
- `feat: add new ORM relationship handling`
- `fix: resolve transaction rollback issue`
- `docs: update API reference for QueryBuilder`
- `test: add integration tests for element creation`
- `perf: optimize element query performance`
- `refactor: simplify transaction manager code`

#### PR Description Template
```markdown
## Description
Brief description of what this PR does.

## Type of Change
- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update
- [ ] Performance improvement
- [ ] Refactoring (no functional changes)

## Related Issues
Closes #123
Relates to #456

## Changes Made
- Detailed list of changes
- What files were modified
- What functionality was added/changed

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] Manual testing completed
- Describe any manual testing performed

## Documentation
- [ ] Code comments added/updated
- [ ] API documentation updated
- [ ] User documentation updated
- [ ] CHANGELOG.md updated

## Performance Impact
Describe any performance implications.

## Breaking Changes
List any breaking changes and migration steps.

## Screenshots (if applicable)
Add screenshots for UI changes.

## Additional Notes
Any additional information for reviewers.
```

### Code Review Process

#### What Reviewers Look For

1. **Code Quality**
   - Follows coding standards
   - Is well-structured and readable
   - Has appropriate error handling
   - Uses proper abstractions

2. **Functionality**
   - Solves the intended problem
   - Handles edge cases
   - Has comprehensive tests
   - Doesn't break existing functionality

3. **Performance**
   - Doesn't introduce performance regressions
   - Uses efficient algorithms and data structures
   - Considers memory usage
   - Has performance tests if needed

4. **Documentation**
   - Code is well-documented
   - API changes are documented
   - User-facing changes have examples

#### Responding to Feedback

- **Be responsive**: Try to respond within 24-48 hours
- **Be open**: Consider feedback objectively
- **Be thorough**: Address all feedback points
- **Be collaborative**: Discuss complex changes

```bash
# Making changes based on feedback
git checkout feature/your-branch
# Make your changes
git add .
git commit -m "Address review feedback: improve error handling"
git push origin feature/your-branch
```

#### Review Approval Process

1. **Automatic Checks**: CI must pass
2. **Code Review**: At least one maintainer approval required
3. **Additional Reviews**: Complex changes may need multiple reviews
4. **Final Approval**: Maintainer merges the PR

## 🏷️ Issue Management

### Reporting Bugs

Use our bug report template:

```markdown
**Bug Description**
Clear description of the bug.

**Steps to Reproduce**
1. Step 1
2. Step 2
3. Step 3

**Expected Behavior**
What should happen.

**Actual Behavior**
What actually happens.

**Environment**
- RevitPy version:
- Python version:
- Revit version:
- Operating system:

**Code Sample**
```python
# Minimal code sample that reproduces the issue
```

**Additional Context**
Any other relevant information.
```

### Feature Requests

Use our feature request template:

```markdown
**Feature Summary**
Brief description of the feature.

**Motivation**
Why is this feature needed?

**Detailed Description**
Detailed description of the desired functionality.

**Use Cases**
Specific use cases and scenarios.

**Proposed API**
```python
# Example of how the feature might work
```

**Alternatives Considered**
Other approaches you've considered.

**Additional Context**
Any other relevant information.
```

### Issue Labels

We use labels to organize and prioritize issues:

#### Type Labels
- `bug`: Something isn't working
- `enhancement`: New feature or request
- `documentation`: Improvements or additions to documentation
- `good first issue`: Good for newcomers
- `help wanted`: Extra attention is needed

#### Priority Labels
- `priority: critical`: Critical issues that block releases
- `priority: high`: Important issues for next release
- `priority: medium`: Regular priority
- `priority: low`: Nice to have

#### Component Labels
- `component: core`: Core framework functionality
- `component: orm`: ORM layer issues
- `component: cli`: Command-line interface
- `component: docs`: Documentation
- `component: tests`: Test-related issues

## 🎯 Contribution Ideas

### Beginner-Friendly Contributions

#### Documentation Improvements
- **Fix typos**: Even small fixes help
- **Add code examples**: Make concepts clearer with examples
- **Improve error messages**: Better error messages help users
- **Write tutorials**: Share your learning experience

#### Small Code Improvements
- **Add type annotations**: Improve code clarity
- **Write unit tests**: Increase test coverage
- **Fix linting issues**: Clean up code quality
- **Optimize imports**: Better organization

### Intermediate Contributions

#### Feature Development
- **New ORM features**: Query improvements and optimizations
- **CLI enhancements**: Better developer experience
- **Performance optimizations**: Make RevitPy faster
- **Integration improvements**: Better tool integration

#### Quality Improvements
- **Test coverage**: Add comprehensive tests
- **Error handling**: Improve error recovery
- **Logging improvements**: Better debugging support
- **Code organization**: Refactor for clarity

### Advanced Contributions

#### Architecture Improvements
- **Performance optimization**: Major performance improvements
- **New integrations**: Connect with other tools and services
- **Security enhancements**: Improve security features
- **Enterprise features**: Advanced enterprise functionality

#### Infrastructure
- **CI/CD improvements**: Better development workflows
- **Deployment automation**: Streamline deployment processes
- **Monitoring and observability**: Better operational insights
- **Developer tooling**: Tools to improve development experience

## 🏆 Recognition and Rewards

### Contributor Recognition

#### GitHub Recognition
- **Contributor badge**: Show your involvement on GitHub profile
- **Contribution statistics**: Track your impact over time
- **Release notes**: Major contributors mentioned in releases

#### Community Recognition
- **Contributor of the month**: Monthly recognition program
- **Community highlights**: Featured in newsletters and social media
- **Speaking opportunities**: Present at conferences and meetups
- **Mentorship opportunities**: Help guide new contributors

### Material Rewards

#### Swag and Perks
- **RevitPy merchandise**: T-shirts, stickers, mugs for active contributors
- **Conference tickets**: Free tickets to relevant conferences
- **Learning resources**: Access to courses and books
- **Tool licenses**: Free licenses for development tools

#### Professional Benefits
- **LinkedIn endorsements**: Public recognition of your skills
- **Reference letters**: For job applications and career growth
- **Networking opportunities**: Connect with industry professionals
- **Job opportunities**: Many contributors find new career opportunities

## 📚 Resources for Contributors

### Documentation
- **[Architecture Guide](../guides/architecture-overview.md)**: Understanding RevitPy's architecture
- **[API Reference](../reference/index.md)**: Complete API documentation
- **[Development Setup](../getting-started/development-setup.md)**: Detailed setup instructions

### Tools and Templates
- **[PR Template](.github/pull_request_template.md)**: Pull request template
- **[Issue Templates](.github/ISSUE_TEMPLATE/)**: Issue reporting templates
- **[VS Code Settings](.vscode/settings.json)**: Recommended IDE configuration

### Community Resources
- **[Discord](https://discord.gg/revitpy)**: Real-time community discussion
- **[Forum](https://forum.revitpy.dev)**: Long-form discussions and Q&A
- **[GitHub Discussions](https://github.com/aj-geddes/revitpy/discussions)**: Development discussions

### Learning Resources
- **[Python Guide](https://docs.python.org/3/)**: Official Python documentation
- **[Git Handbook](https://guides.github.com/introduction/git-handbook/)**: Git basics
- **[Open Source Guides](https://opensource.guide/)**: Contributing to open source

## ❓ Frequently Asked Questions

### Getting Started

**Q: I'm new to open source. Where should I start?**
A: Start with issues labeled "good first issue" and join our Discord community for guidance.

**Q: Do I need to know the Revit API to contribute?**
A: Not necessarily! We need help with documentation, testing, CLI tools, and many other areas.

**Q: How long does it take to get a PR reviewed?**
A: Most PRs get initial feedback within 2-3 days. Complex changes may take longer.

### Development Process

**Q: Should I create an issue before submitting a PR?**
A: For bug fixes and small improvements, a PR is fine. For new features, create an issue first to discuss the approach.

**Q: Can I work on multiple issues at once?**
A: Yes, but we recommend focusing on one at a time, especially when starting out.

**Q: What if my PR conflicts with other changes?**
A: Rebase your branch against the latest main branch and resolve conflicts locally.

### Code and Standards

**Q: Do I need to write tests for every change?**
A: Yes, for any functional changes. Documentation-only changes don't need tests.

**Q: What Python version should I target?**
A: RevitPy requires Python 3.11+. Use modern Python features when appropriate.

**Q: How strict are the coding standards?**
A: We use automated tools (Black, flake8, mypy) to enforce standards. Follow the pre-commit hooks.

### Community and Support

**Q: Where can I get help if I'm stuck?**
A: Discord #contributing channel is the best place for real-time help. GitHub Discussions for longer-form questions.

**Q: Are there regular contributor meetups?**
A: Yes, we have monthly contributor meetups. Check the #events channel on Discord.

**Q: How can I become a maintainer?**
A: Maintainers are selected from active contributors who demonstrate expertise and community leadership over time.

## 📞 Getting Help

### Support Channels

| Topic | Best Channel | Response Time |
|-------|-------------|---------------|
| **General Questions** | Discord #contributing | < 2 hours |
| **Technical Issues** | Discord #dev-help | < 4 hours |
| **Design Decisions** | GitHub Discussions | < 1 day |
| **PR Reviews** | GitHub PR comments | < 2 days |

### Contact Information

- **💬 Discord**: [#contributing channel](https://discord.gg/revitpy)
- **📝 GitHub Discussions**: [Development discussions](https://github.com/aj-geddes/revitpy/discussions)
- **📧 Email**: [contributors@revitpy.dev](mailto:contributors@revitpy.dev)
- **📅 Office Hours**: Wednesdays 2PM UTC in Discord voice

---

Thank you for considering contributing to RevitPy! Every contribution, no matter how small, helps make RevitPy better for the entire community. We're excited to see what we'll build together!

**Ready to contribute?** Start by [forking the repository](https://github.com/aj-geddes/revitpy/fork) and joining our [Discord community](https://discord.gg/revitpy)!

---

!!! tip "Contributor Quick Links"

    - 🍴 [Fork the Repository](https://github.com/aj-geddes/revitpy/fork)
    - 🎯 [Good First Issues](https://github.com/aj-geddes/revitpy/labels/good%20first%20issue)
    - 💬 [Discord #contributing](https://discord.gg/revitpy)
    - 📋 [Issue Templates](https://github.com/aj-geddes/revitpy/issues/new/choose)
    - 📝 [PR Template](https://github.com/aj-geddes/revitpy/compare)

    **Questions?** Ask in Discord or email [contributors@revitpy.dev](mailto:contributors@revitpy.dev)
