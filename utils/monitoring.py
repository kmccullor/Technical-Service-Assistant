"""Performance monitoring utilities for the Technical Service Assistant."""

import functools
import time
import logging
from typing import Callable, Any, Optional
from contextlib import contextmanager
from memory_profiler import profile as memory_profile

# Set up logger
logger = logging.getLogger(__name__)

try:
    from prometheus_client import Counter, Histogram, Gauge
    
    # Prometheus metrics
    OPERATION_COUNTER = Counter(
        'technical_service_operations_total',
        'Total number of operations performed',
        ['operation_type', 'status']
    )
    
    OPERATION_DURATION = Histogram(
        'technical_service_operation_duration_seconds',
        'Time spent on operations',
        ['operation_type']
    )
    
    ACTIVE_OPERATIONS = Gauge(
        'technical_service_active_operations',
        'Number of currently active operations',
        ['operation_type']
    )
    
    PROMETHEUS_AVAILABLE = True
    
except ImportError:
    logger.warning("Prometheus client not available. Metrics will be logged only.")
    PROMETHEUS_AVAILABLE = False


def monitor_performance(operation_type: str = "unknown") -> Callable:
    """Decorator to monitor function performance.
    
    Args:
        operation_type: Type of operation being monitored
        
    Returns:
        Decorated function with performance monitoring
        
    Example:
        @monitor_performance("pdf_processing")
        def process_pdf(file_path: str) -> List[str]:
            # Function implementation
            pass
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            start_time = time.time()
            
            if PROMETHEUS_AVAILABLE:
                ACTIVE_OPERATIONS.labels(operation_type=operation_type).inc()
            
            try:
                result = func(*args, **kwargs)
                
                # Record success
                duration = time.time() - start_time
                logger.info(f"{func.__name__} completed in {duration:.3f}s")
                
                if PROMETHEUS_AVAILABLE:
                    OPERATION_COUNTER.labels(
                        operation_type=operation_type, 
                        status="success"
                    ).inc()
                    OPERATION_DURATION.labels(operation_type=operation_type).observe(duration)
                
                return result
                
            except Exception as e:
                # Record failure
                duration = time.time() - start_time
                logger.error(f"{func.__name__} failed after {duration:.3f}s: {e}")
                
                if PROMETHEUS_AVAILABLE:
                    OPERATION_COUNTER.labels(
                        operation_type=operation_type, 
                        status="error"
                    ).inc()
                
                raise
                
            finally:
                if PROMETHEUS_AVAILABLE:
                    ACTIVE_OPERATIONS.labels(operation_type=operation_type).dec()
        
        return wrapper
    return decorator


@contextmanager
def performance_context(operation_name: str):
    """Context manager for monitoring performance of code blocks.
    
    Args:
        operation_name: Name of the operation being monitored
        
    Example:
        with performance_context("database_query"):
            results = execute_complex_query()
    """
    start_time = time.time()
    
    if PROMETHEUS_AVAILABLE:
        ACTIVE_OPERATIONS.labels(operation_type=operation_name).inc()
    
    try:
        logger.info(f"Starting operation: {operation_name}")
        yield
        
        # Record success
        duration = time.time() - start_time
        logger.info(f"Completed operation: {operation_name} in {duration:.3f}s")
        
        if PROMETHEUS_AVAILABLE:
            OPERATION_COUNTER.labels(
                operation_type=operation_name, 
                status="success"
            ).inc()
            OPERATION_DURATION.labels(operation_type=operation_name).observe(duration)
            
    except Exception as e:
        # Record failure
        duration = time.time() - start_time
        logger.error(f"Failed operation: {operation_name} after {duration:.3f}s: {e}")
        
        if PROMETHEUS_AVAILABLE:
            OPERATION_COUNTER.labels(
                operation_type=operation_name, 
                status="error"
            ).inc()
        
        raise
        
    finally:
        if PROMETHEUS_AVAILABLE:
            ACTIVE_OPERATIONS.labels(operation_type=operation_name).dec()


class PerformanceTimer:
    """Simple performance timer for measuring execution time."""
    
    def __init__(self, name: Optional[str] = None) -> None:
        """Initialize the timer.
        
        Args:
            name: Optional name for the timer
        """
        self.name = name or "operation"
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
    
    def start(self) -> None:
        """Start the timer."""
        self.start_time = time.time()
        logger.debug(f"Started timing: {self.name}")
    
    def stop(self) -> float:
        """Stop the timer and return elapsed time.
        
        Returns:
            Elapsed time in seconds
        """
        if self.start_time is None:
            raise ValueError("Timer not started")
        
        self.end_time = time.time()
        elapsed = self.elapsed
        logger.info(f"Timer {self.name}: {elapsed:.3f}s")
        return elapsed
    
    @property
    def elapsed(self) -> float:
        """Get elapsed time.
        
        Returns:
            Elapsed time in seconds
            
        Raises:
            ValueError: If timer hasn't been started or stopped
        """
        if self.start_time is None:
            raise ValueError("Timer not started")
        
        end_time = self.end_time or time.time()
        return end_time - self.start_time
    
    def __enter__(self) -> 'PerformanceTimer':
        """Enter context manager."""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context manager."""
        self.stop()


def profile_memory(func: Callable) -> Callable:
    """Decorator to profile memory usage of a function.
    
    Args:
        func: Function to profile
        
    Returns:
        Decorated function with memory profiling
        
    Example:
        @profile_memory
        def memory_intensive_function():
            # Function implementation
            pass
    """
    if 'memory_profiler' not in globals():
        logger.warning("memory_profiler not available. Skipping memory profiling.")
        return func
    
    return memory_profile(func)


def log_system_metrics() -> None:
    """Log current system performance metrics."""
    import psutil
    
    # CPU usage
    cpu_percent = psutil.cpu_percent(interval=1)
    logger.info(f"CPU usage: {cpu_percent}%")
    
    # Memory usage
    memory = psutil.virtual_memory()
    logger.info(f"Memory usage: {memory.percent}% ({memory.used / 1024**3:.1f}GB / {memory.total / 1024**3:.1f}GB)")
    
    # Disk usage
    disk = psutil.disk_usage('/')
    logger.info(f"Disk usage: {disk.percent}% ({disk.used / 1024**3:.1f}GB / {disk.total / 1024**3:.1f}GB)")


if PROMETHEUS_AVAILABLE:
    def start_metrics_server(port: int = 8000) -> None:
        """Start Prometheus metrics server.
        
        Args:
            port: Port to serve metrics on
        """
        from prometheus_client import start_http_server
        
        start_http_server(port)
        logger.info(f"Prometheus metrics server started on port {port}")
        logger.info(f"Metrics available at http://localhost:{port}/metrics")