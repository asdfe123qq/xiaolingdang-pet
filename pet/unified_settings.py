# -*- coding: utf-8 -*-
"""统一设置窗口：AI / 语音 / 情绪映射 都整合在一个窗口里（标签页）。"""
from __future__ import annotations

import threading

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout,
    QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QPushButton, QSpinBox, QTabWidget,
    QVBoxLayout, QWidget,
)

from . import catalog
from .config import DEFAULT_EMOTION_ANIMS, DEFAULT_TTS
from .chat.models import SecretStore
from .chat.providers import test_connection

VOICE_OPTIONS = [
    "zh-CN-XiaoyiNeural",
    "zh-CN-XiaoxiaoNeural",
    "zh-CN-YunxiNeural",
    "zh-CN-YunjianNeural",
    "zh-CN-XiaoyouNeural",
    "zh-CN-liaoning-XiaobeiNeural",
    "zh-CN-shaanxi-XiaoniNeural",
]

EMOTION_KEYS = ["开心", "生气", "惊讶", "害羞", "难过", "思考", "平静", "困", "惊喜", "傲娇"]


def _categorized_anims() -> dict[str, list[str]]:
    """按子目录（idle/turn/move/click/drag/random）分类返回动画名。"""
    cats: dict[str, list[str]] = {}
    try:
        video_dir = catalog.resolve_character_video_dir(catalog.DEFAULT_CHARACTER)
        for sub in sorted(video_dir.iterdir()):
            if sub.is_dir():
                names = sorted(p.stem for p in sub.glob("*.webm"))
                if names:
                    cats[sub.name] = names
    except Exception:
        pass
    return cats


def _grouped_combo(categories: dict[str, list[str]]) -> QComboBox:
    """下拉框里按大类分组（组标题不可选）。"""
    combo = QComboBox()
    model = QStandardItemModel()
    for cat, names in categories.items():
        header = QStandardItem(cat)
        header.setEnabled(False)
        header.setSelectable(False)
        header.setForeground(Qt.GlobalColor.gray)
        model.appendRow(header)
        for n in names:
            model.appendRow(QStandardItem(n))
    combo.setModel(model)
    return combo


class UnifiedSettingsDialog(QDialog):
    """统一设置：AI / 语音 / 情绪映射。"""

    settings_saved = Signal()
    _test_done = Signal(bool, str)

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.settings = config.chat_settings()
        self.categories = _categorized_anims()
        self._test_thread = None
        self._test_done.connect(self._on_test_done)

        self.setWindowTitle("小铃铛桌宠 · 设置")
        self.setMinimumWidth(520)

        tabs = QTabWidget()
        tabs.addTab(self._build_ai_tab(), "AI 模型")
        tabs.addTab(self._build_voice_tab(), "语音")
        tabs.addTab(self._build_emotion_tab(), "情绪表情")

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self._save)
        self.buttons.rejected.connect(self.reject)

        root = QVBoxLayout(self)
        root.addWidget(tabs)
        root.addWidget(self.buttons)

    # ------------------------------------------------------------ AI tab
    def _build_ai_tab(self) -> QWidget:
        w = QWidget()
        p = self.settings.active_config
        form = QFormLayout(w)
        self.ai_name = QLineEdit(p.name)
        self.ai_url = QLineEdit(p.base_url)
        self.ai_model = QLineEdit(p.model)
        self.ai_key = QLineEdit()
        self.ai_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.ai_prompt = QPlainTextEdit(self.settings.default_system_prompt)
        self.ai_prompt.setMinimumHeight(100)
        self.ai_temp = QDoubleSpinBox()
        self.ai_temp.setRange(0, 2)
        self.ai_temp.setSingleStep(0.1)
        self.ai_temp.setValue(p.temperature)
        self.ai_tokens = QSpinBox()
        self.ai_tokens.setRange(1, 32768)
        self.ai_tokens.setValue(p.max_tokens)
        self.ai_ssl = QCheckBox("跳过 SSL 证书验证")
        self.ai_ssl.setChecked(not p.verify_ssl)

        form.addRow("名称", self.ai_name)
        form.addRow("API 地址", self.ai_url)
        form.addRow("模型", self.ai_model)
        form.addRow("API Key", self.ai_key)
        form.addRow("System Prompt", self.ai_prompt)
        form.addRow("Temperature", self.ai_temp)
        form.addRow("Max Tokens", self.ai_tokens)
        form.addRow(self.ai_ssl)

        # 本地兜底模型（云端失败/断网时自动切本地，需装 Ollama）
        form.addRow(QLabel("—— 本地兜底（云端失败/断网自动切，需装 Ollama）——"))
        self.local_url = QLineEdit(str(self.config.get("local_base_url", "http://127.0.0.1:11434/v1")))
        self.local_model = QLineEdit(str(self.config.get("local_model", "qwen2.5:7b")))
        form.addRow("本地地址", self.local_url)
        form.addRow("本地模型", self.local_model)

        self.ai_result = QLabel("")
        self.ai_result.setWordWrap(True)
        self.ai_test = QPushButton("测试连接")
        self.ai_test.clicked.connect(self._run_test)
        btns = QHBoxLayout()
        btns.addWidget(self.ai_test)
        btns.addWidget(self.ai_result, 1)
        form.addRow(btns)
        return w

    # ------------------------------------------------------------ 语音 tab
    def _build_voice_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        tts = dict(DEFAULT_TTS)
        tts.update(self.config.get("tts") or {})
        self.tts_voice = QComboBox()
        self.tts_voice.setEditable(True)
        self.tts_voice.addItems(VOICE_OPTIONS)
        self.tts_voice.setCurrentText(str(tts.get("voice", DEFAULT_TTS["voice"])))
        self.tts_rate = QLineEdit(str(tts.get("rate", DEFAULT_TTS["rate"])))
        self.tts_pitch = QLineEdit(str(tts.get("pitch", DEFAULT_TTS["pitch"])))
        self.tts_volume = QLineEdit(str(tts.get("volume", DEFAULT_TTS["volume"])))
        form.addRow("语音", self.tts_voice)
        form.addRow("语速", self.tts_rate)
        form.addRow("音调", self.tts_pitch)
        form.addRow("音量", self.tts_volume)
        form.addRow(QLabel("说明：语速 +5%、音调 -5Hz、音量 +30% 这样的格式。"))
        return w

    # ------------------------------------------------------------ 情绪 tab
    def _build_emotion_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.addWidget(QLabel("每种情绪对应播放哪个动画（按大类分组，可展开选择）："))
        emap = dict(DEFAULT_EMOTION_ANIMS)
        emap.update(self.config.get("emotion_anims") or {})
        form = QFormLayout()
        self.emotion_combos = {}
        for key in EMOTION_KEYS:
            combo = _grouped_combo(self.categories)
            if emap.get(key):
                combo.setCurrentText(emap[key])
            form.addRow(key, combo)
            self.emotion_combos[key] = combo
        layout.addLayout(form)
        return w

    # ------------------------------------------------------------ 测试连接
    def _provisional(self):
        p = self.settings.active_config
        from .chat.models import ProviderConfig
        return ProviderConfig(
            p.provider_id, self.ai_name.text().strip() or p.name,
            self.ai_url.text().strip(), p.chat_path, self.ai_model.text().strip(),
            p.api_key_ref, self.ai_key.text() or p.api_key,
            float(p.timeout), float(self.ai_temp.value()), int(self.ai_tokens.value()),
            verify_ssl=not self.ai_ssl.isChecked(),
        )

    def _run_test(self):
        if self._test_thread is not None and self._test_thread.is_alive():
            return
        self.ai_test.setEnabled(False)
        self.ai_test.setText("测试中…")
        self.ai_result.setText("")
        cfg = self._provisional()

        def worker():
            ok, msg = test_connection(cfg, timeout=10.0)
            self._test_done.emit(ok, msg)

        self._test_thread = threading.Thread(target=worker, daemon=True)
        self._test_thread.start()

    def _on_test_done(self, ok, msg):
        self.ai_test.setEnabled(True)
        self.ai_test.setText("测试连接")
        self.ai_result.setText(msg)
        self.ai_result.setStyleSheet("color: #16a34a;" if ok else "color: #dc2626;")
        self._test_thread = None

    # ------------------------------------------------------------ 保存
    def _save(self):
        # AI
        p = self.settings.active_config
        p.name = self.ai_name.text().strip() or p.name
        p.base_url = self.ai_url.text().strip()
        p.model = self.ai_model.text().strip()
        p.temperature = float(self.ai_temp.value())
        p.max_tokens = int(self.ai_tokens.value())
        p.verify_ssl = not self.ai_ssl.isChecked()
        key = self.ai_key.text()
        if key:
            p.api_key_ref = p.api_key_ref or f"provider/{p.provider_id}"
            if not SecretStore().set(p.api_key_ref, key):
                p.api_key = key
        self.settings.default_system_prompt = self.ai_prompt.toPlainText().strip()
        self.config.set_chat_settings(self.settings)
        # 本地兜底模型
        self.config.set("local_base_url", self.local_url.text().strip())
        self.config.set("local_model", self.local_model.text().strip())
        # 语音
        self.config.set("tts", {
            "voice": self.tts_voice.currentText().strip(),
            "rate": self.tts_rate.text().strip(),
            "pitch": self.tts_pitch.text().strip(),
            "volume": self.tts_volume.text().strip(),
        })
        # 情绪映射
        self.config.set("emotion_anims", {
            k: c.currentText() for k, c in self.emotion_combos.items()
        })
        self.config.save()
        self.settings_saved.emit()
        self.accept()
