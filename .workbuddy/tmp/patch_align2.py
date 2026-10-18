# -*- coding: utf-8 -*-
# 上位机两时刻对齐收尾：回显措辞 + P1 特例说明（读表时刻/阈值数字）。
import pathlib

ME = pathlib.Path(r"C:/Users/14166/Desktop/MC_32/robotcup/xunbao/地图修改上位机/map_editor/map_editor.py")

def probe(path):
    b = path.read_bytes()
    crlf = b.count(b"\r\n"); lf = b.count(b"\n") - crlf
    assert (crlf == 0) or (lf == 0)
    return "\r\n" if crlf >= lf else "\n"

E = []

# 1) 报告回显：与下拉新名一致（这一时刻喂尾段裁剪）
E.append(('''            lines.append("比赛已用时 = %d s（%s）⇒ 尾段按时间预算裁剪，见下面「时间预算」段"
''',
'''            lines.append("出门已用时（N3/N5）= %d s（%s）⇒ 尾段按时间预算裁剪，见下面「时间预算」段"
''', 1))

# 2) 对话框说明：P1 特例（读表时刻在 P1 取宝那刻）+ 阈值数字对齐 config（125/135）
E.append(('''                            "出门（N3/N5）= 选了就会按时间预算裁剪尾段"
                            "（宝物在 P1 另有更紧的 2:15 / 2:25 两档，见「时间预算…」）；"
''',
'''                            "出门（N3/N5）= 选了就会按时间预算裁剪尾段"
                            "（宝物=P1 时固件这次读表在 P1 取宝那一刻，阈值也更紧：2:05 / 2:15，见「时间预算…」）；"
''', 1))

# 3) 解析函数 docstring：说明两个下拉共用这一份解析
E.append(('''        """「比赛已用时」下拉 → 秒数（None = 不启用时间裁剪）。"""
''',
'''        """已用时下拉（「出门 N3/N5」与「规划回程 P7/P8」共用）→ 秒数（None = 不启用）。"""
''', 1))

eol = probe(ME)
data = ME.read_bytes().decode("utf-8")
for i, (old, new, want) in enumerate(E):
    o = old.replace("\n", eol); n = new.replace("\n", eol)
    cnt = data.count(o)
    assert cnt == want, "edit#%d 命中 %d 次（应为 %d）" % (i, cnt, want)
    data = data.replace(o, n)
ME.write_bytes(data.encode("utf-8"))
print("[WROTE] map_editor.py：%d 组替换" % len(E))
