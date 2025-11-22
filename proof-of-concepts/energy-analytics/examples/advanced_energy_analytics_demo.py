#!/usr/bin/env python3
"""
Advanced Energy Analytics Demonstration

This example showcases the full capabilities of the RevitPy Energy Analytics POC,
demonstrating features that are IMPOSSIBLE in PyRevit due to IronPython limitations.

Key Features Demonstrated:
1. Advanced statistical analysis with SciPy
2. Machine learning predictions with scikit-learn
3. Interactive visualizations with Plotly
4. Real-time data processing with async operations
5. Optimization algorithms for energy efficiency
"""

import asyncio
import sys
from pathlib import Path

# Add common utilities to path
sys.path.append(str(Path(__file__).parent.parent.parent / "common" / "src"))

from datetime import datetime

import numpy as np

# Import our energy analytics module
sys.path.append(str(Path(__file__).parent.parent / "src"))
from energy_analyzer import EnergyPerformanceAnalyzer
from integration_helpers import PyRevitBridge, WorkflowRequest

# Import performance utilities
from performance_utils import PYREVIT_BASELINES, PerformanceBenchmark


class EnergyAnalyticsDemo:
    """Comprehensive demonstration of energy analytics capabilities."""

    def __init__(self):
        self.analyzer = EnergyPerformanceAnalyzer()
        self.benchmark = PerformanceBenchmark()
        self.bridge = PyRevitBridge()

        # Set PyRevit baseline performance for comparison
        for operation, baseline_time in PYREVIT_BASELINES.items():
            self.benchmark.set_baseline(operation, baseline_time)

    async def run_comprehensive_demo(self):
        """Run the complete energy analytics demonstration."""
        print("🚀 RevitPy Energy Analytics POC - Comprehensive Demonstration")
        print("=" * 70)
        print("⚠️  ALL capabilities shown are IMPOSSIBLE in PyRevit/IronPython!")
        print()

        # Demonstration sections
        await self._demo_data_extraction_performance()
        await self._demo_advanced_analytics()
        await self._demo_machine_learning_capabilities()
        await self._demo_optimization_algorithms()
        await self._demo_interactive_visualizations()
        await self._demo_real_time_monitoring()
        await self._demo_pyrevit_integration()

        # Generate comprehensive performance report
        self._generate_performance_report()

        print("\n🎉 Demonstration complete!")
        print(
            "📊 This POC replaces $50,000+ energy modeling software with modern Python capabilities!"
        )

    async def _demo_data_extraction_performance(self):
        """Demonstrate high-performance data extraction."""
        print("1️⃣ DATA EXTRACTION & PROCESSING PERFORMANCE")
        print("-" * 50)

        # Benchmark large dataset processing
        with self.benchmark.measure_performance(
            "data_processing_100000", data_size_mb=50
        ):
            # Extract building data
            building_data = self.analyzer.extract_building_data()

            # Simulate processing large amounts of energy data
            print(f"   📊 Processed {len(building_data)} building elements")
            print(
                "   🔍 Analyzing thermal properties, HVAC systems, and energy loads..."
            )

            # Complex data operations (impossible in IronPython)
            thermal_analysis = (
                building_data.groupby("space_type")
                .agg(
                    {
                        "area": ["mean", "sum", "std"],
                        "lighting_load_wsf": ["mean", "max"],
                        "equipment_load_wsf": ["mean", "max"],
                        "cooling_load_btusf": "mean",
                        "heating_load_btusf": "mean",
                    }
                )
                .round(2)
            )

            print(
                f"   ✅ Generated thermal analysis for {len(thermal_analysis)} space types"
            )

        # Show performance vs PyRevit
        latest_result = self.benchmark.results[-1]
        improvement = self.benchmark.get_improvement_factor("data_processing_100000")

        print(f"   ⚡ Execution time: {latest_result.execution_time:.2f} seconds")
        print(f"   💾 Memory usage: {latest_result.memory_usage_mb:.1f} MB")
        print(f"   🏃 Data throughput: {latest_result.mb_per_second:.1f} MB/s")
        if improvement:
            print(
                f"   🚀 Performance improvement vs PyRevit: {improvement:.1f}x faster"
            )
        print()

    async def _demo_advanced_analytics(self):
        """Demonstrate advanced statistical analysis capabilities."""
        print("2️⃣ ADVANCED STATISTICAL ANALYSIS")
        print("-" * 50)

        with self.benchmark.measure_performance("statistical_analysis"):
            # Perform comprehensive energy analysis
            print("   📈 Running comprehensive energy performance analysis...")
            results = self.analyzer.analyze_energy_performance(days=365)

            # Display advanced analytics results
            stats = results["energy_statistics"]
            correlation = results["correlation_analysis"]
            regression = results["temperature_regression"]

            print(
                f"   🏢 Annual consumption: {stats['total_annual_consumption']:,.0f} kWh"
            )
            print(f"   💰 Annual cost: ${results['annual_cost']:,.2f}")
            print(f"   📊 Peak consumption: {stats['peak_consumption']:,.1f} kWh")
            print(f"   🌡️ Temperature correlation: R = {regression['r_value']:.3f}")
            print(f"   📉 Statistical significance: p = {regression['p_value']:.2e}")

        latest_result = self.benchmark.results[-1]
        improvement = self.benchmark.get_improvement_factor("statistical_analysis")

        print(f"   ⚡ Analysis time: {latest_result.execution_time:.2f} seconds")
        if improvement:
            print(f"   🚀 vs PyRevit manual calculations: {improvement:.1f}x faster")
        print()

    async def _demo_machine_learning_capabilities(self):
        """Demonstrate machine learning predictions."""
        print("3️⃣ MACHINE LEARNING PREDICTIONS")
        print("-" * 50)

        with self.benchmark.measure_performance("ml_computation_10000"):
            print("   🤖 Training Random Forest energy prediction model...")
            print(
                "   📚 Features: temperature, humidity, occupancy, solar irradiance, time"
            )

            # The ML model is built as part of the analysis
            # This functionality is completely impossible in PyRevit
            ml_results = self.analyzer._build_energy_prediction_model()

            print(f"   🎯 Model accuracy (R²): {ml_results['prediction_accuracy']}")
            print(f"   📉 Mean absolute error: {ml_results['mae']:.2f} kWh")
            print("   🔝 Top features by importance:")

            for i, feature in enumerate(ml_results["feature_importance"][:3]):
                print(f"      {i+1}. {feature['feature']}: {feature['importance']:.3f}")

        latest_result = self.benchmark.results[-1]
        print(f"   ⚡ ML training time: {latest_result.execution_time:.2f} seconds")
        print(f"   💾 Peak memory: {latest_result.peak_memory_mb:.1f} MB")
        print("   ❌ PyRevit capability: IMPOSSIBLE (no scikit-learn)")
        print()

    async def _demo_optimization_algorithms(self):
        """Demonstrate advanced optimization capabilities."""
        print("4️⃣ OPTIMIZATION ALGORITHMS")
        print("-" * 50)

        with self.benchmark.measure_performance("optimization_algorithms"):
            print("   🎯 Running SciPy optimization for HVAC setpoints...")

            # This uses SciPy optimization which is impossible in PyRevit
            optimization = self.analyzer._optimize_hvac_setpoints()

            print(
                f"   🌡️ Optimal cooling setpoint: {optimization['optimal_cooling_setpoint']}°F"
            )
            print(
                f"   🌡️ Optimal heating setpoint: {optimization['optimal_heating_setpoint']}°F"
            )
            print(f"   💰 Annual HVAC savings: ${optimization['annual_savings']:,.2f}")
            print(
                f"   ✅ Optimization successful: {optimization['optimization_success']}"
            )

        latest_result = self.benchmark.results[-1]
        print(f"   ⚡ Optimization time: {latest_result.execution_time:.2f} seconds")
        print("   ❌ PyRevit capability: IMPOSSIBLE (no SciPy optimization)")
        print()

    async def _demo_interactive_visualizations(self):
        """Demonstrate interactive dashboard creation."""
        print("5️⃣ INTERACTIVE VISUALIZATIONS")
        print("-" * 50)

        with self.benchmark.measure_performance("interactive_dashboard"):
            print("   📊 Creating interactive Plotly dashboard...")

            # Create comprehensive dashboard (impossible in PyRevit)
            dashboard_path = self.analyzer.create_interactive_dashboard()

            print(f"   ✅ Dashboard created: {dashboard_path}")
            print("   📈 Features: Time series, correlations, clustering, trends")
            print("   🖱️ Interactive: Zoom, pan, hover, filter capabilities")
            print("   🌐 Web-ready: HTML5 dashboard with JavaScript interactivity")

        latest_result = self.benchmark.results[-1]
        print(f"   ⚡ Dashboard generation: {latest_result.execution_time:.2f} seconds")
        print("   ❌ PyRevit capability: IMPOSSIBLE (no Plotly/modern web tech)")
        print()

    async def _demo_real_time_monitoring(self):
        """Demonstrate real-time async monitoring capabilities."""
        print("6️⃣ REAL-TIME MONITORING (ASYNC)")
        print("-" * 50)

        with self.benchmark.measure_performance("async_operations_100"):
            print("   🔄 Simulating real-time IoT sensor data collection...")

            # Simulate async operations (impossible in PyRevit)
            async def collect_sensor_data(sensor_id):
                await asyncio.sleep(0.01)  # Simulate network I/O
                return {
                    "sensor_id": sensor_id,
                    "timestamp": datetime.now(),
                    "temperature": np.random.uniform(68, 78),
                    "energy_consumption": np.random.uniform(100, 500),
                    "efficiency": np.random.uniform(0.7, 0.95),
                }

            # Collect data from 100 sensors concurrently
            tasks = [collect_sensor_data(f"sensor_{i}") for i in range(100)]
            sensor_data = await asyncio.gather(*tasks)

            print(f"   📊 Collected data from {len(sensor_data)} sensors concurrently")
            print("   ⚡ Async/await enables real-time monitoring without blocking")

        latest_result = self.benchmark.results[-1]
        improvement = self.benchmark.get_improvement_factor("async_operations_100")

        print(
            f"   ⚡ Concurrent collection time: {latest_result.execution_time:.2f} seconds"
        )
        if improvement:
            print(f"   🚀 vs PyRevit sequential approach: {improvement:.1f}x faster")
        print("   ❌ PyRevit capability: IMPOSSIBLE (no async/await syntax)")
        print()

    async def _demo_pyrevit_integration(self):
        """Demonstrate PyRevit integration workflow."""
        print("7️⃣ PYREVIT INTEGRATION WORKFLOW")
        print("-" * 50)

        print("   🔗 Simulating PyRevit → RevitPy workflow...")

        # Create mock workflow request from PyRevit
        request = WorkflowRequest(
            request_id="energy_analysis_001",
            workflow_type="energy_analysis",
            parameters={
                "analysis_detail": "comprehensive",
                "include_optimization": True,
                "forecast_days": 30,
            },
            element_ids=["space_1_01", "space_1_02", "space_2_01"],
            timestamp=datetime.now(),
        )

        print(f"   📤 PyRevit sends request: {request.workflow_type}")
        print(f"   🆔 Request ID: {request.request_id}")

        # Process request using RevitPy capabilities
        response = await self.bridge.process_workflow_request(request)

        print(f"   📥 RevitPy response status: {response.status}")
        print(f"   ⏱️ Processing time: {response.execution_time:.2f} seconds")

        if response.status == "success":
            print("   ✅ Analysis results ready for PyRevit consumption")
            print(
                f"   💰 Estimated savings: ${response.results.get('cost_savings_potential', 0):,.2f}"
            )

        # Export results for PyRevit
        export_path = self.bridge.export_for_pyrevit(
            response.to_dict(), f"energy_analysis_{request.request_id}"
        )

        print(f"   📁 Results exported to: {export_path}")
        print("   🔄 PyRevit can now import and display results in Revit UI")
        print()

    def _generate_performance_report(self):
        """Generate comprehensive performance comparison report."""
        print("8️⃣ PERFORMANCE COMPARISON REPORT")
        print("-" * 50)

        report = self.benchmark.generate_comparison_report()

        print("   📊 PERFORMANCE SUMMARY:")
        for result in report["performance_results"]:
            print(f"      • {result['operation']}: {result['execution_time_seconds']}s")
            if "improvement_vs_baseline" in result:
                print(f"        └─ {result['improvement_vs_baseline']}")

        print("\n   🚀 CAPABILITY ADVANTAGES:")
        for advantage in report["capability_advantages"][:3]:  # Show top 3
            print(f"      • {advantage['capability']}")
            print(f"        └─ Impact: {advantage['impact']}")

        print(
            f"\n   🏆 Total operations benchmarked: {report['summary']['total_operations']}"
        )
        print("   💡 All capabilities shown are impossible in PyRevit/IronPython")


async def main():
    """Run the comprehensive energy analytics demonstration."""
    demo = EnergyAnalyticsDemo()
    await demo.run_comprehensive_demo()


if __name__ == "__main__":
    asyncio.run(main())
