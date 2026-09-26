# -*- coding: utf-8 -*-
"""配置与宠物状态：JSON 持久化 + 开机自启（注册表）"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path


def _data_dir() -> Path:
    """可写数据目录。

    源码运行时用程序根目录（方便调试和备份）；
    打包成 exe 后必须改用 %APPDATA%，因为 PyInstaller 的解包目录是临时的，
    写进去的文件退出即丢失，且安装到 Program Files 时也没有写权限。
    """
    if getattr(sys, "frozen", False):
        base = Path(os.environ.get("APPDATA") or Path.home()) / "桌面宠物"
    else:
        base = Path(__file__).resolve().parent.parent
    try:
        base.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return base


APP_DIR = Path(__file__).resolve().parent.parent  # 程序资源所在目录（只读）
DATA_DIR = _data_dir()                            # 用户数据目录（可写）
CONFIG_FILE = DATA_DIR / "pet_config.json"
STATE_FILE = DATA_DIR / "pet_state.json"
LOCK_FILE = DATA_DIR / "pet.lock"
ASSET_DIR = DATA_DIR / "assets"

DEFAULT_CONFIG = {
    "pet_name": "团子",          # 宠物名字
    "skin": "橘猫",              # 皮肤
    "size": 160,                 # 宠物大小(px)
    "walk_speed": 220,           # 漫步速度 px/s
    "auto_walk": True,           # 是否自动走动
    "walk_min": 8,               # 两次走动的最小间隔(秒)
    "walk_max": 25,              # 两次走动的最大间隔(秒)
    "speech_freq": 60,           # 随机说话频率 0-100 %
    "quote_auto": True,          # 是否定时自动拉取每日一言
    "quote_interval_s": 14400,   # 每日一言自动刷新间隔(秒)，默认 4 小时
    "anime_auto": True,          # 动漫头像皮肤下是否自动换图
    "anime_interval_s": 3600,    # 动漫头像自动换图间隔(秒)，默认 1 小时
    "city": "北京",              # 天气查询城市
    "always_on_top": True,       # 窗口置顶
    "sound": True,               # 提示音
    "autostart": False,          # 开机自启（以注册表为准，这里仅记录）
}

DEFAULT_STATE = {
    "hunger": 85.0,              # 饱腹度 0-100
    "mood": 80.0,                # 心情 0-100
    "energy": 100.0,             # 体力 0-100
    "sleeping": False,           # 是否在睡觉
    "last_tick": None,           # 上次保存时间（用于离线衰减计算）
}


def _load(path: Path, defaults: dict) -> dict:
    """读取 JSON 并与默认值合并，损坏时静默回退到默认值"""
    data = dict(defaults)
    try:
        if path.exists():
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                data.update({k: v for k, v in raw.items() if k in defaults})
    except Exception:
        pass
    return data


def _save(path: Path, data: dict):
    """原子写入：先写临时文件再替换，避免崩溃损坏数据"""
    try:
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
    except Exception:
        pass


def load_config() -> dict:
    return _load(CONFIG_FILE, DEFAULT_CONFIG)


def save_config(cfg: dict):
    _save(CONFIG_FILE, cfg)


def load_state() -> dict:
    state = _load(STATE_FILE, DEFAULT_STATE)
    # 离线期间的状态衰减：每分钟饱腹/体力 -1.5
    last = state.get("last_tick")
    if isinstance(last, str):
        try:
            dt = datetime.fromisoformat(last)
            minutes = (datetime.now() - dt).total_seconds() / 60.0
            if minutes > 0:
                state["hunger"] = max(0.0, state["hunger"] - 1.5 * minutes)
                state["energy"] = max(0.0, state["energy"] - 1.5 * minutes)
                if state["energy"] <= 5 and not state["sleeping"]:
                    state["sleeping"] = True  # 体力耗尽，自动入睡
        except Exception:
            pass
    return state


def save_state(state: dict):
    state["last_tick"] = datetime.now().isoformat(timespec="seconds")
    _save(STATE_FILE, state)


def reset_state():
    """恢复默认状态"""
    save_state(dict(DEFAULT_STATE))


# ---------- 开机自启（Windows 注册表 HKCU Run） ----------
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_NAME = "桌面宠物"


def _pythonw() -> str:
    """优先使用 pythonw.exe，开机自启时不弹黑色控制台窗口"""
    exe = Path(sys.executable)
    w = exe.with_name(exe.stem + "w" + exe.suffix)
    return str(w) if w.exists() else str(exe)


def _launch_command() -> str:
    """开机自启的启动命令：打包后直接指向 exe，源码运行则用 pythonw + main.py"""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    return f'"{_pythonw()}" "{APP_DIR / "main.py"}"'


def set_autostart(enabled: bool) -> bool:
    if sys.platform != "win32":
        return False
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE)
        try:
            if enabled:
                winreg.SetValueEx(key, RUN_NAME, 0, winreg.REG_SZ, _launch_command())
            else:
                try:
                    winreg.DeleteValue(key, RUN_NAME)
                except FileNotFoundError:
                    pass
        finally:
            winreg.CloseKey(key)
        return True
    except Exception:
        return False


def is_autostart() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, RUN_NAME)
            return True
    except (FileNotFoundError, OSError):
        return False
    except Exception:
        return False
