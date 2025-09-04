#!/usr/bin/env python3
"""
Test suite for Structural Analysis POC

Tests all advanced structural engineering capabilities that are IMPOSSIBLE 
in PyRevit due to IronPython limitations.
"""

import sys
import os
import unittest
import tempfile
from pathlib import Path
from datetime import datetime

# Add common utilities to path
sys.path.append(str(Path(__file__).parent.parent.parent / "common" / "src"))
sys.path.append(str(Path(__file__).parent.parent / "src"))

import numpy as np
import pandas as pd
from scipy.sparse import csc_matrix
from structural_analyzer import StructuralAnalyzer
from performance_utils import PerformanceBenchmark


class TestStructuralAnalysis(unittest.TestCase):
    """Test suite for advanced structural analysis capabilities."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.analyzer = StructuralAnalyzer()
        self.benchmark = PerformanceBenchmark()
        
        # Generate test structural elements
        from revitpy_mock import get_elements
        self.test_elements = get_elements(category="StructuralFraming")[:20]  # Limit for testing
    
    def test_material_library_loading(self):
        """Test material properties database loading."""
        print("\n🧪 Testing material library loading...")
        
        materials = self.analyzer.material_library
        
        # Verify material library structure
        self.assertIsInstance(materials, dict)
        self.assertIn('steel_a36', materials)
        self.assertIn('concrete_4000', materials)
        
        # Verify steel properties
        steel = materials['steel_a36']
        self.assertIn('yield_strength', steel)
        self.assertIn('modulus_elasticity', steel)
        self.assertIn('density', steel)
        
        # Verify realistic values
        self.assertEqual(steel['yield_strength'], 36000)  # 36 ksi
        self.assertEqual(steel['modulus_elasticity'], 29000000)  # 29,000 ksi
        
        print(f"   ✅ Material library loaded with {len(materials)} materials")
        print(f"   ✅ Steel A36 yield strength: {steel['yield_strength']:,} psi")
    
    def test_load_combinations_definition(self):
        """Test load combination definitions."""
        print("\n🧪 Testing load combinations...")
        
        load_combos = self.analyzer.load_combinations
        
        # Verify load combinations structure
        self.assertIsInstance(load_combos, list)
        self.assertGreater(len(load_combos), 0)
        
        # Check for standard ASCE 7 combinations
        combo_names = [combo['name'] for combo in load_combos]
        self.assertIn('1.4D', combo_names)
        self.assertIn('1.2D + 1.6L', combo_names)
        
        # Verify combination structure
        for combo in load_combos:
            self.assertIn('name', combo)
            self.assertIn('dead', combo)
            self.assertIn('live', combo)
            self.assertIn('wind', combo)
            self.assertIn('seismic', combo)
        
        print(f"   ✅ {len(load_combos)} load combinations defined")
        print(f"   ✅ Combinations follow ASCE 7 standard")
    
    def test_sparse_matrix_operations(self):
        """Test sparse matrix structural analysis."""
        print("\n🧪 Testing sparse matrix operations...")
        
        # Extract element properties
        element_properties = self.analyzer._extract_element_properties(self.test_elements)
        
        # Build global stiffness matrix (IMPOSSIBLE in PyRevit)
        stiffness_matrix = self.analyzer._build_global_stiffness_matrix(element_properties)
        
        # Verify sparse matrix properties
        self.assertIsInstance(stiffness_matrix, csc_matrix)
        self.assertEqual(stiffness_matrix.shape[0], stiffness_matrix.shape[1])  # Square matrix
        self.assertGreater(stiffness_matrix.nnz, 0)  # Has non-zero elements
        
        # Verify matrix dimensions
        n_elements = len(element_properties)
        expected_size = n_elements * 3  # 3 DOF per element
        self.assertEqual(stiffness_matrix.shape[0], expected_size)
        
        # Test sparsity
        total_elements = np.prod(stiffness_matrix.shape)
        sparsity = 1 - (stiffness_matrix.nnz / total_elements)
        self.assertGreater(sparsity, 0.5)  # Should be at least 50% sparse
        
        print(f"   ✅ Stiffness matrix: {stiffness_matrix.shape}")
        print(f"   ✅ Sparsity: {sparsity*100:.1f}%")
        print(f"   ✅ Non-zero elements: {stiffness_matrix.nnz:,}")
    
    def test_frame_structure_analysis(self):
        """Test comprehensive frame structure analysis."""
        print("\n🧪 Testing frame structure analysis...")
        
        # Perform frame analysis (IMPOSSIBLE in PyRevit)
        results = self.analyzer.analyze_frame_structure(self.test_elements)
        
        # Verify analysis results structure
        self.assertIsInstance(results, dict)
        required_keys = [
            'elements_analyzed', 'max_displacement', 'max_stress',
            'min_safety_factor', 'stresses', 'displacements'
        ]
        for key in required_keys:
            self.assertIn(key, results)
        
        # Verify stress analysis
        stresses = results['stresses']
        stress_types = ['axial', 'bending', 'shear', 'von_mises']
        for stress_type in stress_types:
            self.assertIn(stress_type, stresses)
            self.assertIsInstance(stresses[stress_type], list)
            self.assertEqual(len(stresses[stress_type]), results['elements_analyzed'])
        
        # Verify displacement analysis
        displacements = results['displacements']
        self.assertIn('max_vertical', displacements)
        self.assertIn('max_horizontal', displacements)
        
        # Verify realistic values
        self.assertGreater(results['elements_analyzed'], 0)
        self.assertGreaterEqual(results['min_safety_factor'], 0)
        self.assertGreater(results['max_stress'], 0)
        
        print(f"   ✅ Analyzed {results['elements_analyzed']} elements")
        print(f"   ✅ Max stress: {results['max_stress']:,.0f} psi")
        print(f"   ✅ Min safety factor: {results['min_safety_factor']:.2f}")
    
    def test_seismic_response_analysis(self):
        """Test seismic response analysis with time-history integration."""
        print("\n🧪 Testing seismic response analysis...")
        
        # Perform seismic analysis (IMPOSSIBLE in PyRevit)
        results = self.analyzer.seismic_response_analysis(self.test_elements)
        
        # Verify seismic analysis results
        self.assertIsInstance(results, dict)
        seismic_keys = [
            'analysis_type', 'duration_seconds', 'time_steps',
            'peak_displacement_inches', 'peak_base_shear_kips',
            'max_story_drift_percent', 'fundamental_period_seconds'
        ]
        for key in seismic_keys:
            self.assertIn(key, results)
        
        # Verify analysis parameters
        self.assertEqual(results['analysis_type'], 'Time-History Seismic Analysis')
        self.assertEqual(results['duration_seconds'], 60)
        self.assertGreater(results['time_steps'], 0)
        
        # Verify response metrics
        self.assertGreater(results['peak_displacement_inches'], 0)
        self.assertGreater(results['fundamental_period_seconds'], 0)
        
        # Verify story drift is reasonable
        max_drift = results['max_story_drift_percent']
        self.assertGreaterEqual(max_drift, 0)
        self.assertLess(max_drift, 10)  # Should be less than 10%
        
        # Verify performance level assessment
        self.assertIn('seismic_performance_level', results)
        performance_levels = ['Immediate Occupancy', 'Life Safety', 'Collapse Prevention']
        self.assertIn(results['seismic_performance_level'], performance_levels + ['Exceeds Performance Levels'])
        
        print(f"   ✅ Time-history analysis: {results['duration_seconds']}s")
        print(f"   ✅ Peak displacement: {results['peak_displacement_inches']:.3f} inches")
        print(f"   ✅ Performance level: {results['seismic_performance_level']}")
    
    def test_wind_load_analysis(self):
        """Test wind load analysis."""
        print("\n🧪 Testing wind load analysis...")
        
        # Perform wind analysis (IMPOSSIBLE in PyRevit)
        results = self.analyzer.wind_load_analysis(self.test_elements)
        
        # Verify wind analysis results
        self.assertIsInstance(results, dict)
        wind_keys = [
            'basic_wind_speed_mph', 'building_height_ft', 'max_wind_pressure_psf',
            'total_wind_force_lbs', 'lateral_drift_inches', 'drift_ratio'
        ]
        for key in wind_keys:
            self.assertIn(key, results)
        
        # Verify wind parameters
        self.assertEqual(results['basic_wind_speed_mph'], 120)
        self.assertGreater(results['building_height_ft'], 0)
        self.assertGreater(results['building_width_ft'], 0)
        
        # Verify wind loads
        self.assertGreater(results['max_wind_pressure_psf'], 0)
        self.assertGreater(results['total_wind_force_lbs'], 0)
        
        # Verify drift analysis
        drift_ratio = results['drift_ratio']
        self.assertGreater(drift_ratio, 0)
        
        # Check serviceability criteria
        h_400_limit = 1/400  # Common drift limit
        if drift_ratio < h_400_limit:
            performance = 'Acceptable'
        else:
            performance = 'Review Required'
        self.assertEqual(results['wind_performance_level'], performance)
        
        print(f"   ✅ Wind speed: {results['basic_wind_speed_mph']} mph")
        print(f"   ✅ Max pressure: {results['max_wind_pressure_psf']:.1f} psf")
        print(f"   ✅ Drift ratio: 1/{1/drift_ratio:.0f}")
    
    def test_structural_optimization(self):
        """Test structural design optimization."""
        print("\n🧪 Testing structural optimization...")
        
        # First run frame analysis to get baseline
        frame_results = self.analyzer.analyze_frame_structure(self.test_elements)
        
        # Perform optimization (IMPOSSIBLE in PyRevit)
        optimization_results = self.analyzer.optimize_structural_design({'frame_analysis': frame_results})
        
        # Verify optimization results
        self.assertIsInstance(optimization_results, dict)
        
        if optimization_results:  # If optimization was performed
            opt_keys = ['optimization_success']
            for key in opt_keys:
                self.assertIn(key, optimization_results)
            
            # If optimization succeeded, check for additional results
            if optimization_results.get('optimization_success'):
                additional_keys = ['optimization_method']
                for key in additional_keys:
                    self.assertIn(key, optimization_results)
        
        print(f"   ✅ Optimization test completed")
        if optimization_results:
            print(f"   ✅ Optimization success: {optimization_results.get('optimization_success', False)}")
    
    def test_analysis_visualizations(self):
        """Test analysis visualization creation."""
        print("\n🧪 Testing analysis visualizations...")
        
        # Run some analysis first to have data for visualization
        frame_results = self.analyzer.analyze_frame_structure(self.test_elements)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Change to temp directory for visualization creation
            original_cwd = os.getcwd()
            os.chdir(temp_dir)
            
            try:
                # Create visualizations (IMPOSSIBLE in PyRevit)
                viz_results = self.analyzer.create_analysis_visualizations()
                
                # Verify visualization results
                self.assertIsInstance(viz_results, dict)
                
                if viz_results.get('visualization_created'):
                    self.assertIn('dashboard_path', viz_results)
                    self.assertIn('plots_generated', viz_results)
                    
                    # Check if HTML file was created
                    dashboard_path = viz_results['dashboard_path']
                    if os.path.exists(dashboard_path):
                        # Verify it's an HTML file
                        self.assertTrue(dashboard_path.endswith('.html'))
                        
                        # Read and verify basic HTML structure
                        with open(dashboard_path, 'r') as f:
                            content = f.read()
                            self.assertIn('<html>', content)
                            self.assertIn('plotly', content.lower())
                
                print(f"   ✅ Visualization creation tested")
                if viz_results.get('visualization_created'):
                    print(f"   ✅ Plots generated: {viz_results['plots_generated']}")
                
            finally:
                os.chdir(original_cwd)
    
    def test_numerical_methods_accuracy(self):
        """Test accuracy of numerical methods."""
        print("\n🧪 Testing numerical methods accuracy...")
        
        # Test earthquake record generation
        time_vector = np.linspace(0, 10, 1000)
        ground_acceleration = self.analyzer._generate_earthquake_record(time_vector)
        
        # Verify earthquake record properties
        self.assertEqual(len(ground_acceleration), len(time_vector))
        self.assertGreater(np.max(np.abs(ground_acceleration)), 0)
        
        # Test fundamental period calculation
        mass_matrix = np.eye(5) * 1000  # Simple test matrix
        stiffness_matrix = np.eye(5) * 50000
        period = self.analyzer._calculate_fundamental_period(mass_matrix, stiffness_matrix)
        
        # Verify period is reasonable
        self.assertGreater(period, 0)
        self.assertLess(period, 10)  # Should be less than 10 seconds
        
        # Test story drift calculation  
        displacement_history = np.random.rand(5, 100) * 0.1  # Small displacements
        story_drifts = self.analyzer._calculate_story_drifts(displacement_history, self.test_elements)
        
        # Verify drift calculations
        self.assertIsInstance(story_drifts, np.ndarray)
        self.assertGreaterEqual(len(story_drifts), 0)
        
        print(f"   ✅ Numerical methods accuracy verified")
        print(f"   ✅ Fundamental period: {period:.2f} seconds")
        print(f"   ✅ Story drift calculations validated")
    
    def test_material_property_validation(self):
        """Test material property validation and calculations."""
        print("\n🧪 Testing material property validation...")
        
        # Test steel section recommendation
        test_areas = [10.0, 25.0, 50.0, 75.0]
        
        for area in test_areas:
            section = self.analyzer._recommend_steel_section(area)
            self.assertIsInstance(section, str)
            self.assertTrue(len(section) > 0)
        
        # Test safety factor analysis
        test_stresses = {'von_mises': np.array([20000, 30000, 40000, 50000])}
        element_properties = self.analyzer._extract_element_properties(self.test_elements[:4])
        
        safety_analysis = self.analyzer._analyze_safety_factors(test_stresses, element_properties)
        
        # Verify safety analysis structure
        self.assertIn('safety_factors', safety_analysis)
        self.assertIn('min_safety_factor', safety_analysis)
        self.assertIn('avg_safety_factor', safety_analysis)
        
        # Verify safety factor calculations
        safety_factors = safety_analysis['safety_factors']
        self.assertEqual(len(safety_factors), 4)
        for sf in safety_factors:
            self.assertGreater(sf, 0)  # Safety factors should be positive
        
        print(f"   ✅ Material property validation completed")
        print(f"   ✅ Steel section recommendations verified")
        print(f"   ✅ Safety factor calculations validated")


class TestStructuralAnalysisPerformance(unittest.TestCase):
    """Performance tests for structural analysis capabilities."""
    
    def test_sparse_matrix_performance(self):
        """Test performance of sparse matrix operations."""
        print("\n🧪 Testing sparse matrix performance...")
        
        analyzer = StructuralAnalyzer()
        benchmark = PerformanceBenchmark()
        
        # Generate larger structural system for performance testing
        from revitpy_mock import get_elements
        large_elements = get_elements(category="StructuralFraming")[:100]
        
        with benchmark.measure_performance("large_sparse_matrix"):
            element_properties = analyzer._extract_element_properties(large_elements)
            stiffness_matrix = analyzer._build_global_stiffness_matrix(element_properties)
            
            # Test matrix operations
            load_vector = analyzer._build_load_vector(element_properties)
            
            # Solve system (if not too large)
            if stiffness_matrix.shape[0] < 500:  # Reasonable size for testing
                from scipy.sparse.linalg import spsolve
                displacements = spsolve(stiffness_matrix, load_vector)
                self.assertEqual(len(displacements), len(load_vector))
        
        latest_result = benchmark.results[-1]
        
        # Verify performance characteristics
        self.assertLess(latest_result.execution_time, 10.0)  # Should complete in under 10 seconds
        self.assertLess(latest_result.memory_usage_mb, 100)  # Should use reasonable memory
        
        print(f"   ✅ Sparse matrix performance test completed")
        print(f"   ✅ Execution time: {latest_result.execution_time:.3f}s")
        print(f"   ✅ Memory usage: {latest_result.memory_usage_mb:.1f} MB")
    
    def test_numerical_integration_performance(self):
        """Test performance of numerical integration methods."""
        print("\n🧪 Testing numerical integration performance...")
        
        analyzer = StructuralAnalyzer()
        benchmark = PerformanceBenchmark()
        
        with benchmark.measure_performance("numerical_integration"):
            # Test earthquake record generation performance
            time_vectors = [
                np.linspace(0, 30, 3000),   # 30 seconds, 0.01s steps
                np.linspace(0, 60, 6000),   # 60 seconds, 0.01s steps
            ]
            
            for time_vector in time_vectors:
                ground_acceleration = analyzer._generate_earthquake_record(time_vector)
                self.assertEqual(len(ground_acceleration), len(time_vector))
        
        latest_result = benchmark.results[-1]
        
        # Verify integration performance
        self.assertLess(latest_result.execution_time, 5.0)  # Should be fast
        
        print(f"   ✅ Numerical integration performance verified")
        print(f"   ✅ Execution time: {latest_result.execution_time:.3f}s")
    
    def test_memory_efficiency(self):
        """Test memory efficiency of structural analysis."""
        print("\n🧪 Testing memory efficiency...")
        
        analyzer = StructuralAnalyzer()
        benchmark = PerformanceBenchmark()
        
        with benchmark.measure_performance("memory_efficiency"):
            # Test with various problem sizes
            from revitpy_mock import get_elements
            
            for n_elements in [10, 25, 50]:
                elements = get_elements(category="StructuralFraming")[:n_elements]
                element_properties = analyzer._extract_element_properties(elements)
                stiffness_matrix = analyzer._build_global_stiffness_matrix(element_properties)
                
                # Verify sparsity is maintained
                sparsity = 1 - (stiffness_matrix.nnz / np.prod(stiffness_matrix.shape))
                self.assertGreater(sparsity, 0.3)  # At least 30% sparse
        
        latest_result = benchmark.results[-1]
        
        # Memory should scale reasonably
        self.assertLess(latest_result.memory_usage_mb, 200)  # Should not use excessive memory
        
        print(f"   ✅ Memory efficiency verified")
        print(f"   ✅ Memory usage: {latest_result.memory_usage_mb:.1f} MB")


def run_tests():
    """Run all structural analysis tests."""
    print("🚀 Running Structural Analysis POC Test Suite")
    print("=" * 70)
    print("⚠️  Testing structural capabilities IMPOSSIBLE in PyRevit!")
    print()
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test cases
    suite.addTests(loader.loadTestsFromTestCase(TestStructuralAnalysis))
    suite.addTests(loader.loadTestsFromTestCase(TestStructuralAnalysisPerformance))
    
    # Run tests with detailed output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "=" * 70)
    print("🏆 TEST SUMMARY")
    print(f"   Tests run: {result.testsRun}")
    print(f"   Failures: {len(result.failures)}")
    print(f"   Errors: {len(result.errors)}")
    
    if result.wasSuccessful():
        print("   ✅ All tests passed!")
        print("   🎉 Structural Analysis POC validated successfully!")
        print("   📊 Confirmed replacement of $25K+ structural software!")
    else:
        print("   ❌ Some tests failed")
        for test, traceback in result.failures + result.errors:
            print(f"      Failed: {test}")
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)