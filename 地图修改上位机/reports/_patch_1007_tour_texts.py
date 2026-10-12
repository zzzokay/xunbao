# -*- coding: utf-8 -*-
"""10-07：把「巡回」的两处旧文案改成新语义（S1/S2 跟着「会不会去 P3/P4」走）。
字节级替换：先探测 eol、assert count==1、全部成功才写盘。"""
import sys

EDITS = {
    r"C:\Users\14166\Desktop\MC_32\robotcup\xunbao\地图修改上位机\map_editor\map_editor.py": [
        # 报告头（map_editor.py:4402）
        ("；一轮宝物 P3→S1、P4→S2；二轮 P3 后绕 S1、P4 后绕 S2",
         "；一轮 S1/S2 跟着「回程会不会去 P3/P4」走（补打卡开着时交错成 P3→S1→P4→S2，"
         "关着则宝物 P3→S1、P4→S2）；二轮 P3 后绕 S1、P4 后绕 S2"),
        # 对话框提示（map_editor.py:4604）
        ("巡回 = UPRIGHT_TOUR_ENABLE（一轮宝物 P3→S1/P4→S2，二轮两个都绕）；",
         "巡回 = UPRIGHT_TOUR_ENABLE（一轮跟着「会不会去 P3/P4」绕 S1/S2，"
         "与补打卡交错成 P3→S1→P4→S2，二轮两个都绕）；"),
    ],
    r"C:\Users\14166\Desktop\MC_32\robotcup\xunbao\地图修改上位机\map_editor\_guismoke.py": [
        ("\"upright_tour_waypoints：一轮宝物 P3→S1、P4→S2，其余宝物不绕\"",
         "\"upright_tour_waypoints：补打卡关时宝物 P3→S1、P4→S2，其余宝物不绕\""),
    ],
}

for path, pairs in EDITS.items():
    raw = open(path, "rb").read()
    crlf = raw.count(b"\r\n")
    lf = raw.count(b"\n") - crlf
    eol = b"\r\n" if crlf >= lf and crlf > 0 else b"\n"
    print("%s  CRLF=%d LF=%d -> 用 %r" % (path.split("\\")[-1], crlf, lf, eol))
    data = raw
    for i, (old, new) in enumerate(pairs):
        ob = old.encode("utf-8")
        nb = new.encode("utf-8")
        n = data.count(ob)
        assert n == 1, "old#%d 在 %s 出现 %d 次（应为 1）" % (i, path, n)
        data = data.replace(ob, nb)
    # 全部成功才写盘
    open(path, "wb").write(data)
    print("  写回 OK，%d 处替换" % len(pairs))

# 回读校验
for path, pairs in EDITS.items():
    chk = open(path, "rb").read().decode("utf-8")
    for old, new in pairs:
        assert old not in chk and new in chk
print("回读校验通过")
