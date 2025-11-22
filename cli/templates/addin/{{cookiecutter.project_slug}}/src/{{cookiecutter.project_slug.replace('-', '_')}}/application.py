"""Main application class for {{ cookiecutter.project_name }} add-in."""

import logging
{% if cookiecutter.include_logging == 'y' -%}
from pathlib import Path
{% endif %}
{% if cookiecutter.use_dependency_injection == 'y' -%}
from typing import Dict, Type, Any
{% endif %}

import revitpy
from revitpy import IExternalApplication, IExternalCommand
from revitpy.UI import RibbonPanel, PushButton

{% if cookiecutter.include_logging == 'y' -%}
from .core.logging import setup_logging
{% endif -%}
{% if cookiecutter.include_settings_manager == 'y' -%}
from .core.settings import SettingsManager
{% endif -%}
{% if cookiecutter.use_dependency_injection == 'y' -%}
from .core.container import Container
{% endif -%}
{% if cookiecutter.create_command_pattern == 'y' -%}
from .commands import (
    ExampleCommand,
    SettingsCommand,
    AboutCommand,
)
{% endif -%}
{% if cookiecutter.create_dockable_panel == 'y' -%}
from .ui.panels import MainPanel
{% endif %}


class {{ cookiecutter.project_name.replace(' ', '') }}Application(IExternalApplication):
    """Main application class that handles add-in lifecycle."""

    def __init__(self) -> None:
        """Initialize the application."""
        self.logger: logging.Logger = None
        {% if cookiecutter.include_settings_manager == 'y' -%}
        self.settings: SettingsManager = None
        {% endif -%}
        {% if cookiecutter.use_dependency_injection == 'y' -%}
        self.container: Container = None
        {% endif -%}
        self.ribbon_panel: RibbonPanel = None
        {% if cookiecutter.create_dockable_panel == 'y' -%}
        self.dockable_panel: MainPanel = None
        {% endif %}

    def OnStartup(self, application: revitpy.UIControlledApplication) -> revitpy.Result:
        """Called when Revit starts up.

        Args:
            application: Revit UI controlled application

        Returns:
            Success or failure result
        """
        try:
            # Initialize logging
            {% if cookiecutter.include_logging == 'y' -%}
            self._initialize_logging()
            self.logger.info("Starting {{ cookiecutter.project_name }} add-in...")
            {% else -%}
            self.logger = logging.getLogger(__name__)
            {% endif %}

            # Initialize settings
            {% if cookiecutter.include_settings_manager == 'y' -%}
            self._initialize_settings()
            {% endif %}

            # Initialize dependency injection
            {% if cookiecutter.use_dependency_injection == 'y' -%}
            self._initialize_container()
            {% endif %}

            # Create ribbon interface
            {% if cookiecutter.create_ribbon_tab == 'y' -%}
            self._create_ribbon_interface(application)
            {% endif %}

            # Register dockable panels
            {% if cookiecutter.create_dockable_panel == 'y' -%}
            self._register_dockable_panels(application)
            {% endif %}

            self.logger.info("{{ cookiecutter.project_name }} add-in started successfully")
            return revitpy.Result.Succeeded

        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to start add-in: {e}", exc_info=True)
            else:
                print(f"Failed to start {{ cookiecutter.project_name }}: {e}")
            return revitpy.Result.Failed

    def OnShutdown(self, application: revitpy.UIControlledApplication) -> revitpy.Result:
        """Called when Revit shuts down.

        Args:
            application: Revit UI controlled application

        Returns:
            Success or failure result
        """
        try:
            if self.logger:
                self.logger.info("Shutting down {{ cookiecutter.project_name }} add-in...")

            # Cleanup dockable panels
            {% if cookiecutter.create_dockable_panel == 'y' -%}
            if self.dockable_panel:
                self.dockable_panel.cleanup()
            {% endif %}

            # Cleanup settings
            {% if cookiecutter.include_settings_manager == 'y' -%}
            if self.settings:
                self.settings.save()
            {% endif %}

            if self.logger:
                self.logger.info("{{ cookiecutter.project_name }} add-in shut down successfully")

            return revitpy.Result.Succeeded

        except Exception as e:
            if self.logger:
                self.logger.error(f"Error during shutdown: {e}", exc_info=True)
            return revitpy.Result.Failed

    {% if cookiecutter.include_logging == 'y' -%}
    def _initialize_logging(self) -> None:
        """Initialize logging system."""
        log_dir = Path.home() / ".{{ cookiecutter.project_slug }}" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        setup_logging(
            log_file=log_dir / "{{ cookiecutter.project_slug }}.log",
            level=logging.INFO,
        )

        self.logger = logging.getLogger(__name__)
    {% endif -%}

    {% if cookiecutter.include_settings_manager == 'y' -%}
    def _initialize_settings(self) -> None:
        """Initialize settings manager."""
        settings_dir = Path.home() / ".{{ cookiecutter.project_slug }}"
        settings_dir.mkdir(parents=True, exist_ok=True)

        self.settings = SettingsManager(
            settings_file=settings_dir / "settings.json"
        )
        self.settings.load()
    {% endif -%}

    {% if cookiecutter.use_dependency_injection == 'y' -%}
    def _initialize_container(self) -> None:
        """Initialize dependency injection container."""
        self.container = Container()

        # Register core services
        if self.logger:
            self.container.register_instance(logging.Logger, self.logger)

        {% if cookiecutter.include_settings_manager == 'y' -%}
        if self.settings:
            self.container.register_instance(SettingsManager, self.settings)
        {% endif %}

        # Register commands
        {% if cookiecutter.create_command_pattern == 'y' -%}
        self.container.register(IExternalCommand, ExampleCommand)
        self.container.register(IExternalCommand, SettingsCommand)
        self.container.register(IExternalCommand, AboutCommand)
        {% endif %}
    {% endif -%}

    {% if cookiecutter.create_ribbon_tab == 'y' -%}
    def _create_ribbon_interface(self, application: revitpy.UIControlledApplication) -> None:
        """Create ribbon tab and buttons.

        Args:
            application: Revit UI controlled application
        """
        # Create ribbon tab
        try:
            application.CreateRibbonTab("{{ cookiecutter.ribbon_tab_name }}")
        except Exception:
            # Tab might already exist
            pass

        # Create ribbon panel
        self.ribbon_panel = application.CreateRibbonPanel(
            "{{ cookiecutter.ribbon_tab_name }}",
            "{{ cookiecutter.project_name }}"
        )

        # Add buttons
        self._add_ribbon_buttons()

    def _add_ribbon_buttons(self) -> None:
        """Add buttons to ribbon panel."""
        {% if cookiecutter.create_command_pattern == 'y' -%}
        # Example command button
        example_button_data = revitpy.UI.PushButtonData(
            "ExampleCmd",
            "Example",
            __file__,
            "{{ cookiecutter.project_slug.replace('-', '_') }}.commands.ExampleCommand"
        )
        example_button_data.ToolTip = "Run example command"
        example_button_data.LongDescription = "Demonstrates basic add-in functionality"

        example_button = self.ribbon_panel.AddItem(example_button_data)

        # Settings command button
        settings_button_data = revitpy.UI.PushButtonData(
            "SettingsCmd",
            "Settings",
            __file__,
            "{{ cookiecutter.project_slug.replace('-', '_') }}.commands.SettingsCommand"
        )
        settings_button_data.ToolTip = "Open settings"
        settings_button_data.LongDescription = "Configure add-in settings"

        settings_button = self.ribbon_panel.AddItem(settings_button_data)

        # Add separator
        self.ribbon_panel.AddSeparator()

        # About command button
        about_button_data = revitpy.UI.PushButtonData(
            "AboutCmd",
            "About",
            __file__,
            "{{ cookiecutter.project_slug.replace('-', '_') }}.commands.AboutCommand"
        )
        about_button_data.ToolTip = "About {{ cookiecutter.project_name }}"
        about_button_data.LongDescription = "Show add-in information"

        about_button = self.ribbon_panel.AddItem(about_button_data)
        {% endif %}
    {% endif -%}

    {% if cookiecutter.create_dockable_panel == 'y' -%}
    def _register_dockable_panels(self, application: revitpy.UIControlledApplication) -> None:
        """Register dockable panels.

        Args:
            application: Revit UI controlled application
        """
        # Register main panel
        main_panel_guid = revitpy.Guid("{{ cookiecutter.assembly_guid | replace('9', 'a') }}")

        application.RegisterDockablePane(
            main_panel_guid,
            "{{ cookiecutter.project_name }} Panel",
            MainPanel()
        )

        self.dockable_panel = MainPanel()
    {% endif %}


# Global application instance
_application_instance: {{ cookiecutter.project_name.replace(' ', '') }}Application = None


def get_application() -> {{ cookiecutter.project_name.replace(' ', '') }}Application:
    """Get the global application instance.

    Returns:
        Application instance
    """
    global _application_instance
    if _application_instance is None:
        _application_instance = {{ cookiecutter.project_name.replace(' ', '') }}Application()
    return _application_instance
