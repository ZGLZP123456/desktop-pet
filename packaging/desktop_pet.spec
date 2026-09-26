# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置：桌面宠物

用 onedir 模式（不是 onefile）：
  - onefile 每次启动都要把上百 MB 解压到临时目录，启动慢好几秒
  - onedir 启动即用，且交给安装程序分发正合适

程序运行所需的全部资源（猫咪精灵、音效）都是运行时代码生成，
用户数据写到 %APPDATA%\\桌面宠物，所以这里不需要打包任何数据文件。
"""
from pathlib import Path

ROOT = Path(SPECPATH).parent

# 明确排除用不到的大体积模块，显著减小打包体积
EXCLUDES = [
    # 只用 PySide6，其它 GUI 框架全排除
    "PyQt5", "PyQt6", "PySide2", "tkinter", "_tkinter",
    # 没用到的重型 Qt 模块
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
    "PySide6.QtQuick", "PySide6.QtQuick3D", "PySide6.QtQml", "PySide6.QtQuickWidgets",
    "PySide6.Qt3DCore", "PySide6.Qt3DRender", "PySide6.Qt3DInput", "PySide6.Qt3DLogic",
    "PySide6.Qt3DAnimation", "PySide6.Qt3DExtras",
    "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets",
    "PySide6.QtCharts", "PySide6.QtDataVisualization", "PySide6.QtGraphs",
    "PySide6.QtBluetooth", "PySide6.QtNfc", "PySide6.QtSerialPort",
    "PySide6.QtPositioning", "PySide6.QtLocation", "PySide6.QtSql",
    "PySide6.QtTest", "PySide6.QtDesigner", "PySide6.QtHelp", "PySide6.QtUiTools",
    "PySide6.QtWebSockets", "PySide6.QtWebChannel", "PySide6.QtPdf", "PySide6.QtPdfWidgets",
    # 没用到的科学计算 / 开发工具
    "numpy", "matplotlib", "pandas", "scipy", "IPython", "pytest",
    "setuptools", "pip", "pydoc_data",
]

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDES,
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="DesktopPet",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,               # UPX 压缩容易触发杀软误报，关闭
    console=False,           # GUI 程序，不弹黑色控制台
    disable_windowed_traceback=False,   # 崩溃时弹窗显示堆栈，便于排查
    icon=str(ROOT / "packaging" / "app.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="DesktopPet",
)
