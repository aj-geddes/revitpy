"""
Test runner script for the RevitPy-PyRevit bridge test suite.

This script provides a comprehensive test runner with various execution modes
and reporting capabilities.
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

# Add bridge module to path
bridge_path = Path(__file__).parent.parent
sys.path.insert(0, str(bridge_path))

from . import TEST_CONFIG


def run_pytest_command(test_args, verbose=True, coverage=False):
    """Run pytest with specified arguments."""
    cmd = ["python", "-m", "pytest"]

    if verbose:
        cmd.extend(["-v", "-s"])

    if coverage:
        cmd.extend(["--cov=..", "--cov-report=html", "--cov-report=term"])

    cmd.extend(test_args)

    print(f"Running command: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=Path(__file__).parent)
    return result.returncode == 0


def run_unit_tests(verbose=True, coverage=False):
    """Run unit tests for core components."""
    print("=" * 60)
    print("RUNNING UNIT TESTS")
    print("=" * 60)

    test_files = [
        "test_core_bridge.py",
        "test_serialization.py",
        "test_communication.py",
        "test_pyrevit_integration.py",
    ]

    return run_pytest_command(test_files, verbose, coverage)


def run_integration_tests(verbose=True, coverage=False):
    """Run integration tests for workflows."""
    print("=" * 60)
    print("RUNNING INTEGRATION TESTS")
    print("=" * 60)

    test_files = ["test_workflows.py"]

    return run_pytest_command(test_files, verbose, coverage)


def run_performance_tests(verbose=True, coverage=False):
    """Run performance and stress tests."""
    print("=" * 60)
    print("RUNNING PERFORMANCE TESTS")
    print("=" * 60)

    test_files = ["test_performance.py"]

    return run_pytest_command(test_files, verbose, coverage)


def run_all_tests(verbose=True, coverage=False):
    """Run all tests in the suite."""
    print("=" * 60)
    print("RUNNING ALL TESTS")
    print("=" * 60)

    return run_pytest_command(["."], verbose, coverage)


def run_specific_test(test_path, verbose=True, coverage=False):
    """Run a specific test file or test method."""
    print("=" * 60)
    print(f"RUNNING SPECIFIC TEST: {test_path}")
    print("=" * 60)

    return run_pytest_command([test_path], verbose, coverage)


def generate_test_report():
    """Generate a comprehensive test report."""
    print("=" * 60)
    print("GENERATING TEST REPORT")
    print("=" * 60)

    # Run tests with JSON output for report generation
    cmd = [
        "python",
        "-m",
        "pytest",
        "--json-report",
        "--json-report-file=test_report.json",
        "--cov=..",
        "--cov-report=json",
        ".",
    ]

    result = subprocess.run(cmd, cwd=Path(__file__).parent)

    if result.returncode == 0:
        print("Test report generated successfully!")
        print("Files created:")
        print("  - test_report.json (pytest results)")
        print("  - coverage.json (coverage report)")
        print("  - htmlcov/ (HTML coverage report)")
    else:
        print("Test report generation failed.")

    return result.returncode == 0


def run_quick_smoke_tests():
    """Run a quick smoke test suite for basic functionality."""
    print("=" * 60)
    print("RUNNING QUICK SMOKE TESTS")
    print("=" * 60)

    # Run key tests that validate basic functionality
    smoke_tests = [
        "test_core_bridge.py::TestBridgeConfig::test_default_config_creation",
        "test_serialization.py::TestElementSerializer::test_single_element_serialization",
        "test_communication.py::TestNamedPipeServer::test_server_initialization",
        "test_pyrevit_integration.py::TestRevitPyBridge::test_bridge_initialization",
        "test_workflows.py::TestBuildingPerformanceWorkflow::test_workflow_initialization",
    ]

    return run_pytest_command(smoke_tests, verbose=True, coverage=False)


def validate_test_environment():
    """Validate that the test environment is properly set up."""
    print("Validating test environment...")

    # Check Python version

    # Check required modules
    required_modules = ["pytest", "asyncio", "unittest.mock"]
    missing_modules = []

    for module in required_modules:
        try:
            __import__(module)
        except ImportError:
            missing_modules.append(module)

    if missing_modules:
        print(f"ERROR: Missing required modules: {', '.join(missing_modules)}")
        print(
            "Install with: pip install pytest pytest-asyncio pytest-cov pytest-json-report"
        )
        return False

    # Check test directories exist
    test_data_dir = TEST_CONFIG["test_data_dir"]
    temp_dir = TEST_CONFIG["temp_dir"]

    if not test_data_dir.exists():
        print(f"Creating test data directory: {test_data_dir}")
        test_data_dir.mkdir(parents=True, exist_ok=True)

    if not temp_dir.exists():
        print(f"Creating temp directory: {temp_dir}")
        temp_dir.mkdir(parents=True, exist_ok=True)

    print("Test environment validation passed!")
    return True


def cleanup_test_artifacts():
    """Clean up test artifacts and temporary files."""
    print("Cleaning up test artifacts...")

    cleanup_patterns = [
        "**/*.pyc",
        "**/__pycache__",
        "test_report.json",
        "coverage.json",
        "htmlcov",
        ".coverage",
        ".pytest_cache",
    ]

    cleaned_count = 0
    for pattern in cleanup_patterns:
        for path in Path(__file__).parent.rglob(pattern):
            try:
                if path.is_file():
                    path.unlink()
                    cleaned_count += 1
                elif path.is_dir():
                    import shutil

                    shutil.rmtree(path)
                    cleaned_count += 1
            except Exception as e:
                print(f"Warning: Could not clean {path}: {e}")

    # Clean temp directories
    temp_dir = TEST_CONFIG["temp_dir"]
    if temp_dir.exists():
        import shutil

        shutil.rmtree(temp_dir)
        temp_dir.mkdir()

    print(f"Cleaned up {cleaned_count} test artifacts.")


def main():
    """Main test runner function."""
    parser = argparse.ArgumentParser(description="RevitPy Bridge Test Runner")
    parser.add_argument(
        "mode",
        choices=[
            "unit",
            "integration",
            "performance",
            "all",
            "smoke",
            "report",
            "specific",
        ],
        help="Test execution mode",
    )
    parser.add_argument("--test", "-t", help="Specific test to run (for specific mode)")
    parser.add_argument("--quiet", "-q", action="store_true", help="Run in quiet mode")
    parser.add_argument(
        "--coverage", "-c", action="store_true", help="Generate coverage report"
    )
    parser.add_argument(
        "--cleanup", action="store_true", help="Clean up test artifacts before running"
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate test environment before running",
    )

    args = parser.parse_args()

    # Validate environment if requested
    if args.validate or args.mode in ["all", "report"]:
        if not validate_test_environment():
            sys.exit(1)

    # Cleanup if requested
    if args.cleanup:
        cleanup_test_artifacts()

    verbose = not args.quiet
    start_time = time.time()

    try:
        # Execute based on mode
        if args.mode == "unit":
            success = run_unit_tests(verbose, args.coverage)
        elif args.mode == "integration":
            success = run_integration_tests(verbose, args.coverage)
        elif args.mode == "performance":
            success = run_performance_tests(verbose, args.coverage)
        elif args.mode == "all":
            success = run_all_tests(verbose, args.coverage)
        elif args.mode == "smoke":
            success = run_quick_smoke_tests()
        elif args.mode == "report":
            success = generate_test_report()
        elif args.mode == "specific":
            if not args.test:
                print("ERROR: --test argument required for specific mode")
                sys.exit(1)
            success = run_specific_test(args.test, verbose, args.coverage)
        else:
            print(f"Unknown mode: {args.mode}")
            sys.exit(1)

        # Report results
        end_time = time.time()
        duration = end_time - start_time

        print("=" * 60)
        if success:
            print(f"✅ Tests PASSED in {duration:.2f} seconds")
        else:
            print(f"❌ Tests FAILED in {duration:.2f} seconds")
        print("=" * 60)

        sys.exit(0 if success else 1)

    except KeyboardInterrupt:
        print("\nTest execution interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"Test execution failed with error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
