"""
Frontend Audio Processing: Real-Time Spectral Denoising & Automatic Gain Control (AGC).
"""
from __future__ import annotations
import numpy as np


class FrontendAudioDenoiser:
    """
    Frame-based streaming audio denoiser with adaptive noise floor tracking and AGC.
    Sample Rate: 16000Hz, Frame Size: 512, Hop Size: 256.
    """

    def __init__(self, sample_rate: int = 16000, n_fft: int = 512, hop_length: int = 256):
        self.sample_rate = sample_rate
        self.n_fft = n_fft
        self.hop_length = hop_length
        self.window = np.hanning(n_fft)
        self.noise_floor = np.full(n_fft // 2 + 1, 1e-4, dtype=np.float32)
        self.noise_update_alpha = 0.95
        self.remnant = np.array([], dtype=np.float32)

    def process_frame(self, frame: np.ndarray, is_speech: bool = False) -> np.ndarray:
        """Process a single 512-sample frame with spectral subtraction."""
        if len(frame) < self.n_fft:
            frame = np.pad(frame, (0, self.n_fft - len(frame)))

        win_frame = frame * self.window
        spec = np.fft.rfft(win_frame)
        mag = np.abs(spec)
        phase = np.angle(spec)

        # Update noise floor during non-speech intervals
        if not is_speech:
            self.noise_floor = self.noise_update_alpha * self.noise_floor + (1 - self.noise_update_alpha) * mag

        # Spectral subtraction with noise floor safeguard
        alpha = 1.3
        clean_mag = np.maximum(mag - alpha * self.noise_floor, 0.08 * mag)
        clean_spec = clean_mag * np.exp(1j * phase)

        # IFFT back to time domain
        enhanced_time = np.fft.irfft(clean_spec) * self.window
        return enhanced_time.astype(np.float32)

    def process_chunk(self, chunk: np.ndarray, is_speech: bool = False) -> np.ndarray:
        """Processes continuous audio chunk with overlap-add."""
        combined = np.concatenate([self.remnant, chunk])
        if len(combined) < self.n_fft:
            self.remnant = combined
            return chunk

        out = np.zeros(len(combined), dtype=np.float32)
        win_sum = np.zeros(len(combined), dtype=np.float32)

        for i in range(0, len(combined) - self.n_fft, self.hop_length):
            frame = combined[i : i + self.n_fft]
            clean_frame = self.process_frame(frame, is_speech=is_speech)
            out[i : i + self.n_fft] += clean_frame
            win_sum[i : i + self.n_fft] += self.window ** 2

        mask = win_sum > 1e-4
        out[mask] = out[mask] / win_sum[mask]

        consumed = ((len(combined) - self.n_fft) // self.hop_length) * self.hop_length
        self.remnant = combined[consumed:]
        # Automatic Gain Control (AGC) clamp
        max_val = np.max(np.abs(out[:consumed])) if consumed > 0 else 1.0
        if max_val > 0.01:
            gain = min(1.5, 0.6 / max_val)
            out[:consumed] *= gain

        return out[:consumed].astype(np.float32) if consumed > 0 else np.array([], dtype=np.float32)
