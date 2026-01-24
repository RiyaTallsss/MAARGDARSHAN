"""
WebSocket handlers for real-time UI updates during API calls and background processing.

This module provides WebSocket endpoints for progress tracking, status updates,
and real-time communication between the backend and frontend.
"""

import asyncio
import json
import logging
from typing import Dict, Any, List, Optional, Set
from datetime import datetime
import uuid

from fastapi import WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState
import weakref

from ..utils.background_processor import get_background_processor, get_progress_websocket, ProgressUpdate
from ..utils.performance_monitor import get_performance_monitor
from ..utils.smart_cache import get_smart_cache

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections for real-time updates."""
    
    def __init__(self):
        # Active connections by type
        self.progress_connections: Dict[str, Set[WebSocket]] = {}  # task_id -> websockets
        self.status_connections: Set[WebSocket] = set()
        self.performance_connections: Set[WebSocket] = set()
        self.cache_connections: Set[WebSocket] = set()
        
        # Connection metadata
        self.connection_metadata: Dict[WebSocket, Dict[str, Any]] = weakref.WeakKeyDictionary()
        
        # Message queues for offline connections
        self.message_queues: Dict[str, List[Dict[str, Any]]] = {}
        
        logger.info("WebSocket connection manager initialized")
    
    async def connect_progress(self, websocket: WebSocket, task_id: str) -> None:
        """Connect WebSocket for task progress updates."""
        await websocket.accept()
        
        if task_id not in self.progress_connections:
            self.progress_connections[task_id] = set()
        
        self.progress_connections[task_id].add(websocket)
        
        # Store connection metadata
        self.connection_metadata[websocket] = {
            'type': 'progress',
            'task_id': task_id,
            'connected_at': datetime.now(),
            'client_id': str(uuid.uuid4())
        }
        
        logger.info(f"WebSocket connected for task progress: {task_id}")
        
        # Send any queued messages
        await self._send_queued_messages(websocket, f"progress_{task_id}")
    
    async def connect_status(self, websocket: WebSocket) -> None:
        """Connect WebSocket for general status updates."""
        await websocket.accept()
        
        self.status_connections.add(websocket)
        
        # Store connection metadata
        self.connection_metadata[websocket] = {
            'type': 'status',
            'connected_at': datetime.now(),
            'client_id': str(uuid.uuid4())
        }
        
        logger.info("WebSocket connected for status updates")
        
        # Send current system status
        await self._send_current_status(websocket)
    
    async def connect_performance(self, websocket: WebSocket) -> None:
        """Connect WebSocket for performance monitoring updates."""
        await websocket.accept()
        
        self.performance_connections.add(websocket)
        
        # Store connection metadata
        self.connection_metadata[websocket] = {
            'type': 'performance',
            'connected_at': datetime.now(),
            'client_id': str(uuid.uuid4())
        }
        
        logger.info("WebSocket connected for performance updates")
        
        # Send current performance metrics
        await self._send_current_performance(websocket)
    
    async def connect_cache(self, websocket: WebSocket) -> None:
        """Connect WebSocket for cache status updates."""
        await websocket.accept()
        
        self.cache_connections.add(websocket)
        
        # Store connection metadata
        self.connection_metadata[websocket] = {
            'type': 'cache',
            'connected_at': datetime.now(),
            'client_id': str(uuid.uuid4())
        }
        
        logger.info("WebSocket connected for cache updates")
        
        # Send current cache info
        await self._send_current_cache_info(websocket)
    
    def disconnect(self, websocket: WebSocket) -> None:
        """Disconnect WebSocket and clean up."""
        metadata = self.connection_metadata.get(websocket)
        
        if metadata:
            connection_type = metadata['type']
            
            if connection_type == 'progress':
                task_id = metadata['task_id']
                if task_id in self.progress_connections:
                    self.progress_connections[task_id].discard(websocket)
                    if not self.progress_connections[task_id]:
                        del self.progress_connections[task_id]
                
                logger.info(f"WebSocket disconnected from task progress: {task_id}")
            
            elif connection_type == 'status':
                self.status_connections.discard(websocket)
                logger.info("WebSocket disconnected from status updates")
            
            elif connection_type == 'performance':
                self.performance_connections.discard(websocket)
                logger.info("WebSocket disconnected from performance updates")
            
            elif connection_type == 'cache':
                self.cache_connections.discard(websocket)
                logger.info("WebSocket disconnected from cache updates")
        
        # Clean up metadata
        if websocket in self.connection_metadata:
            del self.connection_metadata[websocket]
    
    async def broadcast_progress_update(self, task_id: str, update: ProgressUpdate) -> None:
        """Broadcast progress update to connected clients."""
        if task_id not in self.progress_connections:
            # Queue message for when clients connect
            queue_key = f"progress_{task_id}"
            if queue_key not in self.message_queues:
                self.message_queues[queue_key] = []
            
            self.message_queues[queue_key].append({
                'type': 'progress_update',
                'data': update.to_dict()
            })
            
            # Keep only recent messages
            self.message_queues[queue_key] = self.message_queues[queue_key][-10:]
            return
        
        message = {
            'type': 'progress_update',
            'data': update.to_dict()
        }
        
        # Send to all connected clients for this task
        disconnected = []
        for websocket in self.progress_connections[task_id].copy():
            try:
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.send_json(message)
                else:
                    disconnected.append(websocket)
            except Exception as e:
                logger.warning(f"Failed to send progress update: {e}")
                disconnected.append(websocket)
        
        # Clean up disconnected clients
        for websocket in disconnected:
            self.progress_connections[task_id].discard(websocket)
    
    async def broadcast_status_update(self, status_data: Dict[str, Any]) -> None:
        """Broadcast status update to connected clients."""
        message = {
            'type': 'status_update',
            'data': status_data,
            'timestamp': datetime.now().isoformat()
        }
        
        disconnected = []
        for websocket in self.status_connections.copy():
            try:
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.send_json(message)
                else:
                    disconnected.append(websocket)
            except Exception as e:
                logger.warning(f"Failed to send status update: {e}")
                disconnected.append(websocket)
        
        # Clean up disconnected clients
        for websocket in disconnected:
            self.status_connections.discard(websocket)
    
    async def broadcast_performance_update(self, performance_data: Dict[str, Any]) -> None:
        """Broadcast performance update to connected clients."""
        message = {
            'type': 'performance_update',
            'data': performance_data,
            'timestamp': datetime.now().isoformat()
        }
        
        disconnected = []
        for websocket in self.performance_connections.copy():
            try:
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.send_json(message)
                else:
                    disconnected.append(websocket)
            except Exception as e:
                logger.warning(f"Failed to send performance update: {e}")
                disconnected.append(websocket)
        
        # Clean up disconnected clients
        for websocket in disconnected:
            self.performance_connections.discard(websocket)
    
    async def broadcast_cache_update(self, cache_data: Dict[str, Any]) -> None:
        """Broadcast cache update to connected clients."""
        message = {
            'type': 'cache_update',
            'data': cache_data,
            'timestamp': datetime.now().isoformat()
        }
        
        disconnected = []
        for websocket in self.cache_connections.copy():
            try:
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.send_json(message)
                else:
                    disconnected.append(websocket)
            except Exception as e:
                logger.warning(f"Failed to send cache update: {e}")
                disconnected.append(websocket)
        
        # Clean up disconnected clients
        for websocket in disconnected:
            self.cache_connections.discard(websocket)
    
    async def send_task_completion(self, task_id: str, result: Dict[str, Any]) -> None:
        """Send task completion notification."""
        if task_id not in self.progress_connections:
            return
        
        message = {
            'type': 'task_completed',
            'task_id': task_id,
            'data': result,
            'timestamp': datetime.now().isoformat()
        }
        
        disconnected = []
        for websocket in self.progress_connections[task_id].copy():
            try:
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.send_json(message)
                else:
                    disconnected.append(websocket)
            except Exception as e:
                logger.warning(f"Failed to send task completion: {e}")
                disconnected.append(websocket)
        
        # Clean up disconnected clients
        for websocket in disconnected:
            self.progress_connections[task_id].discard(websocket)
    
    async def _send_queued_messages(self, websocket: WebSocket, queue_key: str) -> None:
        """Send queued messages to a newly connected client."""
        if queue_key not in self.message_queues:
            return
        
        for message in self.message_queues[queue_key]:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send queued message: {e}")
                break
        
        # Clear queue after sending
        del self.message_queues[queue_key]
    
    async def _send_current_status(self, websocket: WebSocket) -> None:
        """Send current system status to a newly connected client."""
        try:
            # Get current status from background processor
            processor = get_background_processor()
            queue_status = processor.get_queue_status()
            
            message = {
                'type': 'initial_status',
                'data': {
                    'queue_status': queue_status,
                    'active_connections': len(self.status_connections),
                    'system_time': datetime.now().isoformat()
                }
            }
            
            await websocket.send_json(message)
        except Exception as e:
            logger.warning(f"Failed to send current status: {e}")
    
    async def _send_current_performance(self, websocket: WebSocket) -> None:
        """Send current performance metrics to a newly connected client."""
        try:
            # Get current performance metrics
            performance_monitor = get_performance_monitor()
            performance_report = performance_monitor.get_performance_report()
            
            message = {
                'type': 'initial_performance',
                'data': performance_report
            }
            
            await websocket.send_json(message)
        except Exception as e:
            logger.warning(f"Failed to send current performance: {e}")
    
    async def _send_current_cache_info(self, websocket: WebSocket) -> None:
        """Send current cache information to a newly connected client."""
        try:
            # Get current cache info
            smart_cache = get_smart_cache()
            cache_info = smart_cache.get_cache_info()
            
            message = {
                'type': 'initial_cache_info',
                'data': cache_info
            }
            
            await websocket.send_json(message)
        except Exception as e:
            logger.warning(f"Failed to send current cache info: {e}")
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get connection statistics."""
        return {
            'progress_connections': sum(len(conns) for conns in self.progress_connections.values()),
            'status_connections': len(self.status_connections),
            'performance_connections': len(self.performance_connections),
            'cache_connections': len(self.cache_connections),
            'total_connections': (
                sum(len(conns) for conns in self.progress_connections.values()) +
                len(self.status_connections) +
                len(self.performance_connections) +
                len(self.cache_connections)
            ),
            'queued_message_topics': len(self.message_queues)
        }


# Global connection manager
connection_manager = ConnectionManager()


class WebSocketHandler:
    """WebSocket message handler for client communication."""
    
    def __init__(self, websocket: WebSocket, connection_type: str):
        self.websocket = websocket
        self.connection_type = connection_type
        self.client_id = str(uuid.uuid4())
        
    async def handle_messages(self) -> None:
        """Handle incoming WebSocket messages."""
        try:
            while True:
                # Receive message from client
                data = await self.websocket.receive_json()
                
                # Process message based on type
                await self._process_message(data)
                
        except WebSocketDisconnect:
            logger.info(f"WebSocket client disconnected: {self.client_id}")
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
        finally:
            # Clean up connection
            connection_manager.disconnect(self.websocket)
    
    async def _process_message(self, data: Dict[str, Any]) -> None:
        """Process incoming WebSocket message."""
        message_type = data.get('type')
        
        if message_type == 'ping':
            # Respond to ping with pong
            await self.websocket.send_json({
                'type': 'pong',
                'timestamp': datetime.now().isoformat()
            })
        
        elif message_type == 'subscribe_task':
            # Subscribe to task progress updates
            task_id = data.get('task_id')
            if task_id:
                await self._subscribe_to_task(task_id)
        
        elif message_type == 'unsubscribe_task':
            # Unsubscribe from task progress updates
            task_id = data.get('task_id')
            if task_id:
                await self._unsubscribe_from_task(task_id)
        
        elif message_type == 'get_task_status':
            # Get current task status
            task_id = data.get('task_id')
            if task_id:
                await self._send_task_status(task_id)
        
        elif message_type == 'cancel_task':
            # Cancel a background task
            task_id = data.get('task_id')
            if task_id:
                await self._cancel_task(task_id)
        
        elif message_type == 'get_queue_status':
            # Get current queue status
            await self._send_queue_status()
        
        elif message_type == 'get_performance_metrics':
            # Get current performance metrics
            await self._send_performance_metrics()
        
        elif message_type == 'get_cache_info':
            # Get current cache information
            await self._send_cache_info()
        
        else:
            # Unknown message type
            await self.websocket.send_json({
                'type': 'error',
                'message': f'Unknown message type: {message_type}'
            })
    
    async def _subscribe_to_task(self, task_id: str) -> None:
        """Subscribe to task progress updates."""
        if task_id not in connection_manager.progress_connections:
            connection_manager.progress_connections[task_id] = set()
        
        connection_manager.progress_connections[task_id].add(self.websocket)
        
        # Update connection metadata
        if self.websocket in connection_manager.connection_metadata:
            connection_manager.connection_metadata[self.websocket]['subscribed_tasks'] = \
                connection_manager.connection_metadata[self.websocket].get('subscribed_tasks', []) + [task_id]
        
        await self.websocket.send_json({
            'type': 'subscribed',
            'task_id': task_id
        })
    
    async def _unsubscribe_from_task(self, task_id: str) -> None:
        """Unsubscribe from task progress updates."""
        if task_id in connection_manager.progress_connections:
            connection_manager.progress_connections[task_id].discard(self.websocket)
            
            if not connection_manager.progress_connections[task_id]:
                del connection_manager.progress_connections[task_id]
        
        # Update connection metadata
        if self.websocket in connection_manager.connection_metadata:
            subscribed_tasks = connection_manager.connection_metadata[self.websocket].get('subscribed_tasks', [])
            if task_id in subscribed_tasks:
                subscribed_tasks.remove(task_id)
        
        await self.websocket.send_json({
            'type': 'unsubscribed',
            'task_id': task_id
        })
    
    async def _send_task_status(self, task_id: str) -> None:
        """Send current task status."""
        processor = get_background_processor()
        task_status = processor.get_task_status(task_id)
        
        await self.websocket.send_json({
            'type': 'task_status',
            'task_id': task_id,
            'data': task_status
        })
    
    async def _cancel_task(self, task_id: str) -> None:
        """Cancel a background task."""
        processor = get_background_processor()
        success = processor.cancel_task(task_id)
        
        await self.websocket.send_json({
            'type': 'task_cancel_result',
            'task_id': task_id,
            'success': success
        })
    
    async def _send_queue_status(self) -> None:
        """Send current queue status."""
        processor = get_background_processor()
        queue_status = processor.get_queue_status()
        
        await self.websocket.send_json({
            'type': 'queue_status',
            'data': queue_status
        })
    
    async def _send_performance_metrics(self) -> None:
        """Send current performance metrics."""
        performance_monitor = get_performance_monitor()
        performance_report = performance_monitor.get_performance_report()
        
        await self.websocket.send_json({
            'type': 'performance_metrics',
            'data': performance_report
        })
    
    async def _send_cache_info(self) -> None:
        """Send current cache information."""
        smart_cache = get_smart_cache()
        cache_info = smart_cache.get_cache_info()
        
        await self.websocket.send_json({
            'type': 'cache_info',
            'data': cache_info
        })


class PeriodicUpdater:
    """Sends periodic updates to connected WebSocket clients."""
    
    def __init__(self, connection_manager: ConnectionManager):
        self.connection_manager = connection_manager
        self._active = False
        self._update_task: Optional[asyncio.Task] = None
    
    async def start(self) -> None:
        """Start periodic updates."""
        if self._active:
            return
        
        self._active = True
        self._update_task = asyncio.create_task(self._update_loop())
        logger.info("Periodic WebSocket updater started")
    
    async def stop(self) -> None:
        """Stop periodic updates."""
        if not self._active:
            return
        
        self._active = False
        
        if self._update_task:
            self._update_task.cancel()
            try:
                await self._update_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Periodic WebSocket updater stopped")
    
    async def _update_loop(self) -> None:
        """Main update loop."""
        while self._active:
            try:
                # Send status updates every 30 seconds
                if self.connection_manager.status_connections:
                    await self._send_status_updates()
                
                # Send performance updates every 60 seconds
                if self.connection_manager.performance_connections:
                    await self._send_performance_updates()
                
                # Send cache updates every 120 seconds
                if self.connection_manager.cache_connections:
                    await self._send_cache_updates()
                
                await asyncio.sleep(30)  # Update every 30 seconds
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Periodic update error: {e}")
                await asyncio.sleep(30)
    
    async def _send_status_updates(self) -> None:
        """Send periodic status updates."""
        try:
            processor = get_background_processor()
            queue_status = processor.get_queue_status()
            
            status_data = {
                'queue_status': queue_status,
                'connection_stats': self.connection_manager.get_connection_stats(),
                'system_time': datetime.now().isoformat()
            }
            
            await self.connection_manager.broadcast_status_update(status_data)
        except Exception as e:
            logger.warning(f"Failed to send status updates: {e}")
    
    async def _send_performance_updates(self) -> None:
        """Send periodic performance updates."""
        try:
            performance_monitor = get_performance_monitor()
            performance_report = performance_monitor.get_performance_report()
            
            await self.connection_manager.broadcast_performance_update(performance_report)
        except Exception as e:
            logger.warning(f"Failed to send performance updates: {e}")
    
    async def _send_cache_updates(self) -> None:
        """Send periodic cache updates."""
        try:
            smart_cache = get_smart_cache()
            cache_info = smart_cache.get_cache_info()
            
            await self.connection_manager.broadcast_cache_update(cache_info)
        except Exception as e:
            logger.warning(f"Failed to send cache updates: {e}")


# Global periodic updater
periodic_updater = PeriodicUpdater(connection_manager)


# WebSocket endpoint handlers
async def handle_progress_websocket(websocket: WebSocket, task_id: str) -> None:
    """Handle WebSocket connection for task progress updates."""
    await connection_manager.connect_progress(websocket, task_id)
    
    handler = WebSocketHandler(websocket, 'progress')
    await handler.handle_messages()


async def handle_status_websocket(websocket: WebSocket) -> None:
    """Handle WebSocket connection for status updates."""
    await connection_manager.connect_status(websocket)
    
    handler = WebSocketHandler(websocket, 'status')
    await handler.handle_messages()


async def handle_performance_websocket(websocket: WebSocket) -> None:
    """Handle WebSocket connection for performance updates."""
    await connection_manager.connect_performance(websocket)
    
    handler = WebSocketHandler(websocket, 'performance')
    await handler.handle_messages()


async def handle_cache_websocket(websocket: WebSocket) -> None:
    """Handle WebSocket connection for cache updates."""
    await connection_manager.connect_cache(websocket)
    
    handler = WebSocketHandler(websocket, 'cache')
    await handler.handle_messages()


# Progress callback for background processor integration
async def websocket_progress_callback(update: ProgressUpdate) -> None:
    """Callback to send progress updates via WebSocket."""
    await connection_manager.broadcast_progress_update(update.task_id, update)


# Initialize WebSocket integration
def initialize_websocket_integration() -> None:
    """Initialize WebSocket integration with background systems."""
    # Add progress callback to background processor
    processor = get_background_processor()
    
    # This would be integrated with the actual progress callback system
    logger.info("WebSocket integration initialized")


# Startup and shutdown functions
async def startup_websocket_services() -> None:
    """Start WebSocket services."""
    await periodic_updater.start()
    initialize_websocket_integration()


async def shutdown_websocket_services() -> None:
    """Shutdown WebSocket services."""
    await periodic_updater.stop()