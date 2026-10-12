# -*- coding: utf-8 -*-
"""给编辑器窗口截一张图，展示左栏新的「转弯补偿」表。（只读，不改任何文件）"""
import os, sys
HERE = os.path.dirname(os.path.split(os.path.abspath(__file__))[0])   # reports 的上级 = 地图修改上位机
sys.path.insert(0, os.path.join(HERE, "map_editor"))
os.chdir(os.path.join(HERE, "map_editor"))
import map_editor as E

out = os.path.join(HERE, "reports", "left_turn_list.png")
app = E.App()
# ⚠️ 本机可能已经开着一个旧编辑器窗口；挪到别处 + 置顶，确保截到的是"我们自己这个"。
app.geometry("1500x920+80+60")
# 选中最长的新档名，验证下拉没被左栏裁掉
app.turn_view.set("只看实测停车转")
app._fill_turn_list()
app.attributes("-topmost", True)
app.lift()
app.update_idletasks()
app.update()
app.after(400, lambda: None)
app.update()

try:
    from PIL import ImageGrab
    x, y = app.winfo_rootx(), app.winfo_rooty()
    w, h = app.winfo_width(), app.winfo_height()
    img = ImageGrab.grab(bbox=(x, y, x + w, y + h))
    img.save(out)
    print("SAVED", out, img.size)
except Exception as ex:                                   # noqa: BLE001
    print("截图失败：%r" % (ex,))
app.destroy()
