"""Health check and status API for Nexus."""
import asyncio
import logging
import sys
import time
import signal
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional
from dataclasses import dataclass, field

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False


logger = logging.getLogger(__name__)


@dataclass
class HealthStatus:
    """Health status of a component."""
    name: str
    healthy: bool
    message: str = ""
    latency_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class HealthChecker:
    """Check health of Nexus components."""
    
    def __init__(self):
        self.checks: Dict[str, callable] = {}
        self._start_time = time.time()
    
    def register_check(self, name: str, check_fn: callable):
        """Register a health check function."""
        self.checks[name] = check_fn
    
    async def check_all(self) -> Dict[str, HealthStatus]:
        """Run all health checks."""
        results = {}
        
        for name, check_fn in self.checks.items():
            start = time.time()
            try:
                if asyncio.iscoroutinefunction(check_fn):
                    result = await check_fn()
                else:
                    result = check_fn()
                
                latency = (time.time() - start) * 1000
                
                if isinstance(result, dict):
                    results[name] = HealthStatus(
                        name=name,
                        healthy=result.get("healthy", True),
                        message=result.get("message", ""),
                        latency_ms=latency,
                        metadata=result.get("metadata", {})
                    )
                else:
                    results[name] = HealthStatus(
                        name=name,
                        healthy=bool(result),
                        latency_ms=latency
                    )
            except Exception as e:
                latency = (time.time() - start) * 1000
                results[name] = HealthStatus(
                    name=name,
                    healthy=False,
                    message=str(e),
                    latency_ms=latency
                )
        
        return results
    
    def get_uptime(self) -> float:
        """Get uptime in seconds."""
        return time.time() - self._start_time


# Global health checker
health_checker = HealthChecker()


def check_ollama() -> Dict[str, Any]:
    """Check if Ollama is running."""
    try:
        from nexus.utils.subprocess_utils import run_command
        result = run_command(["ollama", "list"], timeout=5)
        
        if result.returncode == 0:
            return {"healthy": True, "message": "Ollama running"}
        return {"healthy": False, "message": "Ollama not responding"}
    except Exception as e:
        return {"healthy": False, "message": f"Ollama error: {e}"}


def check_workspace() -> Dict[str, Any]:
    """Check if workspace is accessible."""
    try:
        from nexus.config.settings import config
        workspace = config.workspace_root
        
        if not workspace.exists():
            return {"healthy": False, "message": "Workspace does not exist"}
        
        # Check write access
        test_file = workspace / ".nexus_write_test"
        try:
            test_file.write_text("test")
            test_file.unlink()
            return {"healthy": True, "message": "Workspace accessible"}
        except Exception as e:
            return {"healthy": False, "message": f"Workspace not writable: {e}"}
    except Exception as e:
        return {"healthy": False, "message": f"Workspace check error: {e}"}


def check_disk_space() -> Dict[str, Any]:
    """Check available disk space."""
    try:
        import shutil
        stats = shutil.disk_usage("/")
        
        free_gb = stats.free / (1024**3)
        total_gb = stats.total / (1024**3)
        percent_free = (stats.free / stats.total) * 100
        
        healthy = free_gb > 1.0  # At least 1GB free
        
        return {
            "healthy": healthy,
            "message": f"{free_gb:.1f}GB free of {total_gb:.1f}GB",
            "metadata": {
                "free_gb": round(free_gb, 2),
                "total_gb": round(total_gb, 2),
                "percent_free": round(percent_free, 1)
            }
        }
    except Exception as e:
        return {"healthy": False, "message": f"Disk check error: {e}"}


def check_models() -> Dict[str, Any]:
    """Check available Ollama models."""
    try:
        from nexus.utils.subprocess_utils import run_ollama
        result = run_ollama("list", timeout=10)
        
        lines = result.strip().split("\n")
        model_count = len([l for l in lines[1:] if l.strip()])
        
        return {
            "healthy": model_count > 0,
            "message": f"{model_count} models available",
            "metadata": {"model_count": model_count}
        }
    except Exception as e:
        return {"healthy": False, "message": f"Model check error: {e}"}


# Register default health checks
health_checker.register_check("ollama", check_ollama)
health_checker.register_check("workspace", check_workspace)
health_checker.register_check("disk_space", check_disk_space)
health_checker.register_check("models", check_models)


def create_app() -> Optional[FastAPI]:
    """Create FastAPI app for health checks."""
    if not FASTAPI_AVAILABLE:
        return None
    
    app = FastAPI(
        title="Nexus Health API",
        description="Health monitoring for Nexus AI Workstation",
        version="0.1.0"
    )
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    @app.get("/health")
    async def health():
        """Basic health check."""
        checks = await health_checker.check_all()
        all_healthy = all(c.healthy for c in checks.values())
        
        status_code = 200 if all_healthy else 503
        status = "healthy" if all_healthy else "unhealthy"
        
        return {
            "status": status,
            "uptime_seconds": round(health_checker.get_uptime(), 2),
            "checks": {
                name: {
                    "healthy": check.healthy,
                    "message": check.message,
                    "latency_ms": round(check.latency_ms, 2),
                    **check.metadata
                }
                for name, check in checks.items()
            }
        }
    
    @app.get("/health/liveness")
    async def liveness():
        """Liveness probe - is the service running?"""
        return {"status": "alive"}
    
    @app.get("/health/readiness")
    async def readiness():
        """Readiness probe - is the service ready to accept requests?"""
        checks = await health_checker.check_all()
        
        critical_checks = ["workspace", "disk_space"]
        critical_healthy = all(
            checks.get(name, HealthStatus(name=name, healthy=False)).healthy
            for name in critical_checks
        )
        
        if not critical_healthy:
            raise HTTPException(status_code=503, detail="Service not ready")
        
        return {"status": "ready"}
    
    @app.get("/metrics")
    async def metrics():
        """Prometheus metrics endpoint."""
        if not FASTAPI_AVAILABLE:
            raise HTTPException(status_code=501, detail="FastAPI not available")
        
        from nexus.utils.metrics import metrics as metrics_collector
        if metrics_collector._custom_metrics:
            return {"message": "Use Prometheus server at /metrics"}
        
        return {"message": "Metrics not configured"}
    
    @app.get("/status")
    async def status():
        """Detailed status of all components."""
        checks = await health_checker.check_all()
        
        return {
            "version": "0.1.0",
            "uptime_seconds": round(health_checker.get_uptime(), 2),
            "components": {
                name: {
                    "healthy": check.healthy,
                    "message": check.message,
                    "latency_ms": round(check.latency_ms, 2)
                }
                for name, check in checks.items()
            }
        }
    
    return app


class GracefulShutdown:
    """Handle graceful shutdown."""
    
    def __init__(self):
        self.shutdown_requested = False
        self._callbacks: list = []
    
    def register_callback(self, callback: callable):
        """Register a callback to be called on shutdown."""
        self._callbacks.append(callback)
    
    async def shutdown(self):
        """Execute graceful shutdown."""
        if self.shutdown_requested:
            return
        
        self.shutdown_requested = True
        logger.info("Starting graceful shutdown...")
        
        for callback in self._callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback()
                else:
                    callback()
            except Exception as e:
                logger.error(f"Shutdown callback error: {e}")
        
        logger.info("Graceful shutdown complete")
    
    def setup_signal_handlers(self, loop):
        """Set up signal handlers for shutdown."""
        def signal_handler(sig):
            logger.info(f"Received signal {sig}, initiating shutdown...")
            asyncio.create_task(self.shutdown())
        
        if sys.platform != "win32":
            for sig in (signal.SIGTERM, signal.SIGINT):
                signal.signal(sig, signal_handler)
        
        # Windows doesn't support SIGTERM the same way
        signal.signal(signal.SIGINT, lambda s, f: asyncio.create_task(self.shutdown()))


# Global graceful shutdown handler
shutdown_handler = GracefulShutdown()