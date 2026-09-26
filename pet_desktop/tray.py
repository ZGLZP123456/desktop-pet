# -*- coding: utf-8 -*-
"""系统托盘：隐藏/显示宠物、快捷操作、退出"""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QMenu, QSystemTrayIcon


class PetTray(QSystemTrayIcon):
    quit_requested = Signal()

    def __init__(self, icon, pet, panel):
        super().__init__(icon)
        self.pet = pet
        self.panel = panel
        self.setToolTip("桌面宠物 · 右键菜单操作")
        self.setContextMenu(self._build_menu())
        self.activated.connect(self._on_activated)
        self.show()

    def _build_menu(self) -> QMenu:
        menu = QMenu()
        menu.addAction("🐱 显示/隐藏宠物", self._toggle_pet)
        menu.addAction("⚙️ 设置面板", self._toggle_panel)
        menu.addSeparator()
        menu.addAction("🍗 喂食", self.pet.feed)
        menu.addAction("❤️ 抚摸", self.pet.pet)
        menu.addAction("😴 睡觉/起床", self.pet.toggle_sleep)
        menu.addAction("🎾 陪玩", self.pet.play)
        menu.addSeparator()
        menu.addAction("退出", self.quit_requested.emit)
        return menu

    def _toggle_pet(self):
        self.pet.setVisible(not self.pet.isVisible())

    def _toggle_panel(self):
        self.panel.setVisible(not self.panel.isVisible())

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._toggle_panel()
