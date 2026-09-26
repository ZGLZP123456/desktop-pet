# -*- coding: utf-8 -*-
"""精灵帧生成器：用 Pillow 程序化绘制卡通小猫咪，无需任何外部素材。

所有动画帧在启动时一次性生成并缓存，之后只做缩放/镜像，性能开销极小。
"""
from __future__ import annotations

from PIL import Image, ImageDraw

SIZE = 160  # 精灵图原始尺寸（px），显示时由 QLabel 缩放

# 各皮肤配色：body 身体 / dark 描边 / belly 肚皮 / stripe 花纹 / cheek 内耳与腮红底色 / blush 腮红
SKINS = {
    "橘猫": {
        "body": (248, 170, 92), "dark": (205, 125, 55), "belly": (255, 226, 178),
        "stripe": (228, 148, 70), "cheek": (255, 205, 160), "blush": (255, 170, 150, 150),
    },
    "奶牛猫": {
        "body": (238, 238, 238), "dark": (140, 140, 140), "belly": (252, 252, 252),
        "stripe": (70, 70, 70), "cheek": (255, 205, 205), "blush": (255, 160, 160, 140),
    },
    "灰猫": {
        "body": (176, 182, 198), "dark": (118, 124, 142), "belly": (228, 232, 240),
        "stripe": (135, 141, 158), "cheek": (255, 210, 210), "blush": (255, 170, 170, 140),
    },
    "蓝猫": {
        "body": (143, 168, 205), "dark": (100, 125, 162), "belly": (216, 230, 248),
        "stripe": (110, 136, 172), "cheek": (255, 210, 210), "blush": (255, 170, 170, 140),
    },
    "粉粉猫": {
        "body": (252, 192, 206), "dark": (233, 140, 162), "belly": (255, 228, 236),
        "stripe": (242, 162, 182), "cheek": (255, 120, 150), "blush": (255, 130, 160, 160),
    },
}

# 每种姿势的参数：dy 身体上下浮动偏移，eyes/mouth 表情，extras 附加特效
POSES = {
    "idle0": dict(dy=0,  eyes="open",   mouth="smile", extras=()),
    "idle1": dict(dy=-4, eyes="open",   mouth="smile", extras=()),
    "blink": dict(dy=-2, eyes="closed", mouth="smile", extras=()),
    "walk0": dict(dy=-3, eyes="open",   mouth="smile", extras=()),
    "walk1": dict(dy=2,  eyes="open",   mouth="smile", extras=()),
    "sleep": dict(dy=6,  eyes="sleep",  mouth="flat",  extras=("zzz",)),
    "happy": dict(dy=-4, eyes="happy",  mouth="open",  extras=("hearts",)),
    "sad":   dict(dy=2,  eyes="open",   mouth="sad",   extras=("sweat",)),
    "eat":   dict(dy=0,  eyes="open",   mouth="open",  extras=("crumbs",)),
}


def _draw_heart(d: ImageDraw.ImageDraw, cx: float, cy: float, r: float, color):
    """画一颗爱心（两个圆 + 一个三角）"""
    d.ellipse((cx - r, cy - r, cx, cy), fill=color)
    d.ellipse((cx, cy - r, cx + r, cy), fill=color)
    d.polygon([(cx - r, cy), (cx, cy + r), (cx + r, cy)], fill=color)


def _draw_z(d: ImageDraw.ImageDraw, x: float, y: float, s: float, color):
    """画一个 Z 字（睡觉冒泡）"""
    d.line([(x, y), (x + s, y), (x, y + s), (x + s, y + s)],
           fill=color, width=max(2, int(s / 5)), joint="curve")


def _draw_eyes(d: ImageDraw.ImageDraw, cx: float, ey: float, kind: str, dark):
    for s in (-1, 1):
        ex = cx + s * 20
        if kind == "open":          # 圆眼睛 + 高光
            d.ellipse((ex - 7, ey - 9, ex + 7, ey + 9), fill=dark)
            d.ellipse((ex - 3, ey - 7, ex + 1, ey - 3), fill=(255, 255, 255, 255))
        elif kind == "closed":      # 闭眼（向下弯弧）
            d.arc((ex - 7, ey - 5, ex + 7, ey + 6), 200, 340, fill=dark, width=4)
        elif kind == "happy":       # 开心弯眼（∩）
            d.arc((ex - 7, ey - 9, ex + 7, ey + 3), 180, 360, fill=dark, width=4)
        elif kind == "sleep":       # 睡觉闭眼
            d.arc((ex - 7, ey - 6, ex + 7, ey + 5), 180, 360, fill=dark, width=4)


def _draw_mouth(d: ImageDraw.ImageDraw, cx: float, my: float, kind: str, dark):
    if kind == "smile":
        d.arc((cx - 7, my - 4, cx + 7, my + 10), 20, 160, fill=dark, width=3)
    elif kind == "open":            # 张嘴（吃/开心）
        d.ellipse((cx - 6, my - 2, cx + 6, my + 10), fill=(190, 90, 100, 255), outline=dark)
        d.arc((cx - 6, my - 2, cx + 6, my + 5), 180, 360, fill=(255, 175, 185, 255), width=2)
    elif kind == "sad":             # 委屈撇嘴
        d.arc((cx - 7, my + 2, cx + 7, my + 16), 200, 340, fill=dark, width=3)
    elif kind == "flat":
        d.line([(cx - 6, my + 4), (cx + 6, my + 4)], fill=dark, width=3)


def draw_frame(palette: dict, pose: str) -> Image.Image:
    """按姿势绘制一帧猫咪 RGBA 图"""
    cfg = POSES[pose]
    dy = cfg["dy"]
    body, dark, belly = palette["body"], palette["dark"], palette["belly"]
    stripe, cheek, blush = palette["stripe"], palette["cheek"], palette["blush"]

    im = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    cx = 80
    top = 60 + dy  # 身体椭圆顶边

    # ---- 尾巴（画在身体后面）----
    d.arc((cx + 28, top + 40, cx + 74, top + 98), 280, 45, fill=body, width=14)
    d.arc((cx + 28, top + 40, cx + 74, top + 98), 280, 45, fill=dark, width=2)

    # ---- 耳朵 ----
    d.polygon([(cx - 44, top + 4), (cx - 28, top - 30), (cx - 8, top + 4)], fill=body, outline=dark)
    d.polygon([(cx + 8, top + 4), (cx + 28, top - 30), (cx + 44, top + 4)], fill=body, outline=dark)
    d.polygon([(cx - 38, top + 2), (cx - 30, top - 16), (cx - 16, top + 2)], fill=cheek)
    d.polygon([(cx + 16, top + 2), (cx + 30, top - 16), (cx + 38, top + 2)], fill=cheek)

    # ---- 身体 ----
    d.ellipse((cx - 48, top, cx + 48, top + 80), fill=body, outline=dark, width=3)
    # 肚皮
    d.ellipse((cx - 26, top + 30, cx + 26, top + 72), fill=belly)
    # 头顶花纹
    d.arc((cx - 30, top - 6, cx - 6, top + 14), 180, 300, fill=stripe, width=5)
    d.arc((cx + 6, top - 6, cx + 30, top + 14), 240, 360, fill=stripe, width=5)

    # ---- 爪子 ----
    d.ellipse((cx - 30, top + 60, cx - 6, top + 82), fill=body, outline=dark, width=3)
    d.ellipse((cx + 6, top + 60, cx + 30, top + 82), fill=body, outline=dark, width=3)
    d.ellipse((cx - 24, top + 66, cx - 12, top + 78), fill=belly)
    d.ellipse((cx + 12, top + 66, cx + 24, top + 78), fill=belly)

    # ---- 脸 ----
    d.polygon([(cx - 5, top + 34), (cx + 5, top + 34), (cx, top + 42)], fill=(232, 110, 120, 255))  # 鼻子
    d.ellipse((cx - 40, top + 30, cx - 22, top + 46), fill=blush)  # 腮红
    d.ellipse((cx + 22, top + 30, cx + 40, top + 46), fill=blush)
    _draw_eyes(d, cx, top + 30, cfg["eyes"], dark)
    _draw_mouth(d, cx, top + 44, cfg["mouth"], dark)

    # ---- 胡须 ----
    wc = (120, 110, 110, 160)
    d.line([(cx - 38, top + 32), (cx - 58, top + 26)], fill=wc, width=2)
    d.line([(cx - 38, top + 40), (cx - 58, top + 40)], fill=wc, width=2)
    d.line([(cx + 38, top + 32), (cx + 58, top + 26)], fill=wc, width=2)
    d.line([(cx + 38, top + 40), (cx + 58, top + 40)], fill=wc, width=2)

    # ---- 附加特效 ----
    for fx in cfg["extras"]:
        if fx == "zzz":
            _draw_z(d, cx + 46, top - 40, 16, (125, 150, 255, 255))
            _draw_z(d, cx + 60, top - 24, 11, (125, 150, 255, 255))
        elif fx == "hearts":
            _draw_heart(d, cx - 54, top - 20, 10, (255, 90, 120, 235))
            _draw_heart(d, cx + 52, top - 12, 8, (255, 90, 120, 235))
            _draw_heart(d, cx - 30, top - 36, 7, (255, 90, 120, 200))
        elif fx == "crumbs":        # 干饭时嘴边的小饼干
            d.ellipse((cx + 34, top + 36, cx + 40, top + 42), fill=(255, 200, 120, 255))
            d.ellipse((cx + 43, top + 42, cx + 47, top + 46), fill=(255, 200, 120, 255))
        elif fx == "sweat":         # 委屈时头上冒汗
            d.arc((cx - 34, top - 16, cx - 14, top + 4), 180, 330, fill=(120, 180, 255, 220), width=4)

    return im


def _pil_to_qpixmap(img: Image.Image):
    """PIL 图转 QPixmap（保留引用防止缓冲区被回收）"""
    from PySide6.QtGui import QImage, QPixmap
    data = img.tobytes("raw", "RGBA")
    qimg = QImage(data, img.width, img.height, QImage.Format.Format_RGBA8888)
    pm = QPixmap.fromImage(qimg)
    return pm


class SpriteSet:
    """一组皮肤的完整动画帧缓存"""

    def __init__(self, skin_key: str):
        self.skin_key = skin_key
        self.palette = SKINS[skin_key]
        self.frames = {name: _pil_to_qpixmap(draw_frame(self.palette, name)) for name in POSES}


def tray_icon():
    """系统托盘/任务栏图标（开心的猫头）"""
    from PySide6.QtGui import QIcon
    img = draw_frame(SKINS["橘猫"], "happy").resize((64, 64), Image.LANCZOS)
    return QIcon(_pil_to_qpixmap(img))
