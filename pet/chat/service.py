from __future__ import annotations
import threading, uuid
from PySide6.QtCore import QObject, QThread, Signal
from .models import ProviderConfig
from .providers import OpenAICompatibleProvider


class _Worker(QThread):
    delta_received = Signal(str)
    completed = Signal(str)
    failed = Signal(str)
    stopped_by_user = Signal()

    def __init__(self, provider, messages, config, cancel,
                 local_provider=None, local_config=None):
        super().__init__()
        self.provider = provider
        self.messages = messages
        self.config = config
        self.cancel = cancel
        self.local_provider = local_provider
        self.local_config = local_config
        self.parts = []

    def run(self):
        # 1) 先云端
        try:
            for text in self.provider.stream(self.messages, self.config, self.cancel):
                if self.cancel.is_set():
                    self.stopped_by_user.emit()
                    return
                self.parts.append(text)
                self.delta_received.emit(text)
            if self.cancel.is_set():
                self.stopped_by_user.emit()
            else:
                self.completed.emit(''.join(self.parts))
            return
        except Exception as exc:
            if self.cancel.is_set():
                self.stopped_by_user.emit()
                return
            # 2) 云端失败/超时，本地 Ollama 兜底
            if self.local_provider is not None and self.local_config is not None:
                self.parts.clear()
                try:
                    for text in self.local_provider.stream(self.messages, self.local_config, self.cancel):
                        if self.cancel.is_set():
                            self.stopped_by_user.emit()
                            return
                        self.parts.append(text)
                        self.delta_received.emit(text)
                    if self.cancel.is_set():
                        self.stopped_by_user.emit()
                    else:
                        self.completed.emit(''.join(self.parts))
                    return
                except Exception as exc2:
                    self.failed.emit(str(exc2))
                    return
            self.failed.emit(str(exc))


class ChatService(QObject):
    started = Signal(str)
    delta = Signal(str, str)
    finished = Signal(str, str)
    error = Signal(str, str)
    stopped = Signal(str)

    def __init__(self, provider=None, local_provider=None, local_config=None, parent=None):
        super().__init__(parent)
        self.provider = provider or OpenAICompatibleProvider()
        self.local_provider = local_provider
        self.local_config = local_config
        self._request_id = None
        self._cancel = None
        self._worker = None

    @property
    def busy(self):
        return self._worker is not None and self._worker.isRunning()

    def send(self, messages: list[dict[str, str]], config: ProviderConfig, request_id=None):
        self.stop()
        rid = request_id or uuid.uuid4().hex
        cancel = threading.Event()
        worker = _Worker(self.provider, messages, config, cancel, self.local_provider, self.local_config)
        self._request_id = rid
        self._cancel = cancel
        self._worker = worker
        worker.delta_received.connect(lambda text, rid=rid: self._delta(rid, text))
        worker.completed.connect(lambda text, rid=rid: self._finished(rid, text))
        worker.failed.connect(lambda text, rid=rid: self._error(rid, text))
        worker.stopped_by_user.connect(lambda rid=rid: self._stopped(rid))
        worker.finished.connect(lambda rid=rid: self._cleanup(rid))
        self.started.emit(rid)
        worker.start()
        return rid

    def stop(self):
        if self._cancel is not None:
            self._cancel.set()

    def _current(self, rid):
        return rid == self._request_id

    def _delta(self, rid, text):
        if self._current(rid):
            self.delta.emit(rid, text)

    def _finished(self, rid, text):
        if self._current(rid):
            self.finished.emit(rid, text)

    def _error(self, rid, text):
        if self._current(rid):
            self.error.emit(rid, text)

    def _stopped(self, rid):
        if self._current(rid):
            self.stopped.emit(rid)

    def _cleanup(self, rid):
        if self._current(rid):
            self._worker = None
            self._cancel = None
