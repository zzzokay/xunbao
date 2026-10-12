# -*- coding: utf-8 -*-
"""10-07：_guismoke 二轮 N8 断言把「到 N8 的走法」写死成 N10→N8；
权重 3:2→2:3 后规划器改走 N10→N11→N12→N8。放宽成固件语义：经 N8 且 N8→N3。"""
import sys

path = r"C:\Users\14166\Desktop\MC_32\robotcup\xunbao\地图修改上位机\map_editor\_guismoke.py"
old = '''    check(_wpx is not None and "N8" in _wpx and "N10 -> N8" in " -> ".join(flat2 or []),
          "D5黑+D4绿 时固件 wp 明写 N8 ⇒ 经 N10→N8 再 N8→N3 是对的")
'''
new = '''    _flat2 = " -> ".join(flat2 or [])
    check(_wpx is not None and "N8" in _wpx and "N8 -> N3" in _flat2,
          "D5黑+D4绿 时固件 wp 明写 N8 ⇒ 路线经 N8 且 N8→N3 读 D4 回家"
          "（到 N8 走直达还是 N10→N11→N12→N8 由权重/地图定，不写死）")
'''

raw = open(path, "rb").read()
crlf = raw.count(b"\r\n"); lf = raw.count(b"\n") - crlf
eol = b"\r\n" if crlf > lf and crlf > 0 else b"\n"
ob = old.replace("\n", "\r\n").encode("utf-8") if eol == b"\r\n" else old.encode("utf-8")
nb = new.replace("\n", "\r\n").encode("utf-8") if eol == b"\r\n" else new.encode("utf-8")
n = raw.count(ob)
assert n == 1, "old 出现 %d 次（应为 1）" % n
open(path, "wb").write(raw.replace(ob, nb))
chk = open(path, "rb").read().decode("utf-8")
assert "不写死）" in chk and old not in chk
d2 = open(path, "rb").read()
print("写回 OK；回读 CRLF=%d LF=%d" % (d2.count(b"\r\n"), d2.count(b"\n") - d2.count(b"\r\n")))
