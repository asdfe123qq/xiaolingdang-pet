# -*- coding: utf-8 -*-
"""语音与情绪映射设置对话框（界面从简，功能可用即可）。"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit, QVBoxLayout,
)

from .config import DEFAULT_EMOTION_ANIMS, DEFAULT_TTS

# 常用 edge-tts 中文语音（可自行改成别的合法 voice id）
VOICE_OPTIONS = [
    "zh-CN-XiaoyiNeural",
    "zh-CN-XiaoxiaoNeural",
    "zh-CN-YunxiNeural",
    "zh-CN-YunjianNeural",
    "zh-CN-XiaoyouNeural",
    "zh-CN-liaoning-XiaobeiNeural",
    "zh-CN-shaanxi-XiaoniNeural",
]

EMOTION_KEYS = ["开心", "生气", "惊讶", "害羞", "难过", "思考", "平静"]


class VoiceSettingsDialog(QDialog):
    """语音参数 + 情绪→动画 映射设置。"""

    settings_saved = Signal()

    def __init__(self, config, anim_names, parent=None):
        super().__init__(parent)
        self.config = config
        self.anim_names = list(anim_names)
        self.setWindowTitle("语音与情绪设置")
        self.setMinimumWidth(460)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 16)
        root.setSpacing(10)

        root.addWidget(QLabel("语音设置（voice / rate / pitch / volume）"))
        form = QFormLayout()
        tts = dict(DEFAULT_TTS)
        tts.update(config.get("tts") or {})

        self.voice = QComboBox()
        self.voice.setEditable(True)
        self.voice.addItems(VOICE_OPTIONS)
        if tts.get("voice"):
            self.voice.setCurrentText(str(tts["voice"]))
        form.addRow("语音", self.voice)

        self.rate = QLineEdit(str(tts.get("rate", "+5%")))
        self.pitch = QLineEdit(str(tts.get("pitch", "-5Hz")))
        self.volume = QLineEdit(str(tts.get("volume", "+30%")))
        form.addRow("语速", self.rate)
        form.addRow("音调", self.pitch)
        form.addRow("音量", self.volume)
        root.addLayout(form)

        root.addWidget(QLabel("情绪 → 动画 映射（从下拉框选动画）"))
        emap = dict(DEFAULT_EMOTION_ANIMS)
        emap.update(config.get("emotion_anims") or {})
        eform = QFormLayout()
        self.emotion_combos = {}
        for key in EMOTION_KEYS:
            combo = QComboBox()
            combo.addItems(self.anim_names)
            if emap.get(key) in self.anim_names:
                combo.setCurrentText(emap[key])
            eform.addRow(key, combo)
            self.emotion_combos[key] = combo
        root.addLayout(eform)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self._save)
        self.buttons.rejected.connect(self.reject)
        root.addWidget(self.buttons)

    def _save(self) -> None:
        tts = {
            "voice": self.voice.currentText().strip(),
            "rate": self.rate.text().strip(),
            "pitch": self.pitch.text().strip(),
            "volume": self.volume.text().strip(),
        }
        self.config.set("tts", tts)
        emap = {key: combo.currentText() for key, combo in self.emotion_combos.items()}
        self.config.set("emotion_anims", emap)
        self.config.save()
        self.settings_saved.emit()
        self.accept()
