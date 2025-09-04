"""
File-based exchange handler for batch processing and large datasets.
"""

import asyncio
import json
import time
import shutil
import gzip
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass
import logging

from ..core.config import CommunicationConfig
from ..core.exceptions import BridgeDataError, BridgeResourceError


@dataclass
class ExchangeFile:
    """Represents a file in the exchange system."""
    
    file_path: Path
    file_type: str  # 'request', 'response', 'data'
    status: str  # 'pending', 'processing', 'completed', 'error'
    created_at: float
    modified_at: float
    size_bytes: int
    checksum: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'file_path': str(self.file_path),
            'file_type': self.file_type,
            'status': self.status,
            'created_at': self.created_at,
            'modified_at': self.modified_at,
            'size_bytes': self.size_bytes,
            'checksum': self.checksum,
            'metadata': self.metadata or {}
        }


class FileExchangeHandler:
    """Handler for file-based data exchange between PyRevit and RevitPy."""
    
    def __init__(self, config: CommunicationConfig):
        """Initialize file exchange handler."""
        self.config = config
        self.logger = logging.getLogger('revitpy_bridge.file_exchange')
        
        # Setup directories
        self.exchange_dir = Path(config.exchange_directory)
        self.request_dir = self.exchange_dir / "requests"
        self.response_dir = self.exchange_dir / "responses"
        self.data_dir = self.exchange_dir / "data"
        self.temp_dir = self.exchange_dir / "temp"
        self.archive_dir = self.exchange_dir / "archive"
        
        self._ensure_directories()
        
        # File tracking
        self.tracked_files: Dict[str, ExchangeFile] = {}
        self.processing_queue: asyncio.Queue = asyncio.Queue()
        
        # Statistics
        self.stats = {
            'files_created': 0,
            'files_processed': 0,
            'files_archived': 0,
            'total_bytes_processed': 0,
            'errors': 0
        }
    
    def _ensure_directories(self):
        """Ensure all required directories exist."""
        directories = [
            self.exchange_dir,
            self.request_dir,
            self.response_dir,
            self.data_dir,
            self.temp_dir,
            self.archive_dir
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
            self.logger.debug(f"Ensured directory exists: {directory}")
    
    async def create_request_file(self, request_data: Dict[str, Any], 
                                 file_id: Optional[str] = None) -> str:
        """Create a request file for processing."""
        try:
            if file_id is None:
                file_id = f"req_{int(time.time())}_{hash(str(request_data)) % 10000:04d}"
            
            # Create request file
            file_path = self.request_dir / f"{file_id}.json"
            
            # Add metadata
            request_data['_metadata'] = {
                'file_id': file_id,
                'created_at': time.time(),
                'file_type': 'request',
                'version': '1.0.0'
            }
            
            # Write file
            await self._write_json_file(file_path, request_data)
            
            # Track file
            exchange_file = ExchangeFile(
                file_path=file_path,
                file_type='request',
                status='pending',
                created_at=time.time(),
                modified_at=time.time(),
                size_bytes=file_path.stat().st_size,
                checksum=await self._calculate_checksum(file_path)
            )
            
            self.tracked_files[file_id] = exchange_file
            self.stats['files_created'] += 1
            
            self.logger.info(f"Created request file: {file_id}")
            return file_id
            
        except Exception as e:
            self.stats['errors'] += 1
            raise BridgeDataError("file_creation", "request", str(e))
    
    async def create_response_file(self, response_data: Dict[str, Any], 
                                  request_id: str) -> str:
        """Create a response file."""
        try:
            response_id = f"resp_{request_id}_{int(time.time())}"
            file_path = self.response_dir / f"{response_id}.json"
            
            # Add metadata
            response_data['_metadata'] = {
                'response_id': response_id,
                'request_id': request_id,
                'created_at': time.time(),
                'file_type': 'response',
                'version': '1.0.0'
            }
            
            # Write file
            await self._write_json_file(file_path, response_data)
            
            # Track file
            exchange_file = ExchangeFile(
                file_path=file_path,
                file_type='response',
                status='completed',
                created_at=time.time(),
                modified_at=time.time(),
                size_bytes=file_path.stat().st_size,
                checksum=await self._calculate_checksum(file_path)
            )
            
            self.tracked_files[response_id] = exchange_file
            self.stats['files_created'] += 1
            
            self.logger.info(f"Created response file: {response_id}")
            return response_id
            
        except Exception as e:
            self.stats['errors'] += 1
            raise BridgeDataError("file_creation", "response", str(e))
    
    async def create_data_file(self, data: Union[Dict[str, Any], bytes], 
                              data_type: str, 
                              file_id: Optional[str] = None,
                              compress: bool = True) -> str:
        """Create a data file for large datasets."""
        try:
            if file_id is None:
                file_id = f"data_{data_type}_{int(time.time())}_{hash(str(data)) % 10000:04d}"
            
            # Determine file extension
            if compress:
                file_ext = ".json.gz" if isinstance(data, dict) else ".dat.gz"
            else:
                file_ext = ".json" if isinstance(data, dict) else ".dat"
            
            file_path = self.data_dir / f"{file_id}{file_ext}"
            
            # Write data
            if isinstance(data, dict):
                # Add metadata
                data['_metadata'] = {
                    'file_id': file_id,
                    'data_type': data_type,
                    'created_at': time.time(),
                    'file_type': 'data',
                    'compressed': compress,
                    'version': '1.0.0'
                }
                
                if compress:
                    await self._write_compressed_json_file(file_path, data)
                else:
                    await self._write_json_file(file_path, data)
            else:
                # Binary data
                if compress:
                    await self._write_compressed_binary_file(file_path, data)
                else:
                    await self._write_binary_file(file_path, data)
            
            # Track file
            exchange_file = ExchangeFile(
                file_path=file_path,
                file_type='data',
                status='completed',
                created_at=time.time(),
                modified_at=time.time(),
                size_bytes=file_path.stat().st_size,
                checksum=await self._calculate_checksum(file_path),
                metadata={'data_type': data_type, 'compressed': compress}
            )
            
            self.tracked_files[file_id] = exchange_file
            self.stats['files_created'] += 1
            self.stats['total_bytes_processed'] += exchange_file.size_bytes
            
            self.logger.info(f"Created data file: {file_id} ({exchange_file.size_bytes} bytes)")
            return file_id
            
        except Exception as e:
            self.stats['errors'] += 1
            raise BridgeDataError("file_creation", "data", str(e))
    
    async def read_file(self, file_id: str) -> Optional[Union[Dict[str, Any], bytes]]:
        """Read file by ID."""
        try:
            if file_id not in self.tracked_files:
                self.logger.warning(f"File not found in tracking: {file_id}")
                return None
            
            exchange_file = self.tracked_files[file_id]
            file_path = exchange_file.file_path
            
            if not file_path.exists():
                self.logger.error(f"File does not exist: {file_path}")
                return None
            
            # Verify checksum if available
            if exchange_file.checksum:
                current_checksum = await self._calculate_checksum(file_path)
                if current_checksum != exchange_file.checksum:
                    self.logger.warning(f"Checksum mismatch for file: {file_id}")
            
            # Read based on file type and compression
            metadata = exchange_file.metadata or {}
            is_compressed = metadata.get('compressed', file_path.suffix.endswith('.gz'))
            
            if file_path.suffix.startswith('.json'):
                if is_compressed:
                    return await self._read_compressed_json_file(file_path)
                else:
                    return await self._read_json_file(file_path)
            else:
                if is_compressed:
                    return await self._read_compressed_binary_file(file_path)
                else:
                    return await self._read_binary_file(file_path)
                    
        except Exception as e:
            self.stats['errors'] += 1
            raise BridgeDataError("file_reading", file_id, str(e))
    
    async def update_file_status(self, file_id: str, status: str, metadata: Optional[Dict[str, Any]] = None):
        """Update file status and metadata."""
        if file_id in self.tracked_files:
            exchange_file = self.tracked_files[file_id]
            exchange_file.status = status
            exchange_file.modified_at = time.time()
            
            if metadata:
                if exchange_file.metadata is None:
                    exchange_file.metadata = {}
                exchange_file.metadata.update(metadata)
            
            self.logger.debug(f"Updated file status: {file_id} -> {status}")
    
    async def list_files(self, file_type: Optional[str] = None, 
                        status: Optional[str] = None) -> List[ExchangeFile]:
        """List tracked files with optional filtering."""
        files = list(self.tracked_files.values())
        
        if file_type:
            files = [f for f in files if f.file_type == file_type]
        
        if status:
            files = [f for f in files if f.status == status]
        
        return files
    
    async def archive_file(self, file_id: str) -> bool:
        """Archive a file to the archive directory."""
        try:
            if file_id not in self.tracked_files:
                return False
            
            exchange_file = self.tracked_files[file_id]
            source_path = exchange_file.file_path
            
            if not source_path.exists():
                return False
            
            # Create archive path with timestamp
            timestamp = int(time.time())
            archive_filename = f"{timestamp}_{source_path.name}"
            archive_path = self.archive_dir / archive_filename
            
            # Move file to archive
            shutil.move(str(source_path), str(archive_path))
            
            # Update tracking
            exchange_file.file_path = archive_path
            exchange_file.status = 'archived'
            exchange_file.modified_at = time.time()
            
            self.stats['files_archived'] += 1
            self.logger.info(f"Archived file: {file_id}")
            
            return True
            
        except Exception as e:
            self.stats['errors'] += 1
            self.logger.error(f"Error archiving file {file_id}: {e}")
            return False
    
    async def delete_file(self, file_id: str) -> bool:
        """Delete a file and remove from tracking."""
        try:
            if file_id not in self.tracked_files:
                return False
            
            exchange_file = self.tracked_files[file_id]
            file_path = exchange_file.file_path
            
            if file_path.exists():
                file_path.unlink()
            
            # Remove from tracking
            del self.tracked_files[file_id]
            
            self.logger.info(f"Deleted file: {file_id}")
            return True
            
        except Exception as e:
            self.stats['errors'] += 1
            self.logger.error(f"Error deleting file {file_id}: {e}")
            return False
    
    async def cleanup_old_files(self):
        """Clean up old files based on age."""
        current_time = time.time()
        max_age = self.config.max_file_age
        
        files_to_archive = []
        files_to_delete = []
        
        for file_id, exchange_file in self.tracked_files.items():
            file_age = current_time - exchange_file.created_at
            
            if file_age > max_age:
                if exchange_file.status == 'archived':
                    files_to_delete.append(file_id)
                elif exchange_file.status in ['completed', 'error']:
                    files_to_archive.append(file_id)
        
        # Archive old files
        for file_id in files_to_archive:
            try:
                await self.archive_file(file_id)
            except Exception as e:
                self.logger.error(f"Error archiving old file {file_id}: {e}")
        
        # Delete very old archived files
        for file_id in files_to_delete:
            try:
                await self.delete_file(file_id)
            except Exception as e:
                self.logger.error(f"Error deleting old archived file {file_id}: {e}")
        
        if files_to_archive or files_to_delete:
            self.logger.info(f"Cleanup completed: {len(files_to_archive)} archived, "
                           f"{len(files_to_delete)} deleted")
    
    async def get_statistics(self) -> Dict[str, Any]:
        """Get file exchange statistics."""
        file_counts = {
            'total': len(self.tracked_files),
            'by_type': {},
            'by_status': {}
        }
        
        for exchange_file in self.tracked_files.values():
            # Count by type
            file_type = exchange_file.file_type
            file_counts['by_type'][file_type] = file_counts['by_type'].get(file_type, 0) + 1
            
            # Count by status
            status = exchange_file.status
            file_counts['by_status'][status] = file_counts['by_status'].get(status, 0) + 1
        
        return {
            **self.stats,
            'file_counts': file_counts,
            'directories': {
                'exchange_dir': str(self.exchange_dir),
                'request_dir': str(self.request_dir),
                'response_dir': str(self.response_dir),
                'data_dir': str(self.data_dir),
                'archive_dir': str(self.archive_dir)
            }
        }
    
    async def _write_json_file(self, file_path: Path, data: Dict[str, Any]):
        """Write JSON data to file."""
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    async def _write_compressed_json_file(self, file_path: Path, data: Dict[str, Any]):
        """Write compressed JSON data to file."""
        json_str = json.dumps(data)
        with gzip.open(file_path, 'wt') as f:
            f.write(json_str)
    
    async def _write_binary_file(self, file_path: Path, data: bytes):
        """Write binary data to file."""
        with open(file_path, 'wb') as f:
            f.write(data)
    
    async def _write_compressed_binary_file(self, file_path: Path, data: bytes):
        """Write compressed binary data to file."""
        with gzip.open(file_path, 'wb') as f:
            f.write(data)
    
    async def _read_json_file(self, file_path: Path) -> Dict[str, Any]:
        """Read JSON data from file."""
        with open(file_path, 'r') as f:
            return json.load(f)
    
    async def _read_compressed_json_file(self, file_path: Path) -> Dict[str, Any]:
        """Read compressed JSON data from file."""
        with gzip.open(file_path, 'rt') as f:
            return json.load(f)
    
    async def _read_binary_file(self, file_path: Path) -> bytes:
        """Read binary data from file."""
        with open(file_path, 'rb') as f:
            return f.read()
    
    async def _read_compressed_binary_file(self, file_path: Path) -> bytes:
        """Read compressed binary data from file."""
        with gzip.open(file_path, 'rb') as f:
            return f.read()
    
    async def _calculate_checksum(self, file_path: Path) -> str:
        """Calculate MD5 checksum of file."""
        hash_md5 = hashlib.md5()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    
    def create_batch_request(self, requests: List[Dict[str, Any]], 
                           batch_id: Optional[str] = None) -> str:
        """Create a batch request file containing multiple requests."""
        if batch_id is None:
            batch_id = f"batch_{int(time.time())}_{len(requests)}"
        
        batch_data = {
            'batch_id': batch_id,
            'batch_type': 'multi_request',
            'request_count': len(requests),
            'requests': requests,
            'created_at': time.time()
        }
        
        return asyncio.run(self.create_request_file(batch_data, batch_id))
    
    def get_exchange_directory(self) -> Path:
        """Get the exchange directory path."""
        return self.exchange_dir