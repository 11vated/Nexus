"""Async/concurrent tool execution utilities."""
import asyncio
import logging
import time
from typing import Callable, List, Any, Optional, Dict, TypeVar, Awaitable
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import threading


logger = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass
class TaskResult:
    """Result of an async task."""
    task_id: str
    success: bool
    result: Any = None
    error: Optional[str] = None
    duration: float = 0.0


class TaskQueue:
    """Async task queue with concurrency limiting."""
    
    def __init__(self, max_concurrent: int = 4):
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.running_tasks: Dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()
    
    async def run_task(
        self,
        task_id: str,
        coro: Awaitable[T],
        timeout: Optional[float] = None
    ) -> TaskResult:
        """Run a task with concurrency limiting."""
        start_time = time.time()
        
        async def limited_task():
            async with self.semaphore:
                return await coro
        
        async with self._lock:
            task = asyncio.create_task(limited_task())
            self.running_tasks[task_id] = task
        
        try:
            if timeout:
                result = await asyncio.wait_for(task, timeout=timeout)
            else:
                result = await task
            
            duration = time.time() - start_time
            return TaskResult(
                task_id=task_id,
                success=True,
                result=result,
                duration=duration
            )
        except asyncio.TimeoutError:
            task.cancel()
            duration = time.time() - start_time
            return TaskResult(
                task_id=task_id,
                success=False,
                error=f"Task timed out after {timeout}s",
                duration=duration
            )
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Task {task_id} failed: {e}")
            return TaskResult(
                task_id=task_id,
                success=False,
                error=str(e),
                duration=duration
            )
        finally:
            async with self._lock:
                self.running_tasks.pop(task_id, None)
    
    async def run_parallel(
        self,
        tasks: List[tuple[str, Awaitable]],
        timeout: Optional[float] = None
    ) -> List[TaskResult]:
        """Run multiple tasks in parallel with concurrency limit."""
        coros = [self.run_task(task_id, coro, timeout) for task_id, coro in tasks]
        results = await asyncio.gather(*coros, return_exceptions=False)
        return list(results)
    
    async def cancel_all(self):
        """Cancel all running tasks."""
        async with self._lock:
            for task in self.running_tasks.values():
                task.cancel()
            self.running_tasks.clear()
    
    def get_running_count(self) -> int:
        """Get count of running tasks."""
        return len(self.running_tasks)


class ParallelExecutor:
    """Execute functions in parallel with thread/process pools."""
    
    def __init__(self, max_workers: int = 4, use_processes: bool = False):
        self.max_workers = max_workers
        self.use_processes = use_processes
        self.executor_class = (
            ProcessPoolExecutor if use_processes 
            else ThreadPoolExecutor
        )
    
    def map(self, func: Callable, items: List[Any]) -> List[Any]:
        """Map function over items in parallel."""
        with self.executor_class(max_workers=self.max_workers) as executor:
            results = list(executor.map(func, items))
        return results
    
    def submit(self, func: Callable, *args, **kwargs) -> Any:
        """Submit a single task."""
        with self.executor_class(max_workers=self.max_workers) as executor:
            future = executor.submit(func, *args, **kwargs)
            return future.result()


async def gather_with_concurrency(
    n: int,
    *coros: Awaitable[T]
) -> List[T]:
    """Run coroutines with limited concurrency."""
    semaphore = asyncio.Semaphore(n)
    
    async def sem_coro(coro):
        async with semaphore:
            return await coro
    
    return await asyncio.gather(*(sem_coro(c) for c in coros))


async def run_with_timeout(
    coro: Awaitable[T],
    timeout: float,
    default: T = None
) -> T:
    """Run coroutine with timeout, return default on timeout."""
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        return default


class BatchRunner:
    """Run tasks in batches with progress tracking."""
    
    def __init__(self, batch_size: int = 10):
        self.batch_size = batch_size
    
    async def run_batch(
        self,
        items: List[Any],
        process_func: Callable[[Any], Awaitable[Any]],
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> List[Any]:
        """Process items in batches."""
        results = []
        total = len(items)
        
        for i in range(0, total, self.batch_size):
            batch = items[i:i + self.batch_size]
            
            batch_results = await asyncio.gather(
                *[process_func(item) for item in batch],
                return_exceptions=True
            )
            
            for result in batch_results:
                if isinstance(result, Exception):
                    logger.error(f"Batch item failed: {result}")
                    results.append(None)
                else:
                    results.append(result)
            
            if progress_callback:
                progress_callback(i + len(batch), total)
        
        return results


class WorkerPool:
    """Thread-safe worker pool for background tasks."""
    
    def __init__(self, num_workers: int = 4):
        self.num_workers = num_workers
        self.queue: asyncio.Queue = asyncio.Queue()
        self.workers: List[asyncio.Task] = []
        self.running = False
    
    async def _worker(self, worker_id: int):
        """Worker task."""
        while self.running:
            try:
                task = await asyncio.wait_for(self.queue.get(), timeout=1.0)
                func, args, kwargs = task
                try:
                    await func(*args, **kwargs)
                except Exception as e:
                    logger.error(f"Worker {worker_id} error: {e}")
                finally:
                    self.queue.task_done()
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Worker {worker_id} fatal error: {e}")
    
    async def start(self):
        """Start the worker pool."""
        self.running = True
        self.workers = [
            asyncio.create_task(self._worker(i))
            for i in range(self.num_workers)
        ]
    
    async def stop(self):
        """Stop the worker pool."""
        self.running = False
        for worker in self.workers:
            worker.cancel()
        await asyncio.gather(*self.workers, return_exceptions=True)
    
    async def submit(self, func: Callable, *args, **kwargs):
        """Submit a task to the pool."""
        await self.queue.put((func, args, kwargs))
    
    def submit_sync(self, func: Callable, *args, **kwargs):
        """Submit a sync function to run in worker."""
        async def wrapper():
            return func(*args, kwargs)
        asyncio.create_task(self.submit(wrapper))