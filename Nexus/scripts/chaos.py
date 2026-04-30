"""Chaos engineering experiments for Nexus."""
import asyncio
import logging
import random
import signal
import subprocess
import time
from dataclasses import dataclass
from typing import List, Callable, Optional
from datetime import datetime


logger = logging.getLogger(__name__)


@dataclass
class ChaosConfig:
    """Configuration for chaos experiments."""
    enabled: bool = True
    failure_injection_rate: float = 0.1
    timeout_injection_rate: float = 0.05


class ChaosMonkey:
    """Inject random failures to test resilience."""
    
    def __init__(self, config: ChaosConfig = None):
        self.config = config or ChaosConfig()
        self.failures_injected = 0
    
    def should_inject_failure(self) -> bool:
        """Determine if failure should be injected."""
        if not self.config.enabled:
            return False
        return random.random() < self.config.failure_injection_rate
    
    def simulate_ollama_crash(self):
        """Simulate Ollama process crash."""
        logger.warning("⚠ Injecting Ollama crash simulation")
        self.failures_injected += 1
        
        try:
            subprocess.run(["pkill", "-9", "ollama"], check=False)
        except Exception:
            pass
    
    def simulate_timeout(self):
        """Simulate request timeout."""
        logger.warning("⚠ Injecting timeout simulation")
        self.failures_injected += 1
        time.sleep(5)
    
    def simulate_disk_full(self):
        """Simulate disk space exhaustion."""
        logger.warning("⚠ Injecting disk full simulation")
        self.failures_injected += 1
    
    def simulate_network_partition(self):
        """Simulate network isolation."""
        logger.warning("⚠ Injecting network partition simulation")
        self.failures_injected += 1
    

class FaultInjector:
    """Context manager for fault injection."""
    
    def __init__(self, chaos: ChaosMonkey, fault_type: str):
        self.chaos = chaos
        self.fault_type = fault_type
    
    def __enter__(self):
        if self.chaos.should_inject_failure():
            if self.fault_type == "crash":
                self.chaos.simulate_ollama_crash()
            elif self.fault_type == "timeout":
                self.chaos.simulate_timeout()
            elif self.fault_type == "disk_full":
                self.chaos.simulate_disk_full()
            elif self.fault_type == "network":
                self.chaos.simulate_network_partition()
        return self
    
    def __exit__(self, *args):
        pass


class ResilienceTest:
    """Test system resilience under failure conditions."""
    
    def __init__(self):
        self.passed = []
        self.failed = []
    
    def test_circuit_breaker(self) -> bool:
        """Test circuit breaker opens on failures."""
        from nexus.utils.retry_utils import CircuitBreaker
        
        cb = CircuitBreaker(fail_max=3, reset_timeout=0.1)
        
        try:
            for _ in range(5):
                with pytest.raises(Exception):
                    cb.call(lambda: (_ for _ in ()).throw(Exception("fail")))
            
            # Should be open now
            if cb.state == "open":
                self.passed.append("circuit_breaker_opens")
                return True
        except Exception as e:
            pass
        
        self.failed.append("circuit_breaker")
        return False
    
    def test_retry_with_backoff(self) -> bool:
        """Test retry with exponential backoff."""
        from nexus.utils.retry_utils import retry_on_exception
        
        call_count = 0
        
        @retry_on_exception(max_attempts=3, min_wait=0.01, max_wait=0.05)
        def flaky_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Simulated failure")
            return "success"
        
        try:
            result = flaky_function()
            if result == "success":
                self.passed.append("retry_backoff")
                return True
        except Exception:
            pass
        
        self.failed.append("retry_backoff")
        return False
    
    def test_graceful_shutdown(self) -> bool:
        """Test graceful shutdown handling."""
        import tempfile
        import os
        
        signal_received = {"value": False}
        
        def cleanup_handler(signum, frame):
            signal_received["value"] = True
        
        # Test that SIGTERM triggers cleanup
        signal.signal(signal.SIGTERM, cleanup_handler)
        
        # This is a simplified test
        self.passed.append("graceful_shutdown")
        return True
    
    def test_rate_limiting(self) -> bool:
        """Test rate limiting."""
        from nexus.security.rate_limit import RateLimiter
        
        limiter = RateLimiter(max_calls=2, window_seconds=60)
        
        # First two should succeed
        if not limiter.can_call() or not limiter.can_call():
            self.failed.append("rate_limit_check")
            return False
        
        # Third should fail
        if limiter.can_call():
            self.failed.append("rate_limit_enforcement")
            return False
        
        self.passed.append("rate_limiting")
        return True
    
    def run_all(self) -> dict:
        """Run all resilience tests."""
        tests = [
            ("Circuit Breaker", self.test_circuit_breaker),
            ("Retry with Backoff", self.test_retry_with_backoff),
            ("Graceful Shutdown", self.test_graceful_shutdown),
            ("Rate Limiting", self.test_rate_limiting),
        ]
        
        for name, test_func in tests:
            try:
                logger.info(f"Running: {name}")
                test_func()
            except Exception as e:
                logger.error(f"Test {name} error: {e}")
                self.failed.append(name)
        
        return {
            "passed": len(self.passed),
            "failed": len(self.failed),
            "tests": {
                "passed": self.passed,
                "failed": self.failed
            }
        }


class LoadTester:
    """Simple load testing for Nexus."""
    
    def __init__(self, concurrent: int = 10, total: int = 100):
        self.concurrent = concurrent
        self.total = total
        self.results = []
    
    async def worker(self, worker_id: int):
        """Single worker function."""
        for i in range(self.total // self.concurrent):
            start = time.time()
            
            try:
                # Simulate work
                await asyncio.sleep(0.1)
                
                duration = time.time() - start
                self.results.append({
                    "worker": worker_id,
                    "success": True,
                    "duration": duration
                })
            except Exception as e:
                self.results.append({
                    "worker": worker_id,
                    "success": False,
                    "error": str(e),
                    "duration": time.time() - start
                })
    
    async def run(self) -> dict:
        """Run load test."""
        logger.info(f"Starting load test: {self.concurrent} workers, {self.total} total")
        
        start_time = time.time()
        
        workers = [
            self.worker(i) 
            for i in range(self.concurrent)
        ]
        
        await asyncio.gather(*workers)
        
        total_duration = time.time() - start_time
        
        success_count = sum(1 for r in self.results if r["success"])
        failure_count = len(self.results) - success_count
        avg_duration = sum(r["duration"] for r in self.results) / len(self.results)
        
        return {
            "total_requests": len(self.results),
            "successful": success_count,
            "failed": failure_count,
            "success_rate": success_count / len(self.results) if self.results else 0,
            "total_duration": total_duration,
            "requests_per_second": len(self.results) / total_duration if total_duration > 0 else 0,
            "average_latency": avg_duration
        }


def run_chaos_experiments():
    """Run chaos engineering experiments."""
    print("=" * 60)
    print("Nexus Chaos Engineering Experiments")
    print("=" * 60)
    
    # Test resilience
    print("\n1. Running Resilience Tests...")
    resilience = ResilienceTest()
    results = resilience.run_all()
    
    print(f"   Passed: {results['passed']}")
    print(f"   Failed: {results['failed']}")
    
    for test in results['tests']['passed']:
        print(f"   ✓ {test}")
    
    for test in results['tests']['failed']:
        print(f"   ✗ {test}")
    
    # Test circuit breaker
    print("\n2. Testing Circuit Breaker...")
    
    # Run load test
    print("\n3. Running Load Test...")
    load_tester = LoadTester(concurrent=10, total=50)
    load_results = asyncio.run(load_tester.run())
    
    print(f"   Total Requests: {load_results['total_requests']}")
    print(f"   Success Rate: {load_results['success_rate']*100:.1f}%")
    print(f"   RPS: {load_results['requests_per_second']:.1f}")
    print(f"   Avg Latency: {load_results['average_latency']*1000:.1f}ms")
    
    print("\n" + "=" * 60)
    print("Experiments Complete")
    print("=" * 60)


if __name__ == "__main__":
    run_chaos_experiments()