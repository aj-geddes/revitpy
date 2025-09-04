"""
Performance utilities and benchmarking tools for POC demonstrations.
"""

import time
import asyncio
import threading
import psutil
import statistics
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import List, Dict, Any, Callable, Optional
from functools import wraps


@dataclass
class PerformanceMetrics:
    """Container for performance measurement results."""
    operation_name: str
    execution_time: float
    memory_usage_mb: float
    cpu_usage_percent: float
    peak_memory_mb: float = 0.0
    concurrent_operations: int = 1
    data_size_mb: float = 0.0
    iterations: int = 1
    
    @property
    def operations_per_second(self) -> float:
        """Calculate operations per second."""
        return self.iterations / self.execution_time if self.execution_time > 0 else 0
    
    @property
    def mb_per_second(self) -> float:
        """Calculate data throughput in MB/s."""
        return self.data_size_mb / self.execution_time if self.execution_time > 0 else 0


class PerformanceBenchmark:
    """Performance benchmarking utility that demonstrates RevitPy advantages."""
    
    def __init__(self):
        self.results: List[PerformanceMetrics] = []
        self.baseline_results: Dict[str, float] = {}
    
    @contextmanager
    def measure_performance(self, operation_name: str, data_size_mb: float = 0.0, 
                          iterations: int = 1):
        """Context manager for measuring performance."""
        # Get initial system state
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        initial_cpu = process.cpu_percent()
        
        start_time = time.perf_counter()
        peak_memory = initial_memory
        
        # Start memory monitoring thread
        monitoring = True
        
        def monitor_memory():
            nonlocal peak_memory, monitoring
            while monitoring:
                current_memory = process.memory_info().rss / 1024 / 1024
                peak_memory = max(peak_memory, current_memory)
                time.sleep(0.01)  # Monitor every 10ms
        
        monitor_thread = threading.Thread(target=monitor_memory, daemon=True)
        monitor_thread.start()
        
        try:
            yield
        finally:
            monitoring = False
            end_time = time.perf_counter()
            
            # Calculate final metrics
            execution_time = end_time - start_time
            final_memory = process.memory_info().rss / 1024 / 1024
            memory_usage = final_memory - initial_memory
            cpu_usage = process.cpu_percent() - initial_cpu
            
            # Record results
            metrics = PerformanceMetrics(
                operation_name=operation_name,
                execution_time=execution_time,
                memory_usage_mb=memory_usage,
                cpu_usage_percent=cpu_usage,
                peak_memory_mb=peak_memory,
                data_size_mb=data_size_mb,
                iterations=iterations
            )
            
            self.results.append(metrics)
    
    def set_baseline(self, operation_name: str, baseline_time: float):
        """Set baseline performance for comparison (e.g., PyRevit equivalent)."""
        self.baseline_results[operation_name] = baseline_time
    
    def get_improvement_factor(self, operation_name: str) -> Optional[float]:
        """Calculate improvement factor vs baseline."""
        if operation_name not in self.baseline_results:
            return None
        
        revitpy_results = [r for r in self.results if r.operation_name == operation_name]
        if not revitpy_results:
            return None
        
        baseline_time = self.baseline_results[operation_name]
        revitpy_time = revitpy_results[-1].execution_time
        
        return baseline_time / revitpy_time if revitpy_time > 0 else 0
    
    def benchmark_async_operations(self, operation_count: int = 100) -> PerformanceMetrics:
        """Benchmark async operations capability (impossible with PyRevit)."""
        
        async def mock_async_operation():
            """Simulate async API call or computation."""
            await asyncio.sleep(0.01)  # Simulate I/O wait
            return sum(range(1000))  # Some computation
        
        async def run_concurrent_operations():
            tasks = [mock_async_operation() for _ in range(operation_count)]
            results = await asyncio.gather(*tasks)
            return results
        
        with self.measure_performance(
            f"async_operations_{operation_count}", 
            iterations=operation_count
        ):
            # Run async operations
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                results = loop.run_until_complete(run_concurrent_operations())
            finally:
                loop.close()
        
        return self.results[-1]
    
    def benchmark_ml_computation(self, data_size: int = 10000) -> PerformanceMetrics:
        """Benchmark ML computation capability (impossible with PyRevit)."""
        import numpy as np
        
        # Generate synthetic data
        X = np.random.rand(data_size, 10)
        y = np.random.rand(data_size)
        
        data_size_mb = X.nbytes / 1024 / 1024
        
        with self.measure_performance(
            f"ml_computation_{data_size}", 
            data_size_mb=data_size_mb
        ):
            # Simulate ML operations that would be impossible in IronPython
            # Matrix operations
            covariance = np.cov(X.T)
            eigenvals, eigenvecs = np.linalg.eig(covariance)
            
            # Statistical computations
            correlations = np.corrcoef(X.T)
            
            # Advanced mathematical operations
            fft_result = np.fft.fft(X[:, 0])
            
        return self.results[-1]
    
    def benchmark_data_processing(self, record_count: int = 100000) -> PerformanceMetrics:
        """Benchmark large dataset processing (limited in PyRevit)."""
        import pandas as pd
        import numpy as np
        
        # Generate large dataset
        data = {
            'element_id': [f"elem_{i}" for i in range(record_count)],
            'area': np.random.uniform(100, 1000, record_count),
            'volume': np.random.uniform(1000, 10000, record_count),
            'energy_use': np.random.uniform(1000, 5000, record_count),
            'efficiency': np.random.uniform(0.6, 0.95, record_count)
        }
        
        df = pd.DataFrame(data)
        data_size_mb = df.memory_usage(deep=True).sum() / 1024 / 1024
        
        with self.measure_performance(
            f"data_processing_{record_count}",
            data_size_mb=data_size_mb
        ):
            # Complex data operations impossible/slow in IronPython
            # Grouping and aggregation
            grouped = df.groupby(pd.cut(df['area'], bins=10)).agg({
                'energy_use': ['mean', 'std', 'min', 'max'],
                'efficiency': ['mean', 'std'],
                'volume': 'sum'
            })
            
            # Statistical analysis
            correlation_matrix = df.corr()
            
            # Advanced filtering and transformations
            efficient_elements = df[
                (df['efficiency'] > df['efficiency'].quantile(0.75)) &
                (df['energy_use'] < df['energy_use'].median())
            ]
            
            # Pivot operations
            pivot_result = df.pivot_table(
                values='energy_use',
                index=pd.cut(df['area'], bins=5),
                columns=pd.cut(df['efficiency'], bins=3),
                aggfunc='mean'
            )
        
        return self.results[-1]
    
    def generate_comparison_report(self) -> Dict[str, Any]:
        """Generate comprehensive performance comparison report."""
        report = {
            'summary': {
                'total_operations': len(self.results),
                'operations_tested': list(set(r.operation_name for r in self.results))
            },
            'performance_results': [],
            'capability_advantages': []
        }
        
        for result in self.results:
            result_data = {
                'operation': result.operation_name,
                'execution_time_seconds': round(result.execution_time, 4),
                'memory_usage_mb': round(result.memory_usage_mb, 2),
                'peak_memory_mb': round(result.peak_memory_mb, 2),
                'operations_per_second': round(result.operations_per_second, 2),
                'data_throughput_mb_per_sec': round(result.mb_per_second, 2)
            }
            
            # Add improvement factor if baseline exists
            improvement = self.get_improvement_factor(result.operation_name)
            if improvement:
                result_data['improvement_vs_baseline'] = f"{improvement:.1f}x faster"
            
            report['performance_results'].append(result_data)
        
        # Add capability advantages
        report['capability_advantages'] = [
            {
                'capability': 'Asynchronous Operations',
                'revitpy_advantage': 'Native async/await support for concurrent operations',
                'pyrevit_limitation': 'IronPython 2.7 lacks async/await syntax',
                'impact': 'Enable real-time IoT integration and concurrent API calls'
            },
            {
                'capability': 'Modern ML Libraries',
                'revitpy_advantage': 'Full TensorFlow, scikit-learn, PyTorch support',
                'pyrevit_limitation': 'Limited to basic .NET ML libraries',
                'impact': 'Advanced space optimization and predictive analytics'
            },
            {
                'capability': 'Scientific Computing',
                'revitpy_advantage': 'NumPy, SciPy, Pandas for complex computations',
                'pyrevit_limitation': 'Basic math operations only',
                'impact': 'Sophisticated engineering analysis and data processing'
            },
            {
                'capability': 'Computer Vision',
                'revitpy_advantage': 'OpenCV, PIL, modern image processing',
                'pyrevit_limitation': 'No native image processing capabilities',
                'impact': 'Automated progress monitoring and quality control'
            },
            {
                'capability': 'Cloud Integration',
                'revitpy_advantage': 'Modern HTTP clients, cloud SDKs, OAuth',
                'pyrevit_limitation': 'Limited HTTP capabilities',
                'impact': 'Seamless cloud services and API integration'
            }
        ]
        
        return report


def performance_benchmark_decorator(operation_name: str):
    """Decorator to automatically benchmark function performance."""
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            benchmark = PerformanceBenchmark()
            with benchmark.measure_performance(operation_name):
                result = func(*args, **kwargs)
            return result, benchmark.results[-1]
        return wrapper
    return decorator


def simulate_pyrevit_limitations():
    """Simulate performance limitations of PyRevit/IronPython environment."""
    limitations = {
        'async_operations': {
            'supported': False,
            'reason': 'IronPython 2.7 lacks async/await syntax',
            'workaround': 'Thread-based concurrency with significant overhead'
        },
        'ml_libraries': {
            'supported': False,
            'reason': 'TensorFlow, scikit-learn not available in IronPython',
            'workaround': 'Basic .NET ML libraries with limited capabilities'
        },
        'numpy_scipy': {
            'supported': False,
            'reason': 'C extensions not compatible with IronPython',
            'workaround': 'Pure Python math libraries with poor performance'
        },
        'pandas': {
            'supported': False,
            'reason': 'Depends on NumPy and C extensions',
            'workaround': 'Manual data manipulation with significant overhead'
        },
        'opencv': {
            'supported': False,
            'reason': 'Computer vision libraries not available',
            'workaround': 'Basic image operations through .NET libraries'
        },
        'modern_http_clients': {
            'supported': False,
            'reason': 'Limited to .NET WebClient and HttpWebRequest',
            'workaround': 'Manual HTTP handling without modern features'
        }
    }
    
    return limitations


# Example baseline times for PyRevit equivalent operations (estimated)
PYREVIT_BASELINES = {
    'data_processing_100000': 45.0,  # 45 seconds for large dataset processing
    'ml_computation_10000': float('inf'),  # Impossible in PyRevit
    'async_operations_100': 10.0,  # Much slower with threading
    'image_processing': float('inf'),  # Very limited capabilities
    'statistical_analysis': 15.0,  # Manual calculations only
}