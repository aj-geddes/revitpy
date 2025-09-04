"""
Bridge configuration management for PyRevit-RevitPy interoperability.
"""

import os
import json
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class CommunicationConfig:
    """Configuration for communication protocols."""
    
    # Named Pipes Configuration
    pipe_name: str = "revitpy_bridge_pipe"
    pipe_timeout: int = 30000  # milliseconds
    pipe_buffer_size: int = 65536
    
    # WebSocket Configuration  
    websocket_host: str = "localhost"
    websocket_port: int = 8765
    websocket_path: str = "/bridge"
    
    # File Exchange Configuration
    exchange_directory: str = str(Path.home() / ".revitpy" / "bridge_exchange")
    file_cleanup_interval: int = 300  # seconds
    max_file_age: int = 3600  # seconds


@dataclass
class SerializationConfig:
    """Configuration for data serialization."""
    
    # Performance settings
    batch_size: int = 1000
    compression_enabled: bool = True
    compression_level: int = 6
    
    # Data handling
    include_geometry: bool = True
    geometry_precision: int = 6
    include_metadata: bool = True
    
    # Memory management
    max_memory_mb: int = 512
    streaming_threshold: int = 5000  # elements


@dataclass
class PerformanceConfig:
    """Configuration for performance optimization."""
    
    # Timeout settings
    analysis_timeout: int = 300  # seconds
    connection_timeout: int = 10  # seconds
    retry_attempts: int = 3
    retry_delay: int = 1  # seconds
    
    # Monitoring
    enable_monitoring: bool = True
    log_performance_metrics: bool = True
    metrics_interval: int = 30  # seconds


@dataclass
class BridgeConfig:
    """Main configuration class for the PyRevit-RevitPy bridge."""
    
    communication: CommunicationConfig = None
    serialization: SerializationConfig = None
    performance: PerformanceConfig = None
    
    # General settings
    debug_mode: bool = False
    log_level: str = "INFO"
    log_file: Optional[str] = None
    
    def __post_init__(self):
        """Initialize sub-configurations if not provided."""
        if self.communication is None:
            self.communication = CommunicationConfig()
        if self.serialization is None:
            self.serialization = SerializationConfig()
        if self.performance is None:
            self.performance = PerformanceConfig()
    
    @classmethod
    def from_file(cls, config_path: str) -> 'BridgeConfig':
        """Load configuration from a JSON file."""
        config_path = Path(config_path)
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        with open(config_path, 'r') as f:
            data = json.load(f)
        
        return cls.from_dict(data)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BridgeConfig':
        """Create configuration from dictionary."""
        communication_data = data.get('communication', {})
        serialization_data = data.get('serialization', {})
        performance_data = data.get('performance', {})
        
        return cls(
            communication=CommunicationConfig(**communication_data),
            serialization=SerializationConfig(**serialization_data),
            performance=PerformanceConfig(**performance_data),
            debug_mode=data.get('debug_mode', False),
            log_level=data.get('log_level', 'INFO'),
            log_file=data.get('log_file')
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            'communication': asdict(self.communication),
            'serialization': asdict(self.serialization),
            'performance': asdict(self.performance),
            'debug_mode': self.debug_mode,
            'log_level': self.log_level,
            'log_file': self.log_file
        }
    
    def save_to_file(self, config_path: str):
        """Save configuration to a JSON file."""
        config_path = Path(config_path)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(config_path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
    
    def get_default_config_path(self) -> Path:
        """Get the default configuration file path."""
        return Path.home() / ".revitpy" / "bridge_config.json"
    
    def validate(self):
        """Validate configuration settings."""
        errors = []
        
        # Validate communication settings
        if self.communication.pipe_timeout <= 0:
            errors.append("Pipe timeout must be positive")
        
        if not (1024 <= self.communication.websocket_port <= 65535):
            errors.append("WebSocket port must be between 1024 and 65535")
        
        # Validate serialization settings
        if self.serialization.batch_size <= 0:
            errors.append("Batch size must be positive")
        
        if not (1 <= self.serialization.compression_level <= 9):
            errors.append("Compression level must be between 1 and 9")
        
        # Validate performance settings
        if self.performance.analysis_timeout <= 0:
            errors.append("Analysis timeout must be positive")
        
        if self.performance.retry_attempts < 0:
            errors.append("Retry attempts cannot be negative")
        
        if errors:
            raise ValueError(f"Configuration validation failed: {'; '.join(errors)}")


def load_default_config() -> BridgeConfig:
    """Load default configuration, with optional override from file."""
    config = BridgeConfig()
    
    # Try to load from default location
    default_path = config.get_default_config_path()
    if default_path.exists():
        try:
            config = BridgeConfig.from_file(str(default_path))
        except Exception as e:
            # Log warning and continue with default config
            print(f"Warning: Failed to load config from {default_path}: {e}")
    
    # Override with environment variables if present
    if os.getenv('REVITPY_BRIDGE_DEBUG'):
        config.debug_mode = os.getenv('REVITPY_BRIDGE_DEBUG').lower() == 'true'
    
    if os.getenv('REVITPY_BRIDGE_LOG_LEVEL'):
        config.log_level = os.getenv('REVITPY_BRIDGE_LOG_LEVEL').upper()
    
    if os.getenv('REVITPY_BRIDGE_WEBSOCKET_PORT'):
        config.communication.websocket_port = int(os.getenv('REVITPY_BRIDGE_WEBSOCKET_PORT'))
    
    return config