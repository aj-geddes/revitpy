"""Main FastAPI application for the RevitPy package registry."""

from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from ...config import get_settings
from ...security.config import SecurityConfig
from ..database import create_tables
from .routers import admin, auth, health, packages, users


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        description="Enterprise-grade package registry for the RevitPy framework",
        version=settings.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/api/openapi.json",
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.server.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
        allow_headers=["*"],
    )

    # Configure trusted hosts (disabled in debug mode)
    if not settings.server.debug:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=settings.server.trusted_hosts,
        )

    # Add security headers middleware
    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        """Add security headers to all responses."""
        response = await call_next(request)

        # Add security headers
        security_headers = SecurityConfig.get_security_headers()
        for header, value in security_headers.items():
            response.headers[header] = value

        # Remove server header for security
        if "server" in response.headers:
            del response.headers["server"]

        return response

    # Include routers
    app.include_router(health.router, prefix="/api/v1/health", tags=["Health"])

    app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])

    app.include_router(users.router, prefix="/api/v1/users", tags=["Users"])

    app.include_router(packages.router, prefix="/api/v1/packages", tags=["Packages"])

    app.include_router(admin.router, prefix="/api/v1/admin", tags=["Administration"])

    # Global exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """Handle unexpected exceptions."""
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal Server Error",
                "message": "An unexpected error occurred",
                "details": {"type": type(exc).__name__}
                if settings.server.debug
                else None,
            },
        )

    # Startup event
    @app.on_event("startup")
    async def startup_event():
        """Initialize the application on startup."""
        # Create database tables if they don't exist
        await create_tables()

    # Root endpoint
    @app.get("/")
    async def root():
        """Root endpoint with API information."""
        return {
            "name": settings.app_name,
            "version": settings.app_version,
            "description": "Enterprise-grade package registry for the RevitPy framework",
            "docs_url": "/docs",
            "api_base": "/api/v1",
            "timestamp": datetime.utcnow(),
        }

    return app


# Create the application instance
app = create_app()


def main():
    """Main entry point for running the application."""
    import uvicorn

    settings = get_settings()

    uvicorn.run(
        "revitpy_package_manager.registry.api.main:app",
        host=settings.server.host,
        port=settings.server.port,
        reload=settings.server.reload,
        workers=settings.server.workers,
    )


if __name__ == "__main__":
    main()
