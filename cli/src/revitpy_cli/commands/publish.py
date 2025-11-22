"""Package publishing and registry commands."""

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

import httpx
import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.prompt import Confirm, Prompt
from rich.table import Table

from ..core.config import get_config
from ..core.exceptions import AuthenticationError, CommandError, PublishError
from ..core.logging import get_logger, log_command_complete, log_command_start

console = Console()
logger = get_logger(__name__)

app = typer.Typer(
    name="publish",
    help="Publish packages to RevitPy registry",
    rich_markup_mode="rich",
)


@app.command()
def package(
    package_path: str | None = typer.Argument(None, help="Path to package file"),
    registry: str | None = typer.Option(None, "--registry", "-r", help="Registry URL"),
    token: str | None = typer.Option(None, "--token", help="Authentication token"),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Simulate publishing without uploading"
    ),
    sign: bool = typer.Option(
        True, "--sign/--no-sign", help="Sign package before publishing"
    ),
    verify: bool = typer.Option(
        True, "--verify/--no-verify", help="Verify package after publishing"
    ),
    repository: str | None = typer.Option(
        None, "--repository", help="Repository name (for organization publishing)"
    ),
) -> None:
    """Publish a package to the RevitPy registry.

    Examples:
        revitpy publish package
        revitpy publish package dist/my-package-1.0.0.tar.gz
        revitpy publish package --registry https://my-registry.com --dry-run
    """
    start_time = time.time()
    log_command_start(
        "publish package",
        {
            "package_path": package_path,
            "registry": registry,
            "dry_run": dry_run,
            "sign": sign,
            "verify": verify,
            "repository": repository,
        },
    )

    config = get_config()

    # Determine package path
    if package_path:
        pkg_path = Path(package_path).resolve()
        if not pkg_path.exists():
            raise CommandError("publish package", f"Package file not found: {pkg_path}")
    else:
        # Look for packages in dist directory
        dist_dir = Path.cwd() / "dist"
        if not dist_dir.exists():
            raise CommandError(
                "publish package",
                "No package specified and dist/ directory not found",
                suggestion="Build package first with 'revitpy build package'",
            )

        packages = list(dist_dir.glob("*.whl")) + list(dist_dir.glob("*.tar.gz"))
        if not packages:
            raise CommandError(
                "publish package",
                "No packages found in dist/ directory",
                suggestion="Build package first with 'revitpy build package'",
            )
        elif len(packages) == 1:
            pkg_path = packages[0]
        else:
            # Interactive selection
            pkg_path = select_package_interactively(packages)

    # Determine registry
    registry_url = registry or config.publish.registry_url

    try:
        publisher = PackagePublisher(
            package_path=pkg_path,
            registry_url=registry_url,
            config=config,
        )

        console.print(f"[bold blue]📦 Publishing package:[/bold blue] {pkg_path.name}")
        console.print(f"[dim]Registry: {registry_url}[/dim]")
        if dry_run:
            console.print("[yellow]DRY RUN - Package will not be uploaded[/yellow]")
        console.print()

        # Get or prompt for authentication
        auth_token = token or get_authentication_token(registry_url, config)

        # Publish package
        publication_result = publisher.publish(
            auth_token=auth_token,
            dry_run=dry_run,
            sign_package=sign,
            verify_after_upload=verify,
            repository=repository,
        )

        # Success message
        if dry_run:
            console.print(
                "[bold green]✓[/bold green] Package validation completed (dry run)"
            )
        else:
            console.print("[bold green]✓[/bold green] Package published successfully!")
            console.print(
                f"[dim]Package URL: {publication_result['package_url']}[/dim]"
            )

            # Show publication details
            publisher.show_publication_info(publication_result)

    except Exception as e:
        raise PublishError(str(e)) from e
    finally:
        duration = time.time() - start_time
        log_command_complete("publish package", duration)


@app.command()
def login(
    registry: str | None = typer.Option(None, "--registry", "-r", help="Registry URL"),
    username: str | None = typer.Option(None, "--username", "-u", help="Username"),
    token: str | None = typer.Option(
        None, "--token", help="API token (alternative to username/password)"
    ),
) -> None:
    """Login to a RevitPy package registry.

    Examples:
        revitpy publish login
        revitpy publish login --registry https://my-registry.com
        revitpy publish login --username myuser --token my-api-token
    """
    start_time = time.time()
    log_command_start(
        "publish login",
        {
            "registry": registry,
            "username": username,
            "token": bool(token),
        },
    )

    config = get_config()

    # Determine registry
    registry_url = registry or config.publish.registry_url

    try:
        auth_manager = AuthenticationManager(config)

        console.print(f"[bold blue]🔐 Logging into:[/bold blue] {registry_url}")
        console.print()

        # Get credentials
        if token:
            # Use provided token
            username = username or Prompt.ask("Username")
            credentials = {"username": username, "token": token}
        else:
            # Interactive authentication
            credentials = auth_manager.interactive_login(registry_url, username)

        # Verify credentials
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Verifying credentials...", total=None)

            auth_result = auth_manager.authenticate(registry_url, credentials)

            progress.update(task, completed=True)

        if auth_result["success"]:
            # Store credentials
            auth_manager.store_credentials(registry_url, auth_result["token"])

            console.print("[bold green]✓[/bold green] Successfully logged in!")
            console.print(f"[dim]User: {auth_result['username']}[/dim]")
            console.print(f"[dim]Expires: {auth_result.get('expires', 'Never')}[/dim]")
        else:
            raise AuthenticationError(
                "Login failed", auth_result.get("error", "Unknown error")
            )

    except Exception as e:
        raise PublishError(str(e)) from e
    finally:
        duration = time.time() - start_time
        log_command_complete("publish login", duration)


@app.command()
def logout(
    registry: str | None = typer.Option(None, "--registry", "-r", help="Registry URL"),
    all: bool = typer.Option(False, "--all", help="Logout from all registries"),
) -> None:
    """Logout from package registry.

    Examples:
        revitpy publish logout
        revitpy publish logout --registry https://my-registry.com
        revitpy publish logout --all
    """
    log_command_start("publish logout", {"registry": registry, "all": all})

    config = get_config()
    auth_manager = AuthenticationManager(config)

    try:
        if all:
            count = auth_manager.clear_all_credentials()
            console.print(f"[green]✓[/green] Logged out from {count} registries")
        else:
            registry_url = registry or config.publish.registry_url
            auth_manager.clear_credentials(registry_url)
            console.print(f"[green]✓[/green] Logged out from {registry_url}")

    except Exception as e:
        raise PublishError(str(e)) from e
    finally:
        log_command_complete("publish logout", 0)


@app.command()
def status(
    registry: str | None = typer.Option(None, "--registry", "-r", help="Registry URL"),
    package: str | None = typer.Option(
        None, "--package", help="Check specific package status"
    ),
) -> None:
    """Check publishing status and registry connection.

    Examples:
        revitpy publish status
        revitpy publish status --registry https://my-registry.com
        revitpy publish status --package my-package
    """
    log_command_start("publish status", {"registry": registry, "package": package})

    config = get_config()
    registry_url = registry or config.publish.registry_url

    try:
        status_checker = PublishStatusChecker(registry_url, config)

        console.print(f"[bold blue]📊 Registry Status:[/bold blue] {registry_url}")
        console.print()

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            # Check registry connectivity
            task1 = progress.add_task("Checking registry connectivity...", total=None)
            connectivity = status_checker.check_connectivity()
            progress.update(task1, completed=True)

            # Check authentication
            task2 = progress.add_task("Checking authentication...", total=None)
            auth_status = status_checker.check_authentication()
            progress.update(task2, completed=True)

            # Check package status if specified
            package_status = None
            if package:
                task3 = progress.add_task(
                    f"Checking package '{package}'...", total=None
                )
                package_status = status_checker.check_package_status(package)
                progress.update(task3, completed=True)

        # Display results
        status_checker.display_status(connectivity, auth_status, package_status)

    except Exception as e:
        raise PublishError(str(e)) from e
    finally:
        log_command_complete("publish status", 0)


@app.command()
def list_packages(
    registry: str | None = typer.Option(None, "--registry", "-r", help="Registry URL"),
    user: str | None = typer.Option(
        None, "--user", help="List packages for specific user"
    ),
    limit: int = typer.Option(20, "--limit", help="Number of packages to show"),
    search: str | None = typer.Option(None, "--search", help="Search packages"),
) -> None:
    """List published packages in registry.

    Examples:
        revitpy publish list-packages
        revitpy publish list-packages --user myuser
        revitpy publish list-packages --search geometry --limit 10
    """
    log_command_start(
        "publish list-packages",
        {
            "registry": registry,
            "user": user,
            "limit": limit,
            "search": search,
        },
    )

    config = get_config()
    registry_url = registry or config.publish.registry_url

    try:
        package_lister = PackageLister(registry_url, config)

        console.print(f"[bold blue]📋 Packages in:[/bold blue] {registry_url}")
        console.print()

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Fetching packages...", total=None)

            packages = package_lister.list_packages(
                user=user,
                limit=limit,
                search=search,
            )

            progress.update(task, completed=True)

        if packages:
            package_lister.display_packages(packages)
        else:
            console.print("[yellow]No packages found[/yellow]")

    except Exception as e:
        raise PublishError(str(e)) from e
    finally:
        log_command_complete("publish list-packages", 0)


def select_package_interactively(packages: list[Path]) -> Path:
    """Interactively select a package to publish.

    Args:
        packages: List of available packages

    Returns:
        Selected package path
    """
    console.print("\n[bold]Available Packages:[/bold]")
    for i, pkg in enumerate(packages, 1):
        size = pkg.stat().st_size / 1024  # KB
        console.print(f"  {i}. [cyan]{pkg.name}[/cyan] ({size:.1f} KB)")

    while True:
        choice = Prompt.ask(
            f"\nSelect package to publish (1-{len(packages)})", default="1"
        )

        try:
            index = int(choice) - 1
            if 0 <= index < len(packages):
                return packages[index]
            else:
                console.print("[red]Invalid selection. Please try again.[/red]")
        except ValueError:
            console.print("[red]Please enter a valid number.[/red]")


def get_authentication_token(registry_url: str, config: Any) -> str:
    """Get authentication token for registry.

    Args:
        registry_url: Registry URL
        config: CLI configuration

    Returns:
        Authentication token
    """
    auth_manager = AuthenticationManager(config)

    # Try to get stored token
    stored_token = auth_manager.get_stored_token(registry_url)
    if stored_token:
        return stored_token

    # Prompt for authentication
    console.print("[yellow]Authentication required[/yellow]")
    if Confirm.ask("Login now?"):
        credentials = auth_manager.interactive_login(registry_url)
        auth_result = auth_manager.authenticate(registry_url, credentials)

        if auth_result["success"]:
            auth_manager.store_credentials(registry_url, auth_result["token"])
            return auth_result["token"]
        else:
            raise AuthenticationError("Authentication failed", auth_result.get("error"))
    else:
        raise AuthenticationError("Authentication required to publish")


class PackagePublisher:
    """Handles package publishing to registries."""

    def __init__(self, package_path: Path, registry_url: str, config: Any) -> None:
        """Initialize package publisher.

        Args:
            package_path: Path to package file
            registry_url: Registry URL
            config: CLI configuration
        """
        self.package_path = package_path
        self.registry_url = registry_url
        self.config = config

        # HTTP client for API requests
        self.client = httpx.Client(
            timeout=30.0, headers={"User-Agent": f"RevitPy-CLI/{config.version}"}
        )

    def publish(
        self,
        auth_token: str,
        dry_run: bool = False,
        sign_package: bool = False,
        verify_after_upload: bool = True,
        repository: str | None = None,
    ) -> dict[str, Any]:
        """Publish package to registry.

        Args:
            auth_token: Authentication token
            dry_run: Simulate publishing without uploading
            sign_package: Sign package before publishing
            verify_after_upload: Verify package after upload
            repository: Repository name

        Returns:
            Publication result information
        """
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            # Step 1: Validate package
            task1 = progress.add_task("Validating package...", total=None)
            self._validate_package()
            progress.update(task1, completed=True)

            # Step 2: Extract metadata
            task2 = progress.add_task("Extracting metadata...", total=None)
            metadata = self._extract_metadata()
            progress.update(task2, completed=True)

            # Step 3: Sign package (optional)
            if sign_package:
                task3 = progress.add_task("Signing package...", total=None)
                signature = self._sign_package()
                metadata["signature"] = signature
                progress.update(task3, completed=True)

            # Step 4: Check for conflicts
            task4 = progress.add_task("Checking for conflicts...", total=None)
            conflict_check = self._check_conflicts(metadata, auth_token)
            if conflict_check["exists"]:
                if not Confirm.ask(
                    f"Package {metadata['name']} {metadata['version']} already exists. Overwrite?"
                ):
                    raise PublishError("Publication cancelled - package already exists")
            progress.update(task4, completed=True)

            # Step 5: Upload package
            if not dry_run:
                task5 = progress.add_task("Uploading package...", total=None)
                upload_result = self._upload_package(metadata, auth_token, repository)
                progress.update(task5, completed=True)

                # Step 6: Verify upload
                if verify_after_upload:
                    task6 = progress.add_task("Verifying upload...", total=None)
                    self._verify_upload(upload_result["package_id"], auth_token)
                    progress.update(task6, completed=True)

                return upload_result
            else:
                return {
                    "dry_run": True,
                    "metadata": metadata,
                    "package_file": str(self.package_path),
                }

    def _validate_package(self) -> None:
        """Validate package file."""
        if not self.package_path.exists():
            raise PublishError(f"Package file not found: {self.package_path}")

        if self.package_path.suffix not in [".whl", ".tar.gz"]:
            raise PublishError(
                f"Unsupported package format: {self.package_path.suffix}"
            )

        # Check file size
        file_size = self.package_path.stat().st_size
        max_size = self.config.publish.max_package_size_mb * 1024 * 1024

        if file_size > max_size:
            size_mb = file_size / (1024 * 1024)
            max_mb = self.config.publish.max_package_size_mb
            raise PublishError(f"Package too large: {size_mb:.1f}MB (max: {max_mb}MB)")

    def _extract_metadata(self) -> dict[str, Any]:
        """Extract package metadata.

        Returns:
            Package metadata dictionary
        """
        # This would extract metadata from the package
        # For now, use filename parsing
        filename = self.package_path.stem

        if self.package_path.suffix == ".whl":
            # Parse wheel filename: name-version-python-abi-platform.whl
            parts = filename.split("-")
            if len(parts) >= 2:
                name = parts[0]
                version = parts[1]
            else:
                raise PublishError(f"Invalid wheel filename: {filename}")
        else:
            # Parse sdist filename: name-version.tar.gz
            parts = filename.split("-")
            if len(parts) >= 2:
                name = parts[0]
                version = "-".join(parts[1:])  # Version might contain hyphens
            else:
                raise PublishError(f"Invalid sdist filename: {filename}")

        # Calculate file hash
        sha256_hash = hashlib.sha256()
        with open(self.package_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256_hash.update(chunk)

        return {
            "name": name,
            "version": version,
            "filename": self.package_path.name,
            "size": self.package_path.stat().st_size,
            "sha256": sha256_hash.hexdigest(),
            "upload_time": time.time(),
        }

    def _sign_package(self) -> str:
        """Sign package and return signature.

        Returns:
            Package signature
        """
        # Package signing would be implemented here
        logger.warning("Package signing not implemented yet")
        return "dummy-signature"

    def _check_conflicts(
        self, metadata: dict[str, Any], auth_token: str
    ) -> dict[str, Any]:
        """Check for package conflicts in registry.

        Args:
            metadata: Package metadata
            auth_token: Authentication token

        Returns:
            Conflict check result
        """
        try:
            response = self.client.get(
                f"{self.registry_url}/api/v1/packages/{metadata['name']}/{metadata['version']}",
                headers={"Authorization": f"Bearer {auth_token}"},
            )

            if response.status_code == 200:
                return {"exists": True, "package_info": response.json()}
            elif response.status_code == 404:
                return {"exists": False}
            else:
                raise PublishError(f"Error checking package conflicts: {response.text}")

        except httpx.RequestError as e:
            raise PublishError(f"Network error checking conflicts: {e}")

    def _upload_package(
        self,
        metadata: dict[str, Any],
        auth_token: str,
        repository: str | None = None,
    ) -> dict[str, Any]:
        """Upload package to registry.

        Args:
            metadata: Package metadata
            auth_token: Authentication token
            repository: Repository name

        Returns:
            Upload result
        """
        upload_data = {
            "name": metadata["name"],
            "version": metadata["version"],
            "filename": metadata["filename"],
            "sha256": metadata["sha256"],
        }

        if repository:
            upload_data["repository"] = repository

        try:
            with open(self.package_path, "rb") as f:
                files = {"file": (metadata["filename"], f, "application/octet-stream")}

                response = self.client.post(
                    f"{self.registry_url}/api/v1/packages/upload",
                    data=upload_data,
                    files=files,
                    headers={"Authorization": f"Bearer {auth_token}"},
                )

            if response.status_code == 201:
                result = response.json()
                return {
                    "package_id": result["id"],
                    "package_url": result["url"],
                    "upload_time": result["upload_time"],
                }
            else:
                raise PublishError(f"Upload failed: {response.text}")

        except httpx.RequestError as e:
            raise PublishError(f"Network error during upload: {e}")

    def _verify_upload(self, package_id: str, auth_token: str) -> None:
        """Verify package upload was successful.

        Args:
            package_id: Package ID from upload
            auth_token: Authentication token
        """
        try:
            response = self.client.get(
                f"{self.registry_url}/api/v1/packages/{package_id}",
                headers={"Authorization": f"Bearer {auth_token}"},
            )

            if response.status_code != 200:
                raise PublishError(f"Package verification failed: {response.text}")

            package_info = response.json()
            if package_info["status"] != "published":
                raise PublishError(
                    f"Package not properly published: {package_info['status']}"
                )

        except httpx.RequestError as e:
            raise PublishError(f"Network error during verification: {e}")

    def show_publication_info(self, result: dict[str, Any]) -> None:
        """Show publication information.

        Args:
            result: Publication result
        """
        info_table = Table(title="Publication Information")
        info_table.add_column("Property", style="cyan")
        info_table.add_column("Value", style="green")

        info_table.add_row("Package ID", result["package_id"])
        info_table.add_row("Upload Time", time.ctime(result["upload_time"]))

        console.print(info_table)


class AuthenticationManager:
    """Manages authentication with package registries."""

    def __init__(self, config: Any) -> None:
        """Initialize authentication manager.

        Args:
            config: CLI configuration
        """
        self.config = config
        self.credentials_file = Path.home() / ".revitpy" / "credentials.json"
        self.credentials_file.parent.mkdir(exist_ok=True)

    def interactive_login(
        self, registry_url: str, username: str | None = None
    ) -> dict[str, str]:
        """Interactive login flow.

        Args:
            registry_url: Registry URL
            username: Optional username

        Returns:
            Credentials dictionary
        """
        if not username:
            username = Prompt.ask("Username")

        password = Prompt.ask("Password", password=True)

        return {
            "username": username,
            "password": password,
        }

    def authenticate(
        self, registry_url: str, credentials: dict[str, str]
    ) -> dict[str, Any]:
        """Authenticate with registry.

        Args:
            registry_url: Registry URL
            credentials: User credentials

        Returns:
            Authentication result
        """
        try:
            with httpx.Client() as client:
                response = client.post(
                    f"{registry_url}/api/v1/auth/login",
                    json=credentials,
                )

                if response.status_code == 200:
                    result = response.json()
                    return {
                        "success": True,
                        "token": result["token"],
                        "username": result["username"],
                        "expires": result.get("expires"),
                    }
                else:
                    return {
                        "success": False,
                        "error": response.json().get("error", "Authentication failed"),
                    }

        except httpx.RequestError as e:
            return {
                "success": False,
                "error": f"Network error: {e}",
            }

    def store_credentials(self, registry_url: str, token: str) -> None:
        """Store authentication token.

        Args:
            registry_url: Registry URL
            token: Authentication token
        """
        try:
            # Load existing credentials
            if self.credentials_file.exists():
                with open(self.credentials_file) as f:
                    credentials = json.load(f)
            else:
                credentials = {}

            # Update credentials
            credentials[registry_url] = {
                "token": token,
                "stored_at": time.time(),
            }

            # Save credentials
            with open(self.credentials_file, "w") as f:
                json.dump(credentials, f, indent=2)

            # Set secure permissions
            os.chmod(self.credentials_file, 0o600)

        except Exception as e:
            logger.warning(f"Failed to store credentials: {e}")

    def get_stored_token(self, registry_url: str) -> str | None:
        """Get stored authentication token.

        Args:
            registry_url: Registry URL

        Returns:
            Authentication token or None
        """
        try:
            if not self.credentials_file.exists():
                return None

            with open(self.credentials_file) as f:
                credentials = json.load(f)

            registry_creds = credentials.get(registry_url)
            if registry_creds:
                return registry_creds["token"]

        except Exception as e:
            logger.warning(f"Failed to load stored credentials: {e}")

        return None

    def clear_credentials(self, registry_url: str) -> None:
        """Clear stored credentials for registry.

        Args:
            registry_url: Registry URL
        """
        try:
            if not self.credentials_file.exists():
                return

            with open(self.credentials_file) as f:
                credentials = json.load(f)

            if registry_url in credentials:
                del credentials[registry_url]

                with open(self.credentials_file, "w") as f:
                    json.dump(credentials, f, indent=2)

        except Exception as e:
            logger.warning(f"Failed to clear credentials: {e}")

    def clear_all_credentials(self) -> int:
        """Clear all stored credentials.

        Returns:
            Number of cleared registries
        """
        try:
            if not self.credentials_file.exists():
                return 0

            with open(self.credentials_file) as f:
                credentials = json.load(f)

            count = len(credentials)

            # Clear file
            with open(self.credentials_file, "w") as f:
                json.dump({}, f)

            return count

        except Exception as e:
            logger.warning(f"Failed to clear all credentials: {e}")
            return 0


class PublishStatusChecker:
    """Checks publishing status and registry connectivity."""

    def __init__(self, registry_url: str, config: Any) -> None:
        """Initialize status checker.

        Args:
            registry_url: Registry URL
            config: CLI configuration
        """
        self.registry_url = registry_url
        self.config = config
        self.client = httpx.Client(timeout=10.0)

    def check_connectivity(self) -> dict[str, Any]:
        """Check registry connectivity.

        Returns:
            Connectivity status
        """
        try:
            response = self.client.get(f"{self.registry_url}/api/v1/health")

            if response.status_code == 200:
                return {
                    "connected": True,
                    "response_time": response.elapsed.total_seconds(),
                    "server_info": response.json(),
                }
            else:
                return {
                    "connected": False,
                    "error": f"HTTP {response.status_code}",
                }

        except httpx.RequestError as e:
            return {
                "connected": False,
                "error": str(e),
            }

    def check_authentication(self) -> dict[str, Any]:
        """Check authentication status.

        Returns:
            Authentication status
        """
        auth_manager = AuthenticationManager(self.config)
        token = auth_manager.get_stored_token(self.registry_url)

        if not token:
            return {
                "authenticated": False,
                "reason": "No stored token",
            }

        try:
            response = self.client.get(
                f"{self.registry_url}/api/v1/auth/verify",
                headers={"Authorization": f"Bearer {token}"},
            )

            if response.status_code == 200:
                user_info = response.json()
                return {
                    "authenticated": True,
                    "username": user_info.get("username"),
                    "expires": user_info.get("expires"),
                }
            else:
                return {
                    "authenticated": False,
                    "reason": "Token invalid or expired",
                }

        except httpx.RequestError as e:
            return {
                "authenticated": False,
                "reason": f"Network error: {e}",
            }

    def check_package_status(self, package_name: str) -> dict[str, Any]:
        """Check status of specific package.

        Args:
            package_name: Package name to check

        Returns:
            Package status information
        """
        try:
            response = self.client.get(
                f"{self.registry_url}/api/v1/packages/{package_name}"
            )

            if response.status_code == 200:
                package_info = response.json()
                return {
                    "exists": True,
                    "info": package_info,
                }
            elif response.status_code == 404:
                return {
                    "exists": False,
                }
            else:
                return {
                    "exists": False,
                    "error": f"HTTP {response.status_code}",
                }

        except httpx.RequestError as e:
            return {
                "exists": False,
                "error": str(e),
            }

    def display_status(
        self,
        connectivity: dict[str, Any],
        auth_status: dict[str, Any],
        package_status: dict[str, Any] | None = None,
    ) -> None:
        """Display status information.

        Args:
            connectivity: Connectivity status
            auth_status: Authentication status
            package_status: Package status (optional)
        """
        status_table = Table(title="Registry Status")
        status_table.add_column("Component", style="cyan")
        status_table.add_column("Status", style="green")
        status_table.add_column("Details", style="dim")

        # Connectivity
        if connectivity["connected"]:
            status_table.add_row(
                "Registry Connection",
                "🟢 Connected",
                f"{connectivity['response_time']:.3f}s",
            )
        else:
            status_table.add_row(
                "Registry Connection", "🔴 Failed", connectivity["error"]
            )

        # Authentication
        if auth_status["authenticated"]:
            details = f"User: {auth_status['username']}"
            if auth_status.get("expires"):
                details += f" | Expires: {auth_status['expires']}"
            status_table.add_row("Authentication", "🟢 Authenticated", details)
        else:
            status_table.add_row(
                "Authentication", "🔴 Not authenticated", auth_status["reason"]
            )

        # Package status
        if package_status:
            if package_status["exists"]:
                info = package_status["info"]
                details = f"Latest: v{info['latest_version']} | Downloads: {info['downloads']}"
                status_table.add_row(
                    f"Package '{info['name']}'", "🟢 Published", details
                )
            else:
                error = package_status.get("error", "Not found")
                status_table.add_row("Package", "🔴 Not found", error)

        console.print(status_table)


class PackageLister:
    """Lists packages from registry."""

    def __init__(self, registry_url: str, config: Any) -> None:
        """Initialize package lister.

        Args:
            registry_url: Registry URL
            config: CLI configuration
        """
        self.registry_url = registry_url
        self.config = config
        self.client = httpx.Client(timeout=10.0)

    def list_packages(
        self,
        user: str | None = None,
        limit: int = 20,
        search: str | None = None,
    ) -> list[dict[str, Any]]:
        """List packages from registry.

        Args:
            user: Filter by user
            limit: Maximum number of packages
            search: Search term

        Returns:
            List of package information
        """
        params = {"limit": limit}

        if user:
            params["user"] = user
        if search:
            params["q"] = search

        try:
            response = self.client.get(
                f"{self.registry_url}/api/v1/packages",
                params=params,
            )

            if response.status_code == 200:
                return response.json()["packages"]
            else:
                raise PublishError(f"Failed to list packages: {response.text}")

        except httpx.RequestError as e:
            raise PublishError(f"Network error listing packages: {e}")

    def display_packages(self, packages: list[dict[str, Any]]) -> None:
        """Display packages in a table.

        Args:
            packages: List of package information
        """
        table = Table(title="Published Packages")
        table.add_column("Name", style="cyan")
        table.add_column("Version", style="green")
        table.add_column("Author", style="blue")
        table.add_column("Downloads", style="yellow")
        table.add_column("Updated", style="dim")

        for pkg in packages:
            updated = time.strftime("%Y-%m-%d", time.localtime(pkg["updated_at"]))

            table.add_row(
                pkg["name"],
                pkg["latest_version"],
                pkg["author"],
                str(pkg["downloads"]),
                updated,
            )

        console.print(table)
