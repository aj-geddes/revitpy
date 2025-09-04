"""CLI for building and publishing RevitPy packages."""

import os
import sys
import tarfile
from pathlib import Path
from typing import Optional

import click
import toml
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..validator import PackageLinter
from ...security.signing import PackageSignatureManager
from ....__init__ import __version__

console = Console()


@click.group()
@click.version_option(version=__version__)
def cli():
    """RevitPy Package Builder - Build, validate, and publish RevitPy packages."""
    pass


@cli.command()
@click.argument('source_dir', type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option('--output-dir', '-o', type=click.Path(path_type=Path), help="Output directory for built package")
@click.option('--format', 'build_format', type=click.Choice(['sdist', 'wheel', 'both']), default='sdist', help="Build format")
@click.option('--clean', is_flag=True, help="Clean build directory before building")
def build(source_dir: Path, output_dir: Optional[Path], build_format: str, clean: bool):
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
        with open(pyproject_path, 'r') as f:
            config = toml.load(f)
        
        project = config.get('project', {})
        package_name = project.get('name')
        package_version = project.get('version')
        
        if not package_name or not package_version:
            console.print("❌ Missing package name or version in pyproject.toml", style="red")
            sys.exit(1)
        
        console.print(f"📦 Building {package_name} v{package_version}", style="green")
        
    except Exception as e:
        console.print(f"❌ Error reading pyproject.toml: {e}", style="red")
        sys.exit(1)
    
    # Build source distribution
    if build_format in ('sdist', 'both'):
        sdist_path = _build_sdist(source_dir, output_dir, package_name, package_version)
        if sdist_path:
            console.print(f"✅ Built source distribution: {sdist_path.name}", style="green")
        else:
            console.print("❌ Failed to build source distribution", style="red")
            sys.exit(1)
    
    # Build wheel (placeholder - would use proper wheel building)
    if build_format in ('wheel', 'both'):
        console.print("⚠️  Wheel building not yet implemented", style="yellow")
    
    console.print(f"🎉 Build completed! Output in {output_dir}", style="blue")


def _build_sdist(source_dir: Path, output_dir: Path, package_name: str, version: str) -> Optional[Path]:
    """Build a source distribution (tar.gz)."""
    filename = f"{package_name}-{version}.tar.gz"
    output_path = output_dir / filename
    
    try:
        with tarfile.open(output_path, 'w:gz') as tar:
            # Add all files except common build/cache directories
            exclude_patterns = {
                '__pycache__', '*.pyc', '.git', '.svn', '.hg',
                'build', 'dist', '*.egg-info', '.tox', '.pytest_cache',
                '.mypy_cache', '.coverage', 'htmlcov'
            }
            
            for item in source_dir.rglob('*'):
                if item.is_file():
                    # Check if file should be excluded
                    should_exclude = False
                    for pattern in exclude_patterns:
                        if pattern in str(item) or item.name.startswith('.') and item.name not in ('.gitignore',):
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
@click.argument('package_path', type=click.Path(exists=True, path_type=Path))
@click.option('--strict', is_flag=True, help="Treat warnings as errors")
@click.option('--include-info', is_flag=True, help="Include informational messages")
@click.option('--output', '-o', type=click.File('w'), help="Output report to file")
def validate(package_path: Path, strict: bool, include_info: bool, output):
    """Validate a package for quality and compliance."""
    console.print(f"🔍 Validating package: {package_path}", style="blue")
    
    linter = PackageLinter()
    errors, success = linter.lint_package(package_path, strict=strict, include_info=include_info)
    
    # Generate report
    report = linter.generate_report(errors, package_path)
    
    # Output report
    if output:
        output.write(report)
        console.print(f"📄 Report written to {output.name}", style="blue")
    else:
        console.print(report)
    
    # Summary
    error_count = len([e for e in errors if e.level == 'error'])
    warning_count = len([e for e in errors if e.level == 'warning'])
    info_count = len([e for e in errors if e.level == 'info'])
    
    if success:
        console.print(Panel(
            f"✅ Validation passed!\n"
            f"Issues found: {error_count} errors, {warning_count} warnings, {info_count} info",
            title="Validation Result",
            style="green"
        ))
    else:
        console.print(Panel(
            f"❌ Validation failed!\n"
            f"Issues found: {error_count} errors, {warning_count} warnings, {info_count} info",
            title="Validation Result",
            style="red"
        ))
        sys.exit(1)


@cli.command('generate-key')
@click.option('--algorithm', type=click.Choice(['Ed25519', 'RSA-PSS']), default='Ed25519', help="Signing algorithm")
@click.option('--output', '-o', type=click.Path(path_type=Path), help="Output key file path")
@click.option('--passphrase', prompt=True, hide_input=True, help="Passphrase for private key")
def generate_signing_key(algorithm: str, output: Optional[Path], passphrase: str):
    """Generate a signing key pair for package signing."""
    console.print(f"🔑 Generating {algorithm} key pair...", style="blue")
    
    if output is None:
        output = Path.cwd() / "signing_key.pem"
    
    public_key_path = output.with_suffix('.pub')
    
    try:
        signer = PackageSignatureManager(algorithm)
        signer.signer.generate_key_pair_to_files(
            private_key_path=output,
            public_key_path=public_key_path,
            passphrase=passphrase if passphrase else None
        )
        
        console.print(Panel(
            f"✅ Key pair generated successfully!\n"
            f"Private key: {output}\n"
            f"Public key: {public_key_path}\n\n"
            f"⚠️  Keep your private key secure and never share it!",
            title="Key Generation Complete",
            style="green"
        ))
        
    except Exception as e:
        console.print(f"❌ Failed to generate keys: {e}", style="red")
        sys.exit(1)


@cli.command()
@click.argument('package_path', type=click.Path(exists=True, path_type=Path))
@click.option('--key', '-k', type=click.Path(exists=True, path_type=Path), required=True, help="Private key file")
@click.option('--passphrase', prompt=True, hide_input=True, help="Private key passphrase")
@click.option('--algorithm', type=click.Choice(['Ed25519', 'RSA-PSS']), default='Ed25519', help="Signing algorithm")
def sign(package_path: Path, key: Path, passphrase: str, algorithm: str):
    """Sign a package for verification."""
    console.print(f"✍️  Signing package: {package_path.name}", style="blue")
    
    try:
        # Read package data
        with open(package_path, 'rb') as f:
            package_data = f.read()
        
        # Sign package
        signature_manager = PackageSignatureManager(algorithm)
        signature_info = signature_manager.sign_package(
            package_data=package_data,
            private_key_path=key,
            passphrase=passphrase if passphrase else None,
            metadata={
                "package_file": package_path.name,
                "file_size": len(package_data)
            }
        )
        
        # Save signature file
        signature_path = package_path.with_suffix(package_path.suffix + '.sig')
        with open(signature_path, 'w') as f:
            import json
            json.dump(signature_info, f, indent=2)
        
        console.print(Panel(
            f"✅ Package signed successfully!\n"
            f"Signature file: {signature_path.name}\n"
            f"Algorithm: {algorithm}\n"
            f"Fingerprint: {signature_info['public_key_fingerprint'][:16]}...",
            title="Package Signed",
            style="green"
        ))
        
    except Exception as e:
        console.print(f"❌ Failed to sign package: {e}", style="red")
        sys.exit(1)


@cli.command()
@click.argument('package_path', type=click.Path(exists=True, path_type=Path))
@click.option('--signature', '-s', type=click.Path(exists=True, path_type=Path), help="Signature file path")
@click.option('--public-key', '-p', type=click.Path(exists=True, path_type=Path), required=True, help="Public key file")
def verify(package_path: Path, signature: Optional[Path], public_key: Path):
    """Verify a package signature."""
    console.print(f"🔍 Verifying package: {package_path.name}", style="blue")
    
    # Find signature file if not provided
    if signature is None:
        signature = package_path.with_suffix(package_path.suffix + '.sig')
        if not signature.exists():
            console.print("❌ No signature file found. Use --signature to specify.", style="red")
            sys.exit(1)
    
    try:
        # Read package data
        with open(package_path, 'rb') as f:
            package_data = f.read()
        
        # Read signature
        with open(signature, 'r') as f:
            import json
            signature_info = json.load(f)
        
        # Read public key
        public_key_data = public_key.read_bytes()
        
        # Verify signature
        algorithm = signature_info.get('algorithm', 'Ed25519')
        signature_manager = PackageSignatureManager(algorithm)
        
        is_valid, error_message = signature_manager.verify_package_signature(
            package_data=package_data,
            signature_info=signature_info,
            public_key=public_key_data
        )
        
        if is_valid:
            console.print(Panel(
                f"✅ Signature is valid!\n"
                f"Algorithm: {algorithm}\n"
                f"Signed at: {signature_info.get('signed_at', 'Unknown')}\n"
                f"Fingerprint: {signature_info.get('public_key_fingerprint', '')[:16]}...",
                title="Verification Successful",
                style="green"
            ))
        else:
            console.print(Panel(
                f"❌ Signature verification failed!\n"
                f"Error: {error_message}",
                title="Verification Failed",
                style="red"
            ))
            sys.exit(1)
            
    except Exception as e:
        console.print(f"❌ Failed to verify package: {e}", style="red")
        sys.exit(1)


@cli.command()
@click.argument('package_path', type=click.Path(exists=True, path_type=Path))
@click.option('--registry-url', default="http://localhost:8000", help="Registry URL")
@click.option('--token', help="Authentication token")
@click.option('--dry-run', is_flag=True, help="Show what would be uploaded without uploading")
def publish(package_path: Path, registry_url: str, token: Optional[str], dry_run: bool):
    """Publish a package to the registry."""
    if dry_run:
        console.print("🔍 Dry run mode - showing what would be published:", style="yellow")
    else:
        console.print(f"📤 Publishing package: {package_path.name}", style="blue")
    
    console.print(f"Registry: {registry_url}", style="dim")
    
    if dry_run:
        console.print(f"Would upload: {package_path}", style="yellow")
        return
    
    # TODO: Implement actual upload to registry
    console.print("⚠️  Publishing not yet implemented", style="yellow")


def main():
    """Main entry point for the builder CLI."""
    try:
        cli()
    except KeyboardInterrupt:
        console.print("\n⏹️  Interrupted by user.", style="yellow")
        sys.exit(130)
    except Exception as e:
        console.print(f"❌ Unexpected error: {e}", style="red")
        if os.getenv("DEBUG"):
            console.print_exception()
        sys.exit(1)


if __name__ == '__main__':
    main()