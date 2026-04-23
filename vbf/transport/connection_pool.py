"""WebSocket connection pool for VBF.

Manages multiple persistent WebSocket connections for concurrent RPC calls.
Provides connection pooling, health checking, and load balancing.
"""

import asyncio
import json
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
from collections import deque

import websockets


@dataclass
class ConnectionPoolConfig:
    """Configuration for connection pool."""
    min_connections: int = 2
    max_connections: int = 8
    connection_timeout: float = 30.0
    idle_timeout: float = 300.0  # 5 minutes
    batch_size: int = 5  # Batch up to 5 requests together
    health_check_interval: float = 30.0


class PooledConnection:
    """A single managed connection in the pool."""

    def __init__(self, uri: str, conn_id: int):
        self.uri = uri
        self.conn_id = conn_id
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.is_connected: bool = False
        self.is_healthy: bool = True
        self.created_at: Optional[float] = None
        self.last_used: Optional[float] = None
        self.pending_calls: int = 0
        self._recv_task: Optional[asyncio.Task] = None
        self._pending: Dict[int, asyncio.Future] = {}
        self._id_counter: int = 1
        self._lock = asyncio.Lock()

    async def connect(self) -> bool:
        """Connect to WebSocket server."""
        try:
            self.ws = await websockets.connect(
                self.uri,
                ping_interval=20.0,
                ping_timeout=10.0,
            )
            self.is_connected = True
            self.is_healthy = True
            self.created_at = asyncio.get_running_loop().time()
            self.last_used = self.created_at
            self._recv_task = asyncio.create_task(self._recv_loop())
            return True
        except Exception:
            self.is_connected = False
            self.is_healthy = False
            return False

    async def close(self) -> None:
        """Close connection."""
        if self._recv_task:
            self._recv_task.cancel()
            self._recv_task = None
        if self.ws:
            await self.ws.close()
            self.ws = None
        self.is_connected = False
        self.is_healthy = False

    async def call(self, method: str, params: Optional[Dict[str, Any]] = None,
                   timeout: float = 60.0) -> Any:
        """Make RPC call on this connection."""
        if not self.is_connected or not self.ws:
            raise ConnectionError(f"Connection {self.conn_id} not connected")

        self.pending_calls += 1
        try:
            async with self._lock:
                request_id = self._id_counter
                self._id_counter += 1

                fut = asyncio.get_event_loop().create_future()
                self._pending[request_id] = fut

                req = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "method": method,
                    "params": params or {},
                }
                await self.ws.send(json.dumps(req))
                self.last_used = asyncio.get_running_loop().time()

            resp = await asyncio.wait_for(fut, timeout=timeout)
            return resp
        finally:
            self.pending_calls -= 1
            self._pending.pop(request_id, None)

    async def _recv_loop(self) -> None:
        """Background receive loop."""
        try:
            async for msg in self.ws:
                try:
                    data = json.loads(msg)
                except json.JSONDecodeError:
                    continue

                request_id = data.get("id")
                fut = self._pending.get(request_id)
                if not fut:
                    continue

                if "error" in data:
                    err = data["error"] or {}
                    fut.set_exception(Exception(
                        f"JSON-RPC error: {err.get('message', 'unknown')}"
                    ))
                else:
                    fut.set_result(data.get("result"))
        except asyncio.CancelledError:
            pass
        except Exception:
            # Mark unhealthy on error
            self.is_healthy = False
            for fut in self._pending.values():
                if not fut.done():
                    fut.set_exception(ConnectionError("Connection lost"))

    async def health_check(self) -> bool:
        """Check connection health."""
        if not self.is_connected:
            return False
        try:
            # Simple ping call (list_skills is lightweight)
            await self.call("vbf.list_skills", {}, timeout=5.0)
            return True
        except Exception:
            self.is_healthy = False
            return False


class ConnectionPool:
    """WebSocket connection pool for concurrent RPC.

    Features:
    - Manages multiple persistent connections
    - Automatic load balancing across connections
    - Health monitoring and automatic reconnection
    - Idle connection cleanup
    """

    def __init__(self, uri: str, config: Optional[ConnectionPoolConfig] = None):
        self.uri = uri
        self.config = config or ConnectionPoolConfig()
        self._connections: List[PooledConnection] = []
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._lock = asyncio.Lock()
        self._health_task: Optional[asyncio.Task] = None
        self._closed = False

    async def initialize(self) -> None:
        """Initialize pool with minimum connections."""
        self._semaphore = asyncio.Semaphore(self.config.max_connections)

        # Create minimum connections
        for i in range(self.config.min_connections):
            conn = PooledConnection(self.uri, i)
            if await conn.connect():
                self._connections.append(conn)

        if len(self._connections) < self.config.min_connections:
            raise ConnectionError(
                f"Failed to create minimum {self.config.min_connections} connections"
            )

        # Start health check loop
        self._health_task = asyncio.create_task(self._health_loop())

    async def _health_loop(self) -> None:
        """Periodic health check and reconnection."""
        while not self._closed:
            await asyncio.sleep(self.config.health_check_interval)

            if self._closed:
                break

            async with self._lock:
                # Check each connection
                unhealthy = []
                for conn in self._connections:
                    if not conn.is_healthy or not await conn.health_check():
                        unhealthy.append(conn)

                # Replace unhealthy connections
                for conn in unhealthy:
                    await conn.close()
                    self._connections.remove(conn)

                    # Create new connection
                    new_conn = PooledConnection(self.uri, conn.conn_id)
                    if await new_conn.connect():
                        self._connections.append(new_conn)

                # Ensure minimum connections
                while len(self._connections) < self.config.min_connections:
                    new_id = max([c.conn_id for c in self._connections], default=-1) + 1
                    new_conn = PooledConnection(self.uri, new_id)
                    if await new_conn.connect():
                        self._connections.append(new_conn)

    def _get_connection(self) -> PooledConnection:
        """Get least-loaded connection for load balancing."""
        if not self._connections:
            raise ConnectionError("No connections available")

        # Find connection with minimum pending calls
        healthy = [c for c in self._connections if c.is_healthy]
        if not healthy:
            raise ConnectionError("No healthy connections")

        return min(healthy, key=lambda c: c.pending_calls)

    async def call(self, method: str, params: Optional[Dict[str, Any]] = None,
                   timeout: float = 60.0) -> Any:
        """Make RPC call through pooled connection."""
        if self._closed:
            raise ConnectionError("Pool is closed")

        async with self._semaphore:
            conn = self._get_connection()
            return await conn.call(method, params, timeout)

    async def call_batch(self, calls: List[tuple]) -> List[Any]:
        """Execute multiple calls in parallel.

        Args:
            calls: List of (method, params, timeout) tuples

        Returns:
            List of results in same order
        """
        if self._closed:
            raise ConnectionError("Pool is closed")

        tasks = []
        for method, params, *rest in calls:
            timeout = rest[0] if rest else 60.0
            tasks.append(self.call(method, params, timeout))

        return await asyncio.gather(*tasks, return_exceptions=True)

    async def close(self) -> None:
        """Close all connections."""
        self._closed = True

        if self._health_task:
            self._health_task.cancel()
            try:
                await self._health_task
            except asyncio.CancelledError:
                pass

        async with self._lock:
            await asyncio.gather(*[
                conn.close() for conn in self._connections
            ])
            self._connections.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics."""
        return {
            "total_connections": len(self._connections),
            "healthy_connections": sum(1 for c in self._connections if c.is_healthy),
            "busy_connections": sum(1 for c in self._connections if c.pending_calls > 0),
            "total_pending_calls": sum(c.pending_calls for c in self._connections),
        }


# Global pool instance
_global_pool: Optional[ConnectionPool] = None


async def get_pool(uri: str, config: Optional[ConnectionPoolConfig] = None) -> ConnectionPool:
    """Get or create connection pool singleton."""
    global _global_pool
    if _global_pool is None:
        _global_pool = ConnectionPool(uri, config)
        await _global_pool.initialize()
    return _global_pool


async def close_pool() -> None:
    """Close global pool."""
    global _global_pool
    if _global_pool:
        await _global_pool.close()
        _global_pool = None
