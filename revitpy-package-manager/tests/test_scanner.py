"""Tests for security scanning system."""

import tempfile
from datetime import datetime
from pathlib import Path

import pytest
from revitpy_package_manager.security.scanner import (
    BaseSecurityScanner,
    CompositeSecurityScanner,
    DependencyScanner,
    MalwareScanner,
    SecurityFinding,
    SecurityScanResult,
    StaticCodeScanner,
)


class TestSecurityFinding:
    """Test SecurityFinding data class."""

    def test_security_finding_creation(self):
        """Test creating a security finding."""
        finding = SecurityFinding(
            severity="high",
            finding_type="vulnerability",
            title="Test Finding",
            description="Test description",
            file_path="/path/to/file.py",
            line_number=42,
            cve_id="CVE-2023-1234",
            recommendation="Fix the issue",
        )

        assert finding.severity == "high"
        assert finding.finding_type == "vulnerability"
        assert finding.title == "Test Finding"
        assert finding.description == "Test description"
        assert finding.file_path == "/path/to/file.py"
        assert finding.line_number == 42
        assert finding.cve_id == "CVE-2023-1234"
        assert finding.recommendation == "Fix the issue"
        assert isinstance(finding.found_at, datetime)

    def test_security_finding_minimal(self):
        """Test creating a minimal security finding."""
        finding = SecurityFinding(
            severity="low",
            finding_type="info",
            title="Info Finding",
            description="Just some info",
        )

        assert finding.severity == "low"
        assert finding.file_path is None
        assert finding.line_number is None
        assert finding.cve_id is None
        assert finding.recommendation is None

    def test_security_finding_to_dict(self):
        """Test converting finding to dictionary."""
        finding = SecurityFinding(
            severity="critical",
            finding_type="code_injection",
            title="Eval Usage",
            description="Use of eval() detected",
            file_path="test.py",
            line_number=10,
        )

        result = finding.to_dict()

        assert result["severity"] == "critical"
        assert result["finding_type"] == "code_injection"
        assert result["title"] == "Eval Usage"
        assert result["description"] == "Use of eval() detected"
        assert result["file_path"] == "test.py"
        assert result["line_number"] == 10
        assert "found_at" in result
        assert isinstance(result["found_at"], str)


class TestSecurityScanResult:
    """Test SecurityScanResult class."""

    def test_scan_result_creation(self):
        """Test creating a scan result."""
        result = SecurityScanResult("TestScanner", "1.0.0")

        assert result.scanner_name == "TestScanner"
        assert result.scanner_version == "1.0.0"
        assert isinstance(result.started_at, datetime)
        assert result.completed_at is None
        assert len(result.findings) == 0
        assert result.error is None

    def test_add_finding(self):
        """Test adding findings to scan result."""
        result = SecurityScanResult("TestScanner", "1.0.0")

        finding1 = SecurityFinding("high", "vuln", "Test 1", "Description 1")
        finding2 = SecurityFinding("low", "info", "Test 2", "Description 2")

        result.add_finding(finding1)
        result.add_finding(finding2)

        assert len(result.findings) == 2
        assert result.findings[0] == finding1
        assert result.findings[1] == finding2

    def test_complete_scan(self):
        """Test completing a scan."""
        result = SecurityScanResult("TestScanner", "1.0.0")
        assert result.completed_at is None

        result.complete_scan()

        assert result.completed_at is not None
        assert result.error is None

    def test_complete_scan_with_error(self):
        """Test completing a scan with an error."""
        result = SecurityScanResult("TestScanner", "1.0.0")

        result.complete_scan(error="Something went wrong")

        assert result.completed_at is not None
        assert result.error == "Something went wrong"

    def test_get_severity_counts(self):
        """Test counting findings by severity."""
        result = SecurityScanResult("TestScanner", "1.0.0")

        result.add_finding(SecurityFinding("critical", "vuln", "C1", "desc"))
        result.add_finding(SecurityFinding("critical", "vuln", "C2", "desc"))
        result.add_finding(SecurityFinding("high", "vuln", "H1", "desc"))
        result.add_finding(SecurityFinding("medium", "vuln", "M1", "desc"))
        result.add_finding(SecurityFinding("medium", "vuln", "M2", "desc"))
        result.add_finding(SecurityFinding("medium", "vuln", "M3", "desc"))
        result.add_finding(SecurityFinding("low", "vuln", "L1", "desc"))
        result.add_finding(SecurityFinding("info", "vuln", "I1", "desc"))

        counts = result.get_severity_counts()

        assert counts["critical"] == 2
        assert counts["high"] == 1
        assert counts["medium"] == 3
        assert counts["low"] == 1
        assert counts["info"] == 1

    def test_severity_counts_empty(self):
        """Test severity counts with no findings."""
        result = SecurityScanResult("TestScanner", "1.0.0")

        counts = result.get_severity_counts()

        assert counts["critical"] == 0
        assert counts["high"] == 0
        assert counts["medium"] == 0
        assert counts["low"] == 0
        assert counts["info"] == 0

    def test_duration_seconds(self):
        """Test calculating scan duration."""
        result = SecurityScanResult("TestScanner", "1.0.0")

        # Before completion
        assert result.duration_seconds is None

        # After completion
        result.complete_scan()
        duration = result.duration_seconds

        assert duration is not None
        assert duration >= 0

    def test_passed_property_with_no_findings(self):
        """Test passed property with no findings."""
        result = SecurityScanResult("TestScanner", "1.0.0")

        assert result.passed is True

    def test_passed_property_with_safe_findings(self):
        """Test passed property with only low/medium findings."""
        result = SecurityScanResult("TestScanner", "1.0.0")

        result.add_finding(SecurityFinding("medium", "vuln", "M", "desc"))
        result.add_finding(SecurityFinding("low", "vuln", "L", "desc"))

        assert result.passed is True

    def test_passed_property_with_critical_finding(self):
        """Test passed property with critical finding."""
        result = SecurityScanResult("TestScanner", "1.0.0")

        result.add_finding(SecurityFinding("critical", "vuln", "C", "desc"))

        assert result.passed is False

    def test_passed_property_with_high_finding(self):
        """Test passed property with high finding."""
        result = SecurityScanResult("TestScanner", "1.0.0")

        result.add_finding(SecurityFinding("high", "vuln", "H", "desc"))

        assert result.passed is False

    def test_to_dict(self):
        """Test converting scan result to dictionary."""
        result = SecurityScanResult("TestScanner", "1.0.0")
        result.add_finding(SecurityFinding("high", "vuln", "Test", "Description"))
        result.metadata["test_key"] = "test_value"
        result.complete_scan()

        result_dict = result.to_dict()

        assert result_dict["scanner_name"] == "TestScanner"
        assert result_dict["scanner_version"] == "1.0.0"
        assert "started_at" in result_dict
        assert "completed_at" in result_dict
        assert result_dict["duration_seconds"] is not None
        assert result_dict["passed"] is False
        assert result_dict["findings_count"] == 1
        assert "severity_counts" in result_dict
        assert len(result_dict["findings"]) == 1
        assert result_dict["metadata"]["test_key"] == "test_value"
        assert result_dict["error"] is None


class TestBaseSecurityScanner:
    """Test BaseSecurityScanner abstract class."""

    @pytest.mark.asyncio
    async def test_base_scanner_initialization(self):
        """Test initializing base scanner."""
        scanner = BaseSecurityScanner("TestScanner", "2.0.0")

        assert scanner.name == "TestScanner"
        assert scanner.version == "2.0.0"

    @pytest.mark.asyncio
    async def test_base_scanner_default_version(self):
        """Test base scanner with default version."""
        scanner = BaseSecurityScanner("TestScanner")

        assert scanner.version == "1.0.0"

    @pytest.mark.asyncio
    async def test_scan_package_not_implemented(self):
        """Test that _perform_scan must be implemented by subclass."""
        scanner = BaseSecurityScanner("TestScanner")

        with pytest.raises(NotImplementedError):
            await scanner.scan_package(Path("/tmp/test"))

    @pytest.mark.asyncio
    async def test_scan_package_error_handling(self):
        """Test that scan_package handles errors gracefully."""

        class FailingScanner(BaseSecurityScanner):
            async def _perform_scan(self, package_path, result):
                raise ValueError("Test error")

        scanner = FailingScanner("FailingScanner")
        result = await scanner.scan_package(Path("/tmp/test"))

        assert result.completed_at is not None
        assert result.error == "Test error"


class TestStaticCodeScanner:
    """Test StaticCodeScanner for code pattern detection."""

    @pytest.mark.asyncio
    async def test_scanner_initialization(self):
        """Test initializing static code scanner."""
        scanner = StaticCodeScanner()

        assert scanner.name == "StaticCodeScanner"
        assert scanner.version == "1.0.0"

    @pytest.mark.asyncio
    async def test_detect_eval_usage(self):
        """Test detecting eval() usage."""
        scanner = StaticCodeScanner()

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            test_file = temp_path / "test.py"
            test_file.write_text("result = eval(user_input)")

            result = await scanner.scan_package(temp_path)

            assert len(result.findings) > 0
            assert any("eval" in f.title for f in result.findings)
            assert any(f.severity == "high" for f in result.findings)

    @pytest.mark.asyncio
    async def test_detect_exec_usage(self):
        """Test detecting exec() usage."""
        scanner = StaticCodeScanner()

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            test_file = temp_path / "test.py"
            test_file.write_text("exec(code_string)")

            result = await scanner.scan_package(temp_path)

            assert len(result.findings) > 0
            assert any("exec" in f.title.lower() for f in result.findings)

    @pytest.mark.asyncio
    async def test_detect_subprocess_shell_injection(self):
        """Test detecting subprocess with shell=True."""
        scanner = StaticCodeScanner()

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            test_file = temp_path / "test.py"
            test_file.write_text('subprocess.call("ls", shell=True)')

            result = await scanner.scan_package(temp_path)

            assert len(result.findings) > 0
            assert any("Shell" in f.title for f in result.findings)

    @pytest.mark.asyncio
    async def test_detect_os_system(self):
        """Test detecting os.system() usage."""
        scanner = StaticCodeScanner()

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            test_file = temp_path / "test.py"
            test_file.write_text("os.system('ls -la')")

            result = await scanner.scan_package(temp_path)

            assert len(result.findings) > 0
            assert any("Command" in f.title for f in result.findings)

    @pytest.mark.asyncio
    async def test_detect_hardcoded_password(self):
        """Test detecting hardcoded passwords."""
        scanner = StaticCodeScanner()

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            test_file = temp_path / "test.py"
            test_file.write_text('password = "secret123"')

            result = await scanner.scan_package(temp_path)

            assert len(result.findings) > 0
            assert any("Password" in f.title for f in result.findings)
            assert any(f.severity == "critical" for f in result.findings)

    @pytest.mark.asyncio
    async def test_detect_api_key(self):
        """Test detecting hardcoded API keys."""
        scanner = StaticCodeScanner()

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            test_file = temp_path / "test.py"
            test_file.write_text('api_key = "sk-1234567890"')

            result = await scanner.scan_package(temp_path)

            assert len(result.findings) > 0
            assert any("API Key" in f.title for f in result.findings)

    @pytest.mark.asyncio
    async def test_detect_pickle_usage(self):
        """Test detecting pickle.loads() usage."""
        scanner = StaticCodeScanner()

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            test_file = temp_path / "test.py"
            test_file.write_text("data = pickle.loads(untrusted_data)")

            result = await scanner.scan_package(temp_path)

            assert len(result.findings) > 0
            assert any("Deserialization" in f.title for f in result.findings)

    @pytest.mark.asyncio
    async def test_scan_clean_code(self):
        """Test scanning clean code with no issues."""
        scanner = StaticCodeScanner()

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            test_file = temp_path / "test.py"
            test_file.write_text(
                """
def hello_world():
    print("Hello, world!")
    return 42
"""
            )

            result = await scanner.scan_package(temp_path)

            assert result.completed_at is not None
            assert result.error is None
            # Should have no findings
            assert len(result.findings) == 0

    @pytest.mark.asyncio
    async def test_scan_syntax_error(self):
        """Test scanning file with syntax error."""
        scanner = StaticCodeScanner()

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            test_file = temp_path / "test.py"
            test_file.write_text("def broken(\n    syntax error here")

            result = await scanner.scan_package(temp_path)

            assert len(result.findings) > 0
            assert any("Syntax Error" in f.title for f in result.findings)

    @pytest.mark.asyncio
    async def test_line_number_tracking(self):
        """Test that line numbers are tracked correctly."""
        scanner = StaticCodeScanner()

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            test_file = temp_path / "test.py"
            test_file.write_text(
                """# Line 1
# Line 2
# Line 3
result = eval(user_input)  # Line 4
"""
            )

            result = await scanner.scan_package(temp_path)

            assert len(result.findings) > 0
            eval_finding = next(f for f in result.findings if "eval" in f.title.lower())
            assert eval_finding.line_number == 4


class TestDependencyScanner:
    """Test DependencyScanner for vulnerability detection."""

    @pytest.mark.asyncio
    async def test_scanner_initialization(self):
        """Test initializing dependency scanner."""
        scanner = DependencyScanner()

        assert scanner.name == "DependencyScanner"
        assert scanner.version == "1.0.0"
        assert "osv.dev" in scanner.vulnerability_db_url

    @pytest.mark.asyncio
    async def test_extract_dependencies_no_pyproject(self):
        """Test extracting dependencies when no pyproject.toml exists."""
        scanner = DependencyScanner()

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            dependencies = await scanner._extract_dependencies(temp_path)

            assert dependencies == {}

    @pytest.mark.asyncio
    async def test_extract_dependencies_from_pyproject(self):
        """Test extracting dependencies from pyproject.toml."""
        scanner = DependencyScanner()

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            pyproject = temp_path / "pyproject.toml"
            pyproject.write_text(
                """
[project]
dependencies = [
    "fastapi>=0.100.0",
    "sqlalchemy",
    "httpx~=0.24.0",
]
"""
            )

            dependencies = await scanner._extract_dependencies(temp_path)

            assert "fastapi" in dependencies
            assert "sqlalchemy" in dependencies
            assert "httpx" in dependencies

    @pytest.mark.asyncio
    async def test_map_severity_levels(self):
        """Test mapping OSV severity to internal severity."""
        scanner = DependencyScanner()

        assert scanner._map_severity("CRITICAL") == "critical"
        assert scanner._map_severity("HIGH") == "high"
        assert scanner._map_severity("MODERATE") == "medium"
        assert scanner._map_severity("LOW") == "low"
        assert scanner._map_severity("UNKNOWN") == "medium"  # Default

    @pytest.mark.asyncio
    async def test_extract_cve_id(self):
        """Test extracting CVE ID from vulnerability data."""
        scanner = DependencyScanner()

        vuln_data = {"aliases": ["CVE-2023-12345", "GHSA-xxxx-yyyy-zzzz"]}
        cve_id = scanner._extract_cve_id(vuln_data)

        assert cve_id == "CVE-2023-12345"

    @pytest.mark.asyncio
    async def test_extract_cve_id_no_cve(self):
        """Test extracting CVE ID when none exists."""
        scanner = DependencyScanner()

        vuln_data = {"aliases": ["GHSA-xxxx-yyyy-zzzz"]}
        cve_id = scanner._extract_cve_id(vuln_data)

        assert cve_id is None

    @pytest.mark.asyncio
    async def test_scan_package_no_dependencies(self):
        """Test scanning package with no dependencies."""
        scanner = DependencyScanner()

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            result = await scanner.scan_package(temp_path)

            assert result.completed_at is not None
            assert result.metadata.get("dependencies_found") == 0


class TestMalwareScanner:
    """Test MalwareScanner for malware detection."""

    @pytest.mark.asyncio
    async def test_scanner_initialization(self):
        """Test initializing malware scanner."""
        scanner = MalwareScanner()

        assert scanner.name == "MalwareScanner"
        assert scanner.version == "1.0.0"

    @pytest.mark.asyncio
    async def test_calculate_hashes(self):
        """Test calculating file hashes."""
        scanner = MalwareScanner()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("print('Hello')")
            temp_file = Path(f.name)

        try:
            result = SecurityScanResult("MalwareScanner", "1.0.0")
            await scanner._calculate_hashes(temp_file, result)

            assert "file_hashes" in result.metadata
            assert "sha256" in result.metadata["file_hashes"]
            assert "md5" in result.metadata["file_hashes"]
            assert "size" in result.metadata["file_hashes"]
        finally:
            temp_file.unlink()

    @pytest.mark.asyncio
    async def test_detect_suspicious_executable(self):
        """Test detecting suspicious executable files."""
        scanner = MalwareScanner()

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            # Create a suspicious file
            (temp_path / "malware.exe").touch()

            result = await scanner.scan_package(temp_path)

            assert len(result.findings) > 0
            assert any("Suspicious File" in f.title for f in result.findings)
            assert any(f.severity == "critical" for f in result.findings)

    @pytest.mark.asyncio
    async def test_detect_hidden_files(self):
        """Test detecting suspicious hidden files."""
        scanner = MalwareScanner()

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            # Create a suspicious hidden file
            (temp_path / ".hidden_malware_file").touch()

            result = await scanner.scan_package(temp_path)

            assert len(result.findings) > 0
            assert any("Hidden File" in f.title for f in result.findings)

    @pytest.mark.asyncio
    async def test_detect_obfuscation_multiple_eval(self):
        """Test detecting obfuscation with multiple eval calls."""
        scanner = MalwareScanner()

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            test_file = temp_path / "obfuscated.py"
            test_file.write_text(
                """
eval(code1)
eval(code2)
eval(code3)
eval(code4)
"""
            )

            result = await scanner.scan_package(temp_path)

            assert len(result.findings) > 0
            assert any("Obfuscation" in f.title for f in result.findings)

    @pytest.mark.asyncio
    async def test_detect_obfuscation_base64(self):
        """Test detecting base64 decoding obfuscation."""
        scanner = MalwareScanner()

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            test_file = temp_path / "obfuscated.py"
            test_file.write_text(
                """
import base64
data = base64.decode(encoded_data)
"""
            )

            result = await scanner.scan_package(temp_path)

            assert len(result.findings) > 0
            assert any("Obfuscation" in f.title for f in result.findings)

    @pytest.mark.asyncio
    async def test_detect_obfuscation_hex_escapes(self):
        """Test detecting excessive hex escapes."""
        scanner = MalwareScanner()

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            test_file = temp_path / "obfuscated.py"
            # Create content with many hex escapes
            hex_content = "data = '" + "\\x41" * 25 + "'"
            test_file.write_text(hex_content)

            result = await scanner.scan_package(temp_path)

            assert len(result.findings) > 0
            assert any("Obfuscation" in f.title for f in result.findings)

    @pytest.mark.asyncio
    async def test_scan_clean_package(self):
        """Test scanning clean package with no malware indicators."""
        scanner = MalwareScanner()

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            test_file = temp_path / "clean.py"
            test_file.write_text(
                """
def hello():
    return "Hello, world!"
"""
            )

            result = await scanner.scan_package(temp_path)

            # May have metadata but no findings
            assert result.completed_at is not None


class TestCompositeSecurityScanner:
    """Test CompositeSecurityScanner orchestration."""

    @pytest.mark.asyncio
    async def test_composite_scanner_initialization(self):
        """Test initializing composite scanner."""
        scanner = CompositeSecurityScanner()

        assert len(scanner.scanners) == 3
        assert any(isinstance(s, StaticCodeScanner) for s in scanner.scanners)
        assert any(isinstance(s, DependencyScanner) for s in scanner.scanners)
        assert any(isinstance(s, MalwareScanner) for s in scanner.scanners)

    @pytest.mark.asyncio
    async def test_scan_package_runs_all_scanners(self):
        """Test that scan_package runs all scanners."""
        scanner = CompositeSecurityScanner()

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            test_file = temp_path / "test.py"
            test_file.write_text("print('Hello')")

            results = await scanner.scan_package(temp_path)

            assert len(results) == 3
            assert any(r.scanner_name == "StaticCodeScanner" for r in results)
            assert any(r.scanner_name == "DependencyScanner" for r in results)
            assert any(r.scanner_name == "MalwareScanner" for r in results)

    @pytest.mark.asyncio
    async def test_get_security_score_clean_package(self):
        """Test security score for clean package."""
        scanner = CompositeSecurityScanner()

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            test_file = temp_path / "clean.py"
            test_file.write_text(
                """
def hello():
    return "Hello!"
"""
            )

            score_data = await scanner.get_security_score(temp_path)

            assert score_data["score"] == 100
            assert score_data["total_findings"] == 0
            assert score_data["passed"] is True
            assert score_data["severity_breakdown"]["critical"] == 0

    @pytest.mark.asyncio
    async def test_get_security_score_vulnerable_package(self):
        """Test security score for vulnerable package."""
        scanner = CompositeSecurityScanner()

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            test_file = temp_path / "vulnerable.py"
            test_file.write_text('password = "hardcoded123"')

            score_data = await scanner.get_security_score(temp_path)

            # Should have findings and lower score
            assert score_data["score"] < 100
            assert score_data["total_findings"] > 0
            assert score_data["passed"] is False
            assert "results" in score_data

    @pytest.mark.asyncio
    async def test_security_score_calculation(self):
        """Test security score calculation logic."""
        scanner = CompositeSecurityScanner()

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            test_file = temp_path / "test.py"

            # Create code with known severity levels
            test_file.write_text(
                """
password = "secret"  # Critical
exec(code)  # High
input("prompt")  # Low
"""
            )

            score_data = await scanner.get_security_score(temp_path)

            # Should deduct: 25 (critical) + 10 (high) + 1 (low) = 36
            # Score should be around 64 or lower
            assert score_data["score"] < 80
            assert score_data["severity_breakdown"]["critical"] >= 1
            assert score_data["severity_breakdown"]["high"] >= 1


class TestScannerIntegration:
    """Integration tests for scanner system."""

    @pytest.mark.asyncio
    async def test_full_scan_workflow(self):
        """Test complete scanning workflow."""
        scanner = CompositeSecurityScanner()

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create a package with various issues
            (temp_path / "main.py").write_text(
                """
import os
password = "admin123"
os.system(user_command)
"""
            )

            (temp_path / "pyproject.toml").write_text(
                """
[project]
dependencies = ["requests>=2.0.0"]
"""
            )

            results = await scanner.scan_package(temp_path)

            # Should have results from all scanners
            assert len(results) == 3

            # All scans should complete
            for result in results:
                assert result.completed_at is not None

    @pytest.mark.asyncio
    async def test_scanner_error_handling(self):
        """Test that scanners handle errors gracefully."""
        scanner = CompositeSecurityScanner()

        # Try to scan non-existent path
        results = await scanner.scan_package(Path("/nonexistent/path"))

        # Should still return results (possibly with errors)
        assert len(results) == 3

        # At least some scanners should complete (even if with errors)
        assert all(r.completed_at is not None for r in results)
