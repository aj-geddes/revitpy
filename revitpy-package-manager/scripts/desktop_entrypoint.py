#!/usr/bin/env python3
"""Desktop registry entrypoint script."""

import logging
import os
import sys
from pathlib import Path

# Add the application to Python path
sys.path.insert(0, "/app")

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("/app/logs/registry.log"),
    ],
)

logger = logging.getLogger(__name__)


def main():
    """Main entrypoint for desktop registry."""

    logger.info("Starting RevitPy Desktop Package Registry...")

    # Environment configuration
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))
    workers = int(os.getenv("WORKERS", 1))

    # Ensure data directories exist
    data_dirs = ["/data/packages", "/data/cache", "/app/logs"]
    for directory in data_dirs:
        Path(directory).mkdir(parents=True, exist_ok=True)
        logger.info(f"Ensured directory exists: {directory}")

    # Import and run the desktop registry
    try:
        import uvicorn
        from revitpy_package_manager.registry.desktop_registry import app

        uvicorn.run(
            app,
            host=host,
            port=port,
            workers=workers,
            access_log=True,
            log_config={
                "version": 1,
                "disable_existing_loggers": False,
                "formatters": {
                    "default": {
                        "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                    },
                },
                "handlers": {
                    "default": {
                        "formatter": "default",
                        "class": "logging.StreamHandler",
                        "stream": "ext://sys.stdout",
                    },
                    "file": {
                        "formatter": "default",
                        "class": "logging.FileHandler",
                        "filename": "/app/logs/uvicorn.log",
                    },
                },
                "root": {
                    "level": os.getenv("LOG_LEVEL", "INFO"),
                    "handlers": ["default", "file"],
                },
            },
        )

    except Exception as e:
        logger.error(f"Failed to start registry: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
