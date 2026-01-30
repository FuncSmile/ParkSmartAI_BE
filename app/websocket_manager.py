from __future__ import annotations

import asyncio
from typing import Set
from fastapi import WebSocket


class ConnectionManager:
    def __init__(self, max_queue: int = 100):
        self.active_connections: Set[WebSocket] = set()
        self.queue = asyncio.Queue(maxsize=max_queue)
        self._broadcast_task: asyncio.Task | None = None

    async def start(self):
        if self._broadcast_task is None:
            self._broadcast_task = asyncio.create_task(self._broadcast_loop())

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)

    async def send_json(self, data):
        try:
            self.queue.put_nowait(data)
        except asyncio.QueueFull:
            # drop oldest to avoid blocking
            _ = self.queue.get_nowait()
            self.queue.put_nowait(data)

    async def _broadcast_loop(self):
        while True:
            data = await self.queue.get()
            stale = []
            for conn in list(self.active_connections):
                try:
                    await conn.send_json(data)
                except Exception:
                    stale.append(conn)
            for conn in stale:
                self.disconnect(conn)
