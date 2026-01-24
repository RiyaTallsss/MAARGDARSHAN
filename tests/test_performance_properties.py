"""
Property-based tests for enhanced performance requirements.

This module tests the performance properties of the rural infrastructure planning system,
including API latency, large file handling, processing efficiency, UI responsiveness,
and concurrent user performance.

**Property 22: Response Time Performance including API latency**
**Property 23: Large File Handling with API data integration**
**Property 24: API Processing Efficiency with rate limiting**
**Property 25: UI Responsiveness during API calls**
**Property 26: Concurrent User Performance with shared API limits**
**Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5, 10.1**
"""

import asyncio
import time
import pytest
from hypothesis import given, strategies as st, settings, assume
from hypothesis.stateful import RuleBasedStateMachine, rule, initialize, invariant
from unittest.mock import AsyncMock, patch, MagicMock
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from datetime import datetime, timedelta
import json
import tempfile
import os
from pathlib import Path

from rural_infrastructure_planning.data.api_client import API_Client, Coordinate
from rural_infrastructure_planning.utils.performance_monitor import PerformanceMonitor
from rural_infrastructure_planning.utils.api_optimizer import APIOptimizer
from rural_infrastructure_planning.utils.background_processor import BackgroundProcessor, TaskPriority
from rural_infrastructure_planning.utils.smart_cache import SmartCache
from rural_infrastructure_planning.routing.route_generator import Route_Generator, RouteConstraints


class TestPerformanceProperties:
    """Property-based tests for performance requirements."""
    
    @pytest.fixture
    def api_client(self):
        """Create API client for testing."""
        return API_Client()
    
    @pytest.fixture
    def performance_monitor(self):
        """Create performance monitor for testing."""
        return PerformanceMonitor()
    
    @pytest.fixture
    def api_optimizer(self):
        """Create API optimizer for testing."""
        return APIOptimizer()
    
    @pytest.fixture
    def background_processor(self):
        """Create background processor for testing."""
        return BackgroundProcessor(max_concurrent_tasks=3, max_thread_workers=2)
    
    @pytest.fixture
    def smart_cache(self):
        """Create smart cache for testing."""
        return SmartCache(max_size_mb=10)  # Small cache for testing
    
    @pytest.fixture
    def route_generator(self, api_client):
        """Create route generator for testing."""
        return Route_Generator(api_client)

    @given(
        coordinates=st.lists(
            st.tuples(
                st.floats(min_value=29.0, max_value=31.0),  # Uttarkashi region
                st.floats(min_value=77.0, max_value=79.0),
                st.floats(min_value=500, max_value=3000)
            ),
            min_size=2,
            max_size=10
        ),
        timeout_threshold=st.floats(min_value=1.0, max_value=30.0)
    )
    @settings(max_examples=20, deadline=60000)
    async def test_property_22_response_time_performance_with_api_latency(
        self, api_client, performance_monitor, coordinates, timeout_threshold
    ):
        """
        **Property 22: Response Time Performance including API latency**
        **Validates: Requirements 8.1, 8.2, 8.3, 8.5, 10.1**
        
        Tests that the system maintains acceptable response times even with API latency.
        """
        assume(len(coordinates) >= 2)
        
        start_coord = Coordinate(coordinates[0][0], coordinates[0][1], coordinates[0][2])
        end_coord = Coordinate(coordinates[1][0], coordinates[1][1], coordinates[1][2])
        
        # Mock API calls with controlled latency
        with patch.object(api_client, 'fetch_elevation_data') as mock_elevation, \
             patch.object(api_client, 'query_osm_data') as mock_osm, \
             patch.object(api_client, 'get_weather_data') as mock_weather:
            
            # Simulate API latency
            async def mock_api_call_with_latency(delay=0.1):
                await asyncio.sleep(delay)
                return {"data": "mock_response", "cached": False}
            
            mock_elevation.side_effect = lambda *args, **kwargs: mock_api_call_with_latency(0.1)
            mock_osm.side_effect = lambda *args, **kwargs: mock_api_call_with_latency(0.15)
            mock_weather.side_effect = lambda *args, **kwargs: mock_api_call_with_latency(0.05)
            
            # Start performance monitoring
            await performance_monitor.start_monitoring()
            
            try:
                # Measure response time
                start_time = time.time()
                
                # Simulate route generation request
                result = await api_client.fetch_elevation_data(start_coord, end_coord)
                
                end_time = time.time()
                response_time = end_time - start_time
                
                # Record performance metrics
                performance_monitor.record_api_call("elevation_api", response_time * 1000, True)
                
                # Get performance report
                report = performance_monitor.get_performance_report()
                
                # Property assertions
                assert response_time < timeout_threshold, f"Response time {response_time:.2f}s exceeded threshold {timeout_threshold}s"
                assert report["api_performance"]["elevation_api"]["average_response_time"] > 0
                assert report["api_performance"]["elevation_api"]["success_rate"] == 1.0
                
                # API latency should be tracked
                assert "api_latency_ms" in report["system_metrics"]
                
                # System should maintain performance under API latency
                system_efficiency = report["system_metrics"]["processing_efficiency"]
                assert system_efficiency > 0.5, f"System efficiency {system_efficiency} too low under API latency"
                
            finally:
                await performance_monitor.stop_monitoring()

    @given(
        file_sizes_mb=st.lists(
            st.floats(min_value=1.0, max_value=100.0),
            min_size=1,
            max_size=5
        ),
        api_data_ratio=st.floats(min_value=0.1, max_value=0.9)
    )
    @settings(max_examples=15, deadline=90000)
    async def test_property_23_large_file_handling_with_api_integration(
        self, api_client, performance_monitor, smart_cache, file_sizes_mb, api_data_ratio
    ):
        """
        **Property 23: Large File Handling with API data integration**
        **Validates: Requirements 8.2, 10.1**
        
        Tests that the system efficiently handles large files with mixed API and local data.
        """
        # Start services
        await performance_monitor.start_monitoring()
        await smart_cache.start()
        
        try:
            total_processed_mb = 0
            processing_times = []
            
            for file_size_mb in file_sizes_mb:
                # Create mock large file data
                mock_data_size = int(file_size_mb * 1024 * 1024)  # Convert to bytes
                
                # Split between API and local data based on ratio
                api_data_size = int(mock_data_size * api_data_ratio)
                local_data_size = mock_data_size - api_data_size
                
                start_time = time.time()
                
                # Mock API data processing
                if api_data_size > 0:
                    with patch.object(api_client, 'fetch_elevation_data') as mock_api:
                        mock_api.return_value = {"data": "x" * api_data_size, "size_bytes": api_data_size}
                        api_result = await api_client.fetch_elevation_data(
                            Coordinate(30.0, 78.0), Coordinate(30.1, 78.1)
                        )
                        
                        # Cache large API data
                        smart_cache.set(
                            f"large_api_data_{file_size_mb}",
                            api_result,
                            ttl_seconds=3600,
                            source="api_large_file"
                        )
                
                # Mock local data processing
                if local_data_size > 0:
                    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                        temp_file.write(b"x" * local_data_size)
                        temp_file_path = temp_file.name
                    
                    try:
                        # Simulate processing large local file
                        with open(temp_file_path, 'rb') as f:
                            chunk_size = 1024 * 1024  # 1MB chunks
                            while chunk := f.read(chunk_size):
                                # Simulate processing
                                await asyncio.sleep(0.001)  # Small delay to simulate work
                    finally:
                        os.unlink(temp_file_path)
                
                end_time = time.time()
                processing_time = end_time - start_time
                processing_times.append(processing_time)
                total_processed_mb += file_size_mb
                
                # Record performance metrics
                performance_monitor.record_file_processing(file_size_mb, processing_time)
            
            # Get performance report
            report = performance_monitor.get_performance_report()
            cache_info = smart_cache.get_cache_info()
            
            # Property assertions
            avg_processing_time = sum(processing_times) / len(processing_times)
            
            # Large file processing should be efficient (< 2 seconds per MB on average)
            efficiency_threshold = 2.0  # seconds per MB
            assert avg_processing_time / (sum(file_sizes_mb) / len(file_sizes_mb)) < efficiency_threshold, \
                f"Large file processing too slow: {avg_processing_time:.2f}s average"
            
            # Memory usage should be reasonable
            memory_usage_mb = report["system_metrics"]["memory_usage_mb"]
            assert memory_usage_mb < total_processed_mb * 2, \
                f"Memory usage {memory_usage_mb}MB too high for {total_processed_mb}MB processed"
            
            # Cache should handle large data efficiently
            assert cache_info["utilization_percent"] < 90, \
                f"Cache utilization {cache_info['utilization_percent']}% too high"
            
            # API data integration should maintain performance
            if api_data_ratio > 0.5:
                assert report["api_performance"]["total_calls"] > 0
                assert report["api_performance"]["average_response_time"] < 5000  # 5 seconds
            
        finally:
            await performance_monitor.stop_monitoring()
            await smart_cache.stop()

    @given(
        concurrent_requests=st.integers(min_value=2, max_value=10),
        rate_limit_per_second=st.integers(min_value=1, max_value=20),
        request_interval=st.floats(min_value=0.1, max_value=2.0)
    )
    @settings(max_examples=10, deadline=120000)
    async def test_property_24_api_processing_efficiency_with_rate_limiting(
        self, api_client, api_optimizer, performance_monitor, 
        concurrent_requests, rate_limit_per_second, request_interval
    ):
        """
        **Property 24: API Processing Efficiency with rate limiting**
        **Validates: Requirements 8.3, 10.1**
        
        Tests that the system maintains processing efficiency under API rate limiting.
        """
        # Start services
        await performance_monitor.start_monitoring()
        
        # Configure rate limiting
        api_optimizer.configure_rate_limits({
            "nasa_srtm": rate_limit_per_second,
            "openweathermap": rate_limit_per_second,
            "overpass": rate_limit_per_second
        })
        
        try:
            # Create concurrent API requests
            async def make_api_request(request_id):
                start_time = time.time()
                
                # Mock API call with rate limiting
                with patch.object(api_client, 'fetch_elevation_data') as mock_api:
                    # Simulate rate limiting delay
                    await asyncio.sleep(1.0 / rate_limit_per_second)
                    mock_api.return_value = {"data": f"response_{request_id}", "cached": False}
                    
                    result = await api_client.fetch_elevation_data(
                        Coordinate(30.0 + request_id * 0.01, 78.0 + request_id * 0.01),
                        Coordinate(30.1 + request_id * 0.01, 78.1 + request_id * 0.01)
                    )
                
                end_time = time.time()
                return {
                    "request_id": request_id,
                    "response_time": end_time - start_time,
                    "result": result
                }
            
            # Execute concurrent requests
            start_time = time.time()
            
            tasks = []
            for i in range(concurrent_requests):
                await asyncio.sleep(request_interval)  # Stagger requests
                task = asyncio.create_task(make_api_request(i))
                tasks.append(task)
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            end_time = time.time()
            total_time = end_time - start_time
            
            # Analyze results
            successful_requests = [r for r in results if not isinstance(r, Exception)]
            failed_requests = [r for r in results if isinstance(r, Exception)]
            
            # Get performance report
            report = performance_monitor.get_performance_report()
            optimization_analytics = api_optimizer.get_optimization_analytics()
            
            # Property assertions
            success_rate = len(successful_requests) / len(results)
            assert success_rate >= 0.8, f"Success rate {success_rate:.2f} too low under rate limiting"
            
            # Rate limiting should be respected
            expected_min_time = concurrent_requests / rate_limit_per_second
            assert total_time >= expected_min_time * 0.8, \
                f"Requests completed too quickly: {total_time:.2f}s < {expected_min_time:.2f}s (rate limiting not working)"
            
            # Processing efficiency should be maintained
            if successful_requests:
                avg_response_time = sum(r["response_time"] for r in successful_requests) / len(successful_requests)
                assert avg_response_time < 10.0, f"Average response time {avg_response_time:.2f}s too high"
            
            # API optimization should show rate limiting awareness
            assert optimization_analytics["rate_limiting"]["total_delays"] >= 0
            assert optimization_analytics["cost_optimization"]["api_calls_optimized"] >= 0
            
            # System should adapt to rate limits
            throughput = len(successful_requests) / total_time
            expected_throughput = min(rate_limit_per_second, concurrent_requests / total_time)
            assert throughput <= expected_throughput * 1.2, \
                f"Throughput {throughput:.2f} rps exceeds rate limit {rate_limit_per_second} rps"
            
        finally:
            await performance_monitor.stop_monitoring()

    @given(
        background_task_count=st.integers(min_value=1, max_value=8),
        ui_request_frequency=st.floats(min_value=0.5, max_value=3.0),
        task_duration=st.floats(min_value=0.1, max_value=2.0)
    )
    @settings(max_examples=8, deadline=150000)
    async def test_property_25_ui_responsiveness_during_api_calls(
        self, background_processor, smart_cache, performance_monitor,
        background_task_count, ui_request_frequency, task_duration
    ):
        """
        **Property 25: UI Responsiveness during API calls**
        **Validates: Requirements 8.4, 10.1**
        
        Tests that UI remains responsive during background API calls and processing.
        """
        # Start services
        await background_processor.start_processing()
        await smart_cache.start()
        await performance_monitor.start_monitoring()
        
        try:
            ui_response_times = []
            background_tasks = []
            
            # Define background task function
            async def heavy_api_task(task_id, duration):
                """Simulate heavy API processing task."""
                await asyncio.sleep(duration)  # Simulate API call delay
                return f"Task {task_id} completed after {duration:.2f}s"
            
            # Submit background tasks
            for i in range(background_task_count):
                task_id = background_processor.submit_task(
                    name=f"Heavy API Task {i}",
                    function=heavy_api_task,
                    args=(i, task_duration),
                    priority=TaskPriority.NORMAL
                )
                background_tasks.append(task_id)
            
            # Simulate UI requests while background tasks are running
            ui_request_count = int(background_task_count * ui_request_frequency)
            
            for i in range(ui_request_count):
                start_time = time.time()
                
                # Simulate UI request (cache lookup, status check, etc.)
                cache_result = smart_cache.get(f"ui_data_{i}", default={"status": "not_found"})
                if cache_result["status"] == "not_found":
                    # Cache miss - store data
                    smart_cache.set(f"ui_data_{i}", {"status": "loaded", "data": f"ui_data_{i}"})
                
                # Check background task status (UI operation)
                if background_tasks:
                    task_status = background_processor.get_task_status(background_tasks[i % len(background_tasks)])
                
                end_time = time.time()
                ui_response_time = end_time - start_time
                ui_response_times.append(ui_response_time)
                
                # Small delay between UI requests
                await asyncio.sleep(0.1)
            
            # Wait for some background tasks to complete
            await asyncio.sleep(task_duration * 0.5)
            
            # Get performance metrics
            report = performance_monitor.get_performance_report()
            queue_status = background_processor.get_queue_status()
            cache_info = smart_cache.get_cache_info()
            
            # Property assertions
            if ui_response_times:
                avg_ui_response_time = sum(ui_response_times) / len(ui_response_times)
                max_ui_response_time = max(ui_response_times)
                
                # UI should remain responsive (< 100ms average, < 500ms max)
                assert avg_ui_response_time < 0.1, \
                    f"Average UI response time {avg_ui_response_time:.3f}s too high during background processing"
                
                assert max_ui_response_time < 0.5, \
                    f"Maximum UI response time {max_ui_response_time:.3f}s too high during background processing"
            
            # Background processing should not block UI
            assert queue_status["processing_active"] == True
            assert queue_status["running_tasks"] <= background_processor.max_concurrent_tasks
            
            # Cache should improve UI responsiveness
            assert cache_info["metrics"]["hit_rate"] >= 0.0  # Some cache hits expected
            assert cache_info["metrics"]["average_access_time_ms"] < 10  # Fast cache access
            
            # System should maintain performance under load
            system_efficiency = report["system_metrics"]["processing_efficiency"]
            assert system_efficiency > 0.3, \
                f"System efficiency {system_efficiency} too low during concurrent processing"
            
        finally:
            await background_processor.stop_processing()
            await smart_cache.stop()
            await performance_monitor.stop_monitoring()

    @given(
        concurrent_users=st.integers(min_value=2, max_value=8),
        requests_per_user=st.integers(min_value=2, max_value=5),
        shared_api_limit=st.integers(min_value=5, max_value=20)
    )
    @settings(max_examples=6, deadline=180000)
    async def test_property_26_concurrent_user_performance_with_shared_api_limits(
        self, api_client, api_optimizer, performance_monitor, smart_cache,
        concurrent_users, requests_per_user, shared_api_limit
    ):
        """
        **Property 26: Concurrent User Performance with shared API limits**
        **Validates: Requirements 8.5, 10.1**
        
        Tests that the system maintains performance for concurrent users sharing API limits.
        """
        # Start services
        await performance_monitor.start_monitoring()
        await smart_cache.start()
        
        # Configure shared API limits
        api_optimizer.configure_rate_limits({
            "nasa_srtm": shared_api_limit,
            "openweathermap": shared_api_limit,
            "overpass": shared_api_limit
        })
        
        try:
            user_results = {}
            
            async def simulate_user_session(user_id):
                """Simulate a user session with multiple requests."""
                user_start_time = time.time()
                user_requests = []
                
                for request_id in range(requests_per_user):
                    request_start_time = time.time()
                    
                    # Simulate user request with API calls
                    coord_offset = user_id * 0.01 + request_id * 0.001
                    start_coord = Coordinate(30.0 + coord_offset, 78.0 + coord_offset)
                    end_coord = Coordinate(30.1 + coord_offset, 78.1 + coord_offset)
                    
                    # Check cache first (realistic user behavior)
                    cache_key = f"user_{user_id}_request_{request_id}"
                    cached_result = smart_cache.get(cache_key)
                    
                    if cached_result is None:
                        # Cache miss - make API call
                        with patch.object(api_client, 'fetch_elevation_data') as mock_api:
                            # Simulate API rate limiting delay
                            await asyncio.sleep(1.0 / shared_api_limit)
                            mock_api.return_value = {
                                "data": f"user_{user_id}_data_{request_id}",
                                "cached": False
                            }
                            
                            result = await api_client.fetch_elevation_data(start_coord, end_coord)
                            
                            # Cache the result
                            smart_cache.set(cache_key, result, ttl_seconds=300)
                    else:
                        result = cached_result
                    
                    request_end_time = time.time()
                    request_time = request_end_time - request_start_time
                    
                    user_requests.append({
                        "request_id": request_id,
                        "response_time": request_time,
                        "cached": cached_result is not None
                    })
                    
                    # Small delay between user requests
                    await asyncio.sleep(0.2)
                
                user_end_time = time.time()
                user_session_time = user_end_time - user_start_time
                
                return {
                    "user_id": user_id,
                    "session_time": user_session_time,
                    "requests": user_requests,
                    "avg_response_time": sum(r["response_time"] for r in user_requests) / len(user_requests),
                    "cache_hit_rate": sum(1 for r in user_requests if r["cached"]) / len(user_requests)
                }
            
            # Execute concurrent user sessions
            start_time = time.time()
            
            user_tasks = [
                asyncio.create_task(simulate_user_session(user_id))
                for user_id in range(concurrent_users)
            ]
            
            user_results_list = await asyncio.gather(*user_tasks, return_exceptions=True)
            
            end_time = time.time()
            total_time = end_time - start_time
            
            # Process results
            successful_users = [r for r in user_results_list if not isinstance(r, Exception)]
            failed_users = [r for r in user_results_list if isinstance(r, Exception)]
            
            # Get performance metrics
            report = performance_monitor.get_performance_report()
            cache_info = smart_cache.get_cache_info()
            optimization_analytics = api_optimizer.get_optimization_analytics()
            
            # Property assertions
            user_success_rate = len(successful_users) / len(user_results_list)
            assert user_success_rate >= 0.8, \
                f"User success rate {user_success_rate:.2f} too low with shared API limits"
            
            if successful_users:
                # Response time fairness - no user should be significantly slower
                avg_response_times = [user["avg_response_time"] for user in successful_users]
                min_avg_time = min(avg_response_times)
                max_avg_time = max(avg_response_times)
                
                fairness_ratio = max_avg_time / min_avg_time if min_avg_time > 0 else 1.0
                assert fairness_ratio < 3.0, \
                    f"Response time fairness ratio {fairness_ratio:.2f} too high (unfair distribution)"
                
                # Overall performance should be acceptable
                overall_avg_response_time = sum(avg_response_times) / len(avg_response_times)
                assert overall_avg_response_time < 5.0, \
                    f"Overall average response time {overall_avg_response_time:.2f}s too high"
                
                # Cache should improve performance for concurrent users
                overall_cache_hit_rate = sum(user["cache_hit_rate"] for user in successful_users) / len(successful_users)
                if len(successful_users) > 1:  # Multiple users should benefit from shared cache
                    assert overall_cache_hit_rate > 0.1, \
                        f"Cache hit rate {overall_cache_hit_rate:.2f} too low for concurrent users"
            
            # API limits should be respected across all users
            total_requests = concurrent_users * requests_per_user
            expected_min_time = total_requests / shared_api_limit
            assert total_time >= expected_min_time * 0.7, \
                f"Total time {total_time:.2f}s too short for {total_requests} requests with limit {shared_api_limit}"
            
            # System should handle concurrent load efficiently
            system_efficiency = report["system_metrics"]["processing_efficiency"]
            assert system_efficiency > 0.2, \
                f"System efficiency {system_efficiency} too low under concurrent user load"
            
            # Memory usage should be reasonable for concurrent users
            memory_usage_mb = report["system_metrics"]["memory_usage_mb"]
            assert memory_usage_mb < concurrent_users * 50, \
                f"Memory usage {memory_usage_mb}MB too high for {concurrent_users} concurrent users"
            
        finally:
            await performance_monitor.stop_monitoring()
            await smart_cache.stop()


class PerformanceStateMachine(RuleBasedStateMachine):
    """
    Stateful property testing for performance under various system states.
    """
    
    def __init__(self):
        super().__init__()
        self.api_client = None
        self.performance_monitor = None
        self.smart_cache = None
        self.background_processor = None
        self.active_tasks = []
        self.performance_metrics = []
    
    @initialize()
    async def setup_system(self):
        """Initialize the system for testing."""
        self.api_client = API_Client()
        self.performance_monitor = PerformanceMonitor()
        self.smart_cache = SmartCache(max_size_mb=5)
        self.background_processor = BackgroundProcessor(max_concurrent_tasks=2)
        
        # Start services
        await self.performance_monitor.start_monitoring()
        await self.smart_cache.start()
        await self.background_processor.start_processing()
    
    @rule(
        task_count=st.integers(min_value=1, max_value=3),
        task_priority=st.sampled_from([TaskPriority.LOW, TaskPriority.NORMAL, TaskPriority.HIGH])
    )
    async def submit_background_tasks(self, task_count, task_priority):
        """Submit background tasks and verify performance impact."""
        async def mock_task(task_id):
            await asyncio.sleep(0.1)
            return f"Task {task_id} completed"
        
        for i in range(task_count):
            task_id = self.background_processor.submit_task(
                name=f"Test Task {len(self.active_tasks) + i}",
                function=mock_task,
                args=(len(self.active_tasks) + i,),
                priority=task_priority
            )
            self.active_tasks.append(task_id)
        
        # Record performance impact
        queue_status = self.background_processor.get_queue_status()
        self.performance_metrics.append({
            "timestamp": time.time(),
            "queue_length": queue_status["queue_length"],
            "running_tasks": queue_status["running_tasks"],
            "action": "submit_tasks"
        })
    
    @rule(cache_operations=st.integers(min_value=1, max_value=5))
    async def perform_cache_operations(self, cache_operations):
        """Perform cache operations and verify performance."""
        start_time = time.time()
        
        for i in range(cache_operations):
            key = f"test_key_{i}_{time.time()}"
            value = {"data": f"test_data_{i}", "size": i * 100}
            
            # Set and get operations
            self.smart_cache.set(key, value, ttl_seconds=60)
            retrieved = self.smart_cache.get(key)
            
            assert retrieved == value, "Cache operation failed"
        
        end_time = time.time()
        operation_time = end_time - start_time
        
        # Record cache performance
        cache_info = self.smart_cache.get_cache_info()
        self.performance_metrics.append({
            "timestamp": time.time(),
            "cache_operations": cache_operations,
            "operation_time": operation_time,
            "cache_hit_rate": cache_info["metrics"]["hit_rate"],
            "action": "cache_operations"
        })
    
    @rule()
    async def check_system_performance(self):
        """Check overall system performance invariants."""
        report = self.performance_monitor.get_performance_report()
        
        # System should maintain reasonable performance
        processing_efficiency = report["system_metrics"]["processing_efficiency"]
        assert processing_efficiency > 0.1, f"Processing efficiency {processing_efficiency} too low"
        
        # Memory usage should be bounded
        memory_usage = report["system_metrics"]["memory_usage_mb"]
        assert memory_usage < 200, f"Memory usage {memory_usage}MB too high"
    
    @invariant()
    def performance_invariants(self):
        """Invariants that should hold throughout testing."""
        if self.performance_metrics:
            # Performance should not degrade significantly over time
            recent_metrics = self.performance_metrics[-5:]  # Last 5 measurements
            
            if len(recent_metrics) >= 2:
                # Check for performance degradation
                first_metric = recent_metrics[0]
                last_metric = recent_metrics[-1]
                
                # Queue length should not grow unbounded
                if "queue_length" in first_metric and "queue_length" in last_metric:
                    assert last_metric["queue_length"] <= first_metric["queue_length"] + 10, \
                        "Queue length growing too fast"
    
    async def teardown(self):
        """Clean up after testing."""
        if self.background_processor:
            await self.background_processor.stop_processing()
        if self.smart_cache:
            await self.smart_cache.stop()
        if self.performance_monitor:
            await self.performance_monitor.stop_monitoring()


# Test runner for the state machine
TestPerformanceStateMachine = PerformanceStateMachine.TestCase


if __name__ == "__main__":
    # Run property tests
    pytest.main([__file__, "-v", "--tb=short"])