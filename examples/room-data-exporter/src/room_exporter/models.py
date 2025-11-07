"""Data models for room export."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class RoomData:
    """Room data model."""

    number: str
    name: str
    area: float
    volume: float
    level: str
    center_x: float = 0.0
    center_y: float = 0.0
    center_z: float = 0.0
    parameters: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self, columns: Optional[List[str]] = None) -> Dict[str, Any]:
        """Convert to dictionary.

        Args:
            columns: List of columns to include (default: all)

        Returns:
            Dictionary representation
        """
        data = {
            "Number": self.number,
            "Name": self.name,
            "Area": self.area,
            "Volume": self.volume,
            "Level": self.level,
            "Center_X": self.center_x,
            "Center_Y": self.center_y,
            "Center_Z": self.center_z,
        }

        # Add parameters
        data.update(self.parameters)

        # Filter columns if specified
        if columns:
            data = {k: v for k, v in data.items() if k in columns}

        return data


@dataclass
class ExportOptions:
    """Export configuration options."""

    include_unplaced: bool = False
    include_unenclosed: bool = False
    include_redundant: bool = False
    filter_level: Optional[str] = None
    filter_department: Optional[str] = None
    custom_filters: Dict[str, Any] = field(default_factory=dict)
    columns: Optional[List[str]] = None
