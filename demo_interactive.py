"""
Interactive Full-Duplex Voice Agent Demonstration.
Simulates real-time microphone stream, tool invocation, and mid-sentence Barge-In interruption.
"""
from __future__ import annotations
import os
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

import asyncio
import time
import numpy as np
from core.duplex_orchestrator import FullDuplexAgentOrchestrator
from core.state_machine import AgentDuplexState


async def simulate_speaking(orchestrator: FullDuplexAgentOrchestrator, duration_sec: float, chunk_ms: int = 50):
    """Simulates active speech audio frames."""
    sample_rate = 16000
    chunk_samples = int(sample_rate * (chunk_ms / 1000.0))
    n_chunks = int(duration_sec * 1000 / chunk_ms)

    for i in range(n_chunks):
        t = np.linspace(0, chunk_ms / 1000.0, chunk_samples, endpoint=False)
        # Synthetic speech signal (speech formants)
        speech_chunk = (0.25 * np.sin(2 * np.pi * 320.0 * t) + 0.05 * np.random.randn(chunk_samples)).astype(np.float32)
        await orchestrator.feed_audio_chunk(speech_chunk)
        await asyncio.sleep(0.02)


async def simulate_silence(orchestrator: FullDuplexAgentOrchestrator, duration_sec: float, chunk_ms: int = 50):
    """Simulates silence background frames."""
    sample_rate = 16000
    chunk_samples = int(sample_rate * (chunk_ms / 1000.0))
    n_chunks = int(duration_sec * 1000 / chunk_ms)

    for i in range(n_chunks):
        silence_chunk = (0.002 * np.random.randn(chunk_samples)).astype(np.float32)
        await orchestrator.feed_audio_chunk(silence_chunk)
        await asyncio.sleep(0.02)


async def run_demo():
    print("=================================================================")
    print("   全双工流式实时语音交互 Agent 系统 (Full-Duplex Voice Agent)  ")
    print("=================================================================")

    def log_handler(msg: str):
        print(f"[*] {msg}")

    orchestrator = FullDuplexAgentOrchestrator(sample_rate=16000, on_log=log_handler)

    print("\n[场景一：完整对话与工具调用闭环]")
    print(">>> 用户发声: '帮我查询一下北京今天的天气情况' (持续 1.2 秒)...")
    await simulate_speaking(orchestrator, duration_sec=1.2)

    print(">>> 用户停止说话，触发语义级 VAD 端点检测 (静音 800ms)...")
    await simulate_silence(orchestrator, duration_sec=0.8)

    # Let the agent finish speaking
    await asyncio.sleep(2.0)
    print(f"[*] 场景一完成，首包延迟 (TTFA): {orchestrator.metrics['last_ttfa_ms']:.1f}ms\n")

    print("-----------------------------------------------------------------")
    print("[场景二：毫秒级实时插话打断 (Barge-In) 演示]")
    print(">>> 用户发声: '请详细介绍一下全双工语音Agent的系统架构'...")
    await simulate_speaking(orchestrator, duration_sec=1.0)
    await simulate_silence(orchestrator, duration_sec=0.8)

    # Wait until Agent transitions to SPEAKING
    print("[*] 等待 Agent 开始说话并播放首句音频...")
    for _ in range(20):
        if orchestrator.state_machine.is_agent_speaking():
            break
        await asyncio.sleep(0.05)

    print(f"[*] 当前系统状态: {orchestrator.state_machine.current_state.value}")
    print(">>> 💥 用户在 Agent 说话过程中突然插话打断: '别说了，先帮我关闭空调！' 💥 <<<")

    t_barge_start = time.time()
    # User immediately begins speaking while agent is speaking
    await simulate_speaking(orchestrator, duration_sec=0.8)
    barge_latency = (time.time() - t_barge_start) * 1000.0

    print(f"[+] 实际打断生效延迟: {barge_latency:.1f}ms")
    print(f"[*] 播放缓冲区丢弃废弃音频块: {orchestrator.audio_player.total_chunks_dropped} 个")
    print(f"[*] 打断后系统状态: {orchestrator.state_machine.current_state.value}")

    # Silence ends the interrupting turn
    await simulate_silence(orchestrator, duration_sec=0.8)
    await asyncio.sleep(1.5)

    print("\n=================================================================")
    print("   全双工实时交互闭环演练顺利完成！                              ")
    print("=================================================================")


def main():
    asyncio.run(run_demo())


if __name__ == "__main__":
    main()
