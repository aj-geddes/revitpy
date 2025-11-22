"""
High-performance serialization of Revit elements for cross-platform exchange.
"""

import gzip
import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..core.config import SerializationConfig
from ..core.exceptions import BridgeDataError, BridgeResourceError
from .geometry_serializer import GeometrySerializer
from .parameter_serializer import ParameterSerializer


@dataclass
class SerializationMetadata:
    """Metadata for serialized element data."""

    timestamp: float
    element_count: int
    serialization_version: str
    data_hash: str
    compression_used: bool
    total_size_bytes: int
    geometry_included: bool
    parameters_included: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "element_count": self.element_count,
            "serialization_version": self.serialization_version,
            "data_hash": self.data_hash,
            "compression_used": self.compression_used,
            "total_size_bytes": self.total_size_bytes,
            "geometry_included": self.geometry_included,
            "parameters_included": self.parameters_included,
        }


class RevitElementSerializer:
    """High-performance serializer for Revit elements with optimization for large datasets."""

    SERIALIZATION_VERSION = "1.0.0"

    def __init__(self, config: SerializationConfig):
        """Initialize the serializer with configuration."""
        self.config = config
        self.geometry_serializer = GeometrySerializer(config)
        self.parameter_serializer = ParameterSerializer(config)

        # Performance tracking
        self.serialization_stats = {
            "total_elements_serialized": 0,
            "total_bytes_processed": 0,
            "average_serialization_time": 0.0,
            "compression_ratio": 0.0,
        }

    def serialize_elements(
        self,
        elements: list[Any],
        output_path: str | None = None,
        streaming: bool = False,
    ) -> dict[str, Any] | str:
        """
        Serialize a list of Revit elements to JSON format.

        Args:
            elements: List of Revit elements to serialize
            output_path: Optional file path for output
            streaming: Whether to use streaming for large datasets

        Returns:
            Dictionary of serialized data or file path if output_path specified
        """
        start_time = time.time()

        try:
            # Check if streaming is needed
            element_count = len(elements)
            use_streaming = (
                streaming or element_count >= self.config.streaming_threshold
            )

            if use_streaming:
                return self._serialize_streaming(elements, output_path)
            else:
                return self._serialize_batch(elements, output_path)

        except Exception as e:
            raise BridgeDataError("serialization", "elements", str(e))
        finally:
            # Update performance stats
            execution_time = time.time() - start_time
            self._update_serialization_stats(len(elements), execution_time)

    def _serialize_batch(
        self, elements: list[Any], output_path: str | None = None
    ) -> dict[str, Any] | str:
        """Serialize elements in batch mode."""
        serialized_elements = []

        for element in elements:
            try:
                serialized_element = self._serialize_single_element(element)
                serialized_elements.append(serialized_element)
            except Exception as e:
                # Log error but continue with other elements
                print(
                    f"Warning: Failed to serialize element {getattr(element, 'Id', 'unknown')}: {e}"
                )
                continue

        # Create serialization result
        serialized_data = {
            "elements": serialized_elements,
            "metadata": self._create_metadata(serialized_elements).to_dict(),
        }

        # Apply compression if enabled
        if self.config.compression_enabled:
            serialized_data = self._compress_data(serialized_data)

        # Save to file if path specified
        if output_path:
            self._save_to_file(serialized_data, output_path)
            return output_path

        return serialized_data

    def _serialize_streaming(
        self, elements: list[Any], output_path: str | None = None
    ) -> str:
        """Serialize elements using streaming for large datasets."""
        if not output_path:
            # Generate temporary file for streaming
            timestamp = int(time.time())
            output_path = f"/tmp/revitpy_bridge_streaming_{timestamp}.json"

        output_file = Path(output_path)
        batch_size = self.config.batch_size

        with open(output_file, "w") as f:
            # Write opening structure
            f.write('{"elements": [')

            first_batch = True
            total_elements = 0

            # Process in batches
            for i in range(0, len(elements), batch_size):
                batch = elements[i : i + batch_size]
                serialized_batch = []

                for element in batch:
                    try:
                        serialized_element = self._serialize_single_element(element)
                        serialized_batch.append(serialized_element)
                        total_elements += 1
                    except Exception as e:
                        print(
                            f"Warning: Failed to serialize element in streaming mode: {e}"
                        )
                        continue

                # Write batch to file
                if serialized_batch:
                    if not first_batch:
                        f.write(",")

                    batch_json = json.dumps(serialized_batch)[
                        1:-1
                    ]  # Remove array brackets
                    f.write(batch_json)
                    first_batch = False

                # Check memory usage
                self._check_memory_usage()

            # Write metadata
            metadata = SerializationMetadata(
                timestamp=time.time(),
                element_count=total_elements,
                serialization_version=self.SERIALIZATION_VERSION,
                data_hash="streaming_mode",
                compression_used=False,
                total_size_bytes=output_file.stat().st_size,
                geometry_included=self.config.include_geometry,
                parameters_included=True,
            )

            f.write(f'], "metadata": {json.dumps(metadata.to_dict())}}}')

        # Apply compression to file if enabled
        if self.config.compression_enabled:
            compressed_path = output_path + ".gz"
            with open(output_path, "rb") as f_in:
                with gzip.open(compressed_path, "wb") as f_out:
                    f_out.write(f_in.read())

            # Remove uncompressed file
            output_file.unlink()
            return compressed_path

        return output_path

    def _serialize_single_element(self, element: Any) -> dict[str, Any]:
        """Serialize a single Revit element."""
        try:
            # Basic element information
            serialized = {
                "id": self._get_element_id(element),
                "category": self._get_element_category(element),
                "name": self._get_element_name(element),
                "type": self._get_element_type(element),
            }

            # Parameters
            if hasattr(element, "Parameters"):
                serialized["parameters"] = (
                    self.parameter_serializer.serialize_parameters(element.Parameters)
                )

            # Geometry (if enabled and available)
            if self.config.include_geometry and hasattr(element, "Geometry"):
                try:
                    serialized["geometry"] = (
                        self.geometry_serializer.serialize_geometry(element.Geometry)
                    )
                except Exception as e:
                    # Geometry serialization can fail, continue without it
                    serialized["geometry"] = {
                        "error": f"Geometry serialization failed: {e}"
                    }

            # Location information
            if hasattr(element, "Location"):
                serialized["location"] = self._serialize_location(element.Location)

            # Metadata (if enabled)
            if self.config.include_metadata:
                serialized["metadata"] = self._extract_element_metadata(element)

            return serialized

        except Exception as e:
            # Return minimal element data on error
            return {
                "id": self._get_element_id(element),
                "error": f"Serialization failed: {e}",
                "partial_data": True,
            }

    def _get_element_id(self, element: Any) -> int | str:
        """Extract element ID safely."""
        if hasattr(element, "Id"):
            if hasattr(element.Id, "IntegerValue"):
                return element.Id.IntegerValue
            return str(element.Id)
        return "unknown"

    def _get_element_category(self, element: Any) -> str:
        """Extract element category safely."""
        if hasattr(element, "Category") and element.Category:
            if hasattr(element.Category, "Name"):
                return element.Category.Name
        return "unknown"

    def _get_element_name(self, element: Any) -> str:
        """Extract element name safely."""
        if hasattr(element, "Name") and element.Name:
            return element.Name
        return "unnamed"

    def _get_element_type(self, element: Any) -> str:
        """Extract element type safely."""
        return type(element).__name__

    def _serialize_location(self, location: Any) -> dict[str, Any]:
        """Serialize element location."""
        try:
            location_data = {"type": type(location).__name__}

            # Point location
            if hasattr(location, "Point"):
                point = location.Point
                location_data["point"] = {
                    "x": round(point.X, self.config.geometry_precision),
                    "y": round(point.Y, self.config.geometry_precision),
                    "z": round(point.Z, self.config.geometry_precision),
                }

            # Curve location
            if hasattr(location, "Curve"):
                location_data["curve"] = self.geometry_serializer.serialize_curve(
                    location.Curve
                )

            return location_data

        except Exception as e:
            return {"error": f"Location serialization failed: {e}"}

    def _extract_element_metadata(self, element: Any) -> dict[str, Any]:
        """Extract additional element metadata."""
        metadata = {}

        try:
            # Element properties
            if hasattr(element, "Level"):
                metadata["level"] = element.Level.Name if element.Level else None

            if hasattr(element, "Phase"):
                metadata["phase"] = element.Phase.Name if element.Phase else None

            if hasattr(element, "WorksetId"):
                metadata["workset_id"] = element.WorksetId.IntegerValue

            # Design options
            if hasattr(element, "DesignOption"):
                metadata["design_option"] = (
                    element.DesignOption.Name if element.DesignOption else None
                )

            # Creation info
            if hasattr(element, "CreatedPhaseId"):
                metadata["created_phase_id"] = element.CreatedPhaseId.IntegerValue

            if hasattr(element, "DemolishedPhaseId"):
                metadata["demolished_phase_id"] = element.DemolishedPhaseId.IntegerValue

        except Exception as e:
            metadata["extraction_error"] = str(e)

        return metadata

    def _create_metadata(
        self, serialized_elements: list[dict[str, Any]]
    ) -> SerializationMetadata:
        """Create metadata for serialized data."""
        data_str = json.dumps(serialized_elements)
        data_hash = hashlib.md5(data_str.encode()).hexdigest()

        return SerializationMetadata(
            timestamp=time.time(),
            element_count=len(serialized_elements),
            serialization_version=self.SERIALIZATION_VERSION,
            data_hash=data_hash,
            compression_used=self.config.compression_enabled,
            total_size_bytes=len(data_str.encode()),
            geometry_included=self.config.include_geometry,
            parameters_included=True,
        )

    def _compress_data(self, data: dict[str, Any]) -> dict[str, Any]:
        """Compress serialized data if enabled."""
        try:
            json_str = json.dumps(data)
            original_size = len(json_str.encode())

            compressed = gzip.compress(
                json_str.encode(), compresslevel=self.config.compression_level
            )
            compressed_size = len(compressed)

            # Update compression ratio stats
            self.serialization_stats["compression_ratio"] = (
                compressed_size / original_size
            )

            return {
                "compressed_data": compressed.hex(),
                "original_size": original_size,
                "compressed_size": compressed_size,
                "compression_used": True,
            }

        except Exception as e:
            # Return uncompressed data on error
            print(f"Warning: Compression failed, using uncompressed data: {e}")
            return data

    def _save_to_file(self, data: dict[str, Any], file_path: str):
        """Save serialized data to file."""
        output_path = Path(file_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            json.dump(
                data, f, indent=2 if not self.config.compression_enabled else None
            )

    def _check_memory_usage(self):
        """Check memory usage and raise error if limit exceeded."""
        try:
            import psutil

            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024

            if memory_mb > self.config.max_memory_mb:
                raise BridgeResourceError(
                    "memory", f"{self.config.max_memory_mb}MB", f"{memory_mb:.1f}MB"
                )
        except ImportError:
            # psutil not available, skip check
            pass

    def deserialize_elements(
        self, data: dict[str, Any] | str | Path
    ) -> list[dict[str, Any]]:
        """
        Deserialize elements from JSON data or file.

        Args:
            data: Serialized data, file path, or Path object

        Returns:
            List of deserialized element dictionaries
        """
        try:
            # Handle different input types
            if isinstance(data, str | Path):
                data_dict = self._load_from_file(data)
            else:
                data_dict = data

            # Handle compressed data
            if "compressed_data" in data_dict:
                data_dict = self._decompress_data(data_dict)

            # Extract elements
            elements = data_dict.get("elements", [])
            metadata = data_dict.get("metadata", {})

            # Validate metadata
            self._validate_deserialization_metadata(metadata)

            return elements

        except Exception as e:
            raise BridgeDataError("deserialization", "elements", str(e))

    def _load_from_file(self, file_path: str | Path) -> dict[str, Any]:
        """Load serialized data from file."""
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"Serialization file not found: {file_path}")

        # Handle compressed files
        if file_path.suffix == ".gz":
            with gzip.open(file_path, "rt") as f:
                return json.load(f)
        else:
            with open(file_path) as f:
                return json.load(f)

    def _decompress_data(self, compressed_data: dict[str, Any]) -> dict[str, Any]:
        """Decompress data."""
        try:
            hex_data = compressed_data["compressed_data"]
            compressed_bytes = bytes.fromhex(hex_data)
            decompressed_str = gzip.decompress(compressed_bytes).decode()
            return json.loads(decompressed_str)
        except Exception as e:
            raise BridgeDataError("decompression", "compressed_data", str(e))

    def _validate_deserialization_metadata(self, metadata: dict[str, Any]):
        """Validate metadata during deserialization."""
        required_fields = ["timestamp", "element_count", "serialization_version"]

        for field in required_fields:
            if field not in metadata:
                raise BridgeDataError(
                    "validation", "metadata", f"Missing required field: {field}"
                )

        # Check version compatibility
        version = metadata.get("serialization_version")
        if version != self.SERIALIZATION_VERSION:
            print(
                f"Warning: Version mismatch - current: {self.SERIALIZATION_VERSION}, "
                f"data: {version}"
            )

    def _update_serialization_stats(self, element_count: int, execution_time: float):
        """Update performance statistics."""
        self.serialization_stats["total_elements_serialized"] += element_count

        current_avg = self.serialization_stats["average_serialization_time"]
        total_ops = self.serialization_stats["total_elements_serialized"]

        if total_ops == element_count:
            self.serialization_stats["average_serialization_time"] = execution_time
        else:
            # Running average
            self.serialization_stats["average_serialization_time"] = (
                current_avg * (total_ops - element_count) + execution_time
            ) / total_ops

    def get_statistics(self) -> dict[str, Any]:
        """Get serialization performance statistics."""
        return self.serialization_stats.copy()

    def create_analysis_request(
        self,
        elements: list[Any],
        analysis_type: str,
        parameters: dict[str, Any],
        request_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Create a standardized analysis request for RevitPy.

        This is a convenience method for PyRevit integration.
        """
        if request_id is None:
            import uuid

            request_id = str(uuid.uuid4())

        # Serialize elements
        serialized_elements = []
        for element in elements:
            serialized_elements.append(self._serialize_single_element(element))

        return {
            "request_id": request_id,
            "analysis_type": analysis_type,
            "elements_data": serialized_elements,
            "parameters": parameters,
            "timestamp": time.time(),
            "serialization_metadata": {
                "element_count": len(elements),
                "version": self.SERIALIZATION_VERSION,
            },
        }
