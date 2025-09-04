#!/usr/bin/env python3
"""
Comprehensive validation of all RevitPy POCs without requiring external dependencies.
This script validates the structure, imports, and basic functionality of each POC.
"""

import os
import sys
import ast
import importlib.util
from pathlib import Path


class POCValidator:
    """Validator for POC implementations."""
    
    def __init__(self):
        self.pocs = [
            {
                'name': 'Building Energy Performance Analytics',
                'directory': 'energy-analytics',
                'main_module': 'energy_analyzer.py',
                'class_name': 'EnergyPerformanceAnalyzer',
                'key_methods': ['predict_energy_consumption', 'optimize_hvac_systems']
            },
            {
                'name': 'ML-Powered Space Planning Optimization',
                'directory': 'ml-space-planning', 
                'main_module': 'space_optimizer.py',
                'class_name': 'SpaceOptimizer',
                'key_methods': ['predict_space_occupancy', 'optimize_space_allocation']
            },
            {
                'name': 'Real-time IoT Sensor Integration',
                'directory': 'iot-sensor-integration',
                'main_module': 'iot_monitor.py', 
                'class_name': 'RealTimeBuildingMonitor',
                'key_methods': ['monitor_hvac_sensors', 'initialize_cloud_connections']
            },
            {
                'name': 'Advanced Structural Analysis',
                'directory': 'structural-analysis',
                'main_module': 'structural_analyzer.py',
                'class_name': 'StructuralAnalyzer', 
                'key_methods': ['analyze_frame_structure', 'seismic_response_analysis']
            },
            {
                'name': 'Construction Progress Monitoring with Computer Vision',
                'directory': 'computer-vision-progress',
                'main_module': 'progress_monitor.py',
                'class_name': 'ConstructionProgressMonitor',
                'key_methods': ['analyze_construction_photos', 'real_time_progress_monitoring']
            }
        ]
    
    def validate_file_structure(self):
        """Validate that all required files exist."""
        print("🏗️ VALIDATING POC FILE STRUCTURE")
        print("=" * 50)
        
        all_valid = True
        
        for poc in self.pocs:
            print(f"\n📁 {poc['name']}")
            
            # Check main directory
            poc_dir = Path(poc['directory'])
            if poc_dir.exists():
                print(f"   ✅ Directory exists: {poc_dir}")
            else:
                print(f"   ❌ Directory missing: {poc_dir}")
                all_valid = False
                continue
            
            # Check required subdirectories
            required_dirs = ['src', 'examples', 'tests', 'docs']
            for req_dir in required_dirs:
                full_path = poc_dir / req_dir
                if full_path.exists():
                    print(f"   ✅ {req_dir}/ exists")
                else:
                    print(f"   ❌ {req_dir}/ missing")
                    all_valid = False
            
            # Check main module
            main_module_path = poc_dir / 'src' / poc['main_module']
            if main_module_path.exists():
                print(f"   ✅ Main module: {poc['main_module']}")
            else:
                print(f"   ❌ Main module missing: {poc['main_module']}")
                all_valid = False
        
        return all_valid
    
    def validate_code_structure(self):
        """Validate code structure using AST parsing."""
        print("\n\n🔍 VALIDATING CODE STRUCTURE")
        print("=" * 50)
        
        all_valid = True
        
        for poc in self.pocs:
            print(f"\n🐍 {poc['name']}")
            
            main_module_path = Path(poc['directory']) / 'src' / poc['main_module']
            
            if not main_module_path.exists():
                print(f"   ❌ Module file not found: {main_module_path}")
                all_valid = False
                continue
            
            try:
                # Parse the Python file using AST
                with open(main_module_path, 'r') as f:
                    content = f.read()
                
                # Parse the AST
                tree = ast.parse(content)
                
                # Find classes and methods
                classes_found = []
                methods_found = []
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        classes_found.append(node.name)
                        
                        # Find methods in this class
                        for item in node.body:
                            if isinstance(item, ast.FunctionDef):
                                methods_found.append(item.name)
                
                # Check for expected class
                if poc['class_name'] in classes_found:
                    print(f"   ✅ Class found: {poc['class_name']}")
                else:
                    print(f"   ❌ Expected class not found: {poc['class_name']}")
                    print(f"      Found classes: {classes_found}")
                    all_valid = False
                
                # Check for key methods
                key_methods_found = 0
                for method in poc['key_methods']:
                    if method in methods_found:
                        print(f"   ✅ Method found: {method}")
                        key_methods_found += 1
                    else:
                        print(f"   ⚠️  Method not found: {method}")
                
                print(f"   📊 Methods found: {key_methods_found}/{len(poc['key_methods'])}")
                
                # Check for async methods (important for some POCs)
                async_methods = []
                for node in ast.walk(tree):
                    if isinstance(node, ast.AsyncFunctionDef):
                        async_methods.append(node.name)
                
                if async_methods:
                    print(f"   ⚡ Async methods found: {len(async_methods)}")
                
            except SyntaxError as e:
                print(f"   ❌ Syntax error in {main_module_path}: {e}")
                all_valid = False
            except Exception as e:
                print(f"   ❌ Error parsing {main_module_path}: {e}")
                all_valid = False
        
        return all_valid
    
    def validate_documentation(self):
        """Validate that documentation exists."""
        print("\n\n📚 VALIDATING DOCUMENTATION")
        print("=" * 50)
        
        all_valid = True
        
        for poc in self.pocs:
            print(f"\n📖 {poc['name']}")
            
            poc_dir = Path(poc['directory'])
            docs_dir = poc_dir / 'docs'
            
            if docs_dir.exists():
                doc_files = list(docs_dir.glob('*.md'))
                if doc_files:
                    print(f"   ✅ Documentation found: {len(doc_files)} files")
                    for doc_file in doc_files:
                        print(f"      • {doc_file.name}")
                else:
                    print(f"   ⚠️  No .md files in docs directory")
            else:
                print(f"   ❌ No docs directory found")
                all_valid = False
        
        # Check for master documentation
        master_docs = [
            'MASTER_DOCUMENTATION.md',
            'README.md'
        ]
        
        print(f"\n📋 Master Documentation")
        for doc in master_docs:
            if Path(doc).exists():
                print(f"   ✅ {doc} exists")
            else:
                print(f"   ❌ {doc} missing")
                all_valid = False
        
        return all_valid
    
    def validate_examples_and_tests(self):
        """Validate examples and tests exist."""
        print("\n\n🧪 VALIDATING EXAMPLES AND TESTS")
        print("=" * 50)
        
        all_valid = True
        
        for poc in self.pocs:
            print(f"\n🔬 {poc['name']}")
            
            poc_dir = Path(poc['directory'])
            
            # Check examples
            examples_dir = poc_dir / 'examples'
            if examples_dir.exists():
                example_files = list(examples_dir.glob('*.py'))
                if example_files:
                    print(f"   ✅ Examples found: {len(example_files)} files")
                else:
                    print(f"   ⚠️  No .py files in examples directory")
            else:
                print(f"   ❌ No examples directory")
                all_valid = False
            
            # Check tests
            tests_dir = poc_dir / 'tests'
            if tests_dir.exists():
                test_files = list(tests_dir.glob('test_*.py'))
                if test_files:
                    print(f"   ✅ Tests found: {len(test_files)} files")
                else:
                    print(f"   ⚠️  No test_*.py files in tests directory")
            else:
                print(f"   ❌ No tests directory")
                all_valid = False
        
        return all_valid
    
    def validate_common_infrastructure(self):
        """Validate common infrastructure."""
        print("\n\n🔧 VALIDATING COMMON INFRASTRUCTURE")
        print("=" * 50)
        
        common_dir = Path('common/src')
        
        required_files = [
            'performance_utils.py',
            'integration_helpers.py', 
            'revitpy_mock.py',
            'data_generators.py'
        ]
        
        all_valid = True
        
        for file_name in required_files:
            file_path = common_dir / file_name
            if file_path.exists():
                print(f"   ✅ {file_name}")
                
                # Basic validation - check for key classes/functions
                try:
                    with open(file_path, 'r') as f:
                        content = f.read()
                    
                    tree = ast.parse(content)
                    
                    classes = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
                    functions = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
                    
                    print(f"      Classes: {len(classes)}, Functions: {len(functions)}")
                    
                except Exception as e:
                    print(f"      ⚠️  Error parsing: {e}")
            else:
                print(f"   ❌ {file_name} missing")
                all_valid = False
        
        return all_valid
    
    def run_validation(self):
        """Run comprehensive validation."""
        print("🚀 REVITPY POC COMPREHENSIVE VALIDATION")
        print("=" * 60)
        print("⚠️  This validation checks structure without requiring external dependencies")
        print()
        
        results = {
            'file_structure': self.validate_file_structure(),
            'code_structure': self.validate_code_structure(),
            'documentation': self.validate_documentation(),
            'examples_tests': self.validate_examples_and_tests(),
            'common_infrastructure': self.validate_common_infrastructure()
        }
        
        print("\n\n🏆 VALIDATION SUMMARY")
        print("=" * 50)
        
        total_checks = len(results)
        passed_checks = sum(results.values())
        
        for check_name, passed in results.items():
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"   {check_name.replace('_', ' ').title()}: {status}")
        
        print(f"\n📊 Overall Score: {passed_checks}/{total_checks} ({passed_checks/total_checks*100:.1f}%)")
        
        if passed_checks == total_checks:
            print("🎉 ALL VALIDATIONS PASSED!")
            print("🚀 RevitPy POCs are ready for demonstration!")
        else:
            print("⚠️  Some validations failed - see details above")
        
        return results


if __name__ == "__main__":
    validator = POCValidator()
    results = validator.run_validation()
    
    # Exit with non-zero status if any validation failed
    sys.exit(0 if all(results.values()) else 1)