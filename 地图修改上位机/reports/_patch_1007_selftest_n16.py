# -*- coding: utf-8 -*-
"""10-07：_selftest 的 N16→N18 断言过时（地图已把 DLEFT 补上，现 flag=DLEFT|DRIGHT，
只剩多余 DRIGHT）。改成两层：①抓出现图多余 DRIGHT；②内存里人为写反再验一次。"""
import sys

path = r"C:\Users\14166\Desktop\MC_32\robotcup\xunbao\地图修改上位机\map_editor\_selftest.py"
old = '''        # N16→N18 是「左右写反」硬错，right_only 下必须仍能抓出来
        _it = next((x for x in ro if x["edge"] is e_n16), None)
        check(_it is not None and "DRIGHT" in _it["extra"] and "DLEFT" in _it["missing"],
              "right_only 仍能抓出 N16→N18 的左右写反（多余 DRIGHT、缺失 DLEFT）")
'''
new = '''        # 现图 N16→N18 flag=DLEFT|DRIGHT（几何只需 DLEFT）⇒ right_only 应报「多余 DRIGHT」
        _it = next((x for x in ro if x["edge"] is e_n16), None)
        check(_it is not None and "DRIGHT" in _it["extra"],
              "right_only 抓出 N16→N18 多余的 DRIGHT（现图 DLEFT|DRIGHT，几何只需 DLEFT）")
        # 「左右写反」硬错的抓取能力不能依赖真实地图碰巧是错的：内存里把 flag 改回只留
        # DRIGHT（写反态）再验一次，验完立刻还原（⑤ 已有先例：直接改 model 内存实例）
        _orig_flag = e_n16.flag
        e_n16.flag = "DRIGHT"
        _ro2 = M.analyze_junction_flags(model, only_plain=True, include_mul=False,
                                        right_only=True)
        e_n16.flag = _orig_flag
        _it2 = next((x for x in _ro2 if x["edge"] is e_n16), None)
        check(_it2 is not None and "DRIGHT" in _it2["extra"] and "DLEFT" in _it2["missing"],
              "人为写反（只留 DRIGHT）后 right_only 仍抓出 N16→N18（多余 DRIGHT、缺失 DLEFT）")
'''

raw = open(path, "rb").read()
crlf = raw.count(b"\r\n"); lf = raw.count(b"\n") - crlf
eol = b"\r\n" if crlf > lf and crlf > 0 else b"\n"
print("eol CRLF=%d LF=%d -> %r" % (crlf, lf, eol))
ob = old.replace("\n", "\r\n").encode("utf-8") if eol == b"\r\n" else old.encode("utf-8")
nb = new.replace("\n", "\r\n").encode("utf-8") if eol == b"\r\n" else new.encode("utf-8")
n = raw.count(ob)
assert n == 1, "old 出现 %d 次（应为 1）" % n
open(path, "wb").write(raw.replace(ob, nb))
print("写回 OK")

chk = open(path, "rb").read().decode("utf-8")
assert "人为写反（只留 DRIGHT）" in chk and old not in chk
d2 = open(path, "rb").read()
print("回读行尾 CRLF=%d LF=%d" % (d2.count(b"\r\n"), d2.count(b"\n") - d2.count(b"\r\n")))
