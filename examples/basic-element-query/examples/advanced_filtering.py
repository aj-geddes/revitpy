#!/usr/bin/env python3
"""
Advanced Filtering Example - RevitPy Element Query Tool

This example demonstrates advanced filtering capabilities including:
- Complex parameter filtering
- Geometric constraints
- Combined filter conditions
- Performance optimization

Prerequisites:
- RevitPy installed and configured
- Active Revit document with elements
- Python 3.9+

Usage:
    python advanced_filtering.py
"""

import sys
from pathlib import Path

# Add src directory to path for imports
sys.path.append(str(Path(__file__).parent.parent / "src"))

from element_query import ElementQueryTool
from filters import CustomElementFilter
from utils import export_to_file, setup_logging


def main():
    """Main example execution."""
    # Setup logging
    logger = setup_logging("INFO", format_style="detailed")

    print("=== RevitPy Advanced Filtering Example ===\n")

    try:
        # Initialize the query tool
        print("1. Initializing Element Query Tool...")
        query_tool = ElementQueryTool(log_level="INFO")

        # Get initial dataset
        print("\n2. Building initial dataset...")
        all_walls = query_tool.get_elements_by_category("Walls")
        all_doors = query_tool.get_elements_by_category("Doors")
        all_windows = query_tool.get_elements_by_category("Windows")
        all_floors = query_tool.get_elements_by_category("Floors")

        all_elements = all_walls + all_doors + all_windows + all_floors
        print(f"   Total elements in dataset: {len(all_elements)}")
        print(f"     Walls: {len(all_walls)}")
        print(f"     Doors: {len(all_doors)}")
        print(f"     Windows: {len(all_windows)}")
        print(f"     Floors: {len(all_floors)}")

        if not all_elements:
            print(
                "No elements found in the model. Please ensure you have an active Revit document with elements."
            )
            return 1

        # Example 1: Parameter-based filtering
        print("\n3. Parameter-based filtering examples...")

        # Filter walls by structural usage
        print("   a) Structural walls only:")
        structural_filter = CustomElementFilter()
        structural_filter.add_category_filter("Walls")
        structural_filter.add_parameter_filter("Structural Usage", "Bearing", "equals")

        structural_walls = structural_filter.filter_elements(all_elements)
        print(f"      Found {len(structural_walls)} structural bearing walls")

        # Filter by area range
        print("   b) Elements with area between 50-200 square feet:")
        area_filter = CustomElementFilter()
        area_filter.add_parameter_filter("Area", 50, "greater_or_equal")
        area_filter.add_parameter_filter("Area", 200, "less_or_equal")
        area_filter.set_logic("AND")

        medium_elements = area_filter.filter_elements(all_elements)
        print(f"      Found {len(medium_elements)} elements in area range")

        # Filter by type mark pattern
        print("   c) Elements with type marks containing 'A':")
        type_mark_filter = CustomElementFilter()
        type_mark_filter.add_parameter_filter(
            "Type Mark", "A", "contains", case_sensitive=False
        )

        type_a_elements = type_mark_filter.filter_elements(all_elements)
        print(f"      Found {len(type_a_elements)} elements with 'A' in type mark")

        # Example 2: Geometry-based filtering
        print("\n4. Geometry-based filtering examples...")

        # Filter by location bounds
        print("   a) Elements within specific bounds:")
        bounds = {
            "min": {"x": -50, "y": -50, "z": 0},
            "max": {"x": 50, "y": 50, "z": 15},
        }

        location_filter = CustomElementFilter()
        location_filter.add_geometry_filter(bounds=bounds)

        bounded_elements = location_filter.filter_elements(all_elements)
        print(f"      Found {len(bounded_elements)} elements within bounds")

        # Filter large elements by area and volume
        print("   b) Large elements (area > 100, volume > 500):")
        large_filter = CustomElementFilter()
        large_filter.add_geometry_filter(min_area=100, min_volume=500)

        large_elements = large_filter.filter_elements(all_elements)
        print(f"      Found {len(large_elements)} large elements")

        # Example 3: Complex combined filters
        print("\n5. Complex combined filter examples...")

        # Complex filter 1: Exterior walls on specific level
        print("   a) Exterior walls on Level 1:")
        exterior_walls_filter = CustomElementFilter()
        exterior_walls_filter.add_category_filter("Walls")
        exterior_walls_filter.add_parameter_filter(
            "Usage", "Exterior", "contains", case_sensitive=False
        )
        exterior_walls_filter.add_parameter_filter(
            "Level", "Level 1", "contains", case_sensitive=False
        )
        exterior_walls_filter.set_logic("AND")

        exterior_walls = exterior_walls_filter.filter_elements(all_elements)
        print(f"      Found {len(exterior_walls)} exterior walls on Level 1")

        # Complex filter 2: High-performance elements
        print("   b) High-performance elements (multiple criteria):")
        criteria = {
            "categories": ["Walls", "Floors"],
            "parameter_filters": [
                {"parameter_name": "Area", "value": 75, "comparison": "greater"},
                {"parameter_name": "Volume", "value": 50, "comparison": "greater"},
            ],
            "min_area": 60,
            "logic": "AND",
            "elements": all_elements,
        }

        performance_filter = CustomElementFilter()
        high_perf_elements = performance_filter.create_complex_filter(**criteria)
        print(f"      Found {len(high_perf_elements)} high-performance elements")
        print(f"      Filter summary:\n{performance_filter.get_filter_summary()}")

        # Example 4: Advanced parameter analysis
        print("\n6. Advanced parameter analysis...")

        if structural_walls:
            print("   Analyzing structural wall parameters:")
            sample_wall = structural_walls[0]

            # Get all parameters
            all_params = query_tool.get_element_parameters(sample_wall)

            # Categorize parameters
            numeric_params = {}
            text_params = {}

            for param_name, param_value in all_params.items():
                if param_value is not None:
                    try:
                        float_value = float(param_value)
                        numeric_params[param_name] = float_value
                    except (ValueError, TypeError):
                        text_params[param_name] = str(param_value)

            print(f"      Numeric parameters: {len(numeric_params)}")
            print(f"      Text parameters: {len(text_params)}")

            # Show top numeric parameters
            sorted_numeric = sorted(
                numeric_params.items(), key=lambda x: abs(x[1]), reverse=True
            )
            print("      Top 5 numeric parameters by absolute value:")
            for i, (name, value) in enumerate(sorted_numeric[:5]):
                print(f"        {i+1}. {name}: {value}")

        # Example 5: Performance comparison
        print("\n7. Performance comparison...")

        # Method 1: Individual category queries
        import time

        start_time = time.time()

        method1_walls = query_tool.get_elements_by_category("Walls")
        method1_doors = query_tool.get_elements_by_category("Doors")
        method1_total = len(method1_walls) + len(method1_doors)

        method1_time = time.time() - start_time

        # Method 2: Combined filter
        start_time = time.time()

        combined_filter = CustomElementFilter()
        combined_filter.add_category_filter(["Walls", "Doors"])
        method2_elements = combined_filter.filter_elements(all_elements)
        method2_total = len(method2_elements)

        method2_time = time.time() - start_time

        print(
            f"   Method 1 (separate queries): {method1_total} elements in {method1_time:.4f}s"
        )
        print(
            f"   Method 2 (combined filter): {method2_total} elements in {method2_time:.4f}s"
        )
        print(f"   Performance ratio: {method1_time/method2_time:.2f}x")

        # Example 6: Export filtered results
        print("\n8. Exporting filtered results...")

        if high_perf_elements:
            # Process elements for export
            export_data = []
            for element in high_perf_elements[:10]:  # Limit to first 10 for example
                properties = query_tool.display_element_properties(element)
                if properties:
                    # Simplify for export
                    export_item = {
                        "id": properties["id"],
                        "name": properties["name"],
                        "category": properties["category"],
                        "level": properties.get("level"),
                        "area": properties.get("parameters", {}).get("Area"),
                        "volume": properties.get("parameters", {}).get("Volume"),
                    }
                    export_data.append(export_item)

            # Export to different formats
            output_dir = Path(__file__).parent / "output"
            output_dir.mkdir(exist_ok=True)

            formats = ["json", "csv"]  # Skip XML for simplicity
            for fmt in formats:
                output_file = output_dir / f"filtered_elements.{fmt}"
                success = export_to_file(export_data, output_file, fmt)
                if success:
                    print(
                        f"      Exported {len(export_data)} elements to {output_file}"
                    )
                else:
                    print(f"      Failed to export to {fmt} format")

        # Example 7: Custom filter conditions
        print("\n9. Custom filter condition example...")

        # Create a custom filter for elements with specific characteristics
        class CustomAreaFilter(CustomElementFilter):
            """Custom filter for elements with area in specific ranges."""

            def filter_by_area_category(self, elements, small_max=50, large_min=200):
                """Filter elements into small and large categories."""
                small_elements = []
                large_elements = []

                for element in elements:
                    try:
                        area_param = element.LookupParameter("Area")
                        if area_param and area_param.HasValue:
                            area = area_param.AsDouble()
                            if area <= small_max:
                                small_elements.append(element)
                            elif area >= large_min:
                                large_elements.append(element)
                    except Exception:
                        continue

                return small_elements, large_elements

        custom_filter = CustomAreaFilter()
        small_elements, large_elements = custom_filter.filter_by_area_category(
            all_elements
        )

        print(f"   Small elements (area ≤ 50): {len(small_elements)}")
        print(f"   Large elements (area ≥ 200): {len(large_elements)}")

        # Final statistics
        print("\n10. Final Query Statistics:")
        final_stats = query_tool.get_statistics()
        print(f"    Total queries executed: {final_stats['queries_executed']}")
        print(f"    Total elements processed: {final_stats['elements_processed']}")
        print(f"    Total errors encountered: {final_stats['errors_encountered']}")
        print(
            f"    Total processing time: {final_stats['total_processing_time']:.3f} seconds"
        )
        print(
            f"    Average query time: {final_stats['average_processing_time']:.4f} seconds"
        )
        print(f"    Overall error rate: {final_stats['error_rate']:.2f}%")

        print("\n=== Advanced filtering example completed successfully! ===")

    except Exception as e:
        print(f"\nExample failed with error: {e}")
        import traceback

        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
