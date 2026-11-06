"""
Semantic VAD & Conversational Turn-Taking Detector.
Differentiates between short 'Thinking Pauses' and complete 'End-of-Turn' speech conclusions.
"""
from __future__ import annotations
import numpy as np
from enum import Enum
from typing import Tuple


class TurnAction(str, Enum):
    SILENCE = "SILENCE"
    USER_SPEAKING = "USER_SPEAKING"
    THINKING_PAUSE = "THINKING_PAUSE"  # User paused mid-sentence, keep listening
    TURN_FINISHED = "TURN_FINISHED"    # True turn completion, hand off to Agent


class SemanticVADTurnDetector:
    """
    Dual-level Voice Activity Detector with turn-taking arbitration.
    - Fast frame energy: detects speech onset within 30ms (crucial for instant barge-in).
    - Trailing pause analysis: discriminates between micro-pauses (300-500ms) and turn-ends (>700ms).
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        energy_threshold: float = 0.015,
        thinking_pause_ms: int = 400,
        turn_end_ms: int = 700,
    ):
        self.sample_rate = sample_rate
        self.energy_threshold = energy_threshold
        self.thinking_pause_samples = int(sample_rate * (thinking_pause_ms / 1000.0))
        self.turn_end_samples = int(sample_rate * (turn_end_ms / 1000.0))

        self.is_speech_active = False
        self.consecutive_silence_samples = 0
        self.accumulated_speech_samples = 0

    def reset(self):
        self.is_speech_active = False
        self.consecutive_silence_samples = 0
        self.accumulated_speech_samples = 0

    def process_chunk(self, chunk: np.ndarray) -> Tuple[bool, TurnAction]:
        """
        Process incoming audio chunk.
        Returns:
            (is_instant_speaking, turn_action)
        """
        if len(chunk) == 0:
            return False, TurnAction.SILENCE

        # Calculate Root-Mean-Square (RMS) Energy
        rms = np.sqrt(np.mean(chunk.astype(np.float32) ** 2) + 1e-12)
        chunk_is_speech = bool(rms > self.energy_threshold)

        if chunk_is_speech:
            self.is_speech_active = True
            self.consecutive_silence_samples = 0
            self.accumulated_speech_samples += len(chunk)
            return True, TurnAction.USER_SPEAKING

        # Chunk is silent
        if self.is_speech_active:
            self.consecutive_silence_samples += len(chunk)

            if self.consecutive_silence_samples >= self.turn_end_samples:
                # Turn concluded!
                self.is_speech_active = False
                self.consecutive_silence_samples = 0
                return False, TurnAction.TURN_FINISHED
            elif self.consecutive_silence_samples >= self.thinking_pause_samples:
                return False, TurnAction.THINKING_PAUSE
            else:
                return False, TurnAction.USER_SPEAKING

        return False, TurnAction.SILENCE
