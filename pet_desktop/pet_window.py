# -*- coding: utf-8 -*-
"""宠物主窗口：透明置顶窗口 + 帧动画 + 拖拽/点击/右键交互 + 状态机"""
from __future__ import annotations

import datetime
import random
import time
from pathlib import Path

from PySide6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, QRect, Qt, QTimer, Signal
from PySide6.QtGui import QGuiApplication, QPixmap, QTransform
from PySide6.QtWidgets import QFileDialog, QLabel, QMenu, QMessageBox, QWidget

from . import sprites
from .api import FunApi
from .audio import play_sound
from .config import ASSET_DIR, save_config, save_state
from .dialogs import TextDialog

# 各状态对应的动画帧序列
SEQUENCES = {
    "idle":  ["idle0", "idle1", "idle0", "blink"],
    "walk":  ["walk0", "walk1"],
    "sleep": ["sleep"],
    "eat":   ["eat", "eat", "eat", "blink"],
    "happy": ["happy", "happy", "blink"],
    "sad":   ["sad"],
}

# 随机卖萌台词
SPEECHES = [
    "喵呜～", "主人今天也要加油哦！", "我好想睡觉…", "有小鱼干吗？",
    "摸一摸我嘛～", "嘿嘿，你在看我吗？", "今天天气不错喵～",
    "呼噜呼噜…", "再忙也要记得休息哦！", "我的小尾巴藏不住啦！",
    "咕噜咕噜～", "你敲代码的样子真帅！", "肚子有点饿了…", "陪你一起发呆中…",
]

BUBBLE_ZONE = 120  # 窗口顶部预留的气泡区域高度(px)，保证长句也能完整显示

ANIME_SKIN = "动漫头像"  # 特殊皮肤：网络随机动漫图
ANIME_CACHE = ASSET_DIR / "anime_avatar.png"


class PetWindow(QWidget):
    open_panel_requested = Signal()   # 请求打开设置面板
    quit_requested = Signal()         # 请求退出程序
    skin_changed = Signal(str)        # 皮肤变更（供面板同步下拉框）

    def __init__(self, cfg: dict, state: dict):
        super().__init__()
        self.cfg = cfg
        self.state = state
        self.panel = None

        # ---- 状态机变量 ----
        self.facing = 1               # 朝向: 1 右 / -1 左
        self.mode = "idle"
        self._seq = list(SEQUENCES["idle"])
        self._seq_i = 0
        self._mode_ticks = 0
        self._walking = False
        self._dragging = False
        self._click_pending = False
        self._last_click_time = 0.0
        self._press_global = QPoint()
        self._press_pos = QPoint()
        self._press_time = 0.0
        self._last_saved = time.time()
        self._next_walk_at = time.time() + random.uniform(self.cfg["walk_min"], self.cfg["walk_max"])

        # ---- 窗口属性：无边框 + 工具窗（不进任务栏）+ 可选置顶 + 透明背景 ----
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool |
            (Qt.WindowType.WindowStaysOnTopHint if self.cfg["always_on_top"] else Qt.WindowType(0))
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # ---- 精灵与显示控件 ----
        self._anime_mode = False
        self._anime_pixmap = None
        # 动漫头像皮肤不走本地精灵帧；其余皮肤在此生成动画帧
        self._sprites = None
        if self.cfg.get("skin") != ANIME_SKIN:
            self._sprites = sprites.SpriteSet(self.cfg["skin"])
        self.label = QLabel(self)
        self.label.setScaledContents(True)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.bubble = QLabel(self)
        self.bubble.setObjectName("PetBubble")
        self.bubble.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.bubble.setWordWrap(True)
        self.bubble.setStyleSheet(
            "QLabel#PetBubble{background:rgba(255,255,255,0.96);color:#333;"
            "border-radius:14px;padding:8px 12px;font-size:13px;"
            "border:1px solid rgba(0,0,0,0.15);}"
        )
        self.bubble.hide()

        self._apply_size(self.cfg["size"])
        self._place_initial()

        # ---- 定时器：动画 / 每秒逻辑 / 随机说话 / 气泡隐藏 ----
        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(170)
        self._anim_timer.timeout.connect(self._tick_anim)
        self._anim_timer.start()

        self._sec_timer = QTimer(self)
        self._sec_timer.setInterval(1000)
        self._sec_timer.timeout.connect(self._on_second)
        self._sec_timer.start()

        self._speech_timer = QTimer(self)
        self._speech_timer.setInterval(7000)
        self._speech_timer.timeout.connect(self._maybe_speak)
        self._speech_timer.start()

        self._bubble_timer = QTimer(self)
        self._bubble_timer.setSingleShot(True)
        self._bubble_timer.timeout.connect(self._hide_bubble)

        # 单击判定：350ms 内没等到第二次点击才算单击（双击=睡觉/起床）
        self._click_timer = QTimer(self)
        self._click_timer.setSingleShot(True)
        self._click_timer.setInterval(350)
        self._click_timer.timeout.connect(self._fire_click)

        # ---- 好玩接口（异步，不阻塞界面）----
        self.api = FunApi(self)
        self._want_feedback = False
        self.news_dialog = None
        self.api.quote_ready.connect(lambda t: self._on_api_text(t))
        self.api.weather_ready.connect(lambda t: self._on_api_text("今天的天气：" + t))
        self.api.poem_ready.connect(lambda t: self._on_api_text(t))
        self.api.humor_ready.connect(lambda t: self._on_api_text(t))
        self.api.news_ready.connect(self._on_news)
        self.api.anime_ready.connect(self._on_anime_ready)
        self.api.failed.connect(self._on_api_fail)

        # 动漫头像自动换图定时器（仅动漫皮肤下生效）
        self._anime_timer = QTimer(self)
        self._anime_timer.timeout.connect(self.api.fetch_anime)
        self.apply_anime_schedule(self.cfg.get("anime_auto", True),
                                  self.cfg.get("anime_interval_s", 3600))

        # 定时每日一言：按配置开关/间隔启动（面板可改）
        self._quote_first = QTimer(self)
        self._quote_first.setSingleShot(True)
        self._quote_first.setInterval(8000)
        self._quote_first.timeout.connect(self.api.fetch_quote)
        self._quote_loop = QTimer(self)
        self._quote_loop.timeout.connect(self.api.fetch_quote)
        self.apply_quote_schedule(self.cfg.get("quote_auto", True),
                                  self.cfg.get("quote_interval_s", 14400))

        # ---- 移动动画 ----
        self._move = QPropertyAnimation(self, b"pos", self)
        self._move.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._move.finished.connect(self._on_walk_finished)

        # 若上次用的就是动漫头像皮肤，等 label / api / 定时器都就绪后再进入动漫模式
        if self.cfg.get("skin") == ANIME_SKIN:
            self._enter_anime_mode()

    # ================= 布局 =================
    def _apply_size(self, size: int):
        """按大小调整窗口/精灵/气泡区域"""
        self.cfg["size"] = size
        self.resize(size, size + BUBBLE_ZONE)
        self.label.setGeometry(0, BUBBLE_ZONE, size, size)
        self.bubble.setGeometry(8, 2, size - 16, 44)

    def _place_initial(self):
        """初始位置：主屏右下角"""
        geo = self._screen_geo()
        self.move(geo.right() - self.width() - 60, geo.bottom() - self.height() - 40)

    def _screen_geo(self) -> QRect:
        screen = QGuiApplication.primaryScreen()
        return screen.availableGeometry() if screen else QRect(0, 0, 1920, 1080)

    def _union_geo(self) -> QRect:
        """所有显示器可用范围的并集（用于拖拽边界）"""
        rect = QRect()
        for s in QGuiApplication.screens():
            rect = rect.united(s.availableGeometry())
        return rect

    # ================= 动画 =================
    def set_mode(self, mode: str):
        self.mode = mode
        self._seq = list(SEQUENCES.get(mode, SEQUENCES["idle"]))
        self._seq_i = 0
        self._mode_ticks = 0

    def _tick_anim(self):
        # 动漫头像模式：无帧动画，固定显示当前头像（朝向翻转仍生效）
        if self._anime_mode:
            if self._anime_pixmap is not None:
                pm = self._anime_pixmap
                if self.facing < 0:
                    pm = pm.transformed(QTransform().scale(-1, 1))
                self.label.setPixmap(pm)
            return
        name = self._seq[self._seq_i % len(self._seq)]
        self._seq_i += 1
        pm = self._sprites.frames.get(name)
        if pm is None:
            return
        if self.facing < 0:  # 朝左时水平镜像
            pm = pm.transformed(QTransform().scale(-1, 1))
        self.label.setPixmap(pm)
        self._mode_ticks += 1
        # 临时状态（进食/开心）播完两轮自动回到待机
        if self.mode in ("eat", "happy") and self._mode_ticks >= len(self._seq) * 2:
            self.set_mode("idle")

    # ================= 每秒逻辑 =================
    def _on_second(self):
        s = self.state
        if s["sleeping"]:
            s["energy"] = min(100.0, s["energy"] + 0.5)
            s["hunger"] = max(0.0, s["hunger"] - 0.03)
            if s["energy"] >= 95:
                s["sleeping"] = False
                self.set_mode("idle")
                self._say("睡饱啦，满血复活～")
        else:
            s["hunger"] = max(0.0, s["hunger"] - 0.05)
            s["energy"] = max(0.0, s["energy"] - 0.045)
            if s["hunger"] < 20:
                s["mood"] = max(0.0, s["mood"] - 0.4)
                if random.random() < 0.05:
                    self._say("我饿啦… 想吃小鱼干…")
            elif s["mood"] < 100:
                s["mood"] = min(100.0, s["mood"] + 0.05)
            if s["energy"] < 12 and self.mode != "sleep":
                self.toggle_sleep(auto=True)

        # 自动漫步
        if (self.cfg["auto_walk"] and not self._walking and not self._dragging
                and self.mode == "idle" and not s["sleeping"]
                and time.time() >= self._next_walk_at):
            self._start_walk()

        # 周期保存
        if time.time() - self._last_saved > 10:
            save_state(self.state)
            self._last_saved = time.time()

    def _maybe_speak(self):
        if self.mode == "sleep":
            return
        if random.random() * 100 < self.cfg["speech_freq"]:
            self._say(random.choice(SPEECHES))

    # ================= 行走 =================
    def _start_walk(self):
        # 随机选一块屏幕，在其可用范围内选目标点（支持多显示器）
        screens = QGuiApplication.screens()
        if not screens:
            return
        geo = random.choice(screens).availableGeometry()
        m = 24
        w, h = self.width(), self.height()
        x = random.randint(geo.left() + m, max(geo.left() + m, geo.right() - w - m))
        y = random.randint(geo.top() + m, max(geo.top() + m, geo.bottom() - h - m))
        cur = self.pos()
        dx = x - cur.x()
        if dx != 0:
            self.facing = 1 if dx > 0 else -1
        dist = ((x - cur.x()) ** 2 + (y - cur.y()) ** 2) ** 0.5
        dur = max(400, int(dist / max(40, self.cfg["walk_speed"]) * 1000))
        self.set_mode("walk")
        self._walking = True
        self._move.stop()
        self._move.setDuration(dur)
        self._move.setStartValue(cur)
        self._move.setEndValue(QPoint(x, y))
        self._move.start()

    def _on_walk_finished(self):
        self._walking = False
        self.set_mode("idle")
        self._next_walk_at = time.time() + random.uniform(self.cfg["walk_min"], self.cfg["walk_max"])

    # ================= 交互 =================
    def feed(self):
        s = self.state
        if s["sleeping"]:
            s["sleeping"] = False
        s["hunger"] = min(100.0, s["hunger"] + 30)
        s["mood"] = min(100.0, s["mood"] + 5)
        self.set_mode("eat")
        if self.cfg["sound"]:
            play_sound("eat")
        self._say(random.choice(["好吃好吃～", "喵呜～ 谢谢投喂！", "再来一条小鱼干～"]))

    def pet(self):
        s = self.state
        if s["sleeping"]:
            s["sleeping"] = False
        s["mood"] = min(100.0, s["mood"] + 8)
        self.set_mode("happy")
        if self.cfg["sound"]:
            play_sound("pet")
        self._say(random.choice(["喵～ 好舒服～", "嘿嘿，再摸摸嘛～", "最喜欢你啦！"]))

    def toggle_sleep(self, auto=False):
        s = self.state
        s["sleeping"] = not s["sleeping"]
        if s["sleeping"]:
            self._move.stop()
            self._walking = False
            self.set_mode("sleep")
            if self.cfg["sound"]:
                play_sound("sleep")
            if not auto:
                self._say("呼噜呼噜… 晚安～")
        else:
            self.set_mode("idle")
            if not auto:
                self._say("我醒啦！")

    def play(self):
        s = self.state
        if s["sleeping"]:
            s["sleeping"] = False
        s["mood"] = min(100.0, s["mood"] + 15)
        s["energy"] = max(0.0, s["energy"] - 3)
        self.set_mode("happy")
        if self.cfg["sound"]:
            play_sound("play")
        self._say(random.choice(["接住啦！", "哈哈哈，好好玩！", "再玩一次嘛！"]))

    # ================= 气泡 =================
    def _say(self, text: str, secs: float = 4.0):
        """显示说话气泡：按内容自动换行缩放，保证长句完整显示"""
        if not text:
            return
        self.bubble.setText(text)
        max_w = self.width() - 24
        w = min(max_w, max(96, self.bubble.fontMetrics().horizontalAdvance(text) + 30))
        self.bubble.setFixedWidth(w)
        # wordWrap 生效后按宽度算实际高度，并限制在气泡区域内
        h = min(self.bubble.heightForWidth(w) + 24, BUBBLE_ZONE - 8)
        self.bubble.setFixedHeight(max(40, h))
        self.bubble.move((self.width() - w) // 2, 2)
        self.bubble.show()
        self._bubble_timer.start(int(secs * 1000))

    def _hide_bubble(self):
        self.bubble.hide()

    # ================= 好玩接口 =================
    def act_quote(self):
        self._want_feedback = True
        self._say("让我想一句好话…", 2)
        self.api.fetch_quote()

    def act_news(self):
        self._want_feedback = True
        self._say("我去看看今天世界发生了什么…", 2)
        self.api.fetch_news()

    def act_weather(self):
        self._want_feedback = True
        self._say("看看今天的天气～", 2)
        self.api.fetch_weather(self.cfg.get("city", "北京"))

    def act_poem(self):
        self._want_feedback = True
        self.api.fetch_poem()

    def act_humor(self):
        self._want_feedback = True
        self._say("让我想句沙雕语录…", 2)
        self.api.fetch_humor()

    def _on_api_text(self, text: str):
        self._want_feedback = False
        self._say(text, 7)

    def _on_api_fail(self, _msg: str):
        if self._want_feedback:
            self._want_feedback = False
            self._say("网络开了个小差，稍后再试～", 3)

    def _on_news(self, items: list):
        self._want_feedback = False
        if self.news_dialog is None:
            self.news_dialog = TextDialog("🌏 60秒看世界", [], self)
            self.news_dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.news_dialog.set_items(items)
        self.news_dialog.show()
        self.news_dialog.raise_()
        self.news_dialog.activateWindow()
        self._say("快讯更新啦，点开看看～", 4)

    # ================= 动漫头像 =================
    def _enter_anime_mode(self):
        """进入动漫头像模式：优先用本地缓存，没有就自动拉一张"""
        self._anime_mode = True
        cached = QPixmap(str(ANIME_CACHE))
        if not cached.isNull():
            self._anime_pixmap = self._crop_square(cached)
            self._tick_anim()
        else:
            self.api.fetch_anime()
        self.apply_anime_schedule(self.cfg.get("anime_auto", True),
                                  self.cfg.get("anime_interval_s", 3600))

    @staticmethod
    def _crop_square(pm: QPixmap) -> QPixmap:
        """居中裁成正方形，避免动漫图被拉伸变形"""
        side = min(pm.width(), pm.height())
        x = (pm.width() - side) // 2
        y = (pm.height() - side) // 2
        return pm.copy(x, y, side, side)

    def _cache_anime(self, pm: QPixmap):
        try:
            ANIME_CACHE.parent.mkdir(parents=True, exist_ok=True)
            pm.save(str(ANIME_CACHE), "PNG")
        except Exception:
            pass

    def _on_anime_ready(self, data: bytes):
        # 已切回猫咪皮肤时，丢弃迟到的在途图片
        if not self._anime_mode:
            return
        self._want_feedback = False
        pm = QPixmap()
        if pm.loadFromData(data):
            self._anime_pixmap = self._crop_square(pm)
            self._cache_anime(self._anime_pixmap)
            self._tick_anim()
            self._say("换上新头像啦，好看吗？", 4)
        elif self._want_feedback:
            self._say("头像接口开了个小差～", 3)

    def act_anime(self):
        """换一张动漫头像；若当前不是动漫皮肤，先切过去再拉新图"""
        self._want_feedback = True
        if not self._anime_mode:
            self.set_skin(ANIME_SKIN)   # 切进动漫模式（会保存配置并同步面板）
            if self._anime_pixmap is not None:
                # 已有缓存图，先显示出来，再去拉新的
                self._tick_anim()
        self._say("我去找一张好看的…", 2)
        self.api.fetch_anime()

    def download_anime(self):
        """把当前动漫头像保存到本地"""
        if self._anime_pixmap is None:
            self._say("还没有动漫头像，先点「换动漫头像」～", 4)
            return
        default_dir = str(Path.home() / "Pictures")
        default_name = f"桌面宠物头像_{datetime.datetime.now():%Y%m%d_%H%M%S}.png"
        path, _ = QFileDialog.getSaveFileName(
            self, "保存头像", str(Path(default_dir) / default_name), "PNG 图片 (*.png)")
        if not path:
            return
        if self._anime_pixmap.save(path, "PNG"):
            self._say("头像已保存～", 4)
            QMessageBox.information(self, "头像已保存", f"已保存到：\n{path}")
        else:
            self._say("保存失败…", 3)

    def apply_anime_schedule(self, enabled: bool, interval_s: float):
        """动漫头像自动换图设置：仅动漫皮肤下生效"""
        self.cfg["anime_auto"] = bool(enabled)
        self.cfg["anime_interval_s"] = interval_s
        self._anime_timer.stop()
        if enabled and self._anime_mode and interval_s and interval_s > 0:
            self._anime_timer.setInterval(int(float(interval_s) * 1000))
            self._anime_timer.start()

    # ================= 鼠标事件 =================
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._press_global = e.globalPosition().toPoint()
            self._press_pos = self._press_global - self.frameGeometry().topLeft()
            self._press_time = time.time()
            self._move.stop()
            self._walking = False
        e.accept()

    def mouseMoveEvent(self, e):
        if self._dragging and e.buttons() & Qt.MouseButton.LeftButton:
            geo = self._union_geo()
            p = e.globalPosition().toPoint() - self._press_pos
            p.setX(max(geo.left(), min(p.x(), geo.right() - self.width())))
            p.setY(max(geo.top(), min(p.y(), geo.bottom() - self.height())))
            self.move(p)
        e.accept()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self._dragging:
            self._dragging = False
            # 位移很小且时间很短 → 视为点击（单击抚摸 / 双击睡觉）
            d = e.globalPosition().toPoint() - self._press_global
            if d.manhattanLength() < 8 and (time.time() - self._press_time) < 0.35:
                self._handle_click()
        e.accept()

    def _handle_click(self):
        """单击/双击判定：350ms 内两次点击 = 双击（切换睡觉/起床）"""
        now = time.time()
        if now - self._last_click_time < 0.35:
            self._click_pending = False
            self._last_click_time = 0.0
            self.toggle_sleep()
        else:
            self._last_click_time = now
            self._click_pending = True
            self._click_timer.start()

    def _fire_click(self):
        if self._click_pending:
            self._click_pending = False
            self.pet()

    def contextMenuEvent(self, e):
        menu = QMenu(self)
        menu.addAction("🍗 喂食", self.feed)
        menu.addAction("❤️ 抚摸", self.pet)
        menu.addAction("😴 睡觉/起床", self.toggle_sleep)
        menu.addAction("🎾 陪玩", self.play)
        menu.addSeparator()
        menu.addAction("💬 每日一言", self.act_quote)
        menu.addAction("🌏 60秒看世界", self.act_news)
        menu.addAction("🌤 今日天气", self.act_weather)
        menu.addAction("📜 每日诗词", self.act_poem)
        menu.addAction("💘 沙雕语录", self.act_humor)
        menu.addSeparator()
        menu.addAction("🎨 换动漫头像", self.act_anime)
        menu.addAction("⬇️ 下载头像", self.download_anime)
        menu.addSeparator()
        menu.addAction("⚙️ 设置面板", self.open_panel_requested.emit)
        on_top = menu.addAction("📌 窗口置顶")
        on_top.setCheckable(True)
        on_top.setChecked(self.cfg["always_on_top"])
        on_top.toggled.connect(self.set_always_on_top)
        menu.addSeparator()
        menu.addAction("退出程序", self.quit_requested.emit)
        menu.exec(e.globalPos())

    def hideEvent(self, e):
        # 隐藏时停掉移动动画，避免在看不见的地方乱跑
        self._move.stop()
        self._walking = False
        super().hideEvent(e)

    # ================= 配置操作 =================
    def set_always_on_top(self, flag: bool):
        """切换置顶（需要隐藏/显示窗口才会生效）"""
        if self.cfg["always_on_top"] == flag:
            return
        self.cfg["always_on_top"] = flag
        visible = self.isVisible()
        self.hide()
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, flag)
        if visible:
            self.show()

    def set_skin(self, key: str):
        """切换皮肤：动漫头像走网络图，其余重新生成动画帧"""
        self.cfg["skin"] = key
        save_config(self.cfg)
        self.skin_changed.emit(key)
        if key == ANIME_SKIN:
            self._enter_anime_mode()
            return
        self._anime_mode = False
        self._anime_timer.stop()
        self._sprites = sprites.SpriteSet(key)
        self.set_mode(self.mode)
        self._tick_anim()

    def apply_quote_schedule(self, enabled: bool, interval_s: float):
        """应用每日一言定时设置：enabled 开关，interval_s 间隔秒数"""
        self.cfg["quote_auto"] = bool(enabled)
        self.cfg["quote_interval_s"] = interval_s
        self._quote_loop.stop()
        if enabled and interval_s and interval_s > 0:
            self._quote_loop.setInterval(int(float(interval_s) * 1000))
            self._quote_loop.start()
            # 间隔较长时，启动后 8 秒先来一句；间隔 <=60 秒则停掉首条，避免连发两条
            if interval_s > 60:
                if not self._quote_first.isActive():
                    self._quote_first.start()
            else:
                self._quote_first.stop()
