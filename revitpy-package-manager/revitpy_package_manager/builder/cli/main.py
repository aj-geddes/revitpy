"""CLI for building and publishing RevitPy packages."""

import hashlib
import json
import sys
import tarfile
import time
from pathlib import Path

import click
import httpx
import toml
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TransferSpeedColumn,
)

from ...__init__ import __version__
from ...config import get_revitpy_token, is_debug_mode
from ...security.signing import PackageSignatureManager
from ..validator import PackageLinter

console = Console()


@click.group()
@click.version_option(version=__version__)
def cli():
    """RevitPy Package Builder - Build, validate, and publish RevitPy packages."""
    pass


@cli.command()
@click.argument(
    "source_dir", type=click.Path(exists=True, file_okay=False, path_type=Path)
)
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(path_type=Path),
    help="Output directory for built package",
)
@click.option(
    "--format",
    "build_format",
    type=click.Choice(["sdist", "wheel", "both"]),
    default="sdist",
    help="Build format",
)
@click.option("--clean", is_flag=True, help="Clean build directory before building")
def build(source_dir: Path, output_dir: Path | None, build_format: str, clean: bool):
    """Build a package from source directory."""
    console.print(f"🔨 Building package from {source_dir}", style="blue")

    # Set default output directory
    if output_dir is None:
        output_dir = source_dir / "dist"

    output_dir.mkdir(parents=True, exist_ok=True)

    # Clean if requested
    if clean and output_dir.exists():
        import shutil

        shutil.rmtree(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        console.print("🧹 Cleaned build directory", style="yellow")

    # Read package metadata
    pyproject_path = source_dir / "pyproject.toml"
    if not pyproject_path.exists():
        console.print("❌ No pyproject.toml found in source directory", style="red")
        sys.exit(1)

    try:
        with open(pyproject_path) as f:
            config = toml.load(f)

        project = config.get("project", {})
        package_name = project.get("name")
        package_version = project.get("version")

        if not package_name or not package_version:
            console.print(
                "❌ Missing package name or version in pyproject.toml", style="red"
            )
            sys.exit(1)

        console.print(f"📦 Building {package_name} v{package_version}", style="green")

    except Exception as e:
        console.print(f"❌ Error reading pyproject.toml: {e}", style="red")
        sys.exit(1)

    # Build source distribution
    if build_format in ("sdist", "both"):
        sdist_path = _build_sdist(source_dir, output_dir, package_name, package_version)
        if sdist_path:
            console.print(
                f"✅ Built source distribution: {sdist_path.name}", style="green"
            )
        else:
            console.print("❌ Failed to build source distribution", style="red")
            sys.exit(1)

    # Build wheel (placeholder - would use proper wheel building)
    if build_format in ("wheel", "both"):
        console.print("⚠️  Wheel building not yet implemented", style="yellow")

    console.print(f"🎉 Build completed! Output in {output_dir}", style="blue")


def _build_sdist(
    source_dir: Path, output_dir: Path, package_name: str, version: str
) -> Path | None:
    """Build a source distribution (tar.gz)."""
    filename = f"{package_name}-{version}.tar.gz"
    output_path = output_dir / filename

    try:
        with tarfile.open(output_path, "w:gz") as tar:
            # Add all files except common build/cache directories
            exclude_patterns = {
                "__pycache__",
                "*.pyc",
                ".git",
                ".svn",
                ".hg",
                "build",
                "dist",
                "*.egg-info",
                ".tox",
                ".pytest_cache",
                ".mypy_cache",
                ".coverage",
                "htmlcov",
            }

            for item in source_dir.rglob("*"):
                if item.is_file():
                    # Check if file should be excluded
                    should_exclude = False
                    for pattern in exclude_patterns:
                        if (
                            pattern in str(item)
                            or item.name.startswith(".")
                            and item.name not in (".gitignore",)
                        ):
                            should_exclude = True
                            break

                    if not should_exclude:
                        arcname = item.relative_to(source_dir)
                        tar.add(item, arcname=arcname)

        return output_path

    except Exception as e:
        console.print(f"Error building sdist: {e}", style="red")
        return None


@cli.command()
@click.argument("package_path", type=click.Path(exists=True, path_type=Path))
@click.option("--strict", is_flag=True, help="Treat warnings as errors")
@click.option("--include-info", is_flag=True, help="Include informational messages")
@click.option("--output", "-o", type=click.File("w"), help="Output report to file")
def validate(package_path: Path, strict: bool, include_info: bool, output):
    """Validate a package for quality and compliance."""
    console.print(f"🔍 Validating package: {package_path}", style="blue")

    linter = PackageLinter()
    errors, success = linter.lint_package(
        package_path, strict=strict, include_info=include_info
    )

    # Generate report
    report = linter.generate_report(errors, package_path)

    # Output report
    if output:
        output.write(report)
        console.print(f"📄 Report written to {output.name}", style="blue")
    else:
        console.print(report)

    # Summary
    error_count = len([e for e in errors if e.level == "error"])
    warning_count = len([e for e in errors if e.level == "warning"])
    info_count = len([e for e in errors if e.level == "info"])

    if success:
        console.print(
            Panel(
                f"✅ Validation passed!\n"
                f"Issues found: {error_count} errors, {warning_count} warnings, "
                f"{info_count} info",
                title="Validation Result",
                style="green",
            )
        )
    else:
        console.print(
            Panel(
                f"❌ Validation failed!\n"
                f"Issues found: {error_count} errors, {warning_count} warnings, "
                f"{info_count} info",
                title="Validation Result",
                style="red",
            )
        )
        sys.exit(1)


@cli.command("generate-key")
@click.option(
    "--algorithm",
    type=click.Choice(["Ed25519", "RSA-PSS"]),
    default="Ed25519",
    help="Signing algorithm",
)
@click.option(
    "--output", "-o", type=click.Path(path_type=Path), help="Output key file path"
)
@click.option(
    "--passphrase", prompt=True, hide_input=True, help="Passphrase for private key"
)
def generate_signing_key(algorithm: str, output: Path | None, passphrase: str):
    """Generate a signing key pair for package signing."""
    console.print(f"🔑 Generating {algorithm} key pair...", style="blue")

    if output is None:
        output = Path.cwd() / "signing_key.pem"

    public_key_path = output.with_suffix(".pub")

    try:
        signer = PackageSignatureManager(algorithm)
        signer.signer.generate_key_pair_to_files(
            private_key_path=output,
            public_key_path=public_key_path,
            passphrase=passphrase if passphrase else None,
        )

        console.print(
            Panel(
                f"✅ Key pair generated successfully!\n"
                f"Private key: {output}\n"
                f"Public key: {public_key_path}\n\n"
                f"⚠️  Keep your private key secure and never share it!",
                title="Key Generation Complete",
                style="green",
            )
        )

    except Exception as e:
        console.print(f"❌ Failed to generate keys: {e}", style="red")
        sys.exit(1)


@cli.command()
@click.argument("package_path", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--key",
    "-k",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Private key file",
)
@click.option(
    "--passphrase", prompt=True, hide_input=True, help="Private key passphrase"
)
@click.option(
    "--algorithm",
    type=click.Choice(["Ed25519", "RSA-PSS"]),
    default="Ed25519",
    help="Signing algorithm",
)
def sign(package_path: Path, key: Path, passphrase: str, algorithm: str):
    """Sign a package for verification."""
    console.print(f"✍️  Signing package: {package_path.name}", style="blue")

    try:
        # Read package data
        with open(package_path, "rb") as f:
            package_data = f.read()

        # Sign package
        signature_manager = PackageSignatureManager(algorithm)
        signature_info = signature_manager.sign_package(
            package_data=package_data,
            private_key_path=key,
            passphrase=passphrase if passphrase else None,
            metadata={
                "package_file": package_path.name,
                "file_size": len(package_data),
            },
        )

        # Save signature file
        signature_path = package_path.with_suffix(package_path.suffix + ".sig")
        with open(signature_path, "w") as f:
            import json

            json.dump(signature_info, f, indent=2)

        console.print(
            Panel(
                f"✅ Package signed successfully!\n"
                f"Signature file: {signature_path.name}\n"
                f"Algorithm: {algorithm}\n"
                f"Fingerprint: {signature_info['public_key_fingerprint'][:16]}...",
                title="Package Signed",
                style="green",
            )
        )

    except Exception as e:
        console.print(f"❌ Failed to sign package: {e}", style="red")
        sys.exit(1)


@cli.command()
@click.argument("package_path", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--signature",
    "-s",
    type=click.Path(exists=True, path_type=Path),
    help="Signature file path",
)
@click.option(
    "--public-key",
    "-p",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Public key file",
)
def verify(package_path: Path, signature: Path | None, public_key: Path):
    """Verify a package signature."""
    console.print(f"🔍 Verifying package: {package_path.name}", style="blue")

    # Find signature file if not provided
    if signature is None:
        signature = package_path.with_suffix(package_path.suffix + ".sig")
        if not signature.exists():
            console.print(
                "❌ No signature file found. Use --signature to specify.", style="red"
            )
            sys.exit(1)

    try:
        # Read package data
        with open(package_path, "rb") as f:
            package_data = f.read()

        # Read signature
        with open(signature) as f:
            import json

            signature_info = json.load(f)

        # Read public key
        public_key_data = public_key.read_bytes()

        # Verify signature
        algorithm = signature_info.get("algorithm", "Ed25519")
        signature_manager = PackageSignatureManager(algorithm)

        is_valid, error_message = signature_manager.verify_package_signature(
            package_data=package_data,
            signature_info=signature_info,
            public_key=public_key_data,
        )

        if is_valid:
            console.print(
                Panel(
                    f"✅ Signature is valid!\n"
                    f"Algorithm: {algorithm}\n"
                    f"Signed at: {signature_info.get('signed_at', 'Unknown')}\n"
                    f"Fingerprint: {signature_info.get('public_key_fingerprint', '')[:16]}...",
                    title="Verification Successful",
                    style="green",
                )
            )
        else:
            console.print(
                Panel(
                    f"❌ Signature verification failed!\n" f"Error: {error_message}",
                    title="Verification Failed",
                    style="red",
                )
            )
            sys.exit(1)

    except Exception as e:
        console.print(f"❌ Failed to verify package: {e}", style="red")
        sys.exit(1)


@cli.command()
@click.argument("package_path", type=click.Path(exists=True, path_type=Path))
@click.option("--registry-url", default="http://localhost:8000", help="Registry URL")
@click.option("--token", help="Authentication token (or set REVITPY_TOKEN env var)")
@click.option(
    "--dry-run", is_flag=True, help="Show what would be uploaded without uploading"
)
@click.option("--retry-attempts", default=3, help="Number of retry attempts on failure")
@click.option("--timeout", default=300, help="Upload timeout in seconds")
def publish(
    package_path: Path,
    registry_url: str,
    token: str | None,
    dry_run: bool,
    retry_attempts: int,
    timeout: int,
):
    """Publish a package to the registry."""

    # Get authentication token
    if not token:
        token = get_revitpy_token()

    if not token and not dry_run:
        console.print(
            "❌ Authentication token required. Use --token or set CLI_REVITPY_TOKEN env var",
            style="red",
        )
        sys.exit(1)

    # Extract package metadata
    console.print(f"📦 Analyzing package: {package_path.name}", style="blue")

    try:
        metadata = _extract_package_metadata(package_path)
    except Exception as e:
        console.print(f"❌ Failed to extract package metadata: {e}", style="red")
        sys.exit(1)

    # Display package info
    console.print(
        Panel(
            f"[bold]{metadata['name']}[/bold] v{metadata['version']}\n"
            f"{metadata.get('summary', 'No summary')}\n\n"
            f"Size: {metadata['size_mb']:.2f} MB\n"
            f"SHA256: {metadata['sha256'][:16]}...",
            title="Package Information",
            style="cyan",
        )
    )

    console.print(f"Registry: {registry_url}", style="dim")

    if dry_run:
        console.print("\n🔍 Dry run mode - no actual upload will occur", style="yellow")
        console.print(f"✅ Would upload: {package_path}", style="green")
        console.print(f"✅ Package name: {metadata['name']}", style="green")
        console.print(f"✅ Version: {metadata['version']}", style="green")
        return

    # Perform upload with retry logic
    for attempt in range(1, retry_attempts + 1):
        try:
            console.print(
                f"\n📤 Uploading to registry (attempt {attempt}/{retry_attempts})...",
                style="blue",
            )

            _upload_package_to_registry(
                package_path=package_path,
                metadata=metadata,
                registry_url=registry_url,
                token=token,
                timeout=timeout,
            )

            console.print(
                f"\n✅ Successfully published {metadata['name']} v{metadata['version']}",
                style="green bold",
            )
            console.print(
                f"📍 View at: {registry_url}/packages/{metadata['name']}", style="cyan"
            )
            return

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                console.print(
                    "❌ Authentication failed. Check your token.", style="red"
                )
                sys.exit(1)
            elif e.response.status_code == 409:
                console.print(
                    f"❌ Version {metadata['version']} already exists", style="red"
                )
                sys.exit(1)
            elif e.response.status_code >= 500:
                console.print(
                    f"⚠️  Server error (attempt {attempt}/{retry_attempts}): {e.response.status_code}",
                    style="yellow",
                )
                if attempt < retry_attempts:
                    wait_time = 2**attempt  # Exponential backoff
                    console.print(f"⏳ Retrying in {wait_time} seconds...", style="dim")
                    time.sleep(wait_time)
                else:
                    console.print(
                        "❌ Upload failed after all retry attempts", style="red"
                    )
                    sys.exit(1)
            else:
                console.print(
                    f"❌ Upload failed: {e.response.status_code} - {e.response.text}",
                    style="red",
                )
                sys.exit(1)

        except httpx.TimeoutException:
            console.print(
                f"⚠️  Upload timeout (attempt {attempt}/{retry_attempts})",
                style="yellow",
            )
            if attempt < retry_attempts:
                console.print("⏳ Retrying...", style="dim")
            else:
                console.print("❌ Upload failed: timeout", style="red")
                sys.exit(1)

        except Exception as e:
            console.print(f"❌ Unexpected error: {e}", style="red")
            if is_debug_mode():
                raise
            sys.exit(1)


def _extract_package_metadata(package_path: Path) -> dict:
    """Extract metadata from package file."""

    # Calculate file hash and size
    with open(package_path, "rb") as f:
        content = f.read()
        sha256 = hashlib.sha256(content).hexdigest()
        md5 = hashlib.md5(content).hexdigest()
        size_mb = len(content) / (1024 * 1024)

    # Try to extract metadata from package
    # Assume it's a tar.gz with package.toml or pyproject.toml
    metadata = {
        "sha256": sha256,
        "md5": md5,
        "size_mb": size_mb,
        "filename": package_path.name,
    }

    found_metadata = False
    had_extraction_error = False
    try:
        with tarfile.open(package_path, "r:*") as tar:
            # Look for package.toml or pyproject.toml
            for member in tar.getmembers():
                if member.name.endswith("package.toml") or member.name.endswith(
                    "pyproject.toml"
                ):
                    f = tar.extractfile(member)
                    if f:
                        config = toml.loads(f.read().decode("utf-8"))

                        # Extract relevant fields
                        if "project" in config:
                            metadata.update(
                                {
                                    "name": config["project"].get("name", "unknown"),
                                    "version": config["project"].get(
                                        "version", "0.0.0"
                                    ),
                                    "summary": config["project"].get("description", ""),
                                    "author": ", ".join(
                                        [
                                            a.get("name", "")
                                            for a in config["project"].get(
                                                "authors", []
                                            )
                                        ]
                                    ),
                                    "author_email": ", ".join(
                                        [
                                            a.get("email", "")
                                            for a in config["project"].get(
                                                "authors", []
                                            )
                                        ]
                                    ),
                                    "license": config["project"]
                                    .get("license", {})
                                    .get("text", "Unknown"),
                                    "python_version": config["project"].get(
                                        "requires-python", ">=3.11"
                                    ),
                                    "dependencies": config["project"].get(
                                        "dependencies", []
                                    ),
                                }
                            )
                            found_metadata = True
                        elif "package" in config:
                            metadata.update(config["package"])
                            found_metadata = True

                        break
    except Exception as e:
        # If extraction fails due to corruption/invalid file, mark it
        had_extraction_error = True
        console.print(
            f"⚠️  Could not extract metadata from package: {e}", style="yellow"
        )

    # If no metadata found in TOML, try to parse filename
    if not found_metadata:
        if had_extraction_error:
            # Package file is corrupted/invalid - reject it
            raise ValueError(
                "Package file is corrupted or invalid - cannot extract metadata"
            )

        if "name" not in metadata:
            console.print(
                "ℹ️  No metadata file found, inferring from filename...", style="dim"
            )

        # Try to parse filename (e.g., package-name-1.0.0.tar.gz)
        # Remove all known archive extensions first
        stem = package_path.name
        for ext in [".tar.gz", ".tar.bz2", ".tar.xz", ".tar", ".tgz"]:
            if stem.endswith(ext):
                stem = stem[: -len(ext)]
                break

        name_parts = stem.rsplit("-", 1)
        if len(name_parts) == 2:
            metadata["name"] = name_parts[0]
            metadata["version"] = name_parts[1]
        else:
            metadata["name"] = stem
            metadata["version"] = "0.0.0"

    # Validate that we have meaningful package information
    if "name" not in metadata or not metadata["name"]:
        raise ValueError("Could not determine package name")
    if "version" not in metadata or not metadata["version"]:
        raise ValueError("Could not determine package version")

    # Validate package name is reasonable (not corrupted data patterns)
    name = metadata["name"]
    if len(name) < 2:
        raise ValueError(f"Invalid package name: '{name}' - too short")
    if name.endswith(".tar") or "\\x" in name or name.startswith("."):
        raise ValueError(
            f"Invalid package name: '{name}' - appears to be corrupted or malformed"
        )
    # Check for non-printable characters
    if not all(c.isprintable() or c in ["-", "_", "."] for c in name):
        raise ValueError(
            f"Invalid package name: '{name}' - contains invalid characters"
        )

    return metadata


def _upload_package_to_registry(
    package_path: Path, metadata: dict, registry_url: str, token: str, timeout: int
):
    """Upload package to registry with progress tracking."""

    # Prepare headers
    headers = {"Authorization": f"Bearer {token}"}

    # Prepare multipart form data
    with open(package_path, "rb") as f:
        file_content = f.read()

    # Prepare metadata for upload
    upload_metadata = {
        "version": metadata["version"],
        "summary": metadata.get("summary", ""),
        "description": metadata.get("description", ""),
        "author": metadata.get("author", ""),
        "author_email": metadata.get("author_email", ""),
        "license": metadata.get("license", "Unknown"),
        "python_version": metadata.get("python_version", ">=3.11"),
        "supported_revit_versions": metadata.get(
            "supported_revit_versions", ["2021", "2022", "2023", "2024", "2025"]
        ),
        "dependencies": [],
        "is_prerelease": False,
        "metadata": {},
    }

    # Upload with progress bar
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(
            f"Uploading {metadata['name']}...", total=len(file_content)
        )

        # Create multipart form
        files = {"file": (metadata["filename"], file_content, "application/gzip")}

        # Add metadata as form fields
        data = {"metadata": json.dumps(upload_metadata)}

        # Upload to registry
        with httpx.Client(timeout=timeout) as client:
            response = client.post(
                f"{registry_url}/api/v1/packages/{metadata['name']}/versions",
                headers=headers,
                files=files,
                data=data,
            )

            progress.update(task, completed=len(file_content))

            # Check response
            response.raise_for_status()

            return response.json()


def main():
    """Main entry point for the builder CLI."""
    try:
        cli()
    except KeyboardInterrupt:
        console.print("\n⏹️  Interrupted by user.", style="yellow")
        sys.exit(130)
    except Exception as e:
        console.print(f"❌ Unexpected error: {e}", style="red")
        if is_debug_mode():
            console.print_exception()
        sys.exit(1)


if __name__ == "__main__":
    main()
