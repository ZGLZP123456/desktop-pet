# -*- coding: utf-8 -*-
"""好玩接口：一言 / 60秒看世界 / 天气 / 每日诗词 / 沙雕语录

全部使用 QNetworkAccessManager 异步请求，绝不阻塞界面；接口不可用时回退本地提示。
所有接口均已实测可访问（2026-09，无需 key）。
"""
from __future__ import annotations

import json
from urllib.parse import quote

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

# WMO 天气代码 -> 中文描述
WMO = {
    0: "晴", 1: "基本晴", 2: "多云", 3: "阴", 45: "有雾", 48: "雾凇",
    51: "毛毛雨", 53: "毛毛雨", 55: "毛毛雨", 56: "冻毛毛雨", 57: "冻毛毛雨",
    61: "小雨", 63: "中雨", 65: "大雨", 66: "冻雨", 67: "冻雨",
    71: "小雪", 73: "中雪", 75: "大雪", 77: "雪粒",
    80: "阵雨", 81: "阵雨", 82: "强阵雨", 85: "阵雪", 86: "阵雪",
    95: "雷阵雨", 96: "雷阵雨伴冰雹", 99: "雷阵雨伴冰雹",
}


def _is_image(data: bytes) -> bool:
    """简单图片魔数校验：JPEG / PNG / GIF / WebP"""
    return (data[:3] == b"\xff\xd8\xff"                            # JPEG
            or data[:4] == b"\x89PNG"                              # PNG
            or data[:4] == b"GIF8"                                 # GIF
            or (data[:4] == b"RIFF" and data[8:12] == b"WEBP"))    # WebP


class FunApi(QObject):
    quote_ready = Signal(str)    # 每日一言
    news_ready = Signal(list)    # 60秒看世界 -> [str, ...]
    weather_ready = Signal(str)  # 今日天气
    poem_ready = Signal(str)     # 每日诗词
    humor_ready = Signal(str)    # 沙雕语录
    anime_ready = Signal(bytes)  # 动漫头像图片字节
    failed = Signal(str)         # 请求失败提示

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mgr = QNetworkAccessManager(self)

    # ---------------- 通用请求 ----------------
    def _get(self, url: str, ok, fallback: str, timeout: int = 6000):
        req = QNetworkRequest(QUrl(url))
        req.setRawHeader(b"User-Agent", b"Mozilla/5.0 DesktopPet")
        try:
            req.setTransferTimeout(timeout)
        except Exception:
            pass
        reply = self._mgr.get(req)
        reply.finished.connect(lambda r=reply: self._on_done(r, ok, fallback))

    def _on_done(self, reply: QNetworkReply, ok, fallback: str):
        try:
            if reply.error() == QNetworkReply.NetworkError.NoError:
                data = bytes(reply.readAll())
                if data:
                    ok(self, data)
                    return
            self.failed.emit(fallback)
        except Exception:
            self.failed.emit(fallback)
        finally:
            reply.deleteLater()

    @staticmethod
    def _json(data: bytes):
        try:
            return json.loads(data.decode("utf-8", "ignore"))
        except Exception:
            return None

    @staticmethod
    def _text(data: bytes) -> str:
        return data.decode("utf-8", "ignore").strip()

    # ---------------- 每日一言（hitokoto） ----------------
    def fetch_quote(self):
        def ok(api, data):
            text = (api._json(data) or {}).get("hitokoto")
            if text:
                api.quote_ready.emit(f"「{text}」")
                return
            api.failed.emit("一言接口开了个小差")
        self._get("https://v1.hitokoto.cn/?c=d&c=i&c=k", ok, "一言接口开了个小差")

    # ---------------- 每日诗词（hitokoto 诗词类） ----------------
    def fetch_poem(self):
        def ok(api, data):
            j = api._json(data) or {}
            text = j.get("hitokoto")
            if text:
                from_who = j.get("from") or "佚名"
                api.poem_ready.emit(f"「{text}」——《{from_who}》")
                return
            api.failed.emit("诗词接口开了个小差")
        self._get("https://v1.hitokoto.cn/?c=i", ok, "诗词接口开了个小差")

    # ---------------- 沙雕语录（hitokoto 抖机灵类） ----------------
    def fetch_humor(self):
        def ok(api, data):
            text = (api._json(data) or {}).get("hitokoto")
            if text:
                api.humor_ready.emit(text)
                return
            api.failed.emit("语录接口开了个小差")
        self._get("https://v1.hitokoto.cn/?c=l", ok, "语录接口开了个小差")

    # ---------------- 60秒看世界（60s.viki.moe 每日快讯） ----------------
    def fetch_news(self):
        def ok(api, data):
            j = api._json(data)
            if isinstance(j, dict):
                j = j.get("data", j)
            news = (j or {}).get("news") or []
            items = [api._text(str(n).encode("utf-8")) if isinstance(n, str) else str(n)
                     for n in news if str(n).strip()]
            items = [s for s in items if s]
            if items:
                api.news_ready.emit(items)
                return
            api.failed.emit("快讯接口开了个小差")
        self._get("https://60s.viki.moe/v2/60s", ok, "快讯接口开了个小差")

    # ---------------- 动漫头像（dmoe 主源，失败自动换 mwm） ----------------
    def fetch_anime(self):
        state = {"tried": 0}

        def ok(api, data):
            if _is_image(data):
                api.anime_ready.emit(data)
                return
            if state["tried"] == 0:      # 主源返回了非图片，换备胎再试一次
                state["tried"] = 1
                api._get("https://t.mwm.moe/mp", ok, "头像接口开了个小差")
                return
            api.failed.emit("头像接口开了个小差")

        self._get("https://www.dmoe.cc/random.php", ok, "头像接口开了个小差")

    # ---------------- 今日天气（Open-Meteo，无需 key） ----------------
    def fetch_weather(self, city: str):
        city = (city or "北京").strip() or "北京"

        def on_geo(api, data):
            results = (api._json(data) or {}).get("results") or []
            if not results:
                api.failed.emit(f"没找到城市「{city}」，换个试试～")
                return
            r = results[0]
            lat, lon = r["latitude"], r["longitude"]
            name = r.get("name") or city
            fcast = (f"https://api.open-meteo.com/v1/forecast?"
                     f"latitude={lat}&longitude={lon}&current_weather=true")

            def on_weather(api2, data2):
                cw = (api2._json(data2) or {}).get("current_weather") or {}
                temp = cw.get("temperature")
                wind = cw.get("windspeed")
                desc = WMO.get(cw.get("weathercode", 0), "未知")
                if temp is None:
                    api2.failed.emit("天气接口开了个小差")
                    return
                api2.weather_ready.emit(f"{name}：{desc}，{temp}°C，风速{wind}km/h")

            self._get(fcast, on_weather, "天气接口开了个小差")

        url = ("https://geocoding-api.open-meteo.com/v1/search?"
               f"name={quote(city)}&count=1&language=zh&format=json")
        self._get(url, on_geo, "天气接口开了个小差")
