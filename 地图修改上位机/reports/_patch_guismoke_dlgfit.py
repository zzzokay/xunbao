# -*- coding: utf-8 -*-
"""AI 过程脚本：给 _guismoke 加"对话框按内容自适应"的防回归断言（用户报过内容被裁）。"""
import os

G = os.path.join(r"C:\Users\14166\Desktop\MC_32\robotcup\xunbao", "地图修改上位机",
                 "map_editor", "_guismoke.py")
OLD = ('    # 随「保存布局」持久化（沙箱文件，绝不碰真实布局）\n')
NEW = ('    # --- 两个对话框必须"按内容自适应"（曾写死几何 ⇒ 内容 1348px 挤进 660px 窗口，\n'
       '    #     右边整段看不见 —— 用户报「窗口打开不能完整显示内容」）---\n'
       '    step("dialogs fit their content")\n'
       '    for _opener, _name in ((app.plan_clue_route_dialog, "线索路线"),\n'
       '                           (app.plan_round2_route_dialog, "二轮路线")):\n'
       '        _opener()\n'
       '        app.update_idletasks()\n'
       '        _t = [w for w in app.winfo_children() if isinstance(w, tk.Toplevel)][-1]\n'
       '        _f = _t.winfo_children()[0]\n'
       '        check(_f.winfo_reqwidth() + 24 <= _t.winfo_width()\n'
       '              and _f.winfo_reqheight() + 24 <= _t.winfo_height(),\n'
       '              "%s 对话框装得下内容（内容 %dx%d ≤ 窗口 %dx%d）"\n'
       '              % (_name, _f.winfo_reqwidth(), _f.winfo_reqheight(),\n'
       '                 _t.winfo_width(), _t.winfo_height()))\n'
       '        _t.destroy()\n'
       '        app.update()\n'
       '\n'
       '    # 随「保存布局」持久化（沙箱文件，绝不碰真实布局）\n')


def main():
    with open(G, "rb") as f:
        data = f.read()
    eol = "\r\n" if data.count(b"\r\n") else "\n"
    ob = OLD.replace("\n", eol).encode("utf-8")
    nb = NEW.replace("\n", eol).encode("utf-8")
    assert data.count(ob) == 1, "命中 %d 次" % data.count(ob)
    with open(G, "wb") as f:
        f.write(data.replace(ob, nb))
    print("[ok] _guismoke.py 加了对话框尺寸断言")


if __name__ == "__main__":
    main()
