# -*- coding: utf-8 -*-
"""AI 过程脚本：修「线索路线…」对话框内容被裁（提示行没 wraplength ⇒ 内容 1348px 挤进 660px 窗口）。

1) 给提示行加 wraplength/justify（根因）；
2) 两个对话框都改成**按内容自适应**尺寸 + minsize（以后加控件不会再被裁）。
"""
import os

E = os.path.join(r"C:\Users\14166\Desktop\MC_32\robotcup\xunbao", "地图修改上位机",
                 "map_editor", "map_editor.py")
EDITS = []


def rep(old, new):
    EDITS.append((old, new))


# 1) 线索对话框提示行：加 wraplength
rep('        ttk.Label(frm, text="（回程走哪个门区入口不用选：由上面 4 格门灯自动推；"\n'
    '                            "补打卡 = P3P4_PUNCH_ENABLE（缺哪个补哪个）；"\n'
    '                            "巡回 = UPRIGHT_TOUR_ENABLE（一轮宝物 P3→S1/P4→S2，二轮两个都绕）；"\n'
    '                            "这些选择会记住，随「保存布局」一起存，重启也在）",\n'
    '                  foreground="#666666").grid(row=8, column=0, columnspan=2,\n'
    '                                             sticky="w", pady=(6, 0))\n',
    '        ttk.Label(frm, text="（回程走哪个门区入口不用选：由上面 4 格门灯自动推；"\n'
    '                            "补打卡 = P3P4_PUNCH_ENABLE（缺哪个补哪个）；"\n'
    '                            "巡回 = UPRIGHT_TOUR_ENABLE（一轮宝物 P3→S1/P4→S2，二轮两个都绕）；"\n'
    '                            "这些选择会记住，随「保存布局」一起存，重启也在）",\n'
    '                  foreground="#666666", wraplength=620, justify="left").grid(\n'
    '            row=8, column=0, columnspan=2, sticky="w", pady=(6, 0))\n')

# 2) 线索对话框：按钮之后按内容自适应
rep('        buttons = ttk.Frame(frm)\n'
    '        buttons.grid(row=9, column=0, columnspan=2, sticky="w", pady=(14, 0))\n'
    '        ttk.Button(buttons, text="显示路线", command=run).pack(side="left")\n'
    '        ttk.Button(buttons, text="取消", command=dlg.destroy).pack(side="left", padx=8)\n',
    '        buttons = ttk.Frame(frm)\n'
    '        buttons.grid(row=9, column=0, columnspan=2, sticky="w", pady=(14, 0))\n'
    '        ttk.Button(buttons, text="显示路线", command=run).pack(side="left")\n'
    '        ttk.Button(buttons, text="取消", command=dlg.destroy).pack(side="left", padx=8)\n'
    '        _fit_dialog(dlg, frm, 660, 490)\n')

# 3) 二轮对话框：按钮之后按内容自适应
rep('        ttk.Button(btns, text="关闭", command=dlg.destroy).pack(side="left", padx=8)\n'
    '        ttk.Label(btns, text="⚠ 只有「写回 config.h…」才动固件",\n'
    '                  foreground="#a04000").pack(side="left", padx=10)\n',
    '        ttk.Button(btns, text="关闭", command=dlg.destroy).pack(side="left", padx=8)\n'
    '        ttk.Label(btns, text="⚠ 只有「写回 config.h…」才动固件",\n'
    '                  foreground="#a04000").pack(side="left", padx=10)\n'
    '        _fit_dialog(dlg, frm, 740, 560)\n')

# 4) 新增模块级辅助函数（放在 _norm180 之后那一族工具函数里）
rep('def _flat_pts(pts):\n'
    '    """[(x, y), ...] → [x, y, x, y, ...]（Tk 的 create_polygon/create_line 要扁平坐标）。"""\n'
    '    out = []\n'
    '    for p in pts:\n'
    '        out.extend(p)\n'
    '    return out\n',
    'def _flat_pts(pts):\n'
    '    """[(x, y), ...] → [x, y, x, y, ...]（Tk 的 create_polygon/create_line 要扁平坐标）。"""\n'
    '    out = []\n'
    '    for p in pts:\n'
    '        out.extend(p)\n'
    '    return out\n'
    '\n'
    '\n'
    'def _fit_dialog(dlg, frm, minw, minh):\n'
    '    """把对话框调到"刚好装下内容"的尺寸（并设 minsize），免得新增控件被裁。\n'
    '\n'
    '    ⚠️ 一律用**内容实测**的 req 尺寸，别再写死一个几何值 —— 写死的那个一旦小于内容，\n'
    '       就会像「线索路线…」那样：内容 1348px 挤进 660px 窗口，右边整段看不见。\n'
    '    """\n'
    '    dlg.update_idletasks()\n'
    '    w = max(minw, frm.winfo_reqwidth() + 24)\n'
    '    h = max(minh, frm.winfo_reqheight() + 24)\n'
    '    sw, sh = dlg.winfo_screenwidth(), dlg.winfo_screenheight()\n'
    '    w, h = min(w, sw - 40), min(h, sh - 60)      # 别超出屏幕\n'
    '    dlg.geometry("%dx%d" % (w, h))\n'
    '    dlg.minsize(w, h)\n'
    '    return w, h\n')


def main():
    with open(E, "rb") as f:
        data = f.read()
    eol = "\r\n" if data.count(b"\r\n") else "\n"
    for old, new in EDITS:
        ob = old.replace("\n", eol).encode("utf-8")
        nb = new.replace("\n", eol).encode("utf-8")
        cnt = data.count(ob)
        assert cnt == 1, "命中 %d 次（期望 1）:\n%r" % (cnt, old[:90])
        data = data.replace(ob, nb)
    with open(E, "wb") as f:
        f.write(data)
    print("[ok] map_editor.py +%d 处, crlf=%d lf=%d"
          % (len(EDITS), data.count(b"\r\n"), data.count(b"\n") - data.count(b"\r\n")))


if __name__ == "__main__":
    main()
