"""Prometheus metrics utilities for observability."""
import time
import logging
from typing import Optional, Dict, Any
from functools import wraps
from contextlib import contextmanager


logger = logging.getLogger(__name__)

# Try to import prometheus_client, make it optional
try:
    from prometheus_client import Counter, Histogram, Gauge, Summary, Info, start_http_server
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    # Create dummy decorators if not available
    def Counter(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
    
    def Histogram(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
    
    def Gauge(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
    
    def Summary(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
    
    def start_http_server(*args, **kwargs):
        pass


# Define metrics only if prometheus is available
if PROMETHEUS_AVAILABLE:
    # Tool execution metrics
    tool_calls_total = Counter(
        'nexus_tool_calls_total',
        'Total number of tool calls',
        ['tool', 'status']
    )
    
    tool_duration_seconds = Histogram(
        'nexus_tool_duration_seconds',
        'Tool execution duration in seconds',
        ['tool'],
        buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0]
    )
    
    # Model metrics
    model_requests_total = Counter(
        'nexus_model_requests_total',
        'Total model requests',
        ['model', 'status']
    )
    
    model_response_duration_seconds = Histogram(
        'nexus_model_response_duration_seconds',
        'Model response duration in seconds',
        ['model'],
        buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0]
    )
    
    # Agent metrics
    active_agents = Gauge(
        'nexus_active_agents',
        'Number of currently active agents'
    )
    
    agent_tasks_total = Counter(
        'nexus_agent_tasks_total',
        'Total tasks processed by agents',
        ['agent', 'status']
    )
    
    # System metrics
    cache_hits_total = Counter(
        'nexus_cache_hits_total',
        'Total cache hits'
    )
    
    cache_misses_total = Counter(
        'nexus_cache_misses_total',
        'Total cache misses'
    )
    
    # Request metrics
    http_requests_total = Counter(
        'nexus_http_requests_total',
        'Total HTTP requests',
        ['method', 'endpoint', 'status']
    )
    
    http_request_duration_seconds = Histogram(
        'nexus_http_request_duration_seconds',
        'HTTP request duration',
        ['method', 'endpoint'],
        buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]
    )
    
    # Queue metrics
    queue_size = Gauge(
        'nexus_queue_size',
        'Current queue size',
        ['queue_name']
    )
else:
    # Create dummy metrics objects
    class DummyMetric:
        def __init__(self, *args, **kwargs):
            pass
        
        def labels(self, **kwargs):
            return self
        
        def inc(self, *args, **kwargs):
            pass
        
        def dec(self, *args, **kwargs):
            pass
        
        def set(self, *args, **kwargs):
            pass
        
        def time(self):
            return contextmanager(lambda: (lambda: None))
    
    tool_calls_total = DummyMetric()
    tool_duration_seconds = DummyMetric()
    model_requests_total = DummyMetric()
    model_response_duration_seconds = DummyMetric()
    active_agents = DummyMetric()
    agent_tasks_total = DummyMetric()
    cache_hits_total = DummyMetric()
    cache_misses_total = DummyMetric()
    http_requests_total = DummyMetric()
    http_request_duration_seconds = DummyMetric()
    queue_size = DummyMetric()


def track_duration(metric: Histogram, **labels):
    """Decorator to track function duration."""
    def decorator(func):
        if not PROMETHEUS_AVAILABLE:
            return func
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            with metric.labels(**labels).time():
                return func(*args, **kwargs)
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            with metric.labels(**labels).time():
                return await func(*args, **kwargs)
        
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


def count_call(metric: Counter, **labels):
    """Decorator to count function calls."""
    def decorator(func):
        if not PROMETHEUS_AVAILABLE:
            return func
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            metric.labels(**labels).inc()
            return func(*args, **kwargs)
        
        return wrapper
    
    return decorator


@contextmanager
def track_time(metric: Histogram, **labels):
    """Context manager to track execution time."""
    if PROMETHEUS_AVAILABLE:
        with metric.labels(**labels).time():
            yield
    else:
        yield


class MetricsCollector:
    """Collect application metrics."""
    
    def __init__(self):
        self._custom_metrics: Dict[str, Any] = {}
    
    def register_gauge(self, name: str, description: str, **label_names):
        """Register a custom gauge metric."""
        if not PROMETHEUS_AVAILABLE:
            self._custom_metrics[name] = DummyMetric()
            return
        
        gauge = Gauge(name, description, list(label_names.keys()))
        self._custom_metrics[name] = gauge
    
    def register_counter(self, name: str, description: str, **label_names):
        """Register a custom counter metric."""
        if not PROMETHEUS_AVAILABLE:
            self._custom_metrics[name] = DummyMetric()
            return
        
        counter = Counter(name, description, list(label_names.keys()))
        self._custom_metrics[name] = counter
    
    def get_metric(self, name: str):
        """Get a custom metric by name."""
        return self._custom_metrics.get(name)


def start_metrics_server(port: int = 8000):
    """Start Prometheus metrics HTTP server."""
    if not PROMETHEUS_AVAILABLE:
        logger.warning("Prometheus client not available, metrics server not started")
        return
    
    try:
        start_http_server(port)
        logger.info(f"Prometheus metrics server started on port {port}")
    except Exception as e:
        logger.error(f"Failed to start metrics server: {e}")


# Global metrics collector
metrics = MetricsCollector()