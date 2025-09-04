#!/usr/bin/env python3
"""
Basic Usage Example - RevitPy Element Query Tool

This example demonstrates the fundamental usage of the Element Query Tool
for common element querying and analysis tasks.

Prerequisites:
- RevitPy installed and configured
- Active Revit document with elements
- Python 3.9+

Usage:
    python basic_usage.py
"""

import sys
import os
from pathlib import Path

# Add src directory to path for imports
sys.path.append(str(Path(__file__).parent.parent / 'src'))

from element_query import ElementQueryTool
from filters import CustomElementFilter
from utils import setup_logging, format_element_data


def main():
    """Main example execution."""
    # Setup logging
    logger = setup_logging("INFO", format_style="detailed")
    
    print("=== RevitPy Basic Element Query Example ===\n")
    
    try:
        # Initialize the query tool
        print("1. Initializing Element Query Tool...")
        query_tool = ElementQueryTool(log_level="INFO")
        print(f"   Connected to document: {query_tool.doc.Title}")
        
        # Example 1: Query elements by category
        print("\n2. Querying Walls...")
        walls = query_tool.get_elements_by_category("Walls")
        print(f"   Found {len(walls)} walls")
        
        if walls:
            # Display properties of first few walls
            print("   First 3 walls:")
            for i, wall in enumerate(walls[:3]):
                properties = query_tool.display_element_properties(wall)
                print(f"     {i+1}. {format_element_data(properties, 'summary')}")
        
        # Example 2: Query multiple categories
        print("\n3. Querying multiple categories...")
        categories = ["Doors", "Windows", "Floors"]
        
        all_elements = []
        for category in categories:
            try:
                elements = query_tool.get_elements_by_category(category)
                all_elements.extend(elements)
                print(f"   {category}: {len(elements)} elements")
            except Exception as e:
                print(f"   {category}: Error - {e}")
        
        print(f"   Total elements across categories: {len(all_elements)}")
        
        # Example 3: Query specific elements by ID
        print("\n4. Querying elements by ID...")
        if walls:
            # Use IDs from first few walls
            wall_ids = [wall.Id.IntegerValue for wall in walls[:3]]
            retrieved_elements = query_tool.get_elements_by_ids(wall_ids)
            print(f"   Retrieved {len(retrieved_elements)} elements from {len(wall_ids)} IDs")
        
        # Example 4: Search elements by name
        print("\n5. Searching elements by name pattern...")
        search_patterns = ["Wall", "Door", "Window"]
        
        for pattern in search_patterns:
            matching_elements = query_tool.search_elements_by_name(pattern, case_sensitive=False)
            print(f"   Elements matching '{pattern}': {len(matching_elements)}")
            
            # Show first few matches
            for element in matching_elements[:2]:
                properties = query_tool.display_element_properties(element)
                print(f"     - {properties['name']} (ID: {properties['id']})")
        
        # Example 5: Display detailed element analysis
        print("\n6. Detailed element analysis...")
        if walls:
            sample_wall = walls[0]
            print("   Analyzing first wall in detail:")
            properties = query_tool.display_element_properties(sample_wall)
            detailed_info = format_element_data(properties, "detailed")
            print(f"\n{detailed_info}")
            
            # Show specific parameters
            print("\n   Key Parameters:")
            key_params = query_tool.get_element_parameters(
                sample_wall, 
                ["Height", "Width", "Area", "Volume", "Type Mark", "Level"]
            )
            for param_name, param_value in key_params.items():
                if param_value is not None:
                    print(f"     {param_name}: {param_value}")
        
        # Example 6: Basic filtering
        print("\n7. Basic element filtering...")
        if all_elements:
            # Filter by category
            element_filter = CustomElementFilter()
            element_filter.add_category_filter(["Walls", "Doors"])
            
            filtered_elements = element_filter.filter_elements(all_elements)
            print(f"   Filtered to {len(filtered_elements)} walls and doors")
            
            # Show filter summary
            print(f"   Filter configuration:\n{element_filter.get_filter_summary()}")
        
        # Example 7: Performance statistics
        print("\n8. Query Statistics:")
        stats = query_tool.get_statistics()
        print(f"   Queries executed: {stats['queries_executed']}")
        print(f"   Elements processed: {stats['elements_processed']}")
        print(f"   Errors encountered: {stats['errors_encountered']}")
        print(f"   Total processing time: {stats['total_processing_time']:.3f} seconds")
        print(f"   Average query time: {stats['average_processing_time']:.3f} seconds")
        print(f"   Error rate: {stats['error_rate']:.2f}%")
        
        print("\n=== Example completed successfully! ===")
        
    except Exception as e:
        print(f"\nExample failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())