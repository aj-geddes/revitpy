# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| latest  | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability in RevitPy, please report it responsibly.

**Do not open a public GitHub issue for security vulnerabilities.**

Instead, please send an email to the maintainers with:

1. A description of the vulnerability
2. Steps to reproduce the issue
3. Potential impact assessment
4. Any suggested fixes (optional)

### What to Expect

- **Acknowledgment**: We will acknowledge your report within 48 hours.
- **Assessment**: We will assess the vulnerability and determine its severity within 1 week.
- **Fix**: We will work on a fix and coordinate disclosure with you.
- **Disclosure**: We will publish a security advisory once the fix is available.

## Security Practices

- Dependencies are monitored via Dependabot for known vulnerabilities.
- CI runs `pip-audit` and `ruff check --select S` (flake8-bandit) on every pull request.
- We follow the principle of least privilege in all API designs.
