# -*- coding: utf-8 -*-
"""AI 过程脚本：把仿真里那段"补打卡预演"换成"门回程 wp 对比表"（更直观、不跑状态机）。"""
import os

S = os.path.join(r"C:\Users\14166\Desktop\MC_32\robotcup\xunbao", "地图修改上位机",
                 "tools", "sim_route_bookkeeping.py")
OLD = ('    # 补打卡开关打开后的预演（只改仿真入参，不碰任何文件）：\n'
       '    # 宝物选 P1（=2）⇒ 回程腿与 P3/P4 无关，补打卡才看得清楚；\n'
       '    # 线索=3（去程去过 P3）⇒ 只补 P4；线索=0（两个都没去）⇒ 两个都补。\n'
       '    for _clue, _tag in ((3, "只补 P4"), (0, "两个都补")):\n'
       '        run_case("补打卡预演（线索=%d → 一轮回家腿%s）" % (_clue, _tag), _clue, 5, 7,\n'
       '                 [ONE_WAY_PASS, CAN_PASS, CAN_PASS, NO_PASS, NO_PASS], 0,\n'
       '                 punch=True, treasure_at_clue=2)\n')
NEW = ('    # 补打卡开关：一轮「门回程」wp 直出（只调镜像函数，不跑状态机 ——\n'
       '    # 上面 run_case 的预设本身就会复现 Route_Error_Stop，从日志里看不出 wp 差异）\n'
       '    print("=" * 78)\n'
       '    print("P3P4_PUNCH_ENABLE：一轮「门回程」wp 对比（关 → 开）"\n'
       '          "　※ P3/P4 插在宝物平台之后、P2 之前")\n'
       '    for _clue, _tre in ((3, 2), (4, 2), (0, 2), (0, 3), (0, 4)):\n'
       '        _row = []\n'
       '        for _p in (0, 1):\n'
       '            _s = Sim(clue=_clue, treasure=_tre, punch=_p)\n'
       '            try:\n'
       '                _s.map_init()\n'
       '                _row.append(" ".join(_s.route_return_home()))\n'
       '            except RouteError as _ex:\n'
       '                _row.append("★ %s" % _ex)\n'
       '        print("  线索=%s 宝物=P%d  关: %-30s 开: %s"\n'
       '              % (_clue, _tre, _row[0], _row[1]))\n'
       '    print()\n')


def main():
    with open(S, "rb") as f:
        data = f.read()
    eol = "\r\n" if data.count(b"\r\n") else "\n"
    ob = OLD.replace("\n", eol).encode("utf-8")
    nb = NEW.replace("\n", eol).encode("utf-8")
    assert data.count(ob) == 1, "命中 %d 次" % data.count(ob)
    with open(S, "wb") as f:
        f.write(data.replace(ob, nb))
    print("[ok] sim 预演 -> wp 对比表")


if __name__ == "__main__":
    main()
