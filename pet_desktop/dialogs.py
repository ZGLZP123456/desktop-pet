# -*- coding: utf-8 -*-
"""通用可滚动文本窗：用于 60秒看世界 / 历史上的今天 等长内容展示"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from .panel import PANEL_QSS


class TextDialog(QDialog):
    """标题 + 可滚动条目列表（复用面板深色样式）"""

    def __init__(self, title: str, items=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(440, 560)
        # 关键：给对话框本体套上暗色根样式（否则默认白底 + 浅色文字 = 白屏看不见）
        self.setObjectName("PanelRoot")
        self.setStyleSheet(PANEL_QSS)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(10)

        head = QLabel(title)
        head.setStyleSheet("font-size:16px;font-weight:700;color:#f0f2ff;")
        lay.addWidget(head)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._content = QWidget()
        self._content.setObjectName("ScrollContent")
        self._v = QVBoxLayout(self._content)
        self._v.setContentsMargins(2, 2, 8, 2)
        self._v.setSpacing(8)
        self._scroll.setWidget(self._content)
        lay.addWidget(self._scroll, 1)

        btns = QHBoxLayout()
        btns.addStretch(1)
        close = QPushButton("关闭")
        close.setObjectName("ActBtn")
        close.clicked.connect(self.accept)
        btns.addWidget(close)
        lay.addLayout(btns)

        self.set_items(items or [])

    def set_items(self, items):
        """替换条目内容（清空旧的，重建列表）"""
        while self._v.count():
            item = self._v.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        if isinstance(items, str):
            items = items.split("\n")
        for it in items:
            s = str(it).strip()
            if not s:
                continue
            lbl = QLabel(s)
            lbl.setWordWrap(True)
            lbl.setStyleSheet(
                "background:rgba(255,255,255,0.05);border-radius:8px;"
                "padding:10px;color:#e8eaf6;font-size:13px;")
            self._v.addWidget(lbl)
        self._v.addStretch(1)
