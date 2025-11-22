"""
Geometry serialization for Revit elements.
"""

from typing import Any

from ..core.config import SerializationConfig
from ..core.exceptions import BridgeDataError


class GeometrySerializer:
    """Serializer for Revit geometry objects."""

    def __init__(self, config: SerializationConfig):
        """Initialize geometry serializer."""
        self.config = config
        self.precision = config.geometry_precision

    def serialize_geometry(self, geometry: Any) -> dict[str, Any]:
        """
        Serialize Revit geometry object.

        Args:
            geometry: Revit geometry object

        Returns:
            Serialized geometry data
        """
        try:
            geometry_type = type(geometry).__name__

            serialized = {"type": geometry_type, "data": None, "bounding_box": None}

            # Handle different geometry types
            if "GeometryElement" in geometry_type:
                serialized["data"] = self._serialize_geometry_element(geometry)
            elif "Solid" in geometry_type:
                serialized["data"] = self._serialize_solid(geometry)
            elif "Face" in geometry_type:
                serialized["data"] = self._serialize_face(geometry)
            elif "Edge" in geometry_type:
                serialized["data"] = self._serialize_edge(geometry)
            elif "Curve" in geometry_type:
                serialized["data"] = self._serialize_curve(geometry)
            elif "Point" in geometry_type:
                serialized["data"] = self._serialize_point(geometry)
            else:
                # Generic geometry handling
                serialized["data"] = self._serialize_generic_geometry(geometry)

            # Add bounding box if available
            if hasattr(geometry, "GetBoundingBox"):
                try:
                    bbox = geometry.GetBoundingBox()
                    if bbox:
                        serialized["bounding_box"] = self._serialize_bounding_box(bbox)
                except:
                    pass

            return serialized

        except Exception as e:
            raise BridgeDataError(
                "geometry_serialization", type(geometry).__name__, str(e)
            )

    def _serialize_geometry_element(self, geometry_element: Any) -> dict[str, Any]:
        """Serialize GeometryElement."""
        geometries = []

        try:
            for geometry_obj in geometry_element:
                try:
                    serialized_geom = self.serialize_geometry(geometry_obj)
                    geometries.append(serialized_geom)
                except Exception as e:
                    # Skip failed geometry objects
                    geometries.append(
                        {"type": type(geometry_obj).__name__, "error": str(e)}
                    )

            return {"geometries": geometries, "count": len(geometries)}

        except Exception as e:
            return {"error": f"Failed to serialize geometry element: {e}"}

    def _serialize_solid(self, solid: Any) -> dict[str, Any]:
        """Serialize Solid geometry."""
        try:
            data = {
                "volume": round(solid.Volume, self.precision)
                if hasattr(solid, "Volume")
                else None,
                "surface_area": round(solid.SurfaceArea, self.precision)
                if hasattr(solid, "SurfaceArea")
                else None,
                "faces": [],
                "edges": [],
            }

            # Serialize faces
            if hasattr(solid, "Faces"):
                for face in solid.Faces:
                    try:
                        face_data = self._serialize_face(face)
                        data["faces"].append(face_data)
                    except Exception as e:
                        data["faces"].append({"error": str(e)})

            # Serialize edges
            if hasattr(solid, "Edges"):
                for edge in solid.Edges:
                    try:
                        edge_data = self._serialize_edge(edge)
                        data["edges"].append(edge_data)
                    except Exception as e:
                        data["edges"].append({"error": str(e)})

            return data

        except Exception as e:
            return {"error": f"Failed to serialize solid: {e}"}

    def _serialize_face(self, face: Any) -> dict[str, Any]:
        """Serialize Face geometry."""
        try:
            data = {
                "area": round(face.Area, self.precision)
                if hasattr(face, "Area")
                else None,
                "material_element_id": face.MaterialElementId.IntegerValue
                if hasattr(face, "MaterialElementId")
                else None,
            }

            # Add surface information
            if hasattr(face, "GetSurface"):
                try:
                    surface = face.GetSurface()
                    data["surface"] = self._serialize_surface(surface)
                except:
                    pass

            # Add edge loops
            if hasattr(face, "GetEdgesAsCurveLoops"):
                try:
                    curve_loops = face.GetEdgesAsCurveLoops()
                    data["edge_loops"] = []
                    for loop in curve_loops:
                        loop_data = self._serialize_curve_loop(loop)
                        data["edge_loops"].append(loop_data)
                except:
                    pass

            return data

        except Exception as e:
            return {"error": f"Failed to serialize face: {e}"}

    def _serialize_edge(self, edge: Any) -> dict[str, Any]:
        """Serialize Edge geometry."""
        try:
            data = {}

            if hasattr(edge, "AsCurve"):
                curve = edge.AsCurve()
                data["curve"] = self.serialize_curve(curve)

            if hasattr(edge, "ApproximateLength"):
                data["length"] = round(edge.ApproximateLength, self.precision)

            return data

        except Exception as e:
            return {"error": f"Failed to serialize edge: {e}"}

    def serialize_curve(self, curve: Any) -> dict[str, Any]:
        """Serialize curve geometry."""
        try:
            curve_type = type(curve).__name__

            data = {
                "type": curve_type,
                "is_bound": curve.IsBound if hasattr(curve, "IsBound") else False,
                "length": round(curve.Length, self.precision)
                if hasattr(curve, "Length")
                else None,
            }

            # Add curve-specific data
            if "Line" in curve_type:
                data.update(self._serialize_line(curve))
            elif "Arc" in curve_type:
                data.update(self._serialize_arc(curve))
            elif "NurbSpline" in curve_type:
                data.update(self._serialize_nurb_spline(curve))
            elif "Ellipse" in curve_type:
                data.update(self._serialize_ellipse(curve))
            else:
                # Generic curve handling
                data.update(self._serialize_generic_curve(curve))

            return data

        except Exception as e:
            return {"error": f"Failed to serialize curve: {e}"}

    def _serialize_line(self, line: Any) -> dict[str, Any]:
        """Serialize line curve."""
        try:
            data = {}

            if hasattr(line, "GetEndPoint"):
                data["start_point"] = self._serialize_point(line.GetEndPoint(0))
                data["end_point"] = self._serialize_point(line.GetEndPoint(1))

            if hasattr(line, "Direction"):
                data["direction"] = self._serialize_vector(line.Direction)

            if hasattr(line, "Origin"):
                data["origin"] = self._serialize_point(line.Origin)

            return data

        except Exception as e:
            return {"error": f"Failed to serialize line: {e}"}

    def _serialize_arc(self, arc: Any) -> dict[str, Any]:
        """Serialize arc curve."""
        try:
            data = {}

            if hasattr(arc, "Center"):
                data["center"] = self._serialize_point(arc.Center)

            if hasattr(arc, "Radius"):
                data["radius"] = round(arc.Radius, self.precision)

            if hasattr(arc, "Normal"):
                data["normal"] = self._serialize_vector(arc.Normal)

            if hasattr(arc, "XDirection"):
                data["x_direction"] = self._serialize_vector(arc.XDirection)

            if hasattr(arc, "YDirection"):
                data["y_direction"] = self._serialize_vector(arc.YDirection)

            return data

        except Exception as e:
            return {"error": f"Failed to serialize arc: {e}"}

    def _serialize_nurb_spline(self, spline: Any) -> dict[str, Any]:
        """Serialize NURB spline curve."""
        try:
            data = {}

            if hasattr(spline, "CtrlPoints"):
                control_points = []
                for point in spline.CtrlPoints:
                    control_points.append(self._serialize_point(point))
                data["control_points"] = control_points

            if hasattr(spline, "Weights"):
                data["weights"] = list(spline.Weights)

            if hasattr(spline, "Knots"):
                data["knots"] = list(spline.Knots)

            if hasattr(spline, "Degree"):
                data["degree"] = spline.Degree

            return data

        except Exception as e:
            return {"error": f"Failed to serialize NURB spline: {e}"}

    def _serialize_ellipse(self, ellipse: Any) -> dict[str, Any]:
        """Serialize ellipse curve."""
        try:
            data = {}

            if hasattr(ellipse, "Center"):
                data["center"] = self._serialize_point(ellipse.Center)

            if hasattr(ellipse, "RadiusX"):
                data["radius_x"] = round(ellipse.RadiusX, self.precision)

            if hasattr(ellipse, "RadiusY"):
                data["radius_y"] = round(ellipse.RadiusY, self.precision)

            if hasattr(ellipse, "Normal"):
                data["normal"] = self._serialize_vector(ellipse.Normal)

            if hasattr(ellipse, "XDirection"):
                data["x_direction"] = self._serialize_vector(ellipse.XDirection)

            if hasattr(ellipse, "YDirection"):
                data["y_direction"] = self._serialize_vector(ellipse.YDirection)

            return data

        except Exception as e:
            return {"error": f"Failed to serialize ellipse: {e}"}

    def _serialize_generic_curve(self, curve: Any) -> dict[str, Any]:
        """Serialize generic curve with basic properties."""
        try:
            data = {}

            # Sample points along curve
            if hasattr(curve, "Evaluate"):
                sample_count = 10
                points = []
                for i in range(sample_count + 1):
                    parameter = i / sample_count
                    try:
                        if hasattr(curve, "GetNormalizedParameter"):
                            param = curve.GetNormalizedParameter(parameter)
                        else:
                            param = parameter

                        point = curve.Evaluate(param, False)
                        points.append(self._serialize_point(point))
                    except:
                        continue

                data["sample_points"] = points

            return data

        except Exception as e:
            return {"error": f"Failed to serialize generic curve: {e}"}

    def _serialize_point(self, point: Any) -> dict[str, float]:
        """Serialize 3D point."""
        try:
            return {
                "x": round(point.X, self.precision),
                "y": round(point.Y, self.precision),
                "z": round(point.Z, self.precision),
            }
        except Exception as e:
            return {"error": f"Failed to serialize point: {e}"}

    def _serialize_vector(self, vector: Any) -> dict[str, float]:
        """Serialize 3D vector."""
        try:
            return {
                "x": round(vector.X, self.precision),
                "y": round(vector.Y, self.precision),
                "z": round(vector.Z, self.precision),
            }
        except Exception as e:
            return {"error": f"Failed to serialize vector: {e}"}

    def _serialize_surface(self, surface: Any) -> dict[str, Any]:
        """Serialize surface geometry."""
        try:
            surface_type = type(surface).__name__

            data = {"type": surface_type}

            # Add surface-specific properties
            if "Plane" in surface_type:
                if hasattr(surface, "Origin"):
                    data["origin"] = self._serialize_point(surface.Origin)
                if hasattr(surface, "Normal"):
                    data["normal"] = self._serialize_vector(surface.Normal)
                if hasattr(surface, "XVec"):
                    data["x_vector"] = self._serialize_vector(surface.XVec)
                if hasattr(surface, "YVec"):
                    data["y_vector"] = self._serialize_vector(surface.YVec)

            elif "Cylinder" in surface_type:
                if hasattr(surface, "Origin"):
                    data["origin"] = self._serialize_point(surface.Origin)
                if hasattr(surface, "Axis"):
                    data["axis"] = self._serialize_vector(surface.Axis)
                if hasattr(surface, "Radius"):
                    data["radius"] = round(surface.Radius, self.precision)

            return data

        except Exception as e:
            return {"error": f"Failed to serialize surface: {e}"}

    def _serialize_curve_loop(self, curve_loop: Any) -> dict[str, Any]:
        """Serialize curve loop."""
        try:
            curves = []

            for curve in curve_loop:
                curve_data = self.serialize_curve(curve)
                curves.append(curve_data)

            return {
                "curves": curves,
                "count": len(curves),
                "is_open": curve_loop.IsOpen()
                if hasattr(curve_loop, "IsOpen")
                else None,
            }

        except Exception as e:
            return {"error": f"Failed to serialize curve loop: {e}"}

    def _serialize_bounding_box(self, bbox: Any) -> dict[str, Any]:
        """Serialize bounding box."""
        try:
            return {
                "min": self._serialize_point(bbox.Min),
                "max": self._serialize_point(bbox.Max),
                "enabled": bbox.Enabled if hasattr(bbox, "Enabled") else True,
            }
        except Exception as e:
            return {"error": f"Failed to serialize bounding box: {e}"}

    def _serialize_generic_geometry(self, geometry: Any) -> dict[str, Any]:
        """Serialize generic geometry object."""
        try:
            data = {"properties": {}}

            # Extract common properties
            common_props = ["Volume", "Area", "Length", "Radius", "Center", "Origin"]

            for prop in common_props:
                if hasattr(geometry, prop):
                    try:
                        value = getattr(geometry, prop)
                        if isinstance(value, (int, float)):
                            data["properties"][prop.lower()] = round(
                                value, self.precision
                            )
                        elif hasattr(value, "X"):  # Point or Vector
                            if "center" in prop.lower() or "origin" in prop.lower():
                                data["properties"][prop.lower()] = (
                                    self._serialize_point(value)
                                )
                            else:
                                data["properties"][prop.lower()] = (
                                    self._serialize_vector(value)
                                )
                    except:
                        continue

            return data

        except Exception as e:
            return {"error": f"Failed to serialize generic geometry: {e}"}

    def calculate_geometry_hash(self, geometry_data: dict[str, Any]) -> str:
        """Calculate hash for geometry data for caching/comparison."""
        try:
            import hashlib
            import json

            # Create a simplified version for hashing
            hash_data = {
                "type": geometry_data.get("type"),
                "bounding_box": geometry_data.get("bounding_box"),
            }

            # Add key geometric properties
            if "data" in geometry_data:
                data = geometry_data["data"]
                if isinstance(data, dict):
                    # Include key properties for hash
                    hash_props = [
                        "volume",
                        "area",
                        "length",
                        "radius",
                        "center",
                        "origin",
                    ]
                    for prop in hash_props:
                        if prop in data:
                            hash_data[prop] = data[prop]

            json_str = json.dumps(hash_data, sort_keys=True)
            return hashlib.md5(json_str.encode()).hexdigest()

        except Exception:
            return "hash_error"
