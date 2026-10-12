# -*- coding: utf-8 -*-
"""AI 过程脚本：修「跟随 config.h」恒等于"关"的 bug。

根因：`M.parse_config_macros()` 返回 **(macros, field_name) 二元组**，`_switch_on` 漏了 `[0]`
      ⇒ `eval_c_expr(macro, tuple)` 抛 TypeError ⇒ 被 `except: return False` **吞掉** ⇒ 恒等于关。
      连 `_guismoke` 的断言也跟着错（两边同源错 ⇒ 自测"通过"）。

修：① `_switch_on` 用 `macros, _field = M.parse_config_macros()`，失败时**报状态栏**不再静默；
    ② `_guismoke` 那两处读值也补 `[0]`；
    ③ 再加一条**独立**校验（按文本读 config.h 的 0/1，不走 parse_config_macros）防同类自欺。
"""
import os

ME = os.path.join(r"C:\Users\14166\Desktop\MC_32\robotcup\xunbao", "地图修改上位机", "map_editor")
E = os.path.join(ME, "map_editor.py")
G = os.path.join(ME, "_guismoke.py")

E_OLD = (
    '        try:\n'
    '            return bool(M.eval_c_expr(macro, M.parse_config_macros()))\n'
    '        except Exception:                                        # noqa: BLE001\n'
    '            return False\n'
)
E_NEW = (
    '        try:\n'
    '            # ⚠️ parse_config_macros() 返回 **(macros, field_name) 二元组** —— 必须取 [0]。\n'
    '            #    踩过：漏了 [0] ⇒ eval_c_expr 收到 tuple 抛异常 ⇒ 被下面的 except 吞掉\n'
    '            #    ⇒ 「跟随 config.h」**恒等于"关"**（下拉"跟随"了却什么都不生效）。\n'
    '            macros, _field = M.parse_config_macros()\n'
    '            return bool(M.eval_c_expr(macro, macros))\n'
    '        except Exception as ex:                                  # noqa: BLE001\n'
    '            self.status("⚠ 读 config.h 的 %s 失败（按关处理）：%s" % (macro, ex))\n'
    '            return False\n'
)

G_OLD1 = '    _cfg_punch = bool(M.eval_c_expr("P3P4_PUNCH_ENABLE", M.parse_config_macros()))\n'
G_NEW1 = '    _cfg_punch = bool(M.eval_c_expr("P3P4_PUNCH_ENABLE", M.parse_config_macros()[0]))\n'
G_OLD2 = '    _cfg_tour = bool(M.eval_c_expr("UPRIGHT_TOUR_ENABLE", M.parse_config_macros()))\n'
G_NEW2 = '    _cfg_tour = bool(M.eval_c_expr("UPRIGHT_TOUR_ENABLE", M.parse_config_macros()[0]))\n'

G_OLD3 = ('    check(app._tour_on("跟随 config.h") is _cfg_tour\n'
          '          and app._tour_on("强制开") is True and app._tour_on("强制关") is False,\n'
          '          "「直立景点巡回」下拉跟随 config.h（当前 UPRIGHT_TOUR_ENABLE=%d）" % _cfg_tour)\n')
G_NEW3 = (G_OLD3 +
          '    # ⚠️ 独立校验：按**文本**读 config.h 的 0/1，不走 parse_config_macros() ——\n'
          '    #    上面漏 [0] 那次的教训是"断言与实现同源错 ⇒ 自测假通过"，这里换成独立口径。\n'
          '    _cfg_lines = open(M.PATH_CONFIG, encoding="utf-8").read().splitlines()\n'
          '\n'
          '    def _flag(nm):\n'
          '        for _ln in _cfg_lines:\n'
          '            _t = _ln.split()\n'
          '            if len(_t) >= 3 and _t[0] == "#define" and _t[1] == nm:\n'
          '                return _t[2] not in ("0", "0x0", "0U")\n'
          '        return None\n'
          '\n'
          '    check(app._punch_on("跟随 config.h") is _flag("P3P4_PUNCH_ENABLE")\n'
          '          and app._tour_on("跟随 config.h") is _flag("UPRIGHT_TOUR_ENABLE"),\n'
          '          "「跟随 config.h」解析正确（P3P4_PUNCH_ENABLE=%s / UPRIGHT_TOUR_ENABLE=%s）"\n'
          '          % (_flag("P3P4_PUNCH_ENABLE"), _flag("UPRIGHT_TOUR_ENABLE")))\n')


def apply(path, edits):
    with open(path, "rb") as f:
        data = f.read()
    eol = "\r\n" if data.count(b"\r\n") else "\n"
    for old, new in edits:
        ob = old.replace("\n", eol).encode("utf-8")
        nb = new.replace("\n", eol).encode("utf-8")
        cnt = data.count(ob)
        assert cnt == 1, "%s 命中 %d 次:\n%r" % (os.path.basename(path), cnt, old[:90])
        data = data.replace(ob, nb)
    with open(path, "wb") as f:
        f.write(data)
    print("[ok] %-14s +%d 处" % (os.path.basename(path), len(edits)))


apply(E, [(E_OLD, E_NEW)])
apply(G, [(G_OLD1, G_NEW1), (G_OLD2, G_NEW2), (G_OLD3, G_NEW3)])
