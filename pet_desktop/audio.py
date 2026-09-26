# -*- coding: utf-8 -*-
"""提示音：程序内生成 WAV（正弦波 + 指数包络），winsound 异步播放，无需外部素材"""
from __future__ import annotations

import math
import struct
import sys
import wave
from pathlib import Path

from .config import ASSET_DIR

# 每种音效的音符序列（频率 Hz），短促悦耳
SOUNDS = {
    "eat":   [523.25, 659.25, 783.99],                              # 叮咚上扬
    "pet":   [783.99, 1046.50],                                     # 轻快两声
    "sleep": [392.00, 261.63],                                      # 舒缓下行
    "play":  [659.25, 783.99, 1046.50, 1318.51],                    # 快速上行
}
NOTE_DUR = 0.14    # 每个音符时长(秒)
RATE = 44100       # 采样率
VOL = 0.32         # 音量


def _generate_wav(path: Path, notes: list):
    """生成一段悦耳的合成音 WAV（单声道 16bit）"""
    total = int(RATE * (NOTE_DUR * len(notes) + 0.08))
    frames = bytearray()
    for i in range(total):
        t = i / RATE
        s = 0.0
        for j, f in enumerate(notes):
            t0 = j * NOTE_DUR
            if t0 <= t < t0 + NOTE_DUR:
                tt = t - t0
                attack = min(1.0, tt / 0.008)        # 短促起音，防爆音
                env = attack * math.exp(-9.0 * tt)   # 指数衰减包络
                s += math.sin(2 * math.pi * f * tt) * env
        s = max(-1.0, min(1.0, s * VOL))
        frames += struct.pack("<h", int(s * 32767))
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(bytes(frames))


def _ensure_wav(kind: str) -> Path:
    """确保音效文件存在（首次运行时生成，之后直接复用）"""
    path = ASSET_DIR / f"{kind}.wav"
    if path.exists() and path.stat().st_size > 1000:
        return path
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    _generate_wav(path, SOUNDS[kind])
    return path


def play_sound(kind: str):
    if sys.platform != "win32":
        return
    try:
        import winsound
    except Exception:
        return
    try:
        path = _ensure_wav(kind)
        winsound.PlaySound(str(path),
                           winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
    except Exception:
        pass
