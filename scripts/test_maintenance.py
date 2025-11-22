#!/usr/bin/env python3
"""Test maintenance and health monitoring script for RevitPy.

This script provides utilities for maintaining the test suite health,
including coverage analysis, performance monitoring, and test cleanup.
"""

import json
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import click
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


class TestHealthMonitor:
    """Monitor and analyze test suite health."""

    def __init__(self, root_path: Path):
        self.root_path = root_path
        self.test_db_path = root_path / ".test_health.db"
        self.setup_database()

    def setup_database(self):
        """Setup SQLite database for test metrics."""
        with sqlite3.connect(self.test_db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS test_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    test_type TEXT NOT NULL,
                    total_tests INTEGER,
                    passed_tests INTEGER,
                    failed_tests INTEGER,
                    skipped_tests INTEGER,
                    execution_time REAL,
                    coverage_percentage REAL,
                    git_commit TEXT
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS performance_benchmarks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    test_name TEXT NOT NULL,
                    metric_name TEXT NOT NULL,
                    metric_value REAL,
                    baseline_value REAL,
                    regression_threshold REAL,
                    is_regression BOOLEAN
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS flaky_tests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    test_name TEXT NOT NULL,
                    failure_count INTEGER DEFAULT 1,
                    last_failure TEXT NOT NULL,
                    failure_rate REAL,
                    UNIQUE(test_name)
                )
            """)

    def record_test_run(self, test_type: str, results: dict):
        """Record test run results."""
        git_commit = self.get_git_commit()

        with sqlite3.connect(self.test_db_path) as conn:
            conn.execute(
                """
                INSERT INTO test_runs
                (timestamp, test_type, total_tests, passed_tests, failed_tests,
                 skipped_tests, execution_time, coverage_percentage, git_commit)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    datetime.now().isoformat(),
                    test_type,
                    results.get("total", 0),
                    results.get("passed", 0),
                    results.get("failed", 0),
                    results.get("skipped", 0),
                    results.get("execution_time", 0),
                    results.get("coverage", 0),
                    git_commit,
                ),
            )

    def record_performance_benchmark(
        self, test_name: str, metric_name: str, value: float, baseline: float = None
    ):
        """Record performance benchmark result."""
        regression_threshold = 1.2  # 20% regression threshold
        is_regression = False

        if baseline and value > baseline * regression_threshold:
            is_regression = True

        with sqlite3.connect(self.test_db_path) as conn:
            conn.execute(
                """
                INSERT INTO performance_benchmarks
                (timestamp, test_name, metric_name, metric_value,
                 baseline_value, regression_threshold, is_regression)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    datetime.now().isoformat(),
                    test_name,
                    metric_name,
                    value,
                    baseline,
                    regression_threshold,
                    is_regression,
                ),
            )

    def track_flaky_test(self, test_name: str):
        """Track flaky test failures."""
        with sqlite3.connect(self.test_db_path) as conn:
            # Check if test already exists
            cursor = conn.execute(
                "SELECT failure_count FROM flaky_tests WHERE test_name = ?",
                (test_name,),
            )
            row = cursor.fetchone()

            if row:
                # Update existing record
                new_count = row[0] + 1
                conn.execute(
                    """
                    UPDATE flaky_tests
                    SET failure_count = ?, last_failure = ?
                    WHERE test_name = ?
                """,
                    (new_count, datetime.now().isoformat(), test_name),
                )
            else:
                # Insert new record
                conn.execute(
                    """
                    INSERT INTO flaky_tests (test_name, last_failure)
                    VALUES (?, ?)
                """,
                    (test_name, datetime.now().isoformat()),
                )

    def get_git_commit(self) -> str:
        """Get current git commit hash."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.root_path,
                capture_output=True,
                text=True,
            )
            return result.stdout.strip()[:8] if result.returncode == 0 else "unknown"
        except:
            return "unknown"

    def generate_health_report(self) -> dict:
        """Generate comprehensive health report."""
        with sqlite3.connect(self.test_db_path) as conn:
            # Recent test runs
            recent_runs = pd.read_sql_query(
                """
                SELECT * FROM test_runs
                WHERE timestamp > datetime('now', '-30 days')
                ORDER BY timestamp DESC
            """,
                conn,
            )

            # Performance trends
            perf_data = pd.read_sql_query(
                """
                SELECT * FROM performance_benchmarks
                WHERE timestamp > datetime('now', '-30 days')
                ORDER BY timestamp DESC
            """,
                conn,
            )

            # Flaky tests
            flaky_tests = pd.read_sql_query(
                """
                SELECT * FROM flaky_tests
                WHERE failure_count > 3
                ORDER BY failure_count DESC
            """,
                conn,
            )

            return {
                "recent_runs": recent_runs,
                "performance_data": perf_data,
                "flaky_tests": flaky_tests,
                "summary": self._calculate_summary(recent_runs, perf_data, flaky_tests),
            }

    def _calculate_summary(self, runs_df, perf_df, flaky_df) -> dict:
        """Calculate summary statistics."""
        if runs_df.empty:
            return {"status": "no_data"}

        latest_run = runs_df.iloc[0] if not runs_df.empty else None
        avg_coverage = runs_df["coverage_percentage"].mean() if not runs_df.empty else 0

        # Performance regressions
        regressions = (
            len(perf_df[perf_df["is_regression"] == True]) if not perf_df.empty else 0
        )

        return {
            "status": "healthy"
            if avg_coverage > 85 and regressions == 0
            else "warning",
            "latest_coverage": latest_run["coverage_percentage"]
            if latest_run is not None
            else 0,
            "average_coverage": avg_coverage,
            "performance_regressions": regressions,
            "flaky_test_count": len(flaky_df),
            "total_runs": len(runs_df),
        }


class TestCoverageAnalyzer:
    """Analyze and report on test coverage."""

    def __init__(self, root_path: Path):
        self.root_path = root_path
        self.coverage_data_path = root_path / "coverage.xml"

    def analyze_coverage(self) -> dict:
        """Analyze current coverage data."""
        if not self.coverage_data_path.exists():
            return {"error": "No coverage data found"}

        # Parse coverage XML
        import xml.etree.ElementTree as ET

        try:
            tree = ET.parse(self.coverage_data_path)
            root = tree.getroot()

            coverage_data = {"overall": {}, "by_package": {}, "uncovered_lines": []}

            # Extract overall coverage
            coverage = root.find(".//coverage")
            if coverage is not None:
                coverage_data["overall"] = {
                    "lines_covered": int(coverage.get("lines-covered", 0)),
                    "lines_valid": int(coverage.get("lines-valid", 0)),
                    "line_rate": float(coverage.get("line-rate", 0)),
                    "branch_rate": float(coverage.get("branch-rate", 0)),
                }

            # Extract package-level coverage
            for package in root.findall(".//package"):
                package_name = package.get("name")
                coverage_data["by_package"][package_name] = {
                    "line_rate": float(package.get("line-rate", 0)),
                    "branch_rate": float(package.get("branch-rate", 0)),
                }

            # Find uncovered lines
            for cls in root.findall(".//class"):
                filename = cls.get("filename")
                for line in cls.findall(".//line"):
                    if int(line.get("hits", 0)) == 0:
                        coverage_data["uncovered_lines"].append(
                            {
                                "file": filename,
                                "line": int(line.get("number")),
                                "branch": line.get("branch") == "true",
                            }
                        )

            return coverage_data

        except Exception as e:
            return {"error": f"Failed to parse coverage data: {e}"}

    def generate_coverage_report(self) -> str:
        """Generate human-readable coverage report."""
        data = self.analyze_coverage()

        if "error" in data:
            return f"Coverage Analysis Error: {data['error']}"

        report = []
        report.append("=" * 60)
        report.append("REVITPY TEST COVERAGE REPORT")
        report.append("=" * 60)

        # Overall coverage
        overall = data["overall"]
        report.append("\nOVERALL COVERAGE:")
        report.append(
            f"  Lines Covered: {overall['lines_covered']}/{overall['lines_valid']}"
        )
        report.append(f"  Line Coverage: {overall['line_rate']:.1%}")
        report.append(f"  Branch Coverage: {overall['branch_rate']:.1%}")

        # Coverage status
        line_rate = overall["line_rate"]
        if line_rate >= 0.90:
            status = "EXCELLENT ✅"
        elif line_rate >= 0.80:
            status = "GOOD ⚠️"
        else:
            status = "NEEDS IMPROVEMENT ❌"

        report.append(f"  Status: {status}")

        # Package breakdown
        report.append("\nPACKAGE COVERAGE:")
        for package, metrics in data["by_package"].items():
            report.append(f"  {package}: {metrics['line_rate']:.1%}")

        # Uncovered lines summary
        uncovered_count = len(data["uncovered_lines"])
        report.append(f"\nUNCOVERED LINES: {uncovered_count}")

        if uncovered_count > 0:
            # Group by file
            by_file = {}
            for line_info in data["uncovered_lines"]:
                filename = line_info["file"]
                if filename not in by_file:
                    by_file[filename] = []
                by_file[filename].append(line_info["line"])

            report.append("  Files needing attention:")
            for filename, lines in sorted(by_file.items()):
                if len(lines) > 5:  # Only show files with significant uncovered lines
                    report.append(f"    {filename}: {len(lines)} uncovered lines")

        return "\n".join(report)


class PerformanceAnalyzer:
    """Analyze performance benchmark results."""

    def __init__(self, root_path: Path):
        self.root_path = root_path
        self.benchmark_path = root_path / "benchmark-results.json"

    def analyze_benchmarks(self) -> dict:
        """Analyze benchmark results."""
        if not self.benchmark_path.exists():
            return {"error": "No benchmark data found"}

        try:
            with open(self.benchmark_path) as f:
                data = json.load(f)

            benchmarks = data.get("benchmarks", [])
            analysis = {
                "total_benchmarks": len(benchmarks),
                "performance_summary": {},
                "regressions": [],
                "improvements": [],
            }

            # Analyze each benchmark
            for bench in benchmarks:
                name = bench["name"]
                stats = bench["stats"]

                analysis["performance_summary"][name] = {
                    "mean": stats["mean"],
                    "stddev": stats["stddev"],
                    "min": stats["min"],
                    "max": stats["max"],
                    "rounds": stats["rounds"],
                }

                # Check for regressions (would need baseline data)
                # This is simplified for demo purposes
                if stats["mean"] > 0.1:  # Arbitrary threshold
                    analysis["regressions"].append(
                        {
                            "name": name,
                            "mean_time": stats["mean"],
                            "severity": "high" if stats["mean"] > 1.0 else "medium",
                        }
                    )

            return analysis

        except Exception as e:
            return {"error": f"Failed to analyze benchmarks: {e}"}

    def generate_performance_report(self) -> str:
        """Generate performance analysis report."""
        data = self.analyze_benchmarks()

        if "error" in data:
            return f"Performance Analysis Error: {data['error']}"

        report = []
        report.append("=" * 60)
        report.append("REVITPY PERFORMANCE REPORT")
        report.append("=" * 60)

        report.append(f"\nTOTAL BENCHMARKS: {data['total_benchmarks']}")

        # Performance summary
        report.append("\nPERFORMANCE SUMMARY:")
        for name, stats in data["performance_summary"].items():
            report.append(f"  {name}:")
            report.append(f"    Mean: {stats['mean']:.4f}s")
            report.append(f"    StdDev: {stats['stddev']:.4f}s")
            report.append(f"    Min/Max: {stats['min']:.4f}s / {stats['max']:.4f}s")

        # Regressions
        if data["regressions"]:
            report.append("\nPERFORMANCE CONCERNS:")
            for regression in data["regressions"]:
                report.append(
                    f"  ⚠️  {regression['name']}: {regression['mean_time']:.4f}s"
                )
        else:
            report.append("\n✅ No performance regressions detected")

        return "\n".join(report)


@click.group()
def cli():
    """RevitPy Test Suite Maintenance Tools."""
    pass


@cli.command()
@click.option("--output", "-o", help="Output file for report")
@click.option(
    "--format", "-f", type=click.Choice(["text", "html", "json"]), default="text"
)
def health_report(output, format):
    """Generate comprehensive test health report."""
    root_path = Path.cwd()
    monitor = TestHealthMonitor(root_path)

    click.echo("Generating test health report...")

    health_data = monitor.generate_health_report()
    summary = health_data["summary"]

    if format == "text":
        report = []
        report.append("=" * 60)
        report.append("REVITPY TEST HEALTH REPORT")
        report.append("=" * 60)
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"Status: {summary['status'].upper()}")
        report.append("")
        report.append(f"Latest Coverage: {summary['latest_coverage']:.1f}%")
        report.append(f"Average Coverage: {summary['average_coverage']:.1f}%")
        report.append(f"Performance Regressions: {summary['performance_regressions']}")
        report.append(f"Flaky Tests: {summary['flaky_test_count']}")
        report.append(f"Total Test Runs: {summary['total_runs']}")

        if not health_data["flaky_tests"].empty:
            report.append("")
            report.append("FLAKY TESTS:")
            for _, row in health_data["flaky_tests"].iterrows():
                report.append(
                    f"  - {row['test_name']} (failed {row['failure_count']} times)"
                )

        content = "\n".join(report)

    elif format == "json":
        content = json.dumps(
            {
                "timestamp": datetime.now().isoformat(),
                "summary": summary,
                "flaky_tests": health_data["flaky_tests"].to_dict("records")
                if not health_data["flaky_tests"].empty
                else [],
            },
            indent=2,
        )

    if output:
        Path(output).write_text(content)
        click.echo(f"Report saved to {output}")
    else:
        click.echo(content)


@cli.command()
@click.option("--threshold", default=90.0, help="Coverage threshold percentage")
def coverage_report(threshold):
    """Generate test coverage report."""
    root_path = Path.cwd()
    analyzer = TestCoverageAnalyzer(root_path)

    click.echo("Analyzing test coverage...")

    report = analyzer.generate_coverage_report()
    click.echo(report)

    # Check if coverage meets threshold
    data = analyzer.analyze_coverage()
    if "overall" in data:
        coverage_pct = data["overall"]["line_rate"] * 100
        if coverage_pct < threshold:
            click.echo(
                f"\n❌ Coverage {coverage_pct:.1f}% is below threshold {threshold}%"
            )
            sys.exit(1)
        else:
            click.echo(
                f"\n✅ Coverage {coverage_pct:.1f}% meets threshold {threshold}%"
            )


@cli.command()
def performance_report():
    """Generate performance benchmark report."""
    root_path = Path.cwd()
    analyzer = PerformanceAnalyzer(root_path)

    click.echo("Analyzing performance benchmarks...")

    report = analyzer.generate_performance_report()
    click.echo(report)


@cli.command()
@click.option("--days", default=30, help="Number of days to look back")
@click.option("--output", help="Output directory for charts")
def trend_analysis(days, output):
    """Generate trend analysis with charts."""
    root_path = Path.cwd()
    monitor = TestHealthMonitor(root_path)

    click.echo(f"Analyzing trends for the last {days} days...")

    with sqlite3.connect(monitor.test_db_path) as conn:
        # Coverage trends
        coverage_data = pd.read_sql_query(
            f"""
            SELECT timestamp, test_type, coverage_percentage, execution_time
            FROM test_runs
            WHERE timestamp > datetime('now', '-{days} days')
            ORDER BY timestamp
        """,
            conn,
        )

        if not coverage_data.empty:
            coverage_data["timestamp"] = pd.to_datetime(coverage_data["timestamp"])

            # Create coverage trend chart
            fig = make_subplots(
                rows=2,
                cols=1,
                subplot_titles=("Coverage Trend", "Execution Time Trend"),
                vertical_spacing=0.1,
            )

            fig.add_trace(
                go.Scatter(
                    x=coverage_data["timestamp"],
                    y=coverage_data["coverage_percentage"],
                    mode="lines+markers",
                    name="Coverage %",
                ),
                row=1,
                col=1,
            )

            fig.add_trace(
                go.Scatter(
                    x=coverage_data["timestamp"],
                    y=coverage_data["execution_time"],
                    mode="lines+markers",
                    name="Execution Time (s)",
                    line=dict(color="red"),
                ),
                row=2,
                col=1,
            )

            fig.update_layout(title="RevitPy Test Trends", height=600)

            if output:
                output_path = Path(output)
                output_path.mkdir(exist_ok=True)
                fig.write_html(output_path / "test_trends.html")
                click.echo(f"Trend chart saved to {output_path / 'test_trends.html'}")
            else:
                fig.show()
        else:
            click.echo("No trend data available")


@cli.command()
@click.option("--fix", is_flag=True, help="Attempt to fix detected issues")
def cleanup(fix):
    """Clean up test artifacts and detect issues."""
    root_path = Path.cwd()

    click.echo("Scanning for test artifacts and issues...")

    issues = []

    # Check for old test artifacts
    artifacts = [
        ".pytest_cache",
        "__pycache__",
        "*.pyc",
        "htmlcov",
        ".coverage",
        "test-results",
        "benchmark-results.json",
    ]

    for pattern in artifacts:
        matches = list(root_path.rglob(pattern))
        if matches:
            issues.append(f"Found {len(matches)} instances of {pattern}")
            if fix:
                for match in matches:
                    if match.is_file():
                        match.unlink()
                        click.echo(f"Deleted {match}")
                    elif match.is_dir():
                        import shutil

                        shutil.rmtree(match)
                        click.echo(f"Deleted directory {match}")

    # Check for test configuration issues
    pytest_ini = root_path / "pytest.ini"
    if not pytest_ini.exists():
        issues.append("Missing pytest.ini configuration file")

    conftest_py = root_path / "tests" / "conftest.py"
    if not conftest_py.exists():
        issues.append("Missing tests/conftest.py file")

    # Report issues
    if issues:
        click.echo("\nDetected Issues:")
        for issue in issues:
            click.echo(f"  - {issue}")

        if fix:
            click.echo("\nAttempted to fix issues where possible.")
    else:
        click.echo("✅ No issues detected")


@cli.command()
@click.argument("test_name")
def flaky_test_report(test_name):
    """Report a flaky test for tracking."""
    root_path = Path.cwd()
    monitor = TestHealthMonitor(root_path)

    monitor.track_flaky_test(test_name)
    click.echo(f"Recorded flaky test: {test_name}")


if __name__ == "__main__":
    cli()
