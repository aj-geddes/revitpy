"""Exception classes for RevitPy CLI."""


class RevitPyCliError(Exception):
    """Base exception for all RevitPy CLI errors."""

    def __init__(self, message: str, exit_code: int = 1) -> None:
        """Initialize CLI error.

        Args:
            message: Error message to display
            exit_code: Exit code for the CLI (default: 1)
        """
        super().__init__(message)
        self.message = message
        self.exit_code = exit_code


class CommandError(RevitPyCliError):
    """Exception raised when a CLI command fails."""

    def __init__(
        self,
        command: str,
        message: str,
        exit_code: int = 1,
        suggestion: str | None = None,
    ) -> None:
        """Initialize command error.

        Args:
            command: The command that failed
            message: Error message
            exit_code: Exit code for the CLI
            suggestion: Optional suggestion for fixing the error
        """
        full_message = f"Command '{command}' failed: {message}"
        if suggestion:
            full_message += f"\nSuggestion: {suggestion}"

        super().__init__(full_message, exit_code)
        self.command = command
        self.suggestion = suggestion


class ConfigurationError(RevitPyCliError):
    """Exception raised when configuration is invalid or missing."""

    def __init__(self, message: str, config_path: str | None = None) -> None:
        """Initialize configuration error.

        Args:
            message: Error message
            config_path: Path to the problematic config file
        """
        if config_path:
            full_message = f"Configuration error in {config_path}: {message}"
        else:
            full_message = f"Configuration error: {message}"

        super().__init__(full_message)
        self.config_path = config_path


class ProjectError(RevitPyCliError):
    """Exception raised for project-related errors."""

    def __init__(self, message: str, project_path: str | None = None) -> None:
        """Initialize project error.

        Args:
            message: Error message
            project_path: Path to the project with the issue
        """
        if project_path:
            full_message = f"Project error in {project_path}: {message}"
        else:
            full_message = f"Project error: {message}"

        super().__init__(full_message)
        self.project_path = project_path


class TemplateError(RevitPyCliError):
    """Exception raised for template-related errors."""

    def __init__(self, template: str, message: str) -> None:
        """Initialize template error.

        Args:
            template: Template name or path
            message: Error message
        """
        full_message = f"Template error for '{template}': {message}"
        super().__init__(full_message)
        self.template = template


class BuildError(RevitPyCliError):
    """Exception raised during build operations."""

    def __init__(self, message: str, build_step: str | None = None) -> None:
        """Initialize build error.

        Args:
            message: Error message
            build_step: The build step that failed
        """
        if build_step:
            full_message = f"Build failed at step '{build_step}': {message}"
        else:
            full_message = f"Build failed: {message}"

        super().__init__(full_message)
        self.build_step = build_step


class PublishError(RevitPyCliError):
    """Exception raised during publishing operations."""

    def __init__(self, message: str, registry: str | None = None) -> None:
        """Initialize publish error.

        Args:
            message: Error message
            registry: Registry URL that failed
        """
        if registry:
            full_message = f"Publish to {registry} failed: {message}"
        else:
            full_message = f"Publish failed: {message}"

        super().__init__(full_message)
        self.registry = registry


class InstallError(RevitPyCliError):
    """Exception raised during package installation."""

    def __init__(self, package: str, message: str) -> None:
        """Initialize install error.

        Args:
            package: Package name or specification
            message: Error message
        """
        full_message = f"Installation of '{package}' failed: {message}"
        super().__init__(full_message)
        self.package = package


class DevServerError(RevitPyCliError):
    """Exception raised by the development server."""

    def __init__(self, message: str, port: int | None = None) -> None:
        """Initialize dev server error.

        Args:
            message: Error message
            port: Port number if relevant
        """
        if port:
            full_message = f"Dev server error on port {port}: {message}"
        else:
            full_message = f"Dev server error: {message}"

        super().__init__(full_message)
        self.port = port


class PluginError(RevitPyCliError):
    """Exception raised for plugin-related errors."""

    def __init__(self, plugin: str, message: str) -> None:
        """Initialize plugin error.

        Args:
            plugin: Plugin name
            message: Error message
        """
        full_message = f"Plugin '{plugin}' error: {message}"
        super().__init__(full_message)
        self.plugin = plugin
