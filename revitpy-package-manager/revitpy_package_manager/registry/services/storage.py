"""Storage service for package files."""

import os
import tempfile
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from pathlib import Path
from typing import BinaryIO, Optional, Union
from urllib.parse import urlparse

import aiofiles
import boto3
from botocore.exceptions import ClientError


class StorageBackend(ABC):
    """Abstract base class for storage backends."""
    
    @abstractmethod
    async def store_file(
        self, 
        key: str, 
        content: Union[bytes, BinaryIO], 
        metadata: Optional[dict] = None
    ) -> str:
        """Store a file and return its path/URL."""
        pass
    
    @abstractmethod
    async def retrieve_file(self, key: str) -> bytes:
        """Retrieve a file's content."""
        pass
    
    @abstractmethod
    async def delete_file(self, key: str) -> bool:
        """Delete a file."""
        pass
    
    @abstractmethod
    async def file_exists(self, key: str) -> bool:
        """Check if a file exists."""
        pass
    
    @abstractmethod
    async def generate_download_url(
        self, 
        key: str, 
        expiration: int = 3600
    ) -> str:
        """Generate a temporary download URL."""
        pass


class LocalStorageBackend(StorageBackend):
    """Local filesystem storage backend."""
    
    def __init__(self, base_path: Union[str, Path]):
        self.base_path = Path(base_path).resolve()
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def _get_file_path(self, key: str) -> Path:
        """Get the full file path for a key."""
        # Ensure the key doesn't escape the base directory
        safe_key = str(Path(key)).replace("..", "")
        return self.base_path / safe_key
    
    async def store_file(
        self, 
        key: str, 
        content: Union[bytes, BinaryIO], 
        metadata: Optional[dict] = None
    ) -> str:
        """Store a file locally."""
        file_path = self._get_file_path(key)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        if isinstance(content, bytes):
            async with aiofiles.open(file_path, 'wb') as f:
                await f.write(content)
        else:
            async with aiofiles.open(file_path, 'wb') as f:
                chunk_size = 8192
                while chunk := content.read(chunk_size):
                    await f.write(chunk)
        
        return str(file_path.relative_to(self.base_path))
    
    async def retrieve_file(self, key: str) -> bytes:
        """Retrieve a file's content."""
        file_path = self._get_file_path(key)
        
        if not file_path.exists():
            raise FileNotFoundError(f"File {key} not found")
        
        async with aiofiles.open(file_path, 'rb') as f:
            return await f.read()
    
    async def delete_file(self, key: str) -> bool:
        """Delete a file."""
        file_path = self._get_file_path(key)
        
        try:
            file_path.unlink()
            return True
        except FileNotFoundError:
            return False
    
    async def file_exists(self, key: str) -> bool:
        """Check if a file exists."""
        file_path = self._get_file_path(key)
        return file_path.exists()
    
    async def generate_download_url(
        self, 
        key: str, 
        expiration: int = 3600
    ) -> str:
        """Generate a local file URL (not time-limited)."""
        file_path = self._get_file_path(key)
        if file_path.exists():
            return f"/files/{key}"
        raise FileNotFoundError(f"File {key} not found")


class S3StorageBackend(StorageBackend):
    """AWS S3 storage backend."""
    
    def __init__(
        self,
        bucket_name: str,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        aws_region: str = "us-east-1",
        endpoint_url: Optional[str] = None
    ):
        self.bucket_name = bucket_name
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=aws_access_key_id or os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=aws_secret_access_key or os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name=aws_region,
            endpoint_url=endpoint_url
        )
        
        # Ensure bucket exists
        self._ensure_bucket_exists()
    
    def _ensure_bucket_exists(self):
        """Ensure the S3 bucket exists."""
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                try:
                    self.s3_client.create_bucket(Bucket=self.bucket_name)
                except ClientError as create_error:
                    raise RuntimeError(f"Failed to create bucket {self.bucket_name}: {create_error}")
            else:
                raise RuntimeError(f"Failed to access bucket {self.bucket_name}: {e}")
    
    async def store_file(
        self, 
        key: str, 
        content: Union[bytes, BinaryIO], 
        metadata: Optional[dict] = None
    ) -> str:
        """Store a file in S3."""
        extra_args = {}
        if metadata:
            extra_args['Metadata'] = {k: str(v) for k, v in metadata.items()}
        
        try:
            if isinstance(content, bytes):
                self.s3_client.put_object(
                    Bucket=self.bucket_name,
                    Key=key,
                    Body=content,
                    **extra_args
                )
            else:
                self.s3_client.upload_fileobj(
                    content,
                    self.bucket_name,
                    key,
                    ExtraArgs=extra_args
                )
            
            return f"s3://{self.bucket_name}/{key}"
            
        except ClientError as e:
            raise RuntimeError(f"Failed to store file {key}: {e}")
    
    async def retrieve_file(self, key: str) -> bytes:
        """Retrieve a file from S3."""
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=key)
            return response['Body'].read()
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                raise FileNotFoundError(f"File {key} not found")
            raise RuntimeError(f"Failed to retrieve file {key}: {e}")
    
    async def delete_file(self, key: str) -> bool:
        """Delete a file from S3."""
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=key)
            return True
        except ClientError:
            return False
    
    async def file_exists(self, key: str) -> bool:
        """Check if a file exists in S3."""
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=key)
            return True
        except ClientError:
            return False
    
    async def generate_download_url(
        self, 
        key: str, 
        expiration: int = 3600
    ) -> str:
        """Generate a presigned download URL."""
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': key},
                ExpiresIn=expiration
            )
            return url
        except ClientError as e:
            raise RuntimeError(f"Failed to generate download URL for {key}: {e}")


class StorageService:
    """Main storage service that delegates to the appropriate backend."""
    
    def __init__(self, backend: Optional[StorageBackend] = None):
        if backend is None:
            backend = self._create_default_backend()
        self.backend = backend
    
    def _create_default_backend(self) -> StorageBackend:
        """Create the default storage backend based on configuration."""
        storage_type = os.getenv('STORAGE_TYPE', 'local').lower()
        
        if storage_type == 's3':
            bucket_name = os.getenv('S3_BUCKET_NAME', 'revitpy-packages')
            aws_region = os.getenv('S3_REGION', 'us-east-1')
            return S3StorageBackend(
                bucket_name=bucket_name,
                aws_region=aws_region
            )
        elif storage_type == 'local':
            base_path = os.getenv('LOCAL_STORAGE_PATH', './storage/packages')
            return LocalStorageBackend(base_path)
        else:
            raise ValueError(f"Unsupported storage type: {storage_type}")
    
    def _generate_package_key(self, package_name: str, version: str, filename: str) -> str:
        """Generate a storage key for a package file."""
        # Normalize package name and create a predictable key structure
        safe_package_name = package_name.lower().replace("_", "-")
        date_path = datetime.utcnow().strftime("%Y/%m")
        return f"packages/{date_path}/{safe_package_name}/{version}/{filename}"
    
    async def store_package(
        self,
        package_name: str,
        version: str,
        filename: str,
        content: Union[bytes, BinaryIO],
        metadata: Optional[dict] = None
    ) -> str:
        """Store a package file."""
        key = self._generate_package_key(package_name, version, filename)
        
        # Add default metadata
        file_metadata = {
            "package_name": package_name,
            "version": version,
            "filename": filename,
            "uploaded_at": datetime.utcnow().isoformat(),
        }
        if metadata:
            file_metadata.update(metadata)
        
        storage_path = await self.backend.store_file(key, content, file_metadata)
        return storage_path
    
    async def retrieve_package(self, storage_path: str) -> bytes:
        """Retrieve a package file."""
        return await self.backend.retrieve_file(storage_path)
    
    async def delete_package(self, storage_path: str) -> bool:
        """Delete a package file."""
        return await self.backend.delete_file(storage_path)
    
    async def package_exists(self, storage_path: str) -> bool:
        """Check if a package file exists."""
        return await self.backend.file_exists(storage_path)
    
    async def generate_download_url(
        self,
        storage_path: str,
        expiration: int = 3600
    ) -> str:
        """Generate a temporary download URL for a package."""
        return await self.backend.generate_download_url(storage_path, expiration)


# Dependency injection for FastAPI
def get_storage_service() -> StorageService:
    """Get the storage service instance."""
    return StorageService()