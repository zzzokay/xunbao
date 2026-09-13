from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(r"C:\Users\14166\Desktop\MC_32\robotcup\xunbao\寻宝地图")
FONT = r"C:\Windows\Fonts\msyh.ttc"


def font(size):
    return ImageFont.truetype(FONT, size)


def centered(draw, box, text, fill, size):
    x0, y0, x1, y1 = box
    f = font(size)
    left, top, right, bottom = draw.textbbox((0, 0), text, font=f)
    draw.text(((x0 + x1 - (right - left)) / 2, (y0 + y1 - (bottom - top)) / 2 - top), text, font=f, fill=fill)


def edit_node_map(src, dst):
    image = Image.open(src).convert("RGB")
    draw = ImageDraw.Draw(image)
    # The two white node boxes in 节点图.jpg: old P6 is upper, old P8 is lower-left.
    upper = (320, 430, 402, 514)
    lower = (120, 820, 203, 906)
    draw.rectangle(upper, fill="white")
    draw.rectangle(lower, fill="white")
    centered(draw, upper, "P8", "#d71920", 48)
    centered(draw, lower, "P6", "#d71920", 48)
    image.save(dst, quality=95)


def edit_rule_map(src, dst):
    image = Image.open(src).convert("RGB")
    draw = ImageDraw.Draw(image)
    # Replace the platform captions while leaving the platform geometry and leader lines intact.
    old_six = (421, 383, 500, 448)
    old_eight = (232, 677, 315, 738)
    caption_fill = "#d7e2b5"
    draw.rectangle(old_six, fill=caption_fill)
    draw.rectangle(old_eight, fill=caption_fill)
    centered(draw, old_six, "P8", "#c51f25", 28)
    centered(draw, old_eight, "P6", "#c51f25", 28)
    image.save(dst, quality=95)


edit_node_map(ROOT / "节点图.jpg", ROOT / "节点图_P6_P8已交换.jpg")
edit_rule_map(ROOT / "f757242c8fa840d54b66f6c72a6827dc.png", ROOT / "规则图_P6_P8已交换.png")
print("created")
