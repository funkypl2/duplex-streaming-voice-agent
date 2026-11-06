"""
Full-Duplex Multi-State Finite State Machine (FSM).
"""
from __future__ import annotations
from enum import Enum
from typing import Callable, Optional, List
import time


class AgentDuplexState(str, Enum):
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    THINKING_PAUSE = "THINKING_PAUSE"
    AGENT_REASONING = "AGENT_REASONING"
    AGENT_SPEAKING = "AGENT_SPEAKING"
    BARGE_IN_TRIGGERED = "BARGE_IN_TRIGGERED"


class AgentDuplexStateMachine:
    """Finite State Machine tracking full-duplex conversational status."""

    def __init__(self, on_change: Optional[Callable[[AgentDuplexState, AgentDuplexState, str], None]] = None):
        self._state = AgentDuplexState.IDLE
        self.on_change = on_change
        self.last_transition_time = time.time()
        self.transition_log: List[tuple[float, AgentDuplexState, str]] = []

    @property
    def current_state(self) -> AgentDuplexState:
        return self._state

    def transition(self, target: AgentDuplexState, reason: str = ""):
        if self._state == target:
            return
        old = self._state
        self._state = target
        now = time.time()
        self.last_transition_time = now
        self.transition_log.append((now, target, reason))
        if self.on_change:
            self.on_change(old, target, reason)

    def is_agent_speaking(self) -> bool:
        return self._state == AgentDuplexState.AGENT_SPEAKING

    def is_user_speaking(self) -> bool:
        return self._state in (AgentDuplexState.LISTENING, AgentDuplexState.BARGE_IN_TRIGGERED)
