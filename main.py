# -*- coding: utf-8 -*-
"""桌面宠物 · 程序入口
运行方式：
    python main.py       （带控制台窗口，方便看报错）
    pythonw main.py      （无控制台窗口，建议正式使用）
"""
import sys

from PySide6.QtCore import QLockFile
from PySide6.QtWidgets import QApplication, QMessageBox

from pet_desktop import sprites
from pet_desktop.config import LOCK_FILE, load_config, load_state, save_config, save_state
from pet_desktop.panel import ControlPanel
from pet_desktop.pet_window import PetWindow
from pet_desktop.tray import PetTray


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName("桌面宠物")
    app.setApplicationDisplayName("桌面宠物")
    app.setQuitOnLastWindowClosed(False)  # 托盘常驻，关面板不退出

    # 单实例保护：已有实例在跑就直接提示退出
    lock = QLockFile(str(LOCK_FILE))
    if not lock.tryLock(100):
        QMessageBox.information(None, "桌面宠物", "桌面宠物已经在运行了，看看托盘区域～")
        return 0

    cfg = load_config()
    state = load_state()

    icon = sprites.tray_icon()
    app.setWindowIcon(icon)

    pet = PetWindow(cfg, state)
    panel = ControlPanel(cfg, state, pet)
    pet.panel = panel  # 供宠物侧打开面板（当前未直接使用，保留接口）

    tray = PetTray(icon, pet, panel)

    pet.open_panel_requested.connect(
        lambda: (panel.show(), panel.raise_(), panel.activateWindow()))
    pet.quit_requested.connect(app.quit)
    tray.quit_requested.connect(app.quit)

    def on_about_to_quit():
        save_state(state)
        save_config(cfg)

    app.aboutToQuit.connect(on_about_to_quit)

    pet.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
