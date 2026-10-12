# -*- coding: utf-8 -*-
"""AI 过程脚本：两个开关下拉的「跟随 config.h」直接显示当前值（开/关）。

用户报「S1/S2 没画出来」——其实是因为 ①开关默认跟着 config.h（当时 =0=关）②一轮只有宝物=P3/P4 才绕。
把 ① 的当前值直接写进下拉文字里，就不用猜了。同时 `_switch_on` 改成前缀判断（档名带了后缀）。
"""
import os

ME = os.path.join(r"C:\Users\14166\Desktop\MC_32\robotcup\xunbao", "地图修改上位机", "map_editor")
E = os.path.join(ME, "map_editor.py")
G = os.path.join(ME, "_guismoke.py")
EEDITS, GEDITS = [], []


def erep(old, new):
    EEDITS.append((old, new))


def grep_(old, new):
    GEDITS.append((old, new))


# 1) _switch_on 改前缀判断 + 新增 _switch_vals
erep('        if choice == "强制开":\n'
     '            return True\n'
     '        if choice == "强制关":\n'
     '            return False\n'
     '        try:\n'
     '            return bool(M.eval_c_expr(macro, M.parse_config_macros()))\n'
     '        except Exception:                                        # noqa: BLE001\n'
     '            return False\n'
     '\n'
     '    def _punch_on(self, choice):\n',
     '        if str(choice).startswith("强制开"):\n'
     '            return True\n'
     '        if str(choice).startswith("强制关"):\n'
     '            return False\n'
     '        try:\n'
     '            return bool(M.eval_c_expr(macro, M.parse_config_macros()))\n'
     '        except Exception:                                        # noqa: BLE001\n'
     '            return False\n'
     '\n'
     '    def _switch_vals(self, macro):\n'
     '        """开关下拉的取值。\n'
     '\n'
     '        ⚠️ 第一档**把 config.h 的当前值写进文字里**（"跟随 config.h（当前：关）"）——\n'
     '        否则用户选了"跟随"却看不到到底是开是关，会以为"开关没生效 / 路线没画出来"。\n'
     '        """\n'
     '        cur = "开" if self._switch_on(macro, "跟随 config.h") else "关"\n'
     '        return ["跟随 config.h（当前：%s）" % cur, "强制开", "强制关"]\n'
     '\n'
     '    def _punch_on(self, choice):\n')

# 2) 线索对话框：两个 VALS 用 helper
erep('        PUNCH_VALS = ["跟随 config.h", "强制开", "强制关"]\n'
     '        TOUR_VALS = ["跟随 config.h", "强制开", "强制关"]\n',
     '        PUNCH_VALS = self._switch_vals("P3P4_PUNCH_ENABLE")\n'
     '        TOUR_VALS = self._switch_vals("UPRIGHT_TOUR_ENABLE")\n')

# 3) 二轮对话框：TOUR_VALS 用 helper
erep('        TOUR_VALS = ["跟随 config.h", "强制开", "强制关"]\n',
     '        TOUR_VALS = self._switch_vals("UPRIGHT_TOUR_ENABLE")\n')

# 4) _guismoke：回退档的断言改成前缀匹配
grep_('          and _vals2[8] == "跟随 config.h" and _vals2[9] == "跟随 config.h",\n',
      '          and _vals2[8].startswith("跟随 config.h（当前：") and _vals2[9].startswith("跟随 config.h（当前："),\n')

grep_('    _cfg_punch = bool(M.eval_c_expr("P3P4_PUNCH_ENABLE", M.parse_config_macros()))\n',
      '    check(_vals2[8] == app._switch_vals("P3P4_PUNCH_ENABLE")[0]\n'
      '          and _vals2[9] == app._switch_vals("UPRIGHT_TOUR_ENABLE")[0],\n'
      '          "两个开关下拉的「跟随 config.h」直接写出当前值（%s ｜ %s）"\n'
      '          % (_vals2[8], _vals2[9]))\n'
      '    _cfg_punch = bool(M.eval_c_expr("P3P4_PUNCH_ENABLE", M.parse_config_macros()))\n')


def apply(path, edits):
    with open(path, "rb") as f:
        data = f.read()
    eol = "\r\n" if data.count(b"\r\n") else "\n"
    for old, new in edits:
        ob = old.replace("\n", eol).encode("utf-8")
        nb = new.replace("\n", eol).encode("utf-8")
        cnt = data.count(ob)
        assert cnt == 1, "%s 命中 %d 次:\n%r" % (os.path.basename(path), cnt, old[:80])
        data = data.replace(ob, nb)
    with open(path, "wb") as f:
        f.write(data)
    print("[ok] %-14s +%d 处" % (os.path.basename(path), len(edits)))


apply(E, EEDITS)
apply(G, GEDITS)
