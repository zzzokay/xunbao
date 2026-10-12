# -*- coding: utf-8 -*-
"""AI 过程脚本：按 _anim_draw 的同一套几何/配色，渲染「小车动画」造型预览。可随时删。"""
import os
import sys
import math

HERE = os.path.dirname(os.path.abspath(__file__))
ME = os.path.join(os.path.dirname(HERE), "map_editor")
sys.path.insert(0, ME)
import map_editor as E                                     # noqa: E402
from PIL import Image, ImageDraw, ImageFont                # noqa: E402

BG = (251, 251, 248)


def render(ang, label, w=104, h=66):
    im = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(im)
    cx, cy = w / 2.0, h / 2.0 + 5
    d.line([(0, cy), (w, cy)], fill=(30, 136, 229), width=7)          # 路线（蓝）
    rad = math.radians(ang)
    bx, by = cx - 30 * math.cos(rad), cy - 30 * math.sin(rad)
    d.line([(bx, by), (cx, cy)], fill=E.CAR_TRAIL, width=5)           # 尾迹
    body, glass, wheels = E.App._car_sprite_pts(cx, cy, ang)
    for wx, wy in wheels:
        d.ellipse([wx - 2.9, wy - 2.9, wx + 2.9, wy + 2.9], fill=E.CAR_WHEEL)
    d.polygon(body, fill=E.CAR_COLOR, outline=E.CAR_OUTLINE)
    d.polygon(glass, fill=E.CAR_GLASS)
    hx, hy = cx + 11 * math.cos(rad), cy + 11 * math.sin(rad)
    d.ellipse([hx - 1.8, hy - 1.8, hx + 1.8, hy + 1.8], fill=E.CAR_OUTLINE)
    try:
        f = ImageFont.truetype("msyh.ttc", 11)
    except Exception:                                                 # noqa: BLE001
        f = ImageFont.load_default()
    d.text((cx + 12, cy - 24), u"\u2192 " + label, fill=E.CAR_COLOR, font=f)
    return im


Z = 6
tiles = [render(a, lb) for a, lb in ((0, "N5"), (90, "N12"), (180, "B1"), (34, "P7"))]
tiles = [t.resize((t.width * Z, t.height * Z), Image.NEAREST) for t in tiles]
pad = 22
W = sum(t.width for t in tiles) + pad * (len(tiles) + 1)
H = tiles[0].height + pad * 2 + 34
sheet = Image.new("RGB", (W, H), (255, 255, 255))
x = pad
for t in tiles:
    sheet.paste(t, (x, pad))
    x += t.width + pad
try:
    f2 = ImageFont.truetype("msyh.ttc", 15)
except Exception:                                                     # noqa: BLE001
    f2 = ImageFont.load_default()
ImageDraw.Draw(sheet).text(
    (pad, pad + tiles[0].height + 8),
    u"小车动画造型（红车身 / 浅蓝前风挡 / 黑轮 / 浅红尾迹；车头随行进方向转）"
    u"　从左到右：向右 · 向下 · 向左 · 斜向",
    fill=(60, 60, 60), font=f2)
out = os.path.join(HERE, "小车动画_造型预览.png")
sheet.save(out)
print("saved", out, sheet.size)
