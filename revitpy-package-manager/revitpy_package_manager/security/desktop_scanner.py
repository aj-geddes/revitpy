"""Security scanner for RevitPy packages (.rpyx format)."""

import ast
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class SecurityIssue:
    """Represents a security issue found during scanning."""

    severity: str  # low, medium, high, critical
    category: str  # malware, suspicious_code, data_exfiltration, etc.
    description: str
    file_path: str
    line_number: int | None = None
    code_snippet: str | None = None


@dataclass
class SecurityScanResult:
    """Results of a security scan."""

    package_path: str
    risk_level: str  # low, medium, high, critical
    issues: list[SecurityIssue]
    scan_timestamp: str
    scan_duration: float
    files_scanned: int

    @property
    def is_safe(self) -> bool:
        """Return True if package is considered safe."""
        return self.risk_level in ["low", "medium"] and not any(
            issue.severity == "critical" for issue in self.issues
        )


class SecurityScanner:
    """Security scanner for RevitPy packages."""

    def __init__(self):
        self.suspicious_patterns = self._load_suspicious_patterns()
        self.dangerous_imports = self._load_dangerous_imports()
        self.file_extensions = {".py", ".pyw", ".pyx", ".pyi"}

    def _load_suspicious_patterns(self) -> dict[str, dict[str, Any]]:
        """Load patterns that indicate suspicious behavior."""
        return {
            # Command execution patterns
            r"os\.system\s*\(": {
                "severity": "high",
                "category": "command_execution",
                "description": "Executes system commands",
            },
            r"subprocess\.(call|run|Popen|check_output|check_call)": {
                "severity": "high",
                "category": "command_execution",
                "description": "Executes external commands",
            },
            r"eval\s*\(": {
                "severity": "high",
                "category": "code_injection",
                "description": "Dynamic code execution with eval()",
            },
            r"exec\s*\(": {
                "severity": "high",
                "category": "code_injection",
                "description": "Dynamic code execution with exec()",
            },
            r"compile\s*\(": {
                "severity": "medium",
                "category": "code_injection",
                "description": "Dynamic code compilation",
            },
            # Network and file operations
            r"urllib\.(request|urlopen)": {
                "severity": "medium",
                "category": "network_access",
                "description": "Makes network requests",
            },
            r"requests\.(get|post|put|delete)": {
                "severity": "medium",
                "category": "network_access",
                "description": "HTTP requests",
            },
            r"socket\.(socket|connect)": {
                "severity": "medium",
                "category": "network_access",
                "description": "Socket network communication",
            },
            r"ftplib\.": {
                "severity": "medium",
                "category": "network_access",
                "description": "FTP communication",
            },
            r"smtplib\.": {
                "severity": "medium",
                "category": "network_access",
                "description": "Email sending capabilities",
            },
            # File system operations
            r"shutil\.(rmtree|move|copy)": {
                "severity": "medium",
                "category": "file_system",
                "description": "File system manipulation",
            },
            r"os\.(remove|unlink|rmdir)": {
                "severity": "medium",
                "category": "file_system",
                "description": "File deletion operations",
            },
            r"tempfile\.": {
                "severity": "low",
                "category": "file_system",
                "description": "Temporary file operations",
            },
            # Serialization risks
            r"pickle\.(loads|load)": {
                "severity": "high",
                "category": "deserialization",
                "description": "Unsafe deserialization with pickle",
            },
            r"marshal\.(loads|load)": {
                "severity": "high",
                "category": "deserialization",
                "description": "Unsafe deserialization with marshal",
            },
            r"dill\.(loads|load)": {
                "severity": "high",
                "category": "deserialization",
                "description": "Unsafe deserialization with dill",
            },
            # Registry and system information
            r"winreg\.": {
                "severity": "medium",
                "category": "system_access",
                "description": "Windows registry access",
            },
            r"platform\.": {
                "severity": "low",
                "category": "system_info",
                "description": "System information gathering",
            },
            # Obfuscation indicators
            r"base64\.(b64decode|decode)": {
                "severity": "medium",
                "category": "obfuscation",
                "description": "Base64 decoding (possible obfuscation)",
            },
            r"codecs\.decode": {
                "severity": "medium",
                "category": "obfuscation",
                "description": "String decoding (possible obfuscation)",
            },
            # Credential patterns
            r'(password|passwd|pwd)\s*=\s*[\'"][^\'"]+[\'"]': {
                "severity": "medium",
                "category": "credentials",
                "description": "Hardcoded password detected",
            },
            r'(api_key|apikey|secret_key)\s*=\s*[\'"][^\'"]+[\'"]': {
                "severity": "medium",
                "category": "credentials",
                "description": "Hardcoded API key detected",
            },
        }

    def _load_dangerous_imports(self) -> dict[str, dict[str, Any]]:
        """Load imports that are considered dangerous."""
        return {
            "ctypes": {"severity": "high", "description": "Low-level C library access"},
            "win32api": {"severity": "medium", "description": "Windows API access"},
            "win32con": {"severity": "medium", "description": "Windows constants"},
            "win32gui": {
                "severity": "medium",
                "description": "Windows GUI manipulation",
            },
            "psutil": {
                "severity": "low",
                "description": "System and process information",
            },
            "keyring": {"severity": "low", "description": "Credential storage access"},
        }

    async def scan_package_file(self, package_path: str | Path) -> SecurityScanResult:
        """Scan a .rpyx package file for security issues."""
        import time

        package_path = Path(package_path)
        start_time = time.time()
        issues = []
        files_scanned = 0

        if not package_path.exists():
            raise ValueError(f"Package file not found: {package_path}")

        if not package_path.suffix == ".rpyx":
            raise ValueError(f"Not a .rpyx file: {package_path}")

        try:
            with zipfile.ZipFile(package_path, "r") as zf:
                # Scan each file in the package
                for file_info in zf.infolist():
                    if file_info.is_dir():
                        continue

                    file_path = Path(file_info.filename)

                    # Only scan Python files
                    if file_path.suffix.lower() in self.file_extensions:
                        try:
                            content = zf.read(file_info.filename).decode(
                                "utf-8", errors="ignore"
                            )
                            file_issues = self._scan_python_code(
                                content, file_info.filename
                            )
                            issues.extend(file_issues)
                            files_scanned += 1
                        except Exception:
                            # Skip files that can't be decoded
                            continue

                    # Check for suspicious file types
                    elif file_path.suffix.lower() in [
                        ".exe",
                        ".dll",
                        ".bat",
                        ".cmd",
                        ".ps1",
                    ]:
                        issues.append(
                            SecurityIssue(
                                severity="high",
                                category="suspicious_files",
                                description=f"Suspicious executable file: {file_path.suffix}",
                                file_path=file_info.filename,
                            )
                        )

                # Check for package structure issues
                structure_issues = self._check_package_structure(zf)
                issues.extend(structure_issues)

            # Calculate risk level
            risk_level = self._calculate_risk_level(issues)

            scan_duration = time.time() - start_time

            return SecurityScanResult(
                package_path=str(package_path),
                risk_level=risk_level,
                issues=issues,
                scan_timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
                scan_duration=scan_duration,
                files_scanned=files_scanned,
            )

        except zipfile.BadZipFile as e:
            raise ValueError("Invalid or corrupted package file") from e

    def _scan_python_code(self, content: str, file_path: str) -> list[SecurityIssue]:
        """Scan Python code content for security issues."""
        issues = []

        # Pattern-based scanning
        for pattern, info in self.suspicious_patterns.items():
            matches = re.finditer(pattern, content, re.IGNORECASE | re.MULTILINE)

            for match in matches:
                # Find line number
                line_num = content[: match.start()].count("\n") + 1

                # Get code snippet
                lines = content.split("\n")
                line_start = max(0, line_num - 2)
                line_end = min(len(lines), line_num + 1)
                snippet = "\n".join(lines[line_start:line_end])

                issues.append(
                    SecurityIssue(
                        severity=info["severity"],
                        category=info["category"],
                        description=info["description"],
                        file_path=file_path,
                        line_number=line_num,
                        code_snippet=snippet,
                    )
                )

        # AST-based analysis for imports
        try:
            tree = ast.parse(content)
            import_issues = self._analyze_imports(tree, file_path)
            issues.extend(import_issues)
        except SyntaxError:
            # Skip files with syntax errors
            pass

        return issues

    def _analyze_imports(self, tree: ast.AST, file_path: str) -> list[SecurityIssue]:
        """Analyze imports using AST for more accurate detection."""
        issues = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in self.dangerous_imports:
                        info = self.dangerous_imports[alias.name]
                        issues.append(
                            SecurityIssue(
                                severity=info["severity"],
                                category="dangerous_import",
                                description=f"Imports {alias.name}: {info['description']}",
                                file_path=file_path,
                                line_number=node.lineno,
                            )
                        )

            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module in self.dangerous_imports:
                    info = self.dangerous_imports[node.module]
                    issues.append(
                        SecurityIssue(
                            severity=info["severity"],
                            category="dangerous_import",
                            description=f"Imports from {node.module}: {info['description']}",
                            file_path=file_path,
                            line_number=node.lineno,
                        )
                    )

        return issues

    def _check_package_structure(self, zf: zipfile.ZipFile) -> list[SecurityIssue]:
        """Check for suspicious package structure."""
        issues = []
        file_list = zf.namelist()

        # Check for manifest file
        if "rpyx-manifest.json" not in file_list:
            issues.append(
                SecurityIssue(
                    severity="medium",
                    category="package_structure",
                    description="Missing package manifest",
                    file_path="package_root",
                )
            )

        # Check for hidden files
        hidden_files = [
            f for f in file_list if any(part.startswith(".") for part in f.split("/"))
        ]
        if hidden_files:
            issues.append(
                SecurityIssue(
                    severity="low",
                    category="package_structure",
                    description=f'Hidden files detected: {", ".join(hidden_files[:5])}',
                    file_path="package_root",
                )
            )

        # Check for unusual extensions
        unusual_extensions = []
        for filename in file_list:
            ext = Path(filename).suffix.lower()
            if ext in [".exe", ".dll", ".so", ".dylib", ".bin"]:
                unusual_extensions.append(filename)

        if unusual_extensions:
            issues.append(
                SecurityIssue(
                    severity="high",
                    category="suspicious_files",
                    description=f'Binary files detected: {", ".join(unusual_extensions[:5])}',
                    file_path="package_root",
                )
            )

        return issues

    def _calculate_risk_level(self, issues: list[SecurityIssue]) -> str:
        """Calculate overall risk level based on issues found."""
        if not issues:
            return "low"

        severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}

        for issue in issues:
            severity_counts[issue.severity] += 1

        # Risk calculation logic
        if severity_counts["critical"] > 0:
            return "critical"
        elif severity_counts["high"] > 2:
            return "critical"
        elif severity_counts["high"] > 0:
            return "high"
        elif severity_counts["medium"] > 3:
            return "high"
        elif severity_counts["medium"] > 0:
            return "medium"
        else:
            return "low"
