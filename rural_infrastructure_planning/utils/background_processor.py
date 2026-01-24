"""
Background processing system for UI responsiveness during API calls and heavy computations.

This module provides asynchronous task processing, progress tracking, and queue management
to ensure the UI remains responsive during long-running operations.
"""

import asyncio
import time
import uuid
from typing import Dict, Any, List, Optional, Callable, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging
import json
from collections import deque
import threading
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import weakref

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Task execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class TaskPriority(Enum):
    """Task priority levels."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class ProgressUpdate:
    """Progress update information."""
    task_id: str
    progress_percent: float
    current_step: str
    total_steps: int
    current_step_number: int
    estimated_remaining_seconds: Optional[float] = None
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'task_id': self.task_id,
            'progress_percent': self.progress_percent,
            'current_step': self.current_step,
            'total_steps': self.total_steps,
            'current_step_number': self.current_step_number,
            'estimated_remaining_seconds': self.estimated_remaining_seconds,
            'details': self.details,
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class TaskResult:
    """Task execution result."""
    task_id: str
    status: TaskStatus
    result: Optional[Any] = None
    error: Optional[str] = None
    execution_time_seconds: Optional[float] = None
    progress_updates: List[ProgressUpdate] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'task_id': self.task_id,
            'status': self.status.value,
            'result': self.result,
            'error': self.error,
            'execution_time_seconds': self.execution_time_seconds,
            'progress_updates': [update.to_dict() for update in self.progress_updates],
            'metadata': self.metadata
        }


@dataclass
class BackgroundTask:
    """Background task definition."""
    task_id: str
    name: str
    function: Callable
    args: tuple
    kwargs: dict
    priority: TaskPriority
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: TaskStatus = TaskStatus.PENDING
    progress_callback: Optional[Callable[[ProgressUpdate], None]] = None
    result: Optional[TaskResult] = None
    dependencies: List[str] = field(default_factory=list)
    timeout_seconds: Optional[float] = None
    retry_count: int = 0
    max_retries: int = 3
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'task_id': self.task_id,
            'name': self.name,
            'priority': self.priority.value,
            'created_at': self.created_at.isoformat(),
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'status': self.status.value,
            'dependencies': self.dependencies,
            'timeout_seconds': self.timeout_seconds,
            'retry_count': self.retry_count,
            'max_retries': self.max_retries,
            'result': self.result.to_dict() if self.result else None
        }


class ProgressTracker:
    """Progress tracking for long-running tasks."""
    
    def __init__(self, task_id: str, total_steps: int):
        self.task_id = task_id
        self.total_steps = total_steps
        self.current_step = 0
        self.start_time = time.time()
        self.step_times: List[float] = []
        self.callbacks: List[Callable[[ProgressUpdate], None]] = []
    
    def add_callback(self, callback: Callable[[ProgressUpdate], None]) -> None:
        """Add progress update callback."""
        self.callbacks.append(callback)
    
    def update_progress(self, step_name: str, details: Optional[Dict[str, Any]] = None) -> None:
        """Update progress to next step."""
        self.current_step += 1
        current_time = time.time()
        self.step_times.append(current_time)
        
        # Calculate progress percentage
        progress_percent = (self.current_step / self.total_steps) * 100
        
        # Estimate remaining time
        estimated_remaining = None
        if len(self.step_times) > 1:
            avg_step_time = (current_time - self.start_time) / self.current_step
            remaining_steps = self.total_steps - self.current_step
            estimated_remaining = avg_step_time * remaining_steps
        
        # Create progress update
        update = ProgressUpdate(
            task_id=self.task_id,
            progress_percent=progress_percent,
            current_step=step_name,
            total_steps=self.total_steps,
            current_step_number=self.current_step,
            estimated_remaining_seconds=estimated_remaining,
            details=details
        )
        
        # Notify callbacks
        for callback in self.callbacks:
            try:
                callback(update)
            except Exception as e:
                logger.warning(f"Progress callback failed: {e}")
    
    def complete(self) -> None:
        """Mark progress as complete."""
        if self.current_step < self.total_steps:
            self.update_progress("Completed", {"final_step": True})


class BackgroundProcessor:
    """
    Background processing system for UI responsiveness.
    
    Features:
    - Asynchronous task execution with progress tracking
    - Priority-based task queuing
    - Dependency management between tasks
    - Automatic retry with exponential backoff
    - Resource management and throttling
    - Real-time progress updates
    - Task cancellation and cleanup
    """
    
    def __init__(self, max_concurrent_tasks: int = 5, max_thread_workers: int = 4):
        self.max_concurrent_tasks = max_concurrent_tasks
        self.max_thread_workers = max_thread_workers
        
        # Task management
        self.tasks: Dict[str, BackgroundTask] = {}
        self.task_queue: deque = deque()
        self.running_tasks: Dict[str, asyncio.Task] = {}
        
        # Progress tracking
        self.progress_callbacks: Dict[str, List[Callable[[ProgressUpdate], None]]] = {}
        self.task_results: Dict[str, TaskResult] = {}
        
        # Resource management
        self.thread_executor = ThreadPoolExecutor(max_workers=max_thread_workers)
        self.process_executor = ProcessPoolExecutor(max_workers=2)  # Limited for memory
        
        # Processing state
        self._processing_active = False
        self._processor_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()
        
        # Statistics
        self.stats = {
            'total_tasks_processed': 0,
            'successful_tasks': 0,
            'failed_tasks': 0,
            'cancelled_tasks': 0,
            'average_execution_time': 0.0,
            'queue_high_water_mark': 0
        }
        
        logger.info(f"Background processor initialized with {max_concurrent_tasks} concurrent tasks")
    
    async def start_processing(self) -> None:
        """Start the background task processor."""
        if self._processing_active:
            logger.warning("Background processor already active")
            return
        
        self._processing_active = True
        self._shutdown_event.clear()
        
        # Start the main processing loop
        self._processor_task = asyncio.create_task(self._processing_loop())
        
        logger.info("Background processor started")
    
    async def stop_processing(self) -> None:
        """Stop the background task processor."""
        if not self._processing_active:
            return
        
        logger.info("Stopping background processor...")
        
        self._processing_active = False
        self._shutdown_event.set()
        
        # Cancel all running tasks
        for task_id, task in self.running_tasks.items():
            if not task.done():
                task.cancel()
                logger.info(f"Cancelled running task: {task_id}")
        
        # Wait for processor to stop
        if self._processor_task:
            try:
                await asyncio.wait_for(self._processor_task, timeout=10.0)
            except asyncio.TimeoutError:
                logger.warning("Background processor shutdown timeout")
                self._processor_task.cancel()
        
        # Cleanup executors
        self.thread_executor.shutdown(wait=True)
        self.process_executor.shutdown(wait=True)
        
        logger.info("Background processor stopped")
    
    async def _processing_loop(self) -> None:
        """Main processing loop for background tasks."""
        while self._processing_active:
            try:
                # Process pending tasks
                await self._process_pending_tasks()
                
                # Clean up completed tasks
                self._cleanup_completed_tasks()
                
                # Update statistics
                self._update_statistics()
                
                # Wait before next iteration
                try:
                    await asyncio.wait_for(self._shutdown_event.wait(), timeout=1.0)
                    break  # Shutdown requested
                except asyncio.TimeoutError:
                    continue  # Continue processing
                    
            except Exception as e:
                logger.error(f"Error in processing loop: {e}")
                await asyncio.sleep(1.0)
    
    async def _process_pending_tasks(self) -> None:
        """Process pending tasks from the queue."""
        # Check if we can start more tasks
        if len(self.running_tasks) >= self.max_concurrent_tasks:
            return
        
        # Get next task from queue (priority-based)
        next_task = self._get_next_task()
        if not next_task:
            return
        
        # Check dependencies
        if not self._check_dependencies(next_task):
            # Put task back in queue if dependencies not met
            self.task_queue.appendleft(next_task)
            return
        
        # Start the task
        await self._start_task(next_task)
    
    def _get_next_task(self) -> Optional[BackgroundTask]:
        """Get the next task from queue based on priority."""
        if not self.task_queue:
            return None
        
        # Sort queue by priority (higher priority first)
        sorted_tasks = sorted(self.task_queue, key=lambda t: t.priority.value, reverse=True)
        
        # Get highest priority task
        next_task = sorted_tasks[0]
        self.task_queue.remove(next_task)
        
        return next_task
    
    def _check_dependencies(self, task: BackgroundTask) -> bool:
        """Check if task dependencies are satisfied."""
        for dep_id in task.dependencies:
            if dep_id not in self.task_results:
                return False
            
            dep_result = self.task_results[dep_id]
            if dep_result.status != TaskStatus.COMPLETED:
                return False
        
        return True
    
    async def _start_task(self, task: BackgroundTask) -> None:
        """Start executing a background task."""
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()
        
        # Create progress tracker
        progress_tracker = ProgressTracker(task.task_id, total_steps=10)  # Default 10 steps
        
        # Add progress callback
        if task.progress_callback:
            progress_tracker.add_callback(task.progress_callback)
        
        # Add global progress callbacks
        for callback in self.progress_callbacks.get(task.task_id, []):
            progress_tracker.add_callback(callback)
        
        # Create and start the task
        async_task = asyncio.create_task(
            self._execute_task_with_timeout(task, progress_tracker)
        )
        
        self.running_tasks[task.task_id] = async_task
        
        logger.info(f"Started background task: {task.name} ({task.task_id})")
    
    async def _execute_task_with_timeout(self, task: BackgroundTask, progress_tracker: ProgressTracker) -> None:
        """Execute a task with timeout and error handling."""
        start_time = time.time()
        
        try:
            # Execute with timeout if specified
            if task.timeout_seconds:
                result = await asyncio.wait_for(
                    self._execute_task(task, progress_tracker),
                    timeout=task.timeout_seconds
                )
            else:
                result = await self._execute_task(task, progress_tracker)
            
            # Task completed successfully
            execution_time = time.time() - start_time
            
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            
            task_result = TaskResult(
                task_id=task.task_id,
                status=TaskStatus.COMPLETED,
                result=result,
                execution_time_seconds=execution_time,
                progress_updates=progress_tracker.step_times,
                metadata={'retry_count': task.retry_count}
            )
            
            task.result = task_result
            self.task_results[task.task_id] = task_result
            
            logger.info(f"Task completed: {task.name} ({execution_time:.2f}s)")
            
        except asyncio.TimeoutError:
            # Task timed out
            await self._handle_task_timeout(task, progress_tracker)
            
        except asyncio.CancelledError:
            # Task was cancelled
            await self._handle_task_cancellation(task)
            
        except Exception as e:
            # Task failed with error
            await self._handle_task_error(task, e, progress_tracker)
        
        finally:
            # Clean up
            if task.task_id in self.running_tasks:
                del self.running_tasks[task.task_id]
            
            progress_tracker.complete()
    
    async def _execute_task(self, task: BackgroundTask, progress_tracker: ProgressTracker) -> Any:
        """Execute the actual task function."""
        # Add progress tracker to kwargs if the function supports it
        kwargs = task.kwargs.copy()
        
        # Check if function accepts progress_tracker parameter
        import inspect
        sig = inspect.signature(task.function)
        if 'progress_tracker' in sig.parameters:
            kwargs['progress_tracker'] = progress_tracker
        
        # Execute based on function type
        if asyncio.iscoroutinefunction(task.function):
            # Async function
            return await task.function(*task.args, **kwargs)
        else:
            # Sync function - run in thread executor
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                self.thread_executor,
                lambda: task.function(*task.args, **kwargs)
            )
    
    async def _handle_task_timeout(self, task: BackgroundTask, progress_tracker: ProgressTracker) -> None:
        """Handle task timeout."""
        logger.warning(f"Task timed out: {task.name} ({task.timeout_seconds}s)")
        
        task.status = TaskStatus.FAILED
        task.completed_at = datetime.now()
        
        task_result = TaskResult(
            task_id=task.task_id,
            status=TaskStatus.FAILED,
            error=f"Task timed out after {task.timeout_seconds} seconds",
            metadata={'retry_count': task.retry_count, 'timeout': True}
        )
        
        task.result = task_result
        self.task_results[task.task_id] = task_result
        
        # Retry if possible
        if task.retry_count < task.max_retries:
            await self._retry_task(task)
    
    async def _handle_task_cancellation(self, task: BackgroundTask) -> None:
        """Handle task cancellation."""
        logger.info(f"Task cancelled: {task.name}")
        
        task.status = TaskStatus.CANCELLED
        task.completed_at = datetime.now()
        
        task_result = TaskResult(
            task_id=task.task_id,
            status=TaskStatus.CANCELLED,
            error="Task was cancelled",
            metadata={'retry_count': task.retry_count}
        )
        
        task.result = task_result
        self.task_results[task.task_id] = task_result
    
    async def _handle_task_error(self, task: BackgroundTask, error: Exception, progress_tracker: ProgressTracker) -> None:
        """Handle task execution error."""
        logger.error(f"Task failed: {task.name} - {error}")
        
        task.status = TaskStatus.FAILED
        task.completed_at = datetime.now()
        
        task_result = TaskResult(
            task_id=task.task_id,
            status=TaskStatus.FAILED,
            error=str(error),
            metadata={'retry_count': task.retry_count, 'error_type': type(error).__name__}
        )
        
        task.result = task_result
        self.task_results[task.task_id] = task_result
        
        # Retry if possible
        if task.retry_count < task.max_retries:
            await self._retry_task(task)
    
    async def _retry_task(self, task: BackgroundTask) -> None:
        """Retry a failed task with exponential backoff."""
        task.retry_count += 1
        
        # Calculate backoff delay
        backoff_delay = min(2 ** task.retry_count, 60)  # Max 60 seconds
        
        logger.info(f"Retrying task {task.name} in {backoff_delay}s (attempt {task.retry_count + 1})")
        
        # Reset task status
        task.status = TaskStatus.PENDING
        task.started_at = None
        task.completed_at = None
        
        # Schedule retry
        await asyncio.sleep(backoff_delay)
        self.task_queue.append(task)
    
    def _cleanup_completed_tasks(self) -> None:
        """Clean up old completed tasks to prevent memory leaks."""
        cutoff_time = datetime.now() - timedelta(hours=1)  # Keep results for 1 hour
        
        expired_tasks = [
            task_id for task_id, result in self.task_results.items()
            if result.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]
            and task_id in self.tasks
            and self.tasks[task_id].completed_at
            and self.tasks[task_id].completed_at < cutoff_time
        ]
        
        for task_id in expired_tasks:
            del self.tasks[task_id]
            del self.task_results[task_id]
            if task_id in self.progress_callbacks:
                del self.progress_callbacks[task_id]
    
    def _update_statistics(self) -> None:
        """Update processing statistics."""
        self.stats['queue_high_water_mark'] = max(
            self.stats['queue_high_water_mark'],
            len(self.task_queue)
        )
        
        # Calculate average execution time
        completed_tasks = [
            result for result in self.task_results.values()
            if result.status == TaskStatus.COMPLETED and result.execution_time_seconds
        ]
        
        if completed_tasks:
            total_time = sum(result.execution_time_seconds for result in completed_tasks)
            self.stats['average_execution_time'] = total_time / len(completed_tasks)
    
    def submit_task(self, 
                   name: str,
                   function: Callable,
                   args: tuple = (),
                   kwargs: dict = None,
                   priority: TaskPriority = TaskPriority.NORMAL,
                   dependencies: List[str] = None,
                   timeout_seconds: Optional[float] = None,
                   max_retries: int = 3,
                   progress_callback: Optional[Callable[[ProgressUpdate], None]] = None) -> str:
        """
        Submit a task for background processing.
        
        Args:
            name: Human-readable task name
            function: Function to execute
            args: Function arguments
            kwargs: Function keyword arguments
            priority: Task priority
            dependencies: List of task IDs this task depends on
            timeout_seconds: Task timeout
            max_retries: Maximum retry attempts
            progress_callback: Progress update callback
            
        Returns:
            Task ID for tracking
        """
        task_id = str(uuid.uuid4())
        
        task = BackgroundTask(
            task_id=task_id,
            name=name,
            function=function,
            args=args,
            kwargs=kwargs or {},
            priority=priority,
            created_at=datetime.now(),
            dependencies=dependencies or [],
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            progress_callback=progress_callback
        )
        
        self.tasks[task_id] = task
        self.task_queue.append(task)
        
        logger.info(f"Submitted background task: {name} ({task_id})")
        
        return task_id
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a specific task."""
        if task_id not in self.tasks:
            return None
        
        task = self.tasks[task_id]
        return task.to_dict()
    
    def get_task_result(self, task_id: str) -> Optional[TaskResult]:
        """Get result of a completed task."""
        return self.task_results.get(task_id)
    
    def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending or running task."""
        if task_id not in self.tasks:
            return False
        
        task = self.tasks[task_id]
        
        if task.status == TaskStatus.PENDING:
            # Remove from queue
            try:
                self.task_queue.remove(task)
                task.status = TaskStatus.CANCELLED
                task.completed_at = datetime.now()
                
                task_result = TaskResult(
                    task_id=task_id,
                    status=TaskStatus.CANCELLED,
                    error="Task cancelled before execution"
                )
                
                task.result = task_result
                self.task_results[task_id] = task_result
                
                logger.info(f"Cancelled pending task: {task.name}")
                return True
                
            except ValueError:
                pass  # Task not in queue
        
        elif task.status == TaskStatus.RUNNING:
            # Cancel running task
            if task_id in self.running_tasks:
                async_task = self.running_tasks[task_id]
                async_task.cancel()
                logger.info(f"Cancelled running task: {task.name}")
                return True
        
        return False
    
    def add_progress_callback(self, task_id: str, callback: Callable[[ProgressUpdate], None]) -> None:
        """Add progress callback for a task."""
        if task_id not in self.progress_callbacks:
            self.progress_callbacks[task_id] = []
        
        self.progress_callbacks[task_id].append(callback)
    
    def get_queue_status(self) -> Dict[str, Any]:
        """Get current queue status and statistics."""
        return {
            'queue_length': len(self.task_queue),
            'running_tasks': len(self.running_tasks),
            'total_tasks': len(self.tasks),
            'statistics': self.stats.copy(),
            'processing_active': self._processing_active
        }
    
    def get_all_tasks(self) -> List[Dict[str, Any]]:
        """Get status of all tasks."""
        return [task.to_dict() for task in self.tasks.values()]


# Global background processor instance
_background_processor: Optional[BackgroundProcessor] = None


def get_background_processor() -> BackgroundProcessor:
    """Get the global background processor instance."""
    global _background_processor
    if _background_processor is None:
        _background_processor = BackgroundProcessor()
    return _background_processor


def background_task(name: str, 
                   priority: TaskPriority = TaskPriority.NORMAL,
                   timeout_seconds: Optional[float] = None,
                   max_retries: int = 3):
    """
    Decorator to submit a function as a background task.
    
    Args:
        name: Task name
        priority: Task priority
        timeout_seconds: Task timeout
        max_retries: Maximum retry attempts
    """
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            processor = get_background_processor()
            
            # Extract progress callback if provided
            progress_callback = kwargs.pop('progress_callback', None)
            
            task_id = processor.submit_task(
                name=name,
                function=func,
                args=args,
                kwargs=kwargs,
                priority=priority,
                timeout_seconds=timeout_seconds,
                max_retries=max_retries,
                progress_callback=progress_callback
            )
            
            return task_id
        
        return wrapper
    
    return decorator


async def wait_for_task(task_id: str, timeout: Optional[float] = None) -> TaskResult:
    """
    Wait for a background task to complete.
    
    Args:
        task_id: Task ID to wait for
        timeout: Maximum time to wait
        
    Returns:
        Task result
        
    Raises:
        asyncio.TimeoutError: If timeout exceeded
        ValueError: If task not found
    """
    processor = get_background_processor()
    
    if task_id not in processor.tasks:
        raise ValueError(f"Task not found: {task_id}")
    
    start_time = time.time()
    
    while True:
        result = processor.get_task_result(task_id)
        if result and result.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            return result
        
        # Check timeout
        if timeout and (time.time() - start_time) > timeout:
            raise asyncio.TimeoutError(f"Task {task_id} did not complete within {timeout} seconds")
        
        # Wait before checking again
        await asyncio.sleep(0.1)


class TaskProgressWebSocket:
    """WebSocket handler for real-time task progress updates."""
    
    def __init__(self):
        self.connections: Dict[str, List[Any]] = {}  # task_id -> list of websockets
    
    def add_connection(self, task_id: str, websocket: Any) -> None:
        """Add WebSocket connection for task progress."""
        if task_id not in self.connections:
            self.connections[task_id] = []
        
        self.connections[task_id].append(websocket)
        
        # Add progress callback to background processor
        processor = get_background_processor()
        processor.add_progress_callback(task_id, self._send_progress_update)
    
    def remove_connection(self, task_id: str, websocket: Any) -> None:
        """Remove WebSocket connection."""
        if task_id in self.connections:
            try:
                self.connections[task_id].remove(websocket)
                if not self.connections[task_id]:
                    del self.connections[task_id]
            except ValueError:
                pass
    
    async def _send_progress_update(self, update: ProgressUpdate) -> None:
        """Send progress update to connected WebSockets."""
        task_id = update.task_id
        
        if task_id not in self.connections:
            return
        
        # Send to all connected clients
        disconnected = []
        for websocket in self.connections[task_id]:
            try:
                await websocket.send_json(update.to_dict())
            except Exception as e:
                logger.warning(f"Failed to send progress update: {e}")
                disconnected.append(websocket)
        
        # Remove disconnected clients
        for websocket in disconnected:
            self.remove_connection(task_id, websocket)


# Global WebSocket handler
_progress_websocket: Optional[TaskProgressWebSocket] = None


def get_progress_websocket() -> TaskProgressWebSocket:
    """Get the global progress WebSocket handler."""
    global _progress_websocket
    if _progress_websocket is None:
        _progress_websocket = TaskProgressWebSocket()
    return _progress_websocket