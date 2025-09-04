#!/usr/bin/env python3
"""
Test suite for Energy Analytics POC

Tests all capabilities that are IMPOSSIBLE in PyRevit due to IronPython limitations.
"""

import sys
import os
import unittest
import asyncio
import tempfile
from pathlib import Path
from datetime import datetime, timedelta

# Add common utilities to path
sys.path.append(str(Path(__file__).parent.parent.parent / "common" / "src"))
sys.path.append(str(Path(__file__).parent.parent / "src"))

import numpy as np
import pandas as pd
from energy_analyzer import EnergyPerformanceAnalyzer
from performance_utils import PerformanceBenchmark


class TestEnergyAnalytics(unittest.TestCase):
    """Test suite for energy performance analytics."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.analyzer = EnergyPerformanceAnalyzer()
        self.benchmark = PerformanceBenchmark()
    
    def test_building_data_extraction(self):
        """Test building data extraction and processing."""
        print("\n🧪 Testing building data extraction...")
        
        # Extract building data
        building_data = self.analyzer.extract_building_data()
        
        # Verify data structure and content
        self.assertIsInstance(building_data, pd.DataFrame)
        self.assertGreater(len(building_data), 0)
        
        # Check required columns exist
        required_columns = [
            'space_id', 'space_name', 'area', 'volume', 
            'lighting_load_wsf', 'equipment_load_wsf'
        ]
        for column in required_columns:
            self.assertIn(column, building_data.columns)
        
        # Verify data types and ranges
        self.assertTrue(building_data['area'].dtype in [np.float64, np.int64])
        self.assertTrue((building_data['area'] >= 0).all())
        
        print(f"   ✅ Extracted {len(building_data)} building elements")
        print(f"   ✅ Data integrity verified ({len(building_data.columns)} columns)")
    
    def test_energy_performance_analysis(self):
        """Test comprehensive energy performance analysis."""
        print("\n🧪 Testing energy performance analysis...")
        
        # Perform analysis
        results = self.analyzer.analyze_energy_performance(days=30)  # Shorter for testing
        
        # Verify results structure
        required_keys = [
            'energy_statistics', 'correlation_analysis', 'temperature_regression',
            'optimal_setpoints', 'ml_predictions', 'efficiency_clusters'
        ]
        for key in required_keys:
            self.assertIn(key, results)
        
        # Verify energy statistics
        stats = results['energy_statistics']
        self.assertGreater(stats['total_annual_consumption'], 0)
        self.assertGreater(stats['peak_consumption'], 0)
        
        # Verify ML predictions
        ml_results = results['ml_predictions']
        self.assertIn('model_type', ml_results)
        self.assertGreater(ml_results['r2_score'], 0)  # Should have some predictive power
        
        # Verify optimization results
        optimization = results['optimal_setpoints']
        self.assertTrue(optimization['optimization_success'])
        self.assertGreater(optimization['annual_savings'], 0)
        
        print(f"   ✅ Analysis completed successfully")
        print(f"   ✅ ML model R² score: {ml_results['r2_score']:.3f}")
        print(f"   ✅ Optimization savings: ${optimization['annual_savings']:,.2f}")
    
    def test_machine_learning_capabilities(self):
        """Test machine learning model building and predictions."""
        print("\n🧪 Testing machine learning capabilities...")
        
        # This functionality is IMPOSSIBLE in PyRevit
        ml_results = self.analyzer._build_energy_prediction_model()
        
        # Verify ML model results
        self.assertIsInstance(ml_results, dict)
        self.assertIn('model_type', ml_results)
        self.assertIn('r2_score', ml_results)
        self.assertIn('feature_importance', ml_results)
        
        # Verify model performance
        self.assertGreater(ml_results['r2_score'], 0.5)  # Should explain >50% of variance
        self.assertGreater(len(ml_results['feature_importance']), 0)
        
        # Verify feature importance structure
        feature_importance = ml_results['feature_importance']
        self.assertIsInstance(feature_importance, list)
        for feature in feature_importance:
            self.assertIn('feature', feature)
            self.assertIn('importance', feature)
            self.assertGreaterEqual(feature['importance'], 0)
        
        print(f"   ✅ ML model trained successfully")
        print(f"   ✅ Model explains {ml_results['r2_score']:.1%} of variance")
        print(f"   ✅ {len(feature_importance)} features analyzed")
    
    def test_optimization_algorithms(self):
        """Test SciPy optimization algorithms."""
        print("\n🧪 Testing optimization algorithms...")
        
        # This functionality is IMPOSSIBLE in PyRevit (no SciPy)
        optimization_results = self.analyzer._optimize_hvac_setpoints()
        
        # Verify optimization results
        self.assertIsInstance(optimization_results, dict)
        self.assertTrue(optimization_results['optimization_success'])
        
        # Verify setpoint ranges are reasonable
        cooling = optimization_results['optimal_cooling_setpoint']
        heating = optimization_results['optimal_heating_setpoint']
        
        self.assertGreaterEqual(cooling, 65)
        self.assertLessEqual(cooling, 80)
        self.assertGreaterEqual(heating, 60)
        self.assertLessEqual(heating, 75)
        self.assertLess(heating, cooling)  # Heating should be lower than cooling
        
        # Verify savings calculation
        self.assertGreater(optimization_results['annual_savings'], 0)
        
        print(f"   ✅ Optimization completed successfully")
        print(f"   ✅ Optimal cooling: {cooling}°F, heating: {heating}°F")
        print(f"   ✅ Annual savings: ${optimization_results['annual_savings']:,.2f}")
    
    def test_clustering_analysis(self):
        """Test K-means clustering for efficiency analysis."""
        print("\n🧪 Testing clustering analysis...")
        
        # Ensure building data is available
        if self.analyzer.building_data is None:
            self.analyzer.extract_building_data()
        
        # This functionality is IMPOSSIBLE in PyRevit (no scikit-learn)
        clustering_results = self.analyzer._perform_efficiency_clustering()
        
        # Verify clustering results
        self.assertIsInstance(clustering_results, dict)
        self.assertIn('cluster_count', clustering_results)
        self.assertIn('cluster_analysis', clustering_results)
        
        # Verify cluster analysis
        cluster_analysis = clustering_results['cluster_analysis']
        self.assertEqual(len(cluster_analysis), 4)  # Should have 4 clusters
        
        for cluster in cluster_analysis:
            self.assertIn('cluster_id', cluster)
            self.assertIn('space_count', cluster)
            self.assertGreater(cluster['space_count'], 0)
        
        print(f"   ✅ Clustering analysis completed")
        print(f"   ✅ {clustering_results['cluster_count']} clusters identified")
        print(f"   ✅ All clusters have valid space assignments")
    
    def test_interactive_dashboard_creation(self):
        """Test interactive dashboard creation with Plotly."""
        print("\n🧪 Testing interactive dashboard creation...")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Change to temp directory for dashboard creation
            original_cwd = os.getcwd()
            os.chdir(temp_dir)
            
            try:
                # This functionality is IMPOSSIBLE in PyRevit (no Plotly)
                dashboard_path = self.analyzer.create_interactive_dashboard()
                
                # Verify dashboard file was created
                self.assertTrue(os.path.exists(dashboard_path))
                
                # Verify it's an HTML file
                self.assertTrue(dashboard_path.endswith('.html'))
                
                # Read and verify basic HTML structure
                with open(dashboard_path, 'r') as f:
                    content = f.read()
                    self.assertIn('<html>', content)
                    self.assertIn('plotly', content.lower())
                    self.assertIn('energy', content.lower())
                
                print(f"   ✅ Dashboard created successfully")
                print(f"   ✅ HTML file generated: {len(content)} characters")
                print(f"   ✅ Contains Plotly visualization code")
                
            finally:
                os.chdir(original_cwd)
    
    def test_performance_benchmarking(self):
        """Test performance benchmarking capabilities."""
        print("\n🧪 Testing performance benchmarking...")
        
        # Benchmark data processing
        result = self.benchmark.benchmark_data_processing(record_count=10000)
        
        self.assertGreater(result.execution_time, 0)
        self.assertGreater(result.operations_per_second, 0)
        
        # Benchmark ML computation  
        ml_result = self.benchmark.benchmark_ml_computation(data_size=1000)
        
        self.assertGreater(ml_result.execution_time, 0)
        self.assertGreater(ml_result.data_size_mb, 0)
        
        print(f"   ✅ Data processing: {result.execution_time:.3f}s")
        print(f"   ✅ ML computation: {ml_result.execution_time:.3f}s")
        print(f"   ✅ Memory usage: {ml_result.memory_usage_mb:.1f} MB")
    
    def test_async_operations(self):
        """Test async operations capability."""
        print("\n🧪 Testing async operations...")
        
        async def test_async_capability():
            # This functionality is IMPOSSIBLE in PyRevit (no async/await)
            result = self.benchmark.benchmark_async_operations(operation_count=50)
            
            self.assertGreater(result.execution_time, 0)
            self.assertEqual(result.iterations, 50)
            
            return result
        
        # Run async test
        result = asyncio.run(test_async_capability())
        
        print(f"   ✅ Async operations completed: {result.iterations}")
        print(f"   ✅ Execution time: {result.execution_time:.3f}s")
        print(f"   ✅ Operations per second: {result.operations_per_second:.1f}")
    
    def test_pyrevit_limitation_simulation(self):
        """Test PyRevit limitation simulation."""
        print("\n🧪 Testing PyRevit limitation analysis...")
        
        from performance_utils import simulate_pyrevit_limitations
        
        limitations = simulate_pyrevit_limitations()
        
        # Verify limitation documentation
        expected_limitations = [
            'async_operations', 'ml_libraries', 'numpy_scipy', 
            'pandas', 'opencv', 'modern_http_clients'
        ]
        
        for limitation in expected_limitations:
            self.assertIn(limitation, limitations)
            self.assertFalse(limitations[limitation]['supported'])
            self.assertIn('reason', limitations[limitation])
        
        print(f"   ✅ Documented {len(limitations)} PyRevit limitations")
        print(f"   ✅ All limitations have explanations and workarounds")


class TestEnergyAnalyticsIntegration(unittest.TestCase):
    """Integration tests for energy analytics POC."""
    
    def test_end_to_end_workflow(self):
        """Test complete end-to-end energy analysis workflow."""
        print("\n🧪 Testing end-to-end workflow...")
        
        analyzer = EnergyPerformanceAnalyzer()
        
        # Complete workflow
        building_data = analyzer.extract_building_data()
        analysis_results = analyzer.analyze_energy_performance(days=30)
        
        # Verify workflow completion
        self.assertIsNotNone(building_data)
        self.assertIsNotNone(analysis_results)
        self.assertGreater(len(building_data), 0)
        
        # Verify all analysis components completed
        required_results = [
            'energy_statistics', 'ml_predictions', 'optimal_setpoints',
            'efficiency_clusters', 'potential_savings'
        ]
        
        for result_type in required_results:
            self.assertIn(result_type, analysis_results)
        
        print(f"   ✅ End-to-end workflow completed successfully")
        print(f"   ✅ All analysis components generated results")
    
    def test_roi_calculation_accuracy(self):
        """Test ROI and savings calculation accuracy."""
        print("\n🧪 Testing ROI calculation accuracy...")
        
        analyzer = EnergyPerformanceAnalyzer()
        results = analyzer.analyze_energy_performance(days=30)
        
        savings = results['potential_savings']
        
        # Verify savings calculations are reasonable
        self.assertGreater(savings['total_potential_savings'], 0)
        self.assertGreater(savings['potential_savings_percentage'], 0)
        self.assertLess(savings['potential_savings_percentage'], 100)  # Should be realistic
        self.assertGreater(savings['roi_years'], 0)
        self.assertLess(savings['roi_years'], 20)  # Should be reasonable payback
        
        # Verify savings breakdown
        total_calculated = (
            savings['hvac_optimization_savings'] +
            savings['lighting_upgrade_savings'] +
            savings['equipment_efficiency_savings'] +
            savings['envelope_improvement_savings']
        )
        
        self.assertAlmostEqual(
            total_calculated, 
            savings['total_potential_savings'], 
            places=2
        )
        
        print(f"   ✅ ROI calculations validated")
        print(f"   ✅ Total savings: ${savings['total_potential_savings']:,.2f}")
        print(f"   ✅ Payback period: {savings['roi_years']} years")


def run_tests():
    """Run all energy analytics tests."""
    print("🚀 Running Energy Analytics POC Test Suite")
    print("=" * 60)
    print("⚠️  Testing capabilities IMPOSSIBLE in PyRevit!")
    print()
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test cases
    suite.addTests(loader.loadTestsFromTestCase(TestEnergyAnalytics))
    suite.addTests(loader.loadTestsFromTestCase(TestEnergyAnalyticsIntegration))
    
    # Run tests with detailed output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "=" * 60)
    print("🏆 TEST SUMMARY")
    print(f"   Tests run: {result.testsRun}")
    print(f"   Failures: {len(result.failures)}")
    print(f"   Errors: {len(result.errors)}")
    
    if result.wasSuccessful():
        print("   ✅ All tests passed!")
        print("   🎉 Energy Analytics POC validated successfully!")
    else:
        print("   ❌ Some tests failed")
        for test, traceback in result.failures + result.errors:
            print(f"      Failed: {test}")
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)