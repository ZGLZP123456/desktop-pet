# -*- coding: utf-8 -*-
"""设置面板：QScrollArea 可滚动控制台，QSS 深色主题，界面不会卡顿"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFrame, QGridLayout, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QProgressBar, QPushButton, QScrollArea,
    QSlider, QVBoxLayout, QWidget,
)

from . import sprites
from .config import DEFAULT_STATE, is_autostart, reset_state, save_config, set_autostart

PANEL_QSS = """
* { outline: none; }
#PanelRoot { background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #252736, stop:1 #1b1c26); }
#Title { font-size: 17px; font-weight: 700; color: #f0f2ff; }
#Sub { font-size: 12px; color: #9aa1b8; }
#Avatar { background: #3a3d55; border-radius: 27px; font-size: 28px; }
#ScrollContent { background: transparent; }
QGroupBox { background: rgba(255,255,255,0.045); border: 1px solid rgba(255,255,255,0.09);
            border-radius: 10px; margin-top: 12px; font-size: 13px; font-weight: 600; color: #c6cde4; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 5px; }
QPushButton { background: #3a3d55; border: none; border-radius: 8px; padding: 10px 12px;
              color: #eef0fa; font-size: 13px; }
QPushButton:hover { background: #484c6b; }
QPushButton:pressed { background: #2f3248; }
#ActBtn { font-size: 14px; }
#DangerBtn { background: #5a3240; }
#DangerBtn:hover { background: #6e3d4d; }
#QuitBtn { background: #8c3a4a; }
#QuitBtn:hover { background: #a54858; }
QLineEdit, QComboBox { background: #2b2d40; border: 1px solid rgba(255,255,255,0.12);
                       border-radius: 6px; padding: 6px 8px; color: #eef0fa; }
QLineEdit:focus, QComboBox:focus { border-color: #7d8cff; }
QComboBox::drop-down { border: none; width: 22px; }
QComboBox QAbstractItemView { background: #2b2d40; color: #eef0fa;
                              selection-background-color: #7d8cff;
                              border: 1px solid rgba(255,255,255,0.12); }
QSlider::groove:horizontal { height: 6px; background: #2e3044; border-radius: 3px; }
QSlider::sub-page:horizontal { background: #7d8cff; border-radius: 3px; }
QSlider::handle:horizontal { width: 16px; margin: -5px 0; border-radius: 8px; background: #a5b0ff; }
QSlider::handle:horizontal:hover { background: #c0c8ff; }
QCheckBox { spacing: 8px; color: #dfe2f2; font-size: 13px; }
QCheckBox::indicator { width: 18px; height: 18px; border-radius: 5px;
                       border: 2px solid #5a5e7a; background: #2b2d40; }
QCheckBox::indicator:checked { background: #7d8cff; border-color: #7d8cff; }
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { background: transparent; width: 8px; margin: 0; }
QScrollBar::handle:vertical { background: rgba(255,255,255,0.18); border-radius: 4px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: rgba(255,255,255,0.32); }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
#About { font-size: 11px; color: #7c83a0; }
"""

BAR_STYLES = {
    "hunger": ("🍗 饱腹 %v", "#ff9f43"),
    "mood":   ("💖 心情 %v", "#ff6b9d"),
    "energy": ("⚡ 体力 %v", "#4dd0e1"),
}


def _bar(key: str) -> QProgressBar:
    fmt, color = BAR_STYLES[key]
    bar = QProgressBar()
    bar.setRange(0, 100)
    bar.setValue(0)
    bar.setFormat(fmt)
    bar.setStyleSheet(
        "QProgressBar{background:#2b2d40;border:none;border-radius:6px;height:16px;"
        "text-align:center;color:#fff;font-size:11px;font-weight:600;}"
        f"QProgressBar::chunk{{background:{color};border-radius:6px;}}"
    )
    return bar


class ControlPanel(QWidget):
    """宠物控制台（可滚动、可调整大小）"""

    def __init__(self, cfg: dict, state: dict, pet):
        super().__init__()
        self.cfg = cfg
        self.state = state
        self.pet = pet
        self.setObjectName("PanelRoot")
        self.setWindowTitle("桌面宠物 · 控制台")
        self.resize(400, 640)
        self.setStyleSheet(PANEL_QSS)

        # ---- 自动保存：改动后防抖 600ms 落盘，避免拖滑块时狂写磁盘 ----
        self._cfg_dirty = False
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(600)
        self._save_timer.timeout.connect(self._flush_cfg)

        self._build_ui()
        self._timer = QTimer(self)
        self._timer.setInterval(500)
        self._timer.timeout.connect(self._refresh)
        self._timer.start()

    # ---------------- UI 构建 ----------------
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        # 头部
        head = QHBoxLayout()
        head.setSpacing(12)
        self.avatar = QLabel("🐱")
        self.avatar.setObjectName("Avatar")
        self.avatar.setFixedSize(54, 54)
        self.title = QLabel("")
        self.title.setObjectName("Title")
        self.sub = QLabel("会卖萌、会饿、会睡觉的小猫咪")
        self.sub.setObjectName("Sub")
        col = QVBoxLayout()
        col.setSpacing(2)
        col.addWidget(self.title)
        col.addWidget(self.sub)
        head.addWidget(self.avatar)
        head.addLayout(col)
        head.addStretch(1)
        root.addLayout(head)

        # 可滚动区域（保证内容再多也能顺畅上下滑动）
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        content.setObjectName("ScrollContent")
        self._lay = QVBoxLayout(content)
        self._lay.setContentsMargins(2, 2, 8, 2)
        self._lay.setSpacing(10)
        scroll.setWidget(content)
        root.addWidget(scroll, 1)

        self._build_interact()
        self._build_status()
        self._build_info()
        self._build_appearance()
        self._build_behavior()
        self._build_fun()
        self._build_system()
        self._lay.addStretch(1)

        about = QLabel("桌面宠物 v1.0 ｜ PySide6 + Pillow\n建议用 pythonw main.py 运行（不弹黑窗口）")
        about.setObjectName("About")
        about.setWordWrap(True)
        root.addWidget(about)

    def _group(self, title: str, layout):
        box = QGroupBox(title)
        box.setLayout(layout)
        self._lay.addWidget(box)
        return box

    def _slider(self, label: str, lo: int, hi: int, val: int, fmt: str, cb):
        """滑块行：文字标签 + 滑块 + 数值标签"""
        h = QHBoxLayout()
        h.setSpacing(8)
        lbl = QLabel(label)
        lbl.setFixedWidth(60)
        s = QSlider(Qt.Orientation.Horizontal)
        s.setRange(lo, hi)
        s.setValue(val)
        val_lbl = QLabel(fmt.format(val))
        val_lbl.setFixedWidth(64)
        val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        s.valueChanged.connect(lambda v: (val_lbl.setText(fmt.format(v)), cb(v)))
        h.addWidget(lbl)
        h.addWidget(s, 1)
        h.addWidget(val_lbl)
        return h, s

    def _build_interact(self):
        grid = QGridLayout()
        grid.setSpacing(8)
        items = [("🍗 喂食", self.pet.feed), ("❤️ 抚摸", self.pet.pet),
                 ("😴 睡觉/起床", self.pet.toggle_sleep), ("🎾 陪玩", self.pet.play)]
        for i, (text, fn) in enumerate(items):
            b = QPushButton(text)
            b.setObjectName("ActBtn")
            b.clicked.connect(fn)
            b.setMinimumHeight(42)
            grid.addWidget(b, i // 2, i % 2)
        self._group("互动", grid)

    def _build_status(self):
        v = QVBoxLayout()
        v.setSpacing(6)
        self.bar_hunger = _bar("hunger")
        self.bar_mood = _bar("mood")
        self.bar_energy = _bar("energy")
        v.addWidget(self.bar_hunger)
        v.addWidget(self.bar_mood)
        v.addWidget(self.bar_energy)
        self._group("宠物状态", v)

    def _build_info(self):
        v = QVBoxLayout()
        v.setSpacing(8)
        r1 = QHBoxLayout()
        r1.addWidget(QLabel("名字"))
        self.name_edit = QLineEdit(self.cfg["pet_name"])
        self.name_edit.setMaxLength(8)
        r1.addWidget(self.name_edit, 1)
        r2 = QHBoxLayout()
        r2.addWidget(QLabel("皮肤"))
        self.skin_box = QComboBox()
        self.skin_box.addItems(list(sprites.SKINS.keys()) + ["动漫头像"])
        self.skin_box.setCurrentText(self.cfg["skin"])
        r2.addWidget(self.skin_box, 1)
        v.addLayout(r1)
        v.addLayout(r2)
        self.name_edit.editingFinished.connect(self._on_name_changed)
        self.skin_box.currentTextChanged.connect(self._on_skin_changed)
        self.pet.skin_changed.connect(self._on_pet_skin_changed)
        self._group("基本信息", v)

    def _build_appearance(self):
        row, self.size_slider = self._slider(
            "大小", 120, 240, self.cfg["size"], "{} px",
            lambda v: (self.pet._apply_size(v), self._save_cfg()))
        self._group("外观", row)

    def _build_behavior(self):
        v = QVBoxLayout()
        v.setSpacing(8)
        row1, self.speed_slider = self._slider(
            "速度", 60, 400, self.cfg["walk_speed"], "{} px/s",
            lambda v: (self.cfg.__setitem__("walk_speed", v), self._save_cfg()))
        row2, self.speech_slider = self._slider(
            "说话", 0, 100, self.cfg["speech_freq"], "{} %",
            lambda v: (self.cfg.__setitem__("speech_freq", v), self._save_cfg()))

        self.ck_auto_walk = QCheckBox("自动走动")
        self.ck_auto_walk.setChecked(self.cfg["auto_walk"])
        self.ck_auto_walk.toggled.connect(
            lambda v: (self.cfg.__setitem__("auto_walk", v), self._save_cfg()))

        self.ck_top = QCheckBox("窗口置顶")
        self.ck_top.setChecked(self.cfg["always_on_top"])
        self.ck_top.toggled.connect(lambda v: (self.pet.set_always_on_top(v), self._save_cfg()))

        self.ck_sound = QCheckBox("提示音")
        self.ck_sound.setChecked(self.cfg["sound"])
        self.ck_sound.toggled.connect(
            lambda v: (self.cfg.__setitem__("sound", v), self._save_cfg()))

        v.addLayout(row1)
        v.addLayout(row2)
        v.addWidget(self.ck_auto_walk)
        v.addWidget(self.ck_top)
        v.addWidget(self.ck_sound)
        self._group("行为设置", v)

    def _build_fun(self):
        """好玩接口：每日一言 / 60秒看世界 / 天气 / 诗词 / 沙雕语录"""
        grid = QGridLayout()
        grid.setSpacing(8)
        items = [("💬 每日一言", self.pet.act_quote), ("🌏 60秒看世界", self.pet.act_news),
                 ("🌤 今日天气", self.pet.act_weather), ("💘 沙雕语录", self.pet.act_humor),
                 ("📜 每日诗词", self.pet.act_poem)]
        for i, (text, fn) in enumerate(items):
            b = QPushButton(text)
            b.setObjectName("ActBtn")
            b.clicked.connect(fn)
            b.setMinimumHeight(40)
            grid.addWidget(b, i // 2, i % 2)

        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(QLabel("城市"))
        self.city_edit = QLineEdit(self.cfg.get("city", "北京"))
        self.city_edit.setMaxLength(12)
        self.city_edit.editingFinished.connect(self._on_city_changed)
        row.addWidget(self.city_edit, 1)
        tip = QLabel("天气用，回车生效")
        tip.setObjectName("About")
        row.addWidget(tip)

        # 每日一言定时：开关 + 间隔
        sched = QHBoxLayout()
        sched.setSpacing(8)
        self.ck_quote = QCheckBox("定时每日一言")
        self.ck_quote.setChecked(self.cfg.get("quote_auto", True))
        self.ck_quote.toggled.connect(self._on_quote_schedule)
        self.quote_combo = QComboBox()
        self.quote_combo.addItem("10 秒", 10)
        self.quote_combo.addItem("30 秒", 30)
        self.quote_combo.addItem("1 分钟", 60)
        self.quote_combo.addItem("5 分钟", 300)
        self.quote_combo.addItem("10 分钟", 600)
        self.quote_combo.addItem("30 分钟", 1800)
        self.quote_combo.addItem("1 小时", 3600)
        self.quote_combo.addItem("4 小时", 14400)
        self.quote_combo.addItem("8 小时", 28800)
        self.quote_combo.addItem("24 小时（每天）", 86400)
        cur = self.cfg.get("quote_interval_s", 14400)
        idx = self.quote_combo.findData(cur)
        self.quote_combo.setCurrentIndex(idx if idx >= 0 else 7)
        self.quote_combo.currentIndexChanged.connect(self._on_quote_schedule)
        sched.addWidget(self.ck_quote)
        sched.addWidget(self.quote_combo, 1)
        sched_tip = QLabel("到点宠物会主动冒出一句")
        sched_tip.setObjectName("About")
        sched.addWidget(sched_tip)

        # 动漫头像：换图/下载 + 自动换图设置
        anime_btns = QHBoxLayout()
        anime_btns.setSpacing(8)
        b_anime = QPushButton("🎨 换动漫头像")
        b_anime.setObjectName("ActBtn")
        b_anime.clicked.connect(self.pet.act_anime)
        b_dl = QPushButton("⬇️ 下载头像")
        b_dl.setObjectName("ActBtn")
        b_dl.clicked.connect(self.pet.download_anime)
        anime_btns.addWidget(b_anime)
        anime_btns.addWidget(b_dl)

        anime_sched = QHBoxLayout()
        anime_sched.setSpacing(8)
        self.ck_anime = QCheckBox("自动换头像")
        self.ck_anime.setChecked(self.cfg.get("anime_auto", True))
        self.ck_anime.toggled.connect(self._on_anime_schedule)
        self.anime_combo = QComboBox()
        self.anime_combo.addItem("10 秒", 10)
        self.anime_combo.addItem("1 分钟", 60)
        self.anime_combo.addItem("10 分钟", 600)
        self.anime_combo.addItem("1 小时", 3600)
        self.anime_combo.addItem("6 小时", 21600)
        self.anime_combo.addItem("24 小时", 86400)
        cur = self.cfg.get("anime_interval_s", 3600)
        idx = self.anime_combo.findData(cur)
        self.anime_combo.setCurrentIndex(idx if idx >= 0 else 3)
        self.anime_combo.currentIndexChanged.connect(self._on_anime_schedule)
        anime_sched.addWidget(self.ck_anime)
        anime_sched.addWidget(self.anime_combo, 1)
        anime_tip = QLabel("需选择「动漫头像」皮肤")
        anime_tip.setObjectName("About")
        anime_sched.addWidget(anime_tip)

        self.fun_log = QLabel("点击按钮，宠物会告诉你有趣的内容～")
        self.fun_log.setObjectName("About")
        self.fun_log.setWordWrap(True)
        v = QVBoxLayout()
        v.setSpacing(8)
        v.addLayout(grid)
        v.addLayout(row)
        v.addLayout(sched)
        v.addLayout(anime_btns)
        v.addLayout(anime_sched)
        v.addWidget(self.fun_log)
        self._group("好玩接口", v)

        # 接口结果实时回显
        api = self.pet.api
        api.quote_ready.connect(lambda t: self.fun_log.setText("💬 " + t))
        api.news_ready.connect(
            lambda items: self.fun_log.setText(f"🌏 快讯已更新（{len(items)} 条），宠物会弹窗展示"))
        api.weather_ready.connect(lambda t: self.fun_log.setText("🌤 " + t))
        api.poem_ready.connect(lambda t: self.fun_log.setText("📜 " + t[:30] + "…"))
        api.humor_ready.connect(lambda t: self.fun_log.setText("💘 " + t))
        api.anime_ready.connect(lambda _b: self.fun_log.setText("🎨 已换新动漫头像，可点「下载头像」保存"))
        api.failed.connect(lambda msg: self.fun_log.setText("⚠️ " + msg))

        self._update_anime_ctrl()

    def _on_city_changed(self):
        city = self.city_edit.text().strip()
        if city:
            self.cfg["city"] = city
            self._save_cfg()

    def _on_quote_schedule(self, *_):
        """定时每日一言：开关/间隔变更时应用并保存"""
        enabled = self.ck_quote.isChecked()
        interval_s = float(self.quote_combo.currentData())
        self.pet.apply_quote_schedule(enabled, interval_s)
        self._save_cfg()

    def _build_system(self):
        v = QVBoxLayout()
        v.setSpacing(8)
        self.ck_autostart = QCheckBox("开机自启（写入注册表 HKCU\\Run）")
        self.ck_autostart.setChecked(is_autostart())
        self.ck_autostart.toggled.connect(self._on_autostart)

        row = QHBoxLayout()
        reset = QPushButton("重置数据")
        reset.setObjectName("DangerBtn")
        reset.clicked.connect(self._on_reset)
        quit_btn = QPushButton("退出程序")
        quit_btn.setObjectName("QuitBtn")
        quit_btn.clicked.connect(self.pet.quit_requested.emit)
        row.addWidget(reset)
        row.addWidget(quit_btn)

        v.addWidget(self.ck_autostart)
        v.addLayout(row)
        self._group("系统", v)

    # ---------------- 自动保存 ----------------
    def _save_cfg(self):
        """标记配置已改动，防抖 600ms 后统一落盘"""
        self._cfg_dirty = True
        self._save_timer.start()

    def _flush_cfg(self):
        """真正把配置写入磁盘（无改动时跳过，避免无意义 IO）"""
        if not self._cfg_dirty:
            return
        save_config(self.cfg)
        self._cfg_dirty = False

    def _on_name_changed(self):
        name = self.name_edit.text().strip()
        if not name:
            self.name_edit.setText(self.cfg["pet_name"])
            return
        self.cfg["pet_name"] = name
        self._save_cfg()

    def _on_skin_changed(self, key: str):
        self.pet.set_skin(key)
        self._update_anime_ctrl()

    def _on_pet_skin_changed(self, key: str):
        """宠物侧改了皮肤（如右键「换动漫头像」）时，同步下拉框并保存"""
        if self.skin_box.currentText() != key:
            self.skin_box.blockSignals(True)
            self.skin_box.setCurrentText(key)
            self.skin_box.blockSignals(False)
        self._update_anime_ctrl()
        self._save_cfg()

    def _on_anime_schedule(self, *_):
        """自动换头像：开关/间隔变更时应用并保存"""
        enabled = self.ck_anime.isChecked()
        interval_s = float(self.anime_combo.currentData())
        self.pet.apply_anime_schedule(enabled, interval_s)
        self._save_cfg()

    def _update_anime_ctrl(self):
        """非动漫皮肤时，自动换头像相关控件置灰"""
        is_anime = self.cfg.get("skin") == "动漫头像"
        self.ck_anime.setEnabled(is_anime)
        self.anime_combo.setEnabled(is_anime and self.ck_anime.isChecked())

    def _on_autostart(self, checked: bool):
        if set_autostart(checked):
            self.cfg["autostart"] = checked
            self._save_cfg()
        else:
            QMessageBox.warning(self, "开机自启", "写入注册表失败，可能是权限不足。")
            self.ck_autostart.blockSignals(True)
            self.ck_autostart.setChecked(not checked)
            self.ck_autostart.blockSignals(False)

    def _on_reset(self):
        ans = QMessageBox.question(
            self, "重置数据", "确定要把宠物的饱腹度、心情、体力恢复默认吗？")
        if ans == QMessageBox.StandardButton.Yes:
            reset_state()
            self.state.update(dict(DEFAULT_STATE))

    # ---------------- 定时刷新 ----------------
    def _refresh(self):
        s = self.state
        mode_map = {"idle": "待机", "walk": "漫步", "sleep": "睡觉",
                    "eat": "干饭", "happy": "开心", "sad": "委屈"}
        mode = mode_map.get(getattr(self.pet, "mode", "idle"), "待机")
        self.title.setText(f"{self.cfg['pet_name']} · {mode}")
        self.bar_hunger.setValue(int(s["hunger"]))
        self.bar_mood.setValue(int(s["mood"]))
        self.bar_energy.setValue(int(s["energy"]))

    def closeEvent(self, e):
        # 点 X 只是隐藏，不销毁窗口
        e.ignore()
        self._on_name_changed()   # 收尾可能未提交的名字
        self._flush_cfg()         # 待保存的改动立即落盘
        self.hide()
