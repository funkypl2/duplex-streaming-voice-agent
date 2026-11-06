"""
Unit tests for Full-Duplex Voice Agent System.
"""
import os
import sys

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import pytest
import asyncio
import numpy as np
from frontend.denoiser import FrontendAudioDenoiser
from frontend.vad_turn_detector import SemanticVADTurnDetector, TurnAction
from agent.tools import ToolRegistry
from agent.react_engine import VoiceReActAgent
from tts.streaming_tts import PrebufferedStreamingTTS
from tts.audio_player import DualChannelAudioPlayer
from core.state_machine import AgentDuplexStateMachine, AgentDuplexState
from core.barge_in_arbiter import BargeInArbiter
from core.duplex_orchestrator import FullDuplexAgentOrchestrator


def test_frontend_denoiser():
    denoiser = FrontendAudioDenoiser(sample_rate=16000)
    noisy = (0.2 * np.sin(np.linspace(0, 10, 1600)) + 0.1 * np.random.randn(1600)).astype(np.float32)
    cleaned = denoiser.process_chunk(noisy, is_speech=False)
    assert len(cleaned) > 0


def test_vad_turn_detector():
    vad = SemanticVADTurnDetector(sample_rate=16000, energy_threshold=0.01)
    silence = np.zeros(1600, dtype=np.float32)
    is_speaking, action = vad.process_chunk(silence)
    assert not is_speaking
    assert action == TurnAction.SILENCE

    speech = (0.3 * np.sin(np.linspace(0, 50, 1600))).astype(np.float32)
    is_speaking2, action2 = vad.process_chunk(speech)
    assert is_speaking2 is True
    assert action2 == TurnAction.USER_SPEAKING


def test_agent_tool_registry():
    registry = ToolRegistry()
    res = registry.dispatch("get_weather", city="上海")
    assert "上海" in res
    assert "气温" in res


def test_streaming_tts_and_player():
    async def _test():
        tts = PrebufferedStreamingTTS()
        player = DualChannelAudioPlayer()
        cancel_event = asyncio.Event()

        async def token_gen():
            for t in ["北京", "今天", "天气", "晴朗，", "适合", "出门。"]:
                yield t

        chunks = []
        async for clause, audio in tts.stream_synthesize_tokens(token_gen(), cancel_event):
            chunks.append(clause)
            await player.enqueue_audio(audio)

        assert len(chunks) >= 1
        assert not player.is_empty()
        dropped = player.flush_instant()
        assert dropped == len(chunks)
        assert player.is_empty()

    asyncio.run(_test())


def test_barge_in_arbiter():
    async def _test():
        fsm = AgentDuplexStateMachine()
        cancel_event = asyncio.Event()
        flushed = []

        def flush_fn():
            flushed.append(True)
            return 2

        arbiter = BargeInArbiter(
            state_machine=fsm,
            cancel_event=cancel_event,
            flush_audio_fn=flush_fn,
        )

        fsm.transition(AgentDuplexState.AGENT_SPEAKING)
        assert not cancel_event.is_set()

        # User speaks while agent speaking
        interrupted = arbiter.inspect_incoming_speech(user_speaking=True)
        assert interrupted is True
        assert cancel_event.is_set()
        assert len(flushed) == 1
        assert arbiter.total_interruptions == 1
        assert fsm.current_state == AgentDuplexState.LISTENING

    asyncio.run(_test())



def test_orchestrator_turn_cycle():
    async def _test():
        orch = FullDuplexAgentOrchestrator()
        speech_chunk = (0.3 * np.sin(np.linspace(0, 50, 1600))).astype(np.float32)
        await orch.feed_audio_chunk(speech_chunk)
        assert orch.state_machine.current_state == AgentDuplexState.LISTENING

    asyncio.run(_test())
