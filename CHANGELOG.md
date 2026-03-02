# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- CI matrix testing across Python 3.11 and 3.12
- Security job in CI with pip-audit and ruff bandit rules
- Ruff format checking in CI lint job
- Mypy pre-commit hook with type stubs
- SECURITY.md vulnerability reporting policy
- Dependabot configuration for automated dependency updates
- CHANGELOG.md to track project changes
- flake8-bandit (S) rules in ruff lint configuration

### Changed
- Replaced black and isort with ruff format (single formatter)
- Extracted magic numbers into named constants across async and event decorators

### Removed
- black and isort dependencies (replaced by ruff format)
- `[tool.black]` and `[tool.isort]` configuration sections
