"""Security scanning and vulnerability assessment system."""

import ast
import hashlib
import json
import os
import re
import subprocess
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import httpx


class SecurityFinding:
    """Represents a security finding from a scan."""
    
    def __init__(
        self,
        severity: str,
        finding_type: str,
        title: str,
        description: str,
        file_path: Optional[str] = None,
        line_number: Optional[int] = None,
        cve_id: Optional[str] = None,
        recommendation: Optional[str] = None
    ):
        self.severity = severity  # critical, high, medium, low, info
        self.finding_type = finding_type  # vulnerability, malware, policy_violation, etc.
        self.title = title
        self.description = description
        self.file_path = file_path
        self.line_number = line_number
        self.cve_id = cve_id
        self.recommendation = recommendation
        self.found_at = datetime.utcnow()
    
    def to_dict(self) -> Dict:
        """Convert finding to dictionary."""
        return {
            "severity": self.severity,
            "finding_type": self.finding_type,
            "title": self.title,
            "description": self.description,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "cve_id": self.cve_id,
            "recommendation": self.recommendation,
            "found_at": self.found_at.isoformat(),
        }


class SecurityScanResult:
    """Results from a security scan."""
    
    def __init__(self, scanner_name: str, scanner_version: str):
        self.scanner_name = scanner_name
        self.scanner_version = scanner_version
        self.started_at = datetime.utcnow()
        self.completed_at: Optional[datetime] = None
        self.findings: List[SecurityFinding] = []
        self.metadata: Dict = {}
        self.error: Optional[str] = None
    
    def add_finding(self, finding: SecurityFinding):
        """Add a finding to the scan result."""
        self.findings.append(finding)
    
    def complete_scan(self, error: Optional[str] = None):
        """Mark scan as completed."""
        self.completed_at = datetime.utcnow()
        self.error = error
    
    def get_severity_counts(self) -> Dict[str, int]:
        """Get count of findings by severity."""
        counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
        for finding in self.findings:
            if finding.severity in counts:
                counts[finding.severity] += 1
        return counts
    
    @property
    def duration_seconds(self) -> Optional[int]:
        """Get scan duration in seconds."""
        if self.completed_at:
            return int((self.completed_at - self.started_at).total_seconds())
        return None
    
    @property
    def passed(self) -> bool:
        """Check if scan passed (no critical or high severity findings)."""
        severity_counts = self.get_severity_counts()
        return severity_counts["critical"] == 0 and severity_counts["high"] == 0
    
    def to_dict(self) -> Dict:
        """Convert scan result to dictionary."""
        return {
            "scanner_name": self.scanner_name,
            "scanner_version": self.scanner_version,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": self.duration_seconds,
            "passed": self.passed,
            "findings_count": len(self.findings),
            "severity_counts": self.get_severity_counts(),
            "findings": [f.to_dict() for f in self.findings],
            "metadata": self.metadata,
            "error": self.error,
        }


class BaseSecurityScanner:
    """Base class for security scanners."""
    
    def __init__(self, name: str, version: str = "1.0.0"):
        self.name = name
        self.version = version
    
    async def scan_package(self, package_path: Path) -> SecurityScanResult:
        """Scan a package for security issues."""
        result = SecurityScanResult(self.name, self.version)
        
        try:
            await self._perform_scan(package_path, result)
            result.complete_scan()
        except Exception as e:
            result.complete_scan(error=str(e))
        
        return result
    
    async def _perform_scan(self, package_path: Path, result: SecurityScanResult):
        """Perform the actual scan (to be implemented by subclasses)."""
        raise NotImplementedError


class StaticCodeScanner(BaseSecurityScanner):
    """Scanner for static code analysis security issues."""
    
    # Dangerous function patterns
    DANGEROUS_PATTERNS = [
        (re.compile(r'\beval\s*\('), "high", "Code Injection", "Use of eval() function can lead to code injection"),
        (re.compile(r'\bexec\s*\('), "high", "Code Injection", "Use of exec() function can lead to code injection"),
        (re.compile(r'\b__import__\s*\('), "medium", "Dynamic Import", "Dynamic imports can be dangerous"),
        (re.compile(r'\bsubprocess\.call\([^)]*shell\s*=\s*True'), "high", "Shell Injection", "subprocess with shell=True is vulnerable"),
        (re.compile(r'\bos\.system\s*\('), "high", "Command Injection", "os.system() calls are vulnerable to injection"),
        (re.compile(r'\bpickle\.loads?\s*\('), "high", "Deserialization", "Pickle deserialization can execute arbitrary code"),
        (re.compile(r'\binput\s*\('), "low", "Input Function", "input() can be dangerous in some contexts"),
        (re.compile(r'password\s*=\s*["\'][^"\']+["\']', re.IGNORECASE), "critical", "Hardcoded Password", "Hardcoded password found"),
        (re.compile(r'api[_-]?key\s*=\s*["\'][^"\']+["\']', re.IGNORECASE), "critical", "API Key Exposure", "Hardcoded API key found"),
        (re.compile(r'secret\s*=\s*["\'][^"\']+["\']', re.IGNORECASE), "critical", "Secret Exposure", "Hardcoded secret found"),
    ]
    
    def __init__(self):
        super().__init__("StaticCodeScanner", "1.0.0")
    
    async def _perform_scan(self, package_path: Path, result: SecurityScanResult):
        """Perform static code analysis."""
        # Handle both directories and archives
        if package_path.is_file():
            await self._scan_archive(package_path, result)
        else:
            await self._scan_directory(package_path, result)
    
    async def _scan_directory(self, directory: Path, result: SecurityScanResult):
        """Scan Python files in a directory."""
        python_files = list(directory.rglob("*.py"))
        
        for py_file in python_files:
            try:
                await self._scan_python_file(py_file, result)
            except Exception as e:
                result.add_finding(SecurityFinding(
                    "medium", "scan_error", "File Scan Error",
                    f"Failed to scan file: {e}",
                    file_path=str(py_file)
                ))
    
    async def _scan_archive(self, archive_path: Path, result: SecurityScanResult):
        """Scan Python files in an archive."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Extract archive
            if archive_path.suffix.lower() == '.zip':
                with zipfile.ZipFile(archive_path, 'r') as zf:
                    zf.extractall(temp_path)
            elif archive_path.name.endswith('.tar.gz'):
                import tarfile
                with tarfile.open(archive_path, 'r:gz') as tf:
                    tf.extractall(temp_path)
            else:
                result.add_finding(SecurityFinding(
                    "low", "unsupported_format", "Unsupported Archive Format",
                    f"Cannot scan archive format: {archive_path.suffix}"
                ))
                return
            
            await self._scan_directory(temp_path, result)
    
    async def _scan_python_file(self, file_path: Path, result: SecurityScanResult):
        """Scan a single Python file for security issues."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception as e:
            result.add_finding(SecurityFinding(
                "low", "read_error", "File Read Error",
                f"Cannot read file: {e}",
                file_path=str(file_path)
            ))
            return
        
        # Check for syntax errors
        try:
            ast.parse(content)
        except SyntaxError as e:
            result.add_finding(SecurityFinding(
                "medium", "syntax_error", "Python Syntax Error",
                f"Syntax error in Python file: {e}",
                file_path=str(file_path),
                line_number=e.lineno
            ))
            return
        
        # Check for dangerous patterns
        lines = content.splitlines()
        for line_num, line in enumerate(lines, 1):
            for pattern, severity, title, description in self.DANGEROUS_PATTERNS:
                if pattern.search(line):
                    result.add_finding(SecurityFinding(
                        severity, "code_pattern", title, description,
                        file_path=str(file_path),
                        line_number=line_num,
                        recommendation="Review and validate the security implications of this code"
                    ))


class DependencyScanner(BaseSecurityScanner):
    """Scanner for dependency vulnerabilities."""
    
    def __init__(self):
        super().__init__("DependencyScanner", "1.0.0")
        self.vulnerability_db_url = "https://api.osv.dev/v1"
    
    async def _perform_scan(self, package_path: Path, result: SecurityScanResult):
        """Scan package dependencies for vulnerabilities."""
        dependencies = await self._extract_dependencies(package_path)
        
        if not dependencies:
            result.metadata["dependencies_found"] = 0
            return
        
        result.metadata["dependencies_found"] = len(dependencies)
        
        # Check each dependency for vulnerabilities
        async with httpx.AsyncClient() as client:
            for dep_name, dep_version in dependencies.items():
                await self._check_dependency_vulnerability(
                    client, dep_name, dep_version, result
                )
    
    async def _extract_dependencies(self, package_path: Path) -> Dict[str, str]:
        """Extract dependencies from package metadata."""
        dependencies = {}
        
        # Look for pyproject.toml
        pyproject_files = []
        if package_path.is_file():
            # Extract from archive and find pyproject.toml
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                if package_path.suffix.lower() == '.zip':
                    with zipfile.ZipFile(package_path, 'r') as zf:
                        zf.extractall(temp_path)
                elif package_path.name.endswith('.tar.gz'):
                    import tarfile
                    with tarfile.open(package_path, 'r:gz') as tf:
                        tf.extractall(temp_path)
                
                pyproject_files = list(temp_path.rglob("pyproject.toml"))
        else:
            pyproject_files = list(package_path.rglob("pyproject.toml"))
        
        # Parse pyproject.toml files
        for pyproject_file in pyproject_files:
            try:
                import toml
                with open(pyproject_file, 'r') as f:
                    config = toml.load(f)
                
                project_deps = config.get('project', {}).get('dependencies', [])
                for dep in project_deps:
                    # Simple parsing - extract package name
                    dep_name = re.split(r'[<>=!~\s]', dep)[0].strip()
                    if dep_name:
                        dependencies[dep_name] = "unknown"  # Version not easily parsed
                
                # Also check build dependencies
                build_deps = config.get('build-system', {}).get('requires', [])
                for dep in build_deps:
                    dep_name = re.split(r'[<>=!~\s]', dep)[0].strip()
                    if dep_name:
                        dependencies[dep_name] = "unknown"
                        
            except Exception:
                continue  # Skip invalid toml files
        
        return dependencies
    
    async def _check_dependency_vulnerability(
        self,
        client: httpx.AsyncClient,
        package_name: str,
        version: str,
        result: SecurityScanResult
    ):
        """Check a specific dependency for vulnerabilities using OSV database."""
        try:
            # Query OSV API
            query = {
                "package": {
                    "ecosystem": "PyPI",
                    "name": package_name
                }
            }
            
            if version != "unknown":
                query["version"] = version
            
            response = await client.post(
                f"{self.vulnerability_db_url}/query",
                json=query,
                timeout=10.0
            )
            
            if response.status_code == 200:
                data = response.json()
                vulnerabilities = data.get("vulns", [])
                
                for vuln in vulnerabilities:
                    severity = self._map_severity(vuln.get("database_specific", {}).get("severity", "MODERATE"))
                    
                    result.add_finding(SecurityFinding(
                        severity=severity,
                        finding_type="dependency_vulnerability",
                        title=f"Vulnerability in {package_name}",
                        description=vuln.get("summary", "No description available"),
                        cve_id=self._extract_cve_id(vuln),
                        recommendation=f"Update {package_name} to a patched version"
                    ))
                    
        except Exception as e:
            result.add_finding(SecurityFinding(
                "low", "dependency_check_error", "Dependency Check Failed",
                f"Failed to check {package_name} for vulnerabilities: {e}"
            ))
    
    def _map_severity(self, osv_severity: str) -> str:
        """Map OSV severity to our severity levels."""
        severity_map = {
            "CRITICAL": "critical",
            "HIGH": "high",
            "MODERATE": "medium",
            "LOW": "low",
        }
        return severity_map.get(osv_severity.upper(), "medium")
    
    def _extract_cve_id(self, vuln_data: Dict) -> Optional[str]:
        """Extract CVE ID from vulnerability data."""
        aliases = vuln_data.get("aliases", [])
        for alias in aliases:
            if alias.startswith("CVE-"):
                return alias
        return None


class MalwareScanner(BaseSecurityScanner):
    """Scanner for malware detection."""
    
    def __init__(self):
        super().__init__("MalwareScanner", "1.0.0")
    
    async def _perform_scan(self, package_path: Path, result: SecurityScanResult):
        """Scan package for malware indicators."""
        # Calculate file hashes
        await self._calculate_hashes(package_path, result)
        
        # Check for suspicious file types
        await self._check_suspicious_files(package_path, result)
        
        # Check for obfuscation
        await self._check_obfuscation(package_path, result)
    
    async def _calculate_hashes(self, package_path: Path, result: SecurityScanResult):
        """Calculate and store file hashes."""
        if package_path.is_file():
            with open(package_path, 'rb') as f:
                content = f.read()
                sha256_hash = hashlib.sha256(content).hexdigest()
                md5_hash = hashlib.md5(content).hexdigest()
                
                result.metadata["file_hashes"] = {
                    "sha256": sha256_hash,
                    "md5": md5_hash,
                    "size": len(content)
                }
    
    async def _check_suspicious_files(self, package_path: Path, result: SecurityScanResult):
        """Check for suspicious file types and patterns."""
        suspicious_extensions = {'.exe', '.dll', '.bat', '.cmd', '.scr', '.vbs'}
        suspicious_names = {'setup.py', 'install.py'}  # Not suspicious but worth noting
        
        files_to_check = []
        
        if package_path.is_file():
            # Extract and check archive contents
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                try:
                    if package_path.suffix.lower() == '.zip':
                        with zipfile.ZipFile(package_path, 'r') as zf:
                            files_to_check = zf.namelist()
                    elif package_path.name.endswith('.tar.gz'):
                        import tarfile
                        with tarfile.open(package_path, 'r:gz') as tf:
                            files_to_check = tf.getnames()
                except Exception:
                    pass
        else:
            files_to_check = [str(f.relative_to(package_path)) for f in package_path.rglob('*') if f.is_file()]
        
        for file_name in files_to_check:
            file_path = Path(file_name)
            
            # Check for suspicious extensions
            if file_path.suffix.lower() in suspicious_extensions:
                result.add_finding(SecurityFinding(
                    "critical", "suspicious_file", "Suspicious File Type",
                    f"Found executable file: {file_name}",
                    file_path=file_name,
                    recommendation="Review why executable files are included in the package"
                ))
            
            # Check for hidden files that might be suspicious
            if file_path.name.startswith('.') and len(file_path.name) > 10:
                result.add_finding(SecurityFinding(
                    "medium", "hidden_file", "Hidden File",
                    f"Found hidden file with suspicious name: {file_name}",
                    file_path=file_name
                ))
    
    async def _check_obfuscation(self, package_path: Path, result: SecurityScanResult):
        """Check for code obfuscation indicators."""
        python_files = []
        
        if package_path.is_file():
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                try:
                    if package_path.suffix.lower() == '.zip':
                        with zipfile.ZipFile(package_path, 'r') as zf:
                            zf.extractall(temp_path)
                    elif package_path.name.endswith('.tar.gz'):
                        import tarfile
                        with tarfile.open(package_path, 'r:gz') as tf:
                            tf.extractall(temp_path)
                    
                    python_files = list(temp_path.rglob("*.py"))
                except Exception:
                    pass
        else:
            python_files = list(package_path.rglob("*.py"))
        
        for py_file in python_files:
            try:
                with open(py_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                # Check for obfuscation indicators
                obfuscation_indicators = [
                    (len(re.findall(r'eval\s*\(', content)) > 3, "Multiple eval() calls"),
                    (len(re.findall(r'exec\s*\(', content)) > 2, "Multiple exec() calls"),
                    (len(re.findall(r'__import__\s*\(', content)) > 5, "Excessive dynamic imports"),
                    (len([line for line in content.splitlines() if len(line) > 200]) > 10, "Many very long lines"),
                    ('base64' in content.lower() and 'decode' in content.lower(), "Base64 decoding found"),
                    (content.count('\\x') > 20, "Excessive hex escapes"),
                ]
                
                for is_suspicious, description in obfuscation_indicators:
                    if is_suspicious:
                        result.add_finding(SecurityFinding(
                            "high", "obfuscation", "Code Obfuscation",
                            f"Potential obfuscation detected: {description}",
                            file_path=str(py_file),
                            recommendation="Review code for intentional obfuscation"
                        ))
                        break  # Only report once per file
                        
            except Exception:
                continue


class CompositeSecurityScanner:
    """Composite scanner that runs multiple security scanners."""
    
    def __init__(self):
        self.scanners = [
            StaticCodeScanner(),
            DependencyScanner(),
            MalwareScanner(),
        ]
    
    async def scan_package(self, package_path: Path) -> List[SecurityScanResult]:
        """Run all scanners on a package."""
        results = []
        
        for scanner in self.scanners:
            try:
                result = await scanner.scan_package(package_path)
                results.append(result)
            except Exception as e:
                # Create error result
                error_result = SecurityScanResult(scanner.name, scanner.version)
                error_result.complete_scan(error=str(e))
                results.append(error_result)
        
        return results
    
    async def get_security_score(self, package_path: Path) -> Dict:
        """Calculate overall security score for a package."""
        results = await self.scan_package(package_path)
        
        total_critical = 0
        total_high = 0
        total_medium = 0
        total_low = 0
        
        for result in results:
            counts = result.get_severity_counts()
            total_critical += counts["critical"]
            total_high += counts["high"]
            total_medium += counts["medium"]
            total_low += counts["low"]
        
        # Calculate score (0-100, where 100 is best)
        score = 100
        score -= total_critical * 25  # Critical findings are very bad
        score -= total_high * 10      # High findings are bad
        score -= total_medium * 3     # Medium findings have some impact
        score -= total_low * 1        # Low findings have minimal impact
        
        score = max(0, score)  # Don't go below 0
        
        return {
            "score": score,
            "total_findings": sum([total_critical, total_high, total_medium, total_low]),
            "severity_breakdown": {
                "critical": total_critical,
                "high": total_high,
                "medium": total_medium,
                "low": total_low,
            },
            "passed": total_critical == 0 and total_high == 0,
            "results": [r.to_dict() for r in results]
        }