# -*- coding: utf-8 -*-
"""TTS 语音播放：edge-tts 合成（后台线程）+ Qt 播放，用于桌宠口型同步。

语音参数（voice/rate/pitch/volume）可配置，由外部传入 tts 字典。
结束时机优先用「真实播放结束」(EndOfMedia) + 真实时长(duration)，两者都拿不到时
才用文本长度估算兜底，确保口型/字幕跟语音一起结束，不提前消失。
"""
from __future__ import annotations

import asyncio
import hashlib
import tempfile
import threading
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, QUrl, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

DEFAULT_TTS = {
    "voice": "zh-CN-XiaoyiNeural",
    "rate": "+5%",
    "pitch": "-5Hz",
    "volume": "+30%",
}


def _synth_async(text: str, voice: str, rate: str, pitch: str, volume: str, out_file: str) -> None:
    import edge_tts

    async def _run():
        communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch, volume=volume)
        await communicate.save(out_file)

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_run())
    finally:
        loop.close()


def _hash(text: str, voice: str, rate: str, pitch: str, volume: str) -> str:
    return hashlib.md5(f"{voice}|{rate}|{pitch}|{volume}|{text}".encode("utf-8")).hexdigest()


class SpeechPlayer(QObject):
    """合成并播放一段语音；started/finished 信号用于驱动口型动画。"""

    started = Signal()
    finished = Signal()
    _ready = Signal(str, str)  # (mp3 路径, 原文)

    def __init__(self, cache_dir=None, tts=None, parent=None):
        super().__init__(parent)
        self.cache_dir = Path(cache_dir) if cache_dir else (Path(tempfile.gettempdir()) / "dsh-pet-tts")
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        self.tts = dict(DEFAULT_TTS)
        if isinstance(tts, dict):
            self.tts.update(tts)
        self._player = QMediaPlayer()
        self._audio = QAudioOutput()
        self._player.setAudioOutput(self._audio)
        self._player.mediaStatusChanged.connect(self._on_status)
        self._player.durationChanged.connect(self._on_duration)
        self._stop_timer = QTimer(self)
        self._stop_timer.setSingleShot(True)
        self._stop_timer.timeout.connect(self._on_timeout)
        self._done = False
        self._ready.connect(self._play)

    def speak(self, text: str) -> None:
        text = (text or "").strip()
        if not text:
            return
        threading.Thread(target=self._synth_worker, args=(text,), daemon=True).start()

    def _synth_worker(self, text: str) -> None:
        mp3 = self._synth(text)
        if mp3:
            self._ready.emit(str(mp3), text)

    def _play(self, mp3: str, text: str) -> None:
        self._done = False
        self._player.setSource(QUrl.fromLocalFile(mp3))
        self._player.play()
        self.started.emit()
        # 兜底：估算时长（偏长，防止提前结束）
        est_ms = max(4000, int(len(text) * 300) + 2000)
        self._stop_timer.start(est_ms)

    def _on_duration(self, dur: int) -> None:
        # 拿到真实时长（合理值）就更新定时器，加 300ms 余量
        if dur > 500 and not self._done:
            self._stop_timer.start(dur + 300)

    def _on_status(self, status) -> None:
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self._finish()

    def _on_timeout(self) -> None:
        self._finish()

    def _finish(self) -> None:
        if self._done:
            return
        self._done = True
        try:
            self._player.stop()
        except Exception:
            pass
        self.finished.emit()

    def _synth(self, text: str):
        voice = str(self.tts.get("voice", DEFAULT_TTS["voice"]))
        rate = str(self.tts.get("rate", DEFAULT_TTS["rate"]))
        pitch = str(self.tts.get("pitch", DEFAULT_TTS["pitch"]))
        volume = str(self.tts.get("volume", DEFAULT_TTS["volume"]))
        name = _hash(text, voice, rate, pitch, volume) + ".mp3"
        path = self.cache_dir / name
        if path.exists() and path.stat().st_size > 500:
            return path
        try:
            _synth_async(text, voice, rate, pitch, volume, str(path))
            if path.exists() and path.stat().st_size > 500:
                return path
        except Exception:
            return None
        return None

    def stop(self) -> None:
        try:
            self._player.stop()
        except Exception:
            pass
