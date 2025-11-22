"""Client-side package caching system for offline development."""

import asyncio
import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path

import aiofiles
import aiohttp
import packaging.version


@dataclass
class CacheEntry:
    """Represents a cached package entry."""

    package_name: str
    version: str
    file_path: str
    metadata: dict
    file_hash: str
    file_size: int
    cached_at: datetime
    last_accessed: datetime
    access_count: int = 0

    def is_expired(self, ttl_days: int = 7) -> bool:
        """Check if cache entry is expired."""
        return datetime.now() - self.cached_at > timedelta(days=ttl_days)

    def update_access(self):
        """Update access statistics."""
        self.last_accessed = datetime.now()
        self.access_count += 1


@dataclass
class OfflineMetadata:
    """Metadata for offline package information."""

    package_index: dict[str, dict]  # package_name -> package_info
    version_index: dict[str, list[str]]  # package_name -> [versions]
    compatibility_matrix: dict[str, dict]  # package_name -> compatibility info
    last_sync: datetime
    registry_url: str

    def is_stale(self, max_age_hours: int = 24) -> bool:
        """Check if offline metadata is stale."""
        return datetime.now() - self.last_sync > timedelta(hours=max_age_hours)


class DesktopPackageCache:
    """Desktop package cache manager with offline capabilities."""

    def __init__(
        self, cache_dir: str = None, registry_url: str = "http://localhost:8000"
    ):
        self.cache_dir = (
            Path(cache_dir) if cache_dir else Path.home() / ".revitpy" / "cache"
        )
        self.registry_url = registry_url.rstrip("/")

        # Cache structure
        self.packages_dir = self.cache_dir / "packages"
        self.metadata_dir = self.cache_dir / "metadata"
        self.db_path = self.cache_dir / "cache.db"
        self.offline_metadata_path = self.cache_dir / "offline_metadata.json"

        # Ensure directories exist
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.packages_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_dir.mkdir(parents=True, exist_ok=True)

        self.init_database()
        self._session = None

    def init_database(self):
        """Initialize cache database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cache_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    package_name TEXT NOT NULL,
                    version TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    metadata TEXT NOT NULL,
                    file_hash TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    cached_at TIMESTAMP NOT NULL,
                    last_accessed TIMESTAMP NOT NULL,
                    access_count INTEGER DEFAULT 0,

                    UNIQUE(package_name, version)
                )
            """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS download_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    package_name TEXT NOT NULL,
                    version TEXT NOT NULL,
                    priority INTEGER DEFAULT 5,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'pending',  -- pending, downloading, completed, failed
                    error_message TEXT,

                    UNIQUE(package_name, version)
                )
            """
            )

            # Indexes for performance
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_cache_package ON cache_entries(package_name)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_cache_accessed ON cache_entries(last_accessed)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_queue_status ON download_queue(status)"
            )

    async def get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                connector=aiohttp.TCPConnector(limit=10),
            )
        return self._session

    async def close(self):
        """Close the cache manager and cleanup resources."""
        if self._session and not self._session.closed:
            await self._session.close()

    def normalize_name(self, name: str) -> str:
        """Normalize package name for consistent caching."""
        return name.lower().replace("_", "-").replace(" ", "-")

    async def is_package_cached(self, package_name: str, version: str) -> bool:
        """Check if a package version is cached."""
        normalized_name = self.normalize_name(package_name)

        with sqlite3.connect(self.db_path) as conn:
            result = conn.execute(
                "SELECT COUNT(*) FROM cache_entries WHERE package_name = ? AND version = ?",
                (normalized_name, version),
            ).fetchone()
            return result[0] > 0

    async def get_cached_package(
        self, package_name: str, version: str
    ) -> CacheEntry | None:
        """Retrieve a cached package."""
        normalized_name = self.normalize_name(package_name)

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            result = conn.execute(
                """SELECT * FROM cache_entries
                   WHERE package_name = ? AND version = ?""",
                (normalized_name, version),
            ).fetchone()

            if result:
                # Update access statistics
                conn.execute(
                    """UPDATE cache_entries
                       SET last_accessed = ?, access_count = access_count + 1
                       WHERE package_name = ? AND version = ?""",
                    (datetime.now(), normalized_name, version),
                )

                return CacheEntry(
                    package_name=result["package_name"],
                    version=result["version"],
                    file_path=result["file_path"],
                    metadata=json.loads(result["metadata"]),
                    file_hash=result["file_hash"],
                    file_size=result["file_size"],
                    cached_at=datetime.fromisoformat(result["cached_at"]),
                    last_accessed=datetime.fromisoformat(result["last_accessed"]),
                    access_count=result["access_count"],
                )

        return None

    async def cache_package(
        self, package_name: str, version: str, file_content: bytes, metadata: dict
    ) -> CacheEntry:
        """Cache a package file and metadata."""
        normalized_name = self.normalize_name(package_name)

        # Calculate file hash and size
        file_hash = hashlib.sha256(file_content).hexdigest()
        file_size = len(file_content)

        # Create storage path
        package_dir = self.packages_dir / normalized_name
        package_dir.mkdir(parents=True, exist_ok=True)

        file_path = package_dir / f"{version}.rpyx"

        # Write file
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(file_content)

        # Create cache entry
        now = datetime.now()
        entry = CacheEntry(
            package_name=normalized_name,
            version=version,
            file_path=str(file_path),
            metadata=metadata,
            file_hash=file_hash,
            file_size=file_size,
            cached_at=now,
            last_accessed=now,
            access_count=1,
        )

        # Store in database
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO cache_entries
                   (package_name, version, file_path, metadata, file_hash,
                    file_size, cached_at, last_accessed, access_count)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    entry.package_name,
                    entry.version,
                    entry.file_path,
                    json.dumps(entry.metadata),
                    entry.file_hash,
                    entry.file_size,
                    entry.cached_at,
                    entry.last_accessed,
                    entry.access_count,
                ),
            )

        return entry

    async def download_and_cache(
        self, package_name: str, version: str
    ) -> CacheEntry | None:
        """Download a package from registry and cache it."""
        session = await self.get_session()
        normalized_name = self.normalize_name(package_name)

        try:
            # Download package file
            download_url = (
                f"{self.registry_url}/api/packages/{normalized_name}/{version}/download"
            )

            async with session.get(download_url) as response:
                if response.status == 404:
                    return None

                response.raise_for_status()
                file_content = await response.read()

            # Get package metadata
            metadata_url = f"{self.registry_url}/api/packages/{normalized_name}"
            async with session.get(metadata_url) as response:
                response.raise_for_status()
                metadata = await response.json()

            # Cache the package
            entry = await self.cache_package(
                package_name, version, file_content, metadata
            )

            # Update download queue status
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """UPDATE download_queue
                       SET status = 'completed'
                       WHERE package_name = ? AND version = ?""",
                    (normalized_name, version),
                )

            return entry

        except Exception as e:
            # Update download queue with error
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """UPDATE download_queue
                       SET status = 'failed', error_message = ?
                       WHERE package_name = ? AND version = ?""",
                    (str(e), normalized_name, version),
                )

            raise

    async def get_package(
        self, package_name: str, version: str, offline_ok: bool = True
    ) -> CacheEntry | None:
        """Get a package, from cache or by downloading."""

        # Check cache first
        cached = await self.get_cached_package(package_name, version)
        if cached:
            return cached

        # If offline mode and not cached, return None
        if offline_ok:
            try:
                return await self.download_and_cache(package_name, version)
            except Exception:
                return None

        return None

    async def search_packages_offline(
        self, query: str, revit_version: str | None = None
    ) -> list[dict]:
        """Search packages using cached offline metadata."""
        offline_metadata = await self.load_offline_metadata()

        if not offline_metadata or offline_metadata.is_stale():
            # Try to sync metadata if possible
            try:
                await self.sync_metadata()
                offline_metadata = await self.load_offline_metadata()
            except Exception:
                pass  # Continue with stale data if available

        if not offline_metadata:
            return []

        results = []
        query_lower = query.lower()

        for package_name, package_info in offline_metadata.package_index.items():
            # Simple text matching
            if (
                query_lower in package_name.lower()
                or query_lower in package_info.get("summary", "").lower()
                or query_lower in package_info.get("description", "").lower()
            ):
                # Filter by Revit version if specified
                if revit_version:
                    compatibility = offline_metadata.compatibility_matrix.get(
                        package_name, {}
                    )
                    if not self._is_revit_compatible(compatibility, revit_version):
                        continue

                results.append(package_info)

        return results[:20]  # Limit results

    def _is_revit_compatible(self, compatibility: dict, revit_version: str) -> bool:
        """Check if package is compatible with Revit version."""
        for version_info in compatibility.values():
            min_revit = version_info.get("min_revit")
            max_revit = version_info.get("max_revit")

            if min_revit and packaging.version.parse(
                revit_version
            ) < packaging.version.parse(min_revit):
                continue

            if max_revit and packaging.version.parse(
                revit_version
            ) > packaging.version.parse(max_revit):
                continue

            return True

        return False

    async def load_offline_metadata(self) -> OfflineMetadata | None:
        """Load offline metadata from cache."""
        if not self.offline_metadata_path.exists():
            return None

        try:
            async with aiofiles.open(self.offline_metadata_path) as f:
                data = json.loads(await f.read())

                return OfflineMetadata(
                    package_index=data["package_index"],
                    version_index=data["version_index"],
                    compatibility_matrix=data["compatibility_matrix"],
                    last_sync=datetime.fromisoformat(data["last_sync"]),
                    registry_url=data["registry_url"],
                )
        except Exception:
            return None

    async def sync_metadata(self) -> bool:
        """Sync metadata from registry for offline use."""
        session = await self.get_session()

        try:
            # Get popular packages (limited for offline caching)
            search_url = f"{self.registry_url}/api/packages/search?q=*&limit=100"

            async with session.get(search_url) as response:
                response.raise_for_status()
                search_data = await response.json()

            package_index = {}
            version_index = {}
            compatibility_matrix = {}

            # Process each package
            for package in search_data.get("results", []):
                package_name = package["name"]
                normalized_name = self.normalize_name(package_name)

                package_index[normalized_name] = package

                # Get versions and compatibility
                try:
                    package_url = f"{self.registry_url}/api/packages/{normalized_name}"
                    async with session.get(package_url) as pkg_response:
                        pkg_response.raise_for_status()
                        pkg_data = await pkg_response.json()

                        versions = [v["version"] for v in pkg_data.get("versions", [])]
                        version_index[normalized_name] = versions

                    # Get compatibility matrix
                    compat_url = f"{self.registry_url}/api/packages/{normalized_name}/compatibility"
                    async with session.get(compat_url) as compat_response:
                        compat_response.raise_for_status()
                        compat_data = await compat_response.json()
                        compatibility_matrix[normalized_name] = compat_data.get(
                            "compatibility_matrix", {}
                        )

                except Exception:
                    # Continue if individual package fails
                    continue

            # Save offline metadata
            offline_metadata = OfflineMetadata(
                package_index=package_index,
                version_index=version_index,
                compatibility_matrix=compatibility_matrix,
                last_sync=datetime.now(),
                registry_url=self.registry_url,
            )

            async with aiofiles.open(self.offline_metadata_path, "w") as f:
                await f.write(
                    json.dumps(asdict(offline_metadata), default=str, indent=2)
                )

            return True

        except Exception:
            return False

    async def cleanup_cache(
        self, max_size_mb: int = 500, max_age_days: int = 30
    ) -> dict[str, int]:
        """Clean up cache based on size and age constraints."""

        stats = {"removed_files": 0, "freed_bytes": 0, "kept_files": 0}

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            # Get all cache entries sorted by last access
            entries = conn.execute(
                """SELECT * FROM cache_entries
                   ORDER BY last_accessed ASC"""
            ).fetchall()

            total_size = sum(entry["file_size"] for entry in entries)
            max_size_bytes = max_size_mb * 1024 * 1024

            for entry in entries:
                should_remove = False

                # Check age
                cached_at = datetime.fromisoformat(entry["cached_at"])
                if datetime.now() - cached_at > timedelta(days=max_age_days):
                    should_remove = True

                # Check size limits (remove least recently used first)
                if total_size > max_size_bytes:
                    should_remove = True
                    total_size -= entry["file_size"]

                if should_remove:
                    # Remove file
                    file_path = Path(entry["file_path"])
                    if file_path.exists():
                        file_path.unlink()
                        stats["freed_bytes"] += entry["file_size"]
                        stats["removed_files"] += 1

                    # Remove from database
                    conn.execute(
                        "DELETE FROM cache_entries WHERE id = ?", (entry["id"],)
                    )
                else:
                    stats["kept_files"] += 1

        return stats

    async def get_cache_stats(self) -> dict:
        """Get cache statistics."""
        with sqlite3.connect(self.db_path) as conn:
            stats = conn.execute(
                """
                SELECT
                    COUNT(*) as total_packages,
                    SUM(file_size) as total_size,
                    SUM(access_count) as total_accesses,
                    AVG(access_count) as avg_accesses
                FROM cache_entries
            """
            ).fetchone()

            recent_stats = conn.execute(
                """
                SELECT COUNT(*) as recent_accesses
                FROM cache_entries
                WHERE last_accessed > datetime('now', '-7 days')
            """
            ).fetchone()

        return {
            "total_packages": stats[0] or 0,
            "total_size_mb": round((stats[1] or 0) / 1024 / 1024, 2),
            "total_accesses": stats[2] or 0,
            "avg_accesses": round(stats[3] or 0, 2),
            "recent_accesses": recent_stats[0] or 0,
            "cache_directory": str(self.cache_dir),
        }

    async def preload_packages(
        self, package_list: list[tuple[str, str]], max_concurrent: int = 5
    ) -> dict:
        """Preload multiple packages for offline use."""

        semaphore = asyncio.Semaphore(max_concurrent)
        results = {"successful": [], "failed": []}

        async def download_package(package_name: str, version: str):
            async with semaphore:
                try:
                    entry = await self.download_and_cache(package_name, version)
                    if entry:
                        results["successful"].append((package_name, version))
                    else:
                        results["failed"].append(
                            (package_name, version, "Package not found")
                        )
                except Exception as e:
                    results["failed"].append((package_name, version, str(e)))

        tasks = [download_package(name, version) for name, version in package_list]
        await asyncio.gather(*tasks, return_exceptions=True)

        return results


# Global cache instance
default_cache = DesktopPackageCache()


async def get_cache() -> DesktopPackageCache:
    """Get the default cache instance."""
    return default_cache
