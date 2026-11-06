"""
Millisecond-Level Barge-In (Real-Time Interruption) Arbiter.
Coordinates cancellation of running Agent reasoning tasks and instantaneous audio buffer draining.
"""
from __future__ import annotations
import asyncio
import time
from typing import Callable, Optional
from core.state_machine import AgentDuplexStateMachine, AgentDuplexState


class BargeInArbiter:
    """Arbiter managing real-time speech collision and turn preemptions."""

    def __init__(
        self,
        state_machine: AgentDuplexStateMachine,
        cancel_event: asyncio.Event,
        flush_audio_fn: Callable[[], int],
        on_barge_in: Optional[Callable[[float], None]] = None,
    ):
        self.state_machine = state_machine
        self.cancel_event = cancel_event
        self.flush_audio_fn = flush_audio_fn
        self.on_barge_in = on_barge_in
        self.total_interruptions = 0
        self.last_interruption_timestamp = 0.0

    def inspect_incoming_speech(self, user_speaking: bool) -> bool:
        """
        Called on every audio frame.
        If user speaks while Agent is speaking or reasoning, trigger instant barge-in.
        """
        if not user_speaking:
            return False

        if self.state_machine.is_agent_speaking() or self.state_machine.current_state == AgentDuplexState.AGENT_REASONING:
            self.execute_barge_in()
            return True
        return False

    def execute_barge_in(self) -> float:
        """Executes instant interruption protocol. Returns response latency in ms."""
        t0 = time.time()
        self.total_interruptions += 1
        self.last_interruption_timestamp = t0

        # 1. Trigger cooperative cancellation token for Agent generator
        self.cancel_event.set()

        # 2. Flush playback audio buffer immediately
        dropped = self.flush_audio_fn()

        # 3. Transition state machine
        self.state_machine.transition(AgentDuplexState.BARGE_IN_TRIGGERED, reason=f"User Barge-In ({dropped} audio chunks dropped)")
        self.state_machine.transition(AgentDuplexState.LISTENING, reason="Capturing new user speech")

        latency_ms = (time.time() - t0) * 1000.0

        if self.on_barge_in:
            self.on_barge_in(latency_ms)

        return latency_ms
