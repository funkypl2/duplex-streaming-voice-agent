"""
Dual-Channel Audio Playback Ring Buffer with sub-50ms Instant Flush on Barge-In.
"""
from __future__ import annotations
import asyncio
from typing import Optional


class DualChannelAudioPlayer:
    """Manages audio playback queue with millisecond-level buffer dump capability."""

    def __init__(self, maxsize: int = 50):
        self._queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=maxsize)
        self.total_chunks_played = 0
        self.total_chunks_dropped = 0

    async def enqueue_audio(self, audio_bytes: bytes) -> None:
        await self._queue.put(audio_bytes)

    async def dequeue_audio(self) -> bytes:
        chunk = await self._queue.get()
        self.total_chunks_played += 1
        return chunk

    def task_done(self) -> None:
        self._queue.task_done()

    def is_empty(self) -> bool:
        return self._queue.empty()

    def flush_instant(self) -> int:
        """
        Instantly dump all buffered audio chunks upon user interruption (Barge-In).
        Returns number of dropped chunks.
        """
        dropped = 0
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
                self._queue.task_done()
                dropped += 1
            except (asyncio.QueueEmpty, ValueError):
                break
        self.total_chunks_dropped += dropped
        return dropped
