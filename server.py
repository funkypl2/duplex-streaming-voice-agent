"""
FastAPI & WebSocket Server Gateway for Full-Duplex Voice Agent.
"""
from __future__ import annotations
import os
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

import asyncio
import json
import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from core.duplex_orchestrator import FullDuplexAgentOrchestrator

app = FastAPI(title="Full-Duplex Voice Agent Gateway")


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "duplex-streaming-voice-agent",
        "features": ["dual-channel-audio", "barge-in", "react-tools", "streaming-tts"],
    }


@app.websocket("/ws/duplex_agent")
async def websocket_duplex_agent_endpoint(websocket: WebSocket):
    await websocket.accept()

    async def log_to_client(msg: str):
        try:
            await websocket.send_text(json.dumps({"type": "log", "message": msg}))
        except Exception:
            pass

    async def audio_out_to_client(audio_data: bytes):
        try:
            await websocket.send_bytes(audio_data)
        except Exception:
            pass

    orchestrator = FullDuplexAgentOrchestrator(
        sample_rate=16000,
        on_log=lambda m: asyncio.create_task(log_to_client(m)),
        on_audio_out=lambda b: asyncio.create_task(audio_out_to_client(b)),
    )

    await websocket.send_text(json.dumps({
        "type": "ready",
        "message": "Full-duplex streaming voice agent connected. Bi-directional audio enabled."
    }))

    try:
        while True:
            message = await websocket.receive()
            if "bytes" in message and message["bytes"]:
                # Raw PCM16 audio input from client
                pcm_bytes = message["bytes"]
                audio_np = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32767.0
                await orchestrator.feed_audio_chunk(audio_np)
            elif "text" in message and message["text"]:
                data = json.loads(message["text"])
                msg_type = data.get("type")
                if msg_type == "barge_in":
                    orchestrator.arbiter.execute_barge_in()
                elif msg_type == "text_query":
                    await orchestrator._dispatch_agent_turn(data.get("query", ""))
    except WebSocketDisconnect:
        orchestrator.cancel_event.set()
    except Exception:
        orchestrator.cancel_event.set()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8002, reload=True)
