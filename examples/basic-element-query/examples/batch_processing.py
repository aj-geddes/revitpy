#!/usr/bin/env python3
"""
Batch Processing Example - RevitPy Element Query Tool

This example demonstrates batch processing capabilities for handling large datasets:
- Batch element processing with progress tracking
- Performance optimization techniques
- Memory management
- Error resilience
- Parallel processing concepts

Prerequisites:
- RevitPy installed and configured
- Active Revit document with elements
- Python 3.9+

Usage:
    python batch_processing.py
"""

import sys
import os
import time
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any

# Add src directory to path for imports
sys.path.append(str(Path(__file__).parent.parent / 'src'))

from element_query import ElementQueryTool
from filters import CustomElementFilter
from utils import setup_logging, format_element_data, export_to_file

# Third-party imports (would be installed via requirements.txt)
try:
    from tqdm import tqdm
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    # Fallback progress indicator
    def tqdm(iterable, desc="Processing"):
        print(f"{desc}...")
        return iterable


def process_element_batch(query_tool: ElementQueryTool, elements: List, 
                         batch_size: int = 100) -> Dict[str, Any]:
    """
    Process elements in batches with detailed progress tracking.
    
    Args:
        query_tool: ElementQueryTool instance
        elements: List of elements to process
        batch_size: Number of elements per batch
        
    Returns:
        Dictionary with processing results and statistics
    """
    results = {
        'processed_elements': [],
        'batch_statistics': [],
        'errors': [],
        'total_processed': 0,
        'total_errors': 0,
        'total_time': 0,
        'memory_usage': []
    }
    
    total_batches = (len(elements) + batch_size - 1) // batch_size
    print(f"Processing {len(elements)} elements in {total_batches} batches of {batch_size}")
    
    overall_start = time.time()
    
    for batch_idx in range(0, len(elements), batch_size):
        batch_start = time.time()
        batch_elements = elements[batch_idx:batch_idx + batch_size]
        batch_num = (batch_idx // batch_size) + 1
        
        print(f"\nBatch {batch_num}/{total_batches} - Processing {len(batch_elements)} elements...")
        
        batch_results = []
        batch_errors = []
        
        # Process batch with progress bar
        for element in tqdm(batch_elements, desc=f"Batch {batch_num}"):
            try:
                element_data = query_tool.display_element_properties(element)
                if element_data:
                    batch_results.append(element_data)
                    results['total_processed'] += 1
                else:
                    batch_errors.append({
                        'element_id': getattr(element, 'Id', 'Unknown'),
                        'error': 'No data returned',
                        'batch': batch_num
                    })
                    results['total_errors'] += 1
                    
            except Exception as e:
                batch_errors.append({
                    'element_id': getattr(element, 'Id', 'Unknown'),
                    'error': str(e),
                    'batch': batch_num
                })
                results['total_errors'] += 1
        
        batch_time = time.time() - batch_start
        
        # Batch statistics
        batch_stats = {
            'batch_number': batch_num,
            'elements_in_batch': len(batch_elements),
            'successful_processing': len(batch_results),
            'errors_in_batch': len(batch_errors),
            'processing_time': batch_time,
            'elements_per_second': len(batch_results) / batch_time if batch_time > 0 else 0
        }
        
        results['batch_statistics'].append(batch_stats)
        results['processed_elements'].extend(batch_results)
        results['errors'].extend(batch_errors)
        
        # Memory usage tracking (simplified)
        import psutil
        memory_usage = psutil.Process().memory_info().rss / 1024 / 1024  # MB
        results['memory_usage'].append({
            'batch': batch_num,
            'memory_mb': memory_usage
        })
        
        print(f"   Batch {batch_num} complete: {len(batch_results)} processed, "
              f"{len(batch_errors)} errors, {batch_time:.2f}s")
        
        # Optional: Brief pause between batches to prevent overwhelming the system
        if batch_num < total_batches:
            time.sleep(0.1)
    
    results['total_time'] = time.time() - overall_start
    
    return results


def analyze_batch_performance(batch_results: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze batch processing performance and identify bottlenecks.
    
    Args:
        batch_results: Results from batch processing
        
    Returns:
        Performance analysis dictionary
    """
    batch_stats = batch_results['batch_statistics']
    
    if not batch_stats:
        return {'error': 'No batch statistics available'}
    
    # Calculate performance metrics
    processing_times = [batch['processing_time'] for batch in batch_stats]
    elements_per_second = [batch['elements_per_second'] for batch in batch_stats]
    success_rates = [
        batch['successful_processing'] / batch['elements_in_batch'] * 100
        for batch in batch_stats
    ]
    
    analysis = {
        'total_batches': len(batch_stats),
        'average_batch_time': sum(processing_times) / len(processing_times),
        'min_batch_time': min(processing_times),
        'max_batch_time': max(processing_times),
        'average_elements_per_second': sum(elements_per_second) / len(elements_per_second),
        'max_elements_per_second': max(elements_per_second),
        'min_elements_per_second': min(elements_per_second),
        'average_success_rate': sum(success_rates) / len(success_rates),
        'min_success_rate': min(success_rates),
        'total_processing_time': batch_results['total_time'],
        'overall_success_rate': (batch_results['total_processed'] / 
                               (batch_results['total_processed'] + batch_results['total_errors']) * 100),
        'memory_usage_range': {
            'min_mb': min(m['memory_mb'] for m in batch_results['memory_usage']),
            'max_mb': max(m['memory_mb'] for m in batch_results['memory_usage']),
            'avg_mb': sum(m['memory_mb'] for m in batch_results['memory_usage']) / len(batch_results['memory_usage'])
        }
    }
    
    # Performance recommendations
    recommendations = []
    
    if analysis['average_success_rate'] < 95:
        recommendations.append("Consider improving error handling - success rate is below 95%")
    
    if analysis['max_batch_time'] > analysis['average_batch_time'] * 2:
        recommendations.append("Some batches are significantly slower - consider dynamic batch sizing")
    
    if analysis['memory_usage_range']['max_mb'] - analysis['memory_usage_range']['min_mb'] > 100:
        recommendations.append("Memory usage varies significantly - consider memory cleanup between batches")
    
    if analysis['average_elements_per_second'] < 10:
        recommendations.append("Processing speed is low - consider optimizing element property access")
    
    analysis['recommendations'] = recommendations
    
    return analysis


def parallel_element_processing(query_tool: ElementQueryTool, elements: List,
                              max_workers: int = 4) -> Dict[str, Any]:
    """
    Demonstrate parallel processing concepts (Note: Revit API is not thread-safe).
    This is more of a conceptual example for CPU-bound post-processing tasks.
    
    Args:
        query_tool: ElementQueryTool instance
        elements: List of elements to process
        max_workers: Maximum number of worker threads
        
    Returns:
        Processing results
    """
    print(f"Demonstrating parallel processing concepts with {max_workers} workers...")
    print("Note: This is for post-processing tasks only - Revit API is not thread-safe!")
    
    # First, get element data sequentially (required for Revit API)
    print("Step 1: Sequential data collection from Revit API...")
    element_data = []
    
    for element in tqdm(elements[:50], desc="Collecting data"):  # Limit for example
        try:
            data = query_tool.display_element_properties(element)
            if data:
                element_data.append(data)
        except Exception as e:
            print(f"Error collecting data for element: {e}")
    
    if not element_data:
        return {'error': 'No element data collected'}
    
    # Step 2: Parallel post-processing of collected data
    print("Step 2: Parallel post-processing of collected data...")
    
    def process_element_data(data_chunk):
        """Process a chunk of element data (CPU-bound operations)."""
        processed_chunk = []
        
        for data in data_chunk:
            try:
                # Example post-processing tasks
                processed = {
                    'id': data['id'],
                    'category': data['category'],
                    'name': data['name'],
                    'parameter_count': len(data.get('parameters', {})),
                    'has_location': data.get('location') is not None,
                    'has_geometry': data.get('geometry') is not None,
                    'material_count': len(data.get('materials', []) or []),
                    'data_completeness': calculate_data_completeness(data)
                }
                processed_chunk.append(processed)
                
            except Exception as e:
                print(f"Error in post-processing: {e}")
        
        return processed_chunk
    
    # Split data into chunks for parallel processing
    chunk_size = max(1, len(element_data) // max_workers)
    data_chunks = [
        element_data[i:i + chunk_size] 
        for i in range(0, len(element_data), chunk_size)
    ]
    
    start_time = time.time()
    processed_results = []
    
    # Process chunks in parallel
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_chunk = {
            executor.submit(process_element_data, chunk): i 
            for i, chunk in enumerate(data_chunks)
        }
        
        for future in tqdm(future_to_chunk, desc="Parallel processing"):
            chunk_idx = future_to_chunk[future]
            try:
                chunk_result = future.result()
                processed_results.extend(chunk_result)
                print(f"   Chunk {chunk_idx + 1} processed: {len(chunk_result)} items")
            except Exception as e:
                print(f"   Chunk {chunk_idx + 1} failed: {e}")
    
    parallel_time = time.time() - start_time
    
    # Compare with sequential processing
    print("Step 3: Comparing with sequential processing...")
    start_time = time.time()
    
    sequential_results = []
    for data in tqdm(element_data, desc="Sequential processing"):
        try:
            processed = {
                'id': data['id'],
                'category': data['category'], 
                'name': data['name'],
                'parameter_count': len(data.get('parameters', {})),
                'has_location': data.get('location') is not None,
                'has_geometry': data.get('geometry') is not None,
                'material_count': len(data.get('materials', []) or []),
                'data_completeness': calculate_data_completeness(data)
            }
            sequential_results.append(processed)
        except Exception as e:
            print(f"Error in sequential processing: {e}")
    
    sequential_time = time.time() - start_time
    
    return {
        'parallel_results': processed_results,
        'sequential_results': sequential_results,
        'parallel_time': parallel_time,
        'sequential_time': sequential_time,
        'speedup_ratio': sequential_time / parallel_time if parallel_time > 0 else 0,
        'elements_processed': len(element_data)
    }


def calculate_data_completeness(element_data: Dict[str, Any]) -> float:
    """Calculate a data completeness score for an element."""
    total_fields = 7  # id, category, name, location, geometry, parameters, materials
    completed_fields = 0
    
    if element_data.get('id'):
        completed_fields += 1
    if element_data.get('category'):
        completed_fields += 1
    if element_data.get('name'):
        completed_fields += 1
    if element_data.get('location'):
        completed_fields += 1
    if element_data.get('geometry'):
        completed_fields += 1
    if element_data.get('parameters'):
        completed_fields += 1
    if element_data.get('materials'):
        completed_fields += 1
    
    return (completed_fields / total_fields) * 100


def generate_batch_report(batch_results: Dict[str, Any], 
                         performance_analysis: Dict[str, Any],
                         output_path: Path) -> bool:
    """
    Generate a comprehensive batch processing report.
    
    Args:
        batch_results: Results from batch processing
        performance_analysis: Performance analysis results
        output_path: Output file path
        
    Returns:
        True if successful, False otherwise
    """
    try:
        report = {
            'summary': {
                'total_elements_processed': batch_results['total_processed'],
                'total_errors': batch_results['total_errors'],
                'total_processing_time': batch_results['total_time'],
                'overall_success_rate': performance_analysis.get('overall_success_rate', 0),
                'average_processing_speed': performance_analysis.get('average_elements_per_second', 0)
            },
            'batch_details': batch_results['batch_statistics'],
            'performance_analysis': performance_analysis,
            'error_summary': {
                'total_errors': len(batch_results['errors']),
                'errors_by_batch': {}
            },
            'recommendations': performance_analysis.get('recommendations', [])
        }
        
        # Group errors by batch
        for error in batch_results['errors']:
            batch_num = error.get('batch', 'unknown')
            if batch_num not in report['error_summary']['errors_by_batch']:
                report['error_summary']['errors_by_batch'][batch_num] = []
            report['error_summary']['errors_by_batch'][batch_num].append(error)
        
        # Save report
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        return True
        
    except Exception as e:
        print(f"Error generating report: {e}")
        return False


def main():
    """Main example execution."""
    # Setup logging
    logger = setup_logging("INFO", format_style="detailed")
    
    print("=== RevitPy Batch Processing Example ===\n")
    
    try:
        # Initialize the query tool
        print("1. Initializing Element Query Tool...")
        query_tool = ElementQueryTool(log_level="INFO")
        
        # Build large dataset for batch processing
        print("\n2. Building large dataset...")
        all_elements = []
        categories = ["Walls", "Doors", "Windows", "Floors", "Ceilings", "Rooms"]
        
        for category in categories:
            try:
                elements = query_tool.get_elements_by_category(category)
                all_elements.extend(elements)
                print(f"   {category}: {len(elements)} elements")
            except Exception as e:
                print(f"   {category}: Error - {e}")
        
        print(f"   Total dataset size: {len(all_elements)} elements")
        
        if len(all_elements) == 0:
            print("No elements found. Please ensure you have an active Revit document.")
            return 1
        
        # Example 1: Basic batch processing
        print("\n3. Basic batch processing demonstration...")
        batch_size = min(50, max(10, len(all_elements) // 10))  # Adaptive batch size
        
        batch_results = process_element_batch(query_tool, all_elements, batch_size)
        
        print(f"\nBatch Processing Summary:")
        print(f"   Total processed: {batch_results['total_processed']}")
        print(f"   Total errors: {batch_results['total_errors']}")
        print(f"   Processing time: {batch_results['total_time']:.2f} seconds")
        print(f"   Success rate: {(batch_results['total_processed'] / len(all_elements) * 100):.1f}%")
        
        # Example 2: Performance analysis
        print("\n4. Performance analysis...")
        performance_analysis = analyze_batch_performance(batch_results)
        
        print(f"   Average batch time: {performance_analysis['average_batch_time']:.3f}s")
        print(f"   Processing speed: {performance_analysis['average_elements_per_second']:.1f} elements/second")
        print(f"   Memory usage: {performance_analysis['memory_usage_range']['min_mb']:.1f} - "
              f"{performance_analysis['memory_usage_range']['max_mb']:.1f} MB")
        
        if performance_analysis.get('recommendations'):
            print("   Performance Recommendations:")
            for i, rec in enumerate(performance_analysis['recommendations'], 1):
                print(f"     {i}. {rec}")
        
        # Example 3: Filtered batch processing
        print("\n5. Filtered batch processing...")
        
        # Create a filter for specific elements
        element_filter = CustomElementFilter()
        element_filter.add_category_filter(["Walls", "Doors"])
        element_filter.add_parameter_filter("Area", 10, "greater")  # Minimum area
        
        filtered_elements = element_filter.filter_elements(all_elements)
        print(f"   Filtered to {len(filtered_elements)} elements")
        
        if filtered_elements:
            filtered_batch_results = process_element_batch(
                query_tool, 
                filtered_elements, 
                min(25, len(filtered_elements))
            )
            
            print(f"   Filtered batch processing: {filtered_batch_results['total_processed']} processed")
        
        # Example 4: Parallel processing demonstration
        print("\n6. Parallel processing demonstration...")
        
        if len(all_elements) > 10:
            parallel_results = parallel_element_processing(query_tool, all_elements, max_workers=4)
            
            if 'parallel_time' in parallel_results:
                print(f"   Parallel processing time: {parallel_results['parallel_time']:.3f}s")
                print(f"   Sequential processing time: {parallel_results['sequential_time']:.3f}s")
                print(f"   Speedup ratio: {parallel_results['speedup_ratio']:.2f}x")
        
        # Example 5: Data export with different formats
        print("\n7. Exporting batch results...")
        
        output_dir = Path(__file__).parent / "output"
        output_dir.mkdir(exist_ok=True)
        
        # Export processed elements
        if batch_results['processed_elements']:
            # Limit export size for example
            export_elements = batch_results['processed_elements'][:100]
            
            # JSON export
            json_file = output_dir / "batch_results.json"
            json_success = export_to_file(export_elements, json_file, "json")
            if json_success:
                print(f"   Exported {len(export_elements)} elements to {json_file}")
            
            # Generate comprehensive report
            report_file = output_dir / "batch_processing_report.json"
            report_success = generate_batch_report(
                batch_results, performance_analysis, report_file
            )
            if report_success:
                print(f"   Generated batch report: {report_file}")
            
            # If pandas is available, create additional analysis
            if PANDAS_AVAILABLE and batch_results['processed_elements']:
                try:
                    # Convert to DataFrame for analysis
                    df_data = []
                    for element in export_elements:
                        row = {
                            'id': element['id'],
                            'category': element['category'],
                            'name': element['name'],
                            'parameter_count': len(element.get('parameters', {})),
                            'has_geometry': element.get('geometry') is not None
                        }
                        df_data.append(row)
                    
                    df = pd.DataFrame(df_data)
                    
                    # Basic statistics
                    print("\n   Pandas Analysis:")
                    print(f"     Categories: {df['category'].nunique()}")
                    print(f"     Average parameters per element: {df['parameter_count'].mean():.1f}")
                    print(f"     Elements with geometry: {df['has_geometry'].sum()}")
                    
                    # Export to CSV
                    csv_file = output_dir / "batch_analysis.csv"
                    df.to_csv(csv_file, index=False)
                    print(f"   Exported analysis to {csv_file}")
                    
                except Exception as e:
                    print(f"   Pandas analysis failed: {e}")
        
        # Example 6: Memory management demonstration
        print("\n8. Memory management tips...")
        
        print("   Memory usage during processing:")
        for i, mem_data in enumerate(batch_results['memory_usage'][:5]):  # Show first 5
            print(f"     Batch {mem_data['batch']}: {mem_data['memory_mb']:.1f} MB")
        
        print("   Memory management recommendations:")
        print("     - Process elements in smaller batches if memory usage grows")
        print("     - Clear references to large objects after processing")
        print("     - Use generators for large datasets when possible")
        print("     - Monitor memory usage throughout processing")
        
        # Final statistics
        print("\n9. Final Statistics:")
        final_stats = query_tool.get_statistics()
        print(f"   Total API queries: {final_stats['queries_executed']}")
        print(f"   Total elements accessed: {final_stats['elements_processed']}")
        print(f"   Total API time: {final_stats['total_processing_time']:.3f} seconds")
        print(f"   Average query time: {final_stats['average_processing_time']:.4f} seconds")
        
        print("\n=== Batch processing example completed successfully! ===")
        
    except Exception as e:
        print(f"\nExample failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    # Install required packages note
    try:
        import psutil
    except ImportError:
        print("Note: Install 'psutil' for memory usage tracking: pip install psutil")
    
    sys.exit(main())