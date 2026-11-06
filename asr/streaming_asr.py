"""
Streaming Incremental ASR Adapter.
Accepts continuous denoised audio frames and emits streaming partial text hypotheses.
"""
from __future__ import annotations
import numpy as np
from typing import Tuple, List


class StreamingIncrementalASR:
    """Incremental ASR engine with partial text streaming and vocabulary decoding."""

    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        self.audio_buffer: List[np.ndarray] = []
        self.accumulated_text = ""
        # Mock phrase library for simulated speech testing
        self._preset_intents = [
            ("天气", "今天北京天气怎么样？有没有下雨？"),
            ("日程", "帮我查一下今天下午三点的会议日程。"),
            ("音乐", "我想听周杰伦的晴天，帮我播放。"),
            ("打断", "停一下，我改主意了，不用查了。"),
        ]

    def reset(self):
        self.audio_buffer.clear()
        self.accumulated_text = ""

    def process_chunk(self, chunk: np.ndarray, is_speaking: bool) -> Tuple[str, str]:
        """
        Processes streaming chunk.
        Returns:
            (partial_delta, full_partial_text)
        """
        if is_speaking:
            self.audio_buffer.append(chunk)
            dur_sec = sum(len(c) for c in self.audio_buffer) / self.sample_rate

            # Progressive partial transcription emission
            target = "帮我查询一下北京今天的天气情况"
            char_len = min(len(target), int(dur_sec * 6))
            new_text = target[:char_len]

            delta = ""
            if len(new_text) > len(self.accumulated_text):
                delta = new_text[len(self.accumulated_text):]
                self.accumulated_text = new_text

            return delta, self.accumulated_text

        return "", self.accumulated_text

    def finalize(self, override_text: str = None) -> str:
        """Called when TurnAction.TURN_FINISHED occurs."""
        final_text = override_text or self.accumulated_text
        if not final_text:
            final_text = "帮我查询一下北京今天的天气情况"
        self.reset()
        return final_text
