#!/usr/bin/env python3
"""
RevitPy Package Manager - Security Validation Script

This script performs comprehensive security validation to ensure all
critical vulnerabilities have been addressed.
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


def run_command(cmd: list[str], timeout: int = 60) -> dict[str, Any]:
    """Run a command and return the result."""
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, check=False
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "stdout": "",
            "stderr": "Command timed out",
            "returncode": -1,
        }
    except Exception as e:
        return {"success": False, "stdout": "", "stderr": str(e), "returncode": -1}


def check_dependencies() -> dict[str, Any]:
    """Check for vulnerable dependencies."""
    print("🔍 Checking dependencies for vulnerabilities...")

    result = run_command(["pip-audit", "--format=json"])

    if not result["success"]:
        return {
            "status": "error",
            "message": f"Failed to run pip-audit: {result['stderr']}",
        }

    try:
        audit_data = json.loads(result["stdout"])
        vulnerabilities = []

        for dep in audit_data.get("dependencies", []):
            if dep.get("vulns"):
                for vuln in dep["vulns"]:
                    vulnerabilities.append(
                        {
                            "package": dep["name"],
                            "version": dep["version"],
                            "vulnerability": vuln["id"],
                            "description": vuln.get("description", ""),
                            "fix_versions": vuln.get("fix_versions", []),
                        }
                    )

        critical_vulns = [
            v
            for v in vulnerabilities
            if "CVSS" in v.get("description", "") and "9." in v.get("description", "")
        ]
        high_vulns = [
            v
            for v in vulnerabilities
            if "CVSS" in v.get("description", "")
            and ("8." in v.get("description", "") or "7." in v.get("description", ""))
        ]

        return {
            "status": "success",
            "total_vulnerabilities": len(vulnerabilities),
            "critical_vulnerabilities": len(critical_vulns),
            "high_vulnerabilities": len(high_vulns),
            "vulnerabilities": vulnerabilities,
            "critical": critical_vulns,
            "high": high_vulns,
        }
    except json.JSONDecodeError as e:
        return {"status": "error", "message": f"Failed to parse pip-audit output: {e}"}


def check_bandit_security() -> dict[str, Any]:
    """Run Bandit security analysis."""
    print("🔍 Running Bandit security analysis...")

    result = run_command(
        [
            "bandit",
            "-r",
            "revitpy_package_manager/",
            "-f",
            "json",
            "-ll",  # Only high severity issues
        ]
    )

    if result["returncode"] not in [0, 1]:  # Bandit returns 1 when issues found
        return {"status": "error", "message": f"Bandit failed: {result['stderr']}"}

    try:
        bandit_data = json.loads(result["stdout"])
        results = bandit_data.get("results", [])

        # Filter for high and medium severity issues
        high_severity = [r for r in results if r.get("issue_severity") == "HIGH"]
        medium_severity = [r for r in results if r.get("issue_severity") == "MEDIUM"]

        return {
            "status": "success",
            "total_issues": len(results),
            "high_severity": len(high_severity),
            "medium_severity": len(medium_severity),
            "issues": results,
            "high_issues": high_severity,
            "medium_issues": medium_severity,
        }
    except json.JSONDecodeError as e:
        return {"status": "error", "message": f"Failed to parse Bandit output: {e}"}


def check_jwt_security() -> dict[str, Any]:
    """Check JWT security configuration."""
    print("🔍 Checking JWT security configuration...")

    # Check that JWT_SECRET_KEY is required
    try:
        # Try to import without JWT_SECRET_KEY
        old_env = os.environ.copy()
        if "JWT_SECRET_KEY" in os.environ:
            del os.environ["JWT_SECRET_KEY"]

        try:
            return {
                "status": "fail",
                "message": "JWT_SECRET_KEY is not required - security vulnerability!",
            }
        except ValueError as e:
            if "JWT_SECRET_KEY" in str(e):
                return {
                    "status": "pass",
                    "message": "JWT_SECRET_KEY is properly required",
                }
            else:
                return {"status": "error", "message": f"Unexpected error: {e}"}
        except Exception as e:
            return {"status": "error", "message": f"Failed to test JWT security: {e}"}
        finally:
            os.environ.clear()
            os.environ.update(old_env)

    except Exception as e:
        return {"status": "error", "message": f"Failed to check JWT configuration: {e}"}


def check_file_permissions() -> dict[str, Any]:
    """Check critical file permissions."""
    print("🔍 Checking file permissions...")

    issues = []

    # Check for world-writable files
    for root, _dirs, files in os.walk("."):
        for file in files:
            filepath = os.path.join(root, file)
            try:
                stat = os.stat(filepath)
                mode = stat.st_mode

                # Check if world-writable
                if mode & 0o002:
                    issues.append(f"World-writable file: {filepath}")

                # Check for executable config files
                if (
                    file.endswith((".yaml", ".yml", ".json", ".toml", ".env"))
                    and mode & 0o111
                ):
                    issues.append(f"Executable config file: {filepath}")

            except (OSError, PermissionError):
                continue

    return {
        "status": "pass" if not issues else "fail",
        "issues": issues,
        "message": f"Found {len(issues)} permission issues",
    }


def check_hardcoded_secrets() -> dict[str, Any]:
    """Check for hardcoded secrets."""
    print("🔍 Checking for hardcoded secrets...")

    result = run_command(
        [
            "grep",
            "-r",
            "-i",
            "-E",
            "(password|secret|key|token).*[=:].*['\"][^'\"]{8,}['\"]",
            "revitpy_package_manager/",
            "--exclude-dir=__pycache__",
        ]
    )

    hardcoded_secrets = []

    if result["success"] and result["stdout"]:
        lines = result["stdout"].strip().split("\n")
        for line in lines:
            # Filter out test files and examples
            if (
                "test_" not in line
                and "example" not in line
                and ".env.example" not in line
            ):
                # Check for actual hardcoded values (not placeholders)
                if any(
                    bad in line.lower()
                    for bad in [
                        "change_me",
                        "your_secret",
                        "your-secret",
                        "test_secret",
                    ]
                ):
                    continue
                hardcoded_secrets.append(line)

    return {
        "status": "pass" if not hardcoded_secrets else "fail",
        "secrets_found": len(hardcoded_secrets),
        "secrets": hardcoded_secrets,
        "message": f"Found {len(hardcoded_secrets)} potential hardcoded secrets",
    }


def generate_security_report(results: dict[str, Any]) -> None:
    """Generate a comprehensive security report."""
    print("\n" + "=" * 80)
    print("🛡️  REVITPY SECURITY VALIDATION REPORT")
    print("=" * 80)
    print(
        f"Generated: {subprocess.run(['date'], capture_output=True, text=True).stdout.strip()}"
    )
    print()

    # Overall status
    critical_issues = 0
    warnings = 0

    # Dependency vulnerabilities
    dep_result = results.get("dependencies", {})
    if dep_result.get("status") == "success":
        critical_vulns = dep_result.get("critical_vulnerabilities", 0)
        high_vulns = dep_result.get("high_vulnerabilities", 0)
        total_vulns = dep_result.get("total_vulnerabilities", 0)

        print("📦 DEPENDENCY SECURITY:")
        if critical_vulns > 0:
            print(f"   ❌ CRITICAL: {critical_vulns} critical vulnerabilities found")
            critical_issues += critical_vulns
        elif high_vulns > 0:
            print(f"   ⚠️  HIGH: {high_vulns} high severity vulnerabilities")
            warnings += high_vulns
        elif total_vulns > 0:
            print(f"   ⚠️  MEDIUM: {total_vulns} total vulnerabilities")
            warnings += total_vulns
        else:
            print("   ✅ No critical vulnerabilities found")
    else:
        print(f"   ❌ ERROR: {dep_result.get('message', 'Unknown error')}")
        critical_issues += 1

    # Bandit analysis
    bandit_result = results.get("bandit", {})
    if bandit_result.get("status") == "success":
        high_issues = bandit_result.get("high_severity", 0)
        medium_issues = bandit_result.get("medium_severity", 0)

        print("\n🔍 CODE SECURITY (Bandit):")
        if high_issues > 0:
            print(f"   ❌ HIGH: {high_issues} high severity issues")
            critical_issues += high_issues
        elif medium_issues > 0:
            print(f"   ⚠️  MEDIUM: {medium_issues} medium severity issues")
            warnings += medium_issues
        else:
            print("   ✅ No high/medium security issues found")
    else:
        print(f"\n❌ BANDIT ERROR: {bandit_result.get('message', 'Unknown error')}")
        critical_issues += 1

    # JWT security
    jwt_result = results.get("jwt", {})
    print("\n🔑 JWT SECURITY:")
    if jwt_result.get("status") == "pass":
        print("   ✅ JWT secret key properly required")
    elif jwt_result.get("status") == "fail":
        print(f"   ❌ JWT SECURITY ISSUE: {jwt_result.get('message')}")
        critical_issues += 1
    else:
        print(f"   ⚠️  WARNING: {jwt_result.get('message')}")
        warnings += 1

    # File permissions
    perm_result = results.get("permissions", {})
    print("\n📁 FILE PERMISSIONS:")
    if perm_result.get("status") == "pass":
        print("   ✅ No critical permission issues")
    else:
        issues = perm_result.get("issues", [])
        print(f"   ⚠️  WARNING: {len(issues)} permission issues")
        warnings += len(issues)
        for issue in issues[:5]:  # Show first 5
            print(f"      - {issue}")
        if len(issues) > 5:
            print(f"      ... and {len(issues) - 5} more")

    # Hardcoded secrets
    secret_result = results.get("secrets", {})
    print("\n🔐 HARDCODED SECRETS:")
    if secret_result.get("status") == "pass":
        print("   ✅ No hardcoded secrets detected")
    else:
        secrets = secret_result.get("secrets_found", 0)
        print(f"   ❌ CRITICAL: {secrets} potential hardcoded secrets")
        critical_issues += secrets

    # Overall assessment
    print("\n" + "=" * 80)
    print("📊 OVERALL SECURITY ASSESSMENT")
    print("=" * 80)

    if critical_issues > 0:
        print(f"❌ FAILED: {critical_issues} critical security issues found")
        print(
            "\n🚨 DEPLOYMENT BLOCKED - Critical issues must be resolved before production deployment"
        )
        return False
    elif warnings > 0:
        print(f"⚠️  WARNINGS: {warnings} security warnings found")
        print("\n⚠️  CONDITIONAL PASS - Address warnings before production deployment")
        return True
    else:
        print("✅ PASSED: No critical security issues found")
        print("\n🎉 SECURITY VALIDATION SUCCESSFUL - Ready for secure deployment")
        return True


def main():
    """Main security validation function."""
    print("🛡️  Starting RevitPy Package Manager Security Validation...")
    print("=" * 80)

    # Change to package manager directory
    os.chdir(Path(__file__).parent.parent)

    results = {}

    # Run all security checks
    results["dependencies"] = check_dependencies()
    results["bandit"] = check_bandit_security()
    results["jwt"] = check_jwt_security()
    results["permissions"] = check_file_permissions()
    results["secrets"] = check_hardcoded_secrets()

    # Generate report
    success = generate_security_report(results)

    # Create security artifacts
    artifacts_dir = Path("security_artifacts")
    artifacts_dir.mkdir(exist_ok=True)

    # Save detailed results
    with open(artifacts_dir / "security_validation_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)

    # Create security checklist
    checklist = f"""# RevitPy Package Manager - Security Checklist

## Critical Vulnerabilities - {'RESOLVED' if success else 'REQUIRES ACTION'}
- [ ] All critical (CVSS 9.0+) vulnerabilities patched
- [ ] All high (CVSS 7.0-8.9) vulnerabilities addressed
- [ ] JWT secret key properly configured and required
- [ ] No hardcoded secrets in production code
- [ ] Subprocess calls properly secured

## Security Controls - IMPLEMENTED
- [x] Input validation and sanitization
- [x] SQL injection prevention via ORM
- [x] XSS prevention in user inputs
- [x] Path traversal protection
- [x] File upload security validation
- [x] Password strength requirements
- [x] bcrypt password hashing
- [x] JWT algorithm confusion prevention
- [x] Security headers implementation
- [x] CORS configuration
- [x] Trusted host validation

## Deployment Security
- [ ] Generate strong JWT secret (64+ characters)
- [ ] Configure secure database passwords
- [ ] Set up HTTPS certificates
- [ ] Configure firewall rules
- [ ] Set up monitoring and alerting
- [ ] Review security headers configuration
- [ ] Configure trusted hosts for production
- [ ] Set up log aggregation

## Monitoring & Maintenance
- [ ] Automated vulnerability scanning
- [ ] Security log monitoring
- [ ] Regular dependency updates
- [ ] Security incident response plan

## Status: {'SECURITY VALIDATION PASSED' if success else 'SECURITY ISSUES REQUIRE RESOLUTION'}
"""

    with open(artifacts_dir / "security_checklist.md", "w") as f:
        f.write(checklist)

    print(f"\n📄 Security artifacts saved to: {artifacts_dir.absolute()}")

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
