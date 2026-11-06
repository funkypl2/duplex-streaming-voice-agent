"""
Full-Duplex Streaming Voice Interaction Agent Orchestrator.
Integrates Frontend Denoising, Semantic VAD, Incremental ASR, ReAct Agent, and Pre-buffered TTS.
"""
from __future__ import annotations
import asyncio
import time
import numpy as np
from typing import Callable, Optional, Dict, Any, List

from frontend.denoiser import FrontendAudioDenoiser
from frontend.vad_turn_detector import SemanticVADTurnDetector, TurnAction
from asr.streaming_asr import StreamingIncrementalASR
from agent.react_engine import VoiceReActAgent
from tts.streaming_tts import PrebufferedStreamingTTS
from tts.audio_player import DualChannelAudioPlayer
from core.state_machine import AgentDuplexStateMachine, AgentDuplexState
from core.barge_in_arbiter import BargeInArbiter


class FullDuplexAgentOrchestrator:
    """
    Central Coordinator managing dual-channel full-duplex conversational pipeline.
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        on_log: Optional[Callable[[str], None]] = None,
        on_audio_out: Optional[Callable[[bytes], None]] = None,
    ):
        self.sample_rate = sample_rate
        self.on_log = on_log or (lambda msg: None)
        self.on_audio_out = on_audio_out or (lambda data: None)

        # Core Components
        self.denoiser = FrontendAudioDenoiser(sample_rate=sample_rate)
        self.vad = SemanticVADTurnDetector(sample_rate=sample_rate)
        self.asr = StreamingIncrementalASR(sample_rate=sample_rate)
        self.agent = VoiceReActAgent()
        self.tts = PrebufferedStreamingTTS(sample_rate=sample_rate)
        self.audio_player = DualChannelAudioPlayer()

        self.cancel_event = asyncio.Event()
        self.state_machine = AgentDuplexStateMachine(on_change=self._on_state_change)
        self.arbiter = BargeInArbiter(
            state_machine=self.state_machine,
            cancel_event=self.cancel_event,
            flush_audio_fn=self.audio_player.flush_instant,
            on_barge_in=self._on_barge_in_triggered,
        )

        self._active_gen_task: Optional[asyncio.Task] = None
        self.metrics = {
            "total_turns": 0,
            "last_ttfa_ms": 0.0,
            "barge_in_count": 0,
        }

    def _log(self, text: str):
        self.on_log(text)

    def _on_state_change(self, old_state: AgentDuplexState, new_state: AgentDuplexState, reason: str):
        self._log(f"[FSM] {old_state.value} -> {new_state.value} ({reason})")

    def _on_barge_in_triggered(self, latency_ms: float):
        self.metrics["barge_in_count"] += 1
        self._log(f"[Arbiter] *** BARGE-IN TRIGGERED in {latency_ms:.2f}ms! Interruption #{self.arbiter.total_interruptions} ***")

    async def feed_audio_chunk(self, raw_chunk: np.ndarray):
        """
        Input channel: processes continuous microphone audio chunk (e.g. 50ms ~ 100ms).
        """
        # 1. Frontend Real-time Denoising
        denoised = self.denoiser.process_chunk(raw_chunk, is_speech=self.vad.is_speech_active)

        # 2. Semantic VAD & Turn-taking detection
        is_speaking, turn_action = self.vad.process_chunk(denoised)

        # 3. Millisecond-level Barge-in Check
        if is_speaking:
            interrupted = self.arbiter.inspect_incoming_speech(user_speaking=True)
            if not interrupted and self.state_machine.current_state in (AgentDuplexState.IDLE, AgentDuplexState.THINKING_PAUSE):
                self.state_machine.transition(AgentDuplexState.LISTENING, reason="User speaking started")

        # 4. Incremental ASR Processing
        if turn_action in (TurnAction.USER_SPEAKING, TurnAction.THINKING_PAUSE):
            delta, full_text = self.asr.process_chunk(denoised, is_speaking=is_speaking)
            if delta:
                self._log(f"[ASR Partial]: '{full_text}'")

        elif turn_action == TurnAction.TURN_FINISHED:
            final_user_text = self.asr.finalize()
            self._log(f"[User Turn Concluded]: '{final_user_text}'")
            # Trigger Agent reasoning and streaming response pipeline
            await self._dispatch_agent_turn(final_user_text)

    async def _dispatch_agent_turn(self, user_query: str):
        """Dispatches Agent reasoning and begins pre-buffered streaming synthesis."""
        self.metrics["total_turns"] += 1
        # Clear cancellation token
        self.cancel_event.clear()

        # State transition to AGENT_REASONING
        self.state_machine.transition(AgentDuplexState.AGENT_REASONING, reason="Starting ReAct pipeline")

        # Cancel any previous task
        if self._active_gen_task and not self._active_gen_task.done():
            self._active_gen_task.cancel()

        self._active_gen_task = asyncio.create_task(self._run_agent_pipeline(user_query))

    async def _run_agent_pipeline(self, user_query: str):
        t_start = time.time()
        first_audio_sent = False

        # Stream tokens from Agent
        token_stream = self.agent.stream_reason_and_respond(user_query, self.cancel_event)

        # Stream synthesizes into clauses with pre-buffering
        async for clause, audio_data in self.tts.stream_synthesize_tokens(token_stream, self.cancel_event):
            if self.cancel_event.is_set():
                break

            if not first_audio_sent:
                ttfa_ms = (time.time() - t_start) * 1000.0
                self.metrics["last_ttfa_ms"] = ttfa_ms
                first_audio_sent = True
                self.state_machine.transition(AgentDuplexState.AGENT_SPEAKING, reason=f"First clause ready (TTFA: {ttfa_ms:.1f}ms)")

            self._log(f"[Agent Speaking]: '{clause}'")
            await self.audio_player.enqueue_audio(audio_data)
            self.on_audio_out(audio_data)

        # Wait until playback queue drains or is interrupted
        while not self.audio_player.is_empty():
            if self.cancel_event.is_set():
                break
            await asyncio.sleep(0.04)

        if not self.cancel_event.is_set():
            self.state_machine.transition(AgentDuplexState.IDLE, reason="Agent finished speaking")
            self._log("[Agent] Dialogue cycle complete. Standing by.")
