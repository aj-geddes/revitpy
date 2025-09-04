"""Simplified desktop-focused RevitPy package registry.

This replaces the complex microservices architecture with a simple web application
optimized for desktop framework distribution and CLI integration.
"""

import hashlib
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union
import json
import asyncio
from dataclasses import dataclass, asdict
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, UploadFile, File, Query, Depends
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import aiofiles
from pydantic import BaseModel, Field
import packaging.version


@dataclass
class RevitVersionCompatibility:
    """Revit version compatibility information."""
    min_version: str
    max_version: Optional[str] = None
    tested_versions: List[str] = None
    known_issues: List[str] = None
    
    def __post_init__(self):
        if self.tested_versions is None:
            self.tested_versions = []
        if self.known_issues is None:
            self.known_issues = []


@dataclass
class PackageMetadata:
    """Desktop-optimized package metadata."""
    name: str
    version: str
    summary: str
    description: str
    author: str
    author_email: str
    license: str
    homepage_url: Optional[str] = None
    repository_url: Optional[str] = None
    documentation_url: Optional[str] = None
    
    # Desktop-specific fields
    revit_compatibility: RevitVersionCompatibility = None
    package_type: str = "addon"  # addon, library, template, tool
    installation_size: int = 0  # bytes
    performance_impact: str = "low"  # low, medium, high
    requires_admin: bool = False
    
    # Security metadata
    security_scan_status: str = "pending"  # pending, passed, failed, warning
    security_scan_date: Optional[str] = None
    digital_signature: Optional[str] = None
    
    # Dependencies
    dependencies: List[Dict[str, str]] = None
    revit_dependencies: List[str] = None  # Required Revit components
    
    # Installation metadata
    install_hooks: Dict[str, str] = None  # pre_install, post_install scripts
    uninstall_hooks: Dict[str, str] = None
    file_associations: List[str] = None  # File extensions this package handles
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []
        if self.revit_dependencies is None:
            self.revit_dependencies = []
        if self.install_hooks is None:
            self.install_hooks = {}
        if self.uninstall_hooks is None:
            self.uninstall_hooks = {}
        if self.file_associations is None:
            self.file_associations = []


class DesktopPackageRegistry:
    """Simplified package registry for desktop distribution."""
    
    def __init__(self, storage_path: str = "./registry_data"):
        self.storage_path = Path(storage_path)
        self.db_path = self.storage_path / "registry.db"
        self.packages_path = self.storage_path / "packages"
        self.cache_path = self.storage_path / "cache"
        
        # Ensure directories exist
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.packages_path.mkdir(parents=True, exist_ok=True)
        self.cache_path.mkdir(parents=True, exist_ok=True)
        
        self.init_database()
    
    def init_database(self):
        """Initialize SQLite database with desktop-optimized schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS packages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    normalized_name TEXT UNIQUE NOT NULL,
                    summary TEXT,
                    description TEXT,
                    homepage_url TEXT,
                    repository_url TEXT,
                    documentation_url TEXT,
                    download_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS package_versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    package_id INTEGER NOT NULL,
                    version TEXT NOT NULL,
                    summary TEXT,
                    description TEXT,
                    author TEXT,
                    author_email TEXT,
                    license TEXT,
                    
                    -- Desktop-specific fields
                    package_type TEXT DEFAULT 'addon',
                    installation_size INTEGER DEFAULT 0,
                    performance_impact TEXT DEFAULT 'low',
                    requires_admin BOOLEAN DEFAULT FALSE,
                    
                    -- Revit compatibility
                    min_revit_version TEXT,
                    max_revit_version TEXT,
                    tested_revit_versions TEXT, -- JSON array
                    known_issues TEXT, -- JSON array
                    
                    -- Security
                    security_scan_status TEXT DEFAULT 'pending',
                    security_scan_date TIMESTAMP,
                    digital_signature TEXT,
                    
                    -- File information
                    filename TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    file_hash_sha256 TEXT NOT NULL,
                    storage_path TEXT NOT NULL,
                    
                    -- Metadata
                    dependencies TEXT, -- JSON
                    revit_dependencies TEXT, -- JSON array
                    install_hooks TEXT, -- JSON
                    uninstall_hooks TEXT, -- JSON
                    file_associations TEXT, -- JSON array
                    
                    download_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    
                    UNIQUE(package_id, version),
                    FOREIGN KEY (package_id) REFERENCES packages (id)
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS download_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    package_id INTEGER NOT NULL,
                    version_id INTEGER,
                    client_info TEXT,
                    revit_version TEXT,
                    os_info TEXT,
                    download_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    
                    FOREIGN KEY (package_id) REFERENCES packages (id),
                    FOREIGN KEY (version_id) REFERENCES package_versions (id)
                )
            """)
            
            # Indexes for performance
            conn.execute("CREATE INDEX IF NOT EXISTS idx_packages_name ON packages(normalized_name)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_versions_package ON package_versions(package_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_versions_revit ON package_versions(min_revit_version, max_revit_version)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_stats_package ON download_stats(package_id)")
    
    @staticmethod
    def normalize_name(name: str) -> str:
        """Normalize package name for consistent lookup."""
        return name.lower().replace("_", "-").replace(" ", "-")
    
    async def search_packages(
        self, 
        query: str, 
        revit_version: Optional[str] = None,
        package_type: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict]:
        """Search packages with desktop-optimized filtering."""
        
        sql = """
            SELECT DISTINCT p.*, pv.version as latest_version,
                   pv.package_type, pv.performance_impact,
                   pv.min_revit_version, pv.max_revit_version
            FROM packages p
            LEFT JOIN package_versions pv ON p.id = pv.package_id
            WHERE (p.name LIKE ? OR p.summary LIKE ? OR p.description LIKE ?)
        """
        params = [f"%{query}%", f"%{query}%", f"%{query}%"]
        
        # Add Revit version filtering
        if revit_version:
            sql += """ AND (
                pv.min_revit_version IS NULL OR ? >= pv.min_revit_version
            ) AND (
                pv.max_revit_version IS NULL OR ? <= pv.max_revit_version
            )"""
            params.extend([revit_version, revit_version])
        
        # Add package type filtering
        if package_type:
            sql += " AND pv.package_type = ?"
            params.append(package_type)
        
        sql += " ORDER BY p.download_count DESC LIMIT ?"
        params.append(limit)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(sql, params)
            return [dict(row) for row in cursor.fetchall()]
    
    async def get_package_details(self, package_name: str) -> Optional[Dict]:
        """Get detailed package information."""
        normalized_name = self.normalize_name(package_name)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            # Get package info
            package = conn.execute(
                "SELECT * FROM packages WHERE normalized_name = ?",
                (normalized_name,)
            ).fetchone()
            
            if not package:
                return None
            
            # Get all versions
            versions = conn.execute(
                """SELECT * FROM package_versions 
                   WHERE package_id = ? 
                   ORDER BY created_at DESC""",
                (package["id"],)
            ).fetchall()
            
            return {
                "package": dict(package),
                "versions": [dict(v) for v in versions]
            }
    
    async def get_compatibility_matrix(self, package_name: str) -> Dict:
        """Get Revit version compatibility matrix for a package."""
        normalized_name = self.normalize_name(package_name)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            package = conn.execute(
                "SELECT id FROM packages WHERE normalized_name = ?",
                (normalized_name,)
            ).fetchone()
            
            if not package:
                raise HTTPException(status_code=404, detail="Package not found")
            
            versions = conn.execute(
                """SELECT version, min_revit_version, max_revit_version,
                          tested_revit_versions, known_issues
                   FROM package_versions 
                   WHERE package_id = ?
                   ORDER BY version DESC""",
                (package["id"],)
            ).fetchall()
            
            compatibility = {}
            for version in versions:
                compatibility[version["version"]] = {
                    "min_revit": version["min_revit_version"],
                    "max_revit": version["max_revit_version"],
                    "tested_versions": json.loads(version["tested_revit_versions"] or "[]"),
                    "known_issues": json.loads(version["known_issues"] or "[]")
                }
            
            return compatibility
    
    async def store_package(
        self, 
        package_file: UploadFile, 
        metadata: PackageMetadata
    ) -> Dict:
        """Store a package with desktop-optimized validation."""
        
        # Validate file format (.rpyx)
        if not package_file.filename.endswith('.rpyx'):
            raise HTTPException(
                status_code=400, 
                detail="Package must be in .rpyx format"
            )
        
        # Read file content
        content = await package_file.read()
        file_size = len(content)
        
        # Calculate hash
        sha256_hash = hashlib.sha256(content).hexdigest()
        
        # Store file
        normalized_name = self.normalize_name(metadata.name)
        package_dir = self.packages_path / normalized_name
        package_dir.mkdir(parents=True, exist_ok=True)
        
        filename = f"{metadata.name}-{metadata.version}.rpyx"
        file_path = package_dir / filename
        
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(content)
        
        # Store in database
        with sqlite3.connect(self.db_path) as conn:
            # Insert or get package
            cursor = conn.execute(
                """INSERT OR IGNORE INTO packages 
                   (name, normalized_name, summary, description, homepage_url, 
                    repository_url, documentation_url)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (metadata.name, normalized_name, metadata.summary, 
                 metadata.description, metadata.homepage_url,
                 metadata.repository_url, metadata.documentation_url)
            )
            
            package_id = cursor.lastrowid or conn.execute(
                "SELECT id FROM packages WHERE normalized_name = ?",
                (normalized_name,)
            ).fetchone()[0]
            
            # Insert version
            conn.execute(
                """INSERT INTO package_versions
                   (package_id, version, summary, description, author, author_email,
                    license, package_type, installation_size, performance_impact,
                    requires_admin, min_revit_version, max_revit_version,
                    tested_revit_versions, known_issues, filename, file_size,
                    file_hash_sha256, storage_path, dependencies, revit_dependencies,
                    install_hooks, uninstall_hooks, file_associations)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (package_id, metadata.version, metadata.summary, metadata.description,
                 metadata.author, metadata.author_email, metadata.license,
                 metadata.package_type, metadata.installation_size, metadata.performance_impact,
                 metadata.requires_admin, 
                 metadata.revit_compatibility.min_version if metadata.revit_compatibility else None,
                 metadata.revit_compatibility.max_version if metadata.revit_compatibility else None,
                 json.dumps(metadata.revit_compatibility.tested_versions) if metadata.revit_compatibility else "[]",
                 json.dumps(metadata.revit_compatibility.known_issues) if metadata.revit_compatibility else "[]",
                 filename, file_size, sha256_hash, str(file_path),
                 json.dumps(metadata.dependencies), json.dumps(metadata.revit_dependencies),
                 json.dumps(metadata.install_hooks), json.dumps(metadata.uninstall_hooks),
                 json.dumps(metadata.file_associations))
            )
        
        return {
            "package_name": metadata.name,
            "version": metadata.version,
            "file_hash": sha256_hash,
            "file_size": file_size,
            "storage_path": str(file_path)
        }
    
    async def get_download_url(self, package_name: str, version: str) -> str:
        """Get download URL for a package version."""
        normalized_name = self.normalize_name(package_name)
        
        with sqlite3.connect(self.db_path) as conn:
            result = conn.execute(
                """SELECT pv.storage_path, pv.filename
                   FROM packages p
                   JOIN package_versions pv ON p.id = pv.package_id
                   WHERE p.normalized_name = ? AND pv.version = ?""",
                (normalized_name, version)
            ).fetchone()
            
            if not result:
                raise HTTPException(status_code=404, detail="Package version not found")
            
            # Update download count
            conn.execute(
                """UPDATE packages SET download_count = download_count + 1
                   WHERE normalized_name = ?""",
                (normalized_name,)
            )
            
            conn.execute(
                """UPDATE package_versions SET download_count = download_count + 1
                   WHERE package_id = (SELECT id FROM packages WHERE normalized_name = ?)
                   AND version = ?""",
                (normalized_name, version)
            )
        
        return result[0]


# API Models
class PackageSearchRequest(BaseModel):
    q: str = Field(..., min_length=1, description="Search query")
    revit_version: Optional[str] = Field(None, description="Filter by Revit version")
    package_type: Optional[str] = Field(None, description="Filter by package type")
    limit: int = Field(20, ge=1, le=50, description="Maximum results")


class PackageUploadRequest(BaseModel):
    name: str
    version: str
    summary: str
    description: str
    author: str
    author_email: str
    license: str
    homepage_url: Optional[str] = None
    repository_url: Optional[str] = None
    documentation_url: Optional[str] = None
    package_type: str = "addon"
    performance_impact: str = "low"
    requires_admin: bool = False
    min_revit_version: Optional[str] = None
    max_revit_version: Optional[str] = None
    tested_revit_versions: List[str] = []
    dependencies: List[Dict[str, str]] = []
    revit_dependencies: List[str] = []


# Global registry instance
registry = DesktopPackageRegistry()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    print("Starting desktop package registry...")
    yield
    # Shutdown
    print("Shutting down...")


# Create FastAPI app
def create_desktop_registry_app() -> FastAPI:
    """Create simplified desktop registry application."""
    
    app = FastAPI(
        title="RevitPy Desktop Package Registry",
        description="Simplified package registry optimized for desktop framework distribution",
        version="2.0.0",
        lifespan=lifespan
    )
    
    # CORS for desktop clients
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Allow all origins for desktop clients
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["*"],
    )
    
    return app


app = create_desktop_registry_app()


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "RevitPy Desktop Package Registry",
        "version": "2.0.0",
        "description": "Simplified registry optimized for desktop distribution",
        "endpoints": {
            "search": "/api/packages/search",
            "package_details": "/api/packages/{name}",
            "compatibility": "/api/packages/{name}/compatibility",
            "download": "/api/packages/{name}/{version}/download",
            "upload": "/api/packages/upload"
        }
    }


@app.get("/api/packages/search")
async def search_packages(
    q: str = Query(..., min_length=1),
    revit_version: Optional[str] = Query(None),
    package_type: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=50)
):
    """Fast package search optimized for CLI integration."""
    results = await registry.search_packages(q, revit_version, package_type, limit)
    
    return {
        "query": q,
        "results": results,
        "total": len(results),
        "filters": {
            "revit_version": revit_version,
            "package_type": package_type
        }
    }


@app.get("/api/packages/{package_name}")
async def get_package_details(package_name: str):
    """Get detailed package information."""
    details = await registry.get_package_details(package_name)
    if not details:
        raise HTTPException(status_code=404, detail="Package not found")
    
    return details


@app.get("/api/packages/{package_name}/compatibility")
async def get_compatibility_matrix(package_name: str):
    """Get Revit version compatibility matrix."""
    compatibility = await registry.get_compatibility_matrix(package_name)
    return {
        "package": package_name,
        "compatibility_matrix": compatibility
    }


@app.get("/api/packages/{package_name}/{version}/download")
async def download_package(package_name: str, version: str):
    """Download a package version."""
    file_path = await registry.get_download_url(package_name, version)
    
    if not Path(file_path).exists():
        raise HTTPException(status_code=404, detail="Package file not found")
    
    return FileResponse(
        path=file_path,
        filename=f"{package_name}-{version}.rpyx",
        media_type="application/octet-stream"
    )


@app.post("/api/packages/upload")
async def upload_package(
    file: UploadFile = File(...),
    metadata: str = Query(..., description="Package metadata as JSON")
):
    """Upload a new package version."""
    try:
        metadata_dict = json.loads(metadata)
        
        # Create RevitVersionCompatibility object
        compat_data = metadata_dict.get("revit_compatibility", {})
        revit_compat = RevitVersionCompatibility(
            min_version=compat_data.get("min_version"),
            max_version=compat_data.get("max_version"),
            tested_versions=compat_data.get("tested_versions", []),
            known_issues=compat_data.get("known_issues", [])
        ) if compat_data else None
        
        # Create PackageMetadata object
        package_metadata = PackageMetadata(
            name=metadata_dict["name"],
            version=metadata_dict["version"],
            summary=metadata_dict["summary"],
            description=metadata_dict["description"],
            author=metadata_dict["author"],
            author_email=metadata_dict["author_email"],
            license=metadata_dict["license"],
            homepage_url=metadata_dict.get("homepage_url"),
            repository_url=metadata_dict.get("repository_url"),
            documentation_url=metadata_dict.get("documentation_url"),
            revit_compatibility=revit_compat,
            package_type=metadata_dict.get("package_type", "addon"),
            performance_impact=metadata_dict.get("performance_impact", "low"),
            requires_admin=metadata_dict.get("requires_admin", False),
            dependencies=metadata_dict.get("dependencies", []),
            revit_dependencies=metadata_dict.get("revit_dependencies", [])
        )
        
        result = await registry.store_package(file, package_metadata)
        return result
        
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid metadata JSON")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stats")
async def get_registry_stats():
    """Get registry statistics."""
    with sqlite3.connect(registry.db_path) as conn:
        stats = conn.execute("""
            SELECT 
                COUNT(DISTINCT p.id) as total_packages,
                COUNT(pv.id) as total_versions,
                SUM(p.download_count) as total_downloads,
                COUNT(DISTINCT pv.package_type) as package_types
            FROM packages p
            LEFT JOIN package_versions pv ON p.id = pv.package_id
        """).fetchone()
        
        return {
            "total_packages": stats[0] or 0,
            "total_versions": stats[1] or 0,
            "total_downloads": stats[2] or 0,
            "package_types": stats[3] or 0
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)