# -*- coding: utf-8 -*-
"""打包辅助：生成程序图标 app.ico

直接用程序里的猫咪精灵绘制逻辑，保证图标与宠物形象一致，
多尺寸图标（16~256）由 Pillow 自动生成，Windows 各场景都清晰。
"""
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from pet_desktop.sprites import SKINS, draw_frame  # noqa: E402

OUT = ROOT / "packaging" / "app.ico"
SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def main():
    # 用橘猫的待机脸做图标：形象干净，缩到 16x16 也清晰可辨
    # （不用带爱心特效的开心姿势，小尺寸下那些装饰会变成噪点）
    img = draw_frame(SKINS["橘猫"], "idle0")
    # 裁掉透明边，让猫脸在图标里占满
    bbox = img.getbbox()
    if bbox:
        img = img.crop(bbox)
    # 补成正方形，保持居中
    side = max(img.width, img.height)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.paste(img, ((side - img.width) // 2, (side - img.height) // 2), img)

    # 精灵原始尺寸只有 160px，Pillow 不会自动放大，
    # 必须先升采样到最大图标尺寸，否则 ICO 里不会有 256 那一档
    square = square.resize((256, 256), Image.LANCZOS)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    square.save(OUT, format="ICO", sizes=SIZES)
    print(f"图标已生成: {OUT}  ({OUT.stat().st_size} bytes, {len(SIZES)} 种尺寸)")


if __name__ == "__main__":
    main()
