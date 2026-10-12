# -*- coding: utf-8 -*-
"""AI 过程脚本：确认 _guismoke 的第三条失败（D5黑+D4绿 wp 明写 N8）是不是本次改动引入的。

做法：把 map_model.py / map_editor.py / _guismoke.py 临时换成 stash@{0}（加 P3P4 之前）的版本，
跑 _guismoke 并抓那三条断言，然后**无论如何都还原**当前版本（try/finally + 字节级校验）。
"""
import os
import subprocess
import sys

ROOT = r"C:\Users\14166\Desktop\MC_32\robotcup\xunbao"
PY = r"C:\Users\14166\AppData\Local\Microsoft\WindowsApps\python.exe"
ME = os.path.join(ROOT, "地图修改上位机", "map_editor")
FILES = ["地图修改上位机/map_editor/map_model.py",
         "地图修改上位机/map_editor/map_editor.py",
         "地图修改上位机/map_editor/_guismoke.py"]
KEYS = ["对话框按上次配置预填", "配置非法时回退默认值",
        "D5黑+D4绿 时固件 wp 明写 N8"]


def run_smoke():
    r = subprocess.run([PY, os.path.join(ME, "_guismoke.py")],
                       capture_output=True, text=True, cwd=ME)
    out = (r.stdout or "") + (r.stderr or "")
    res = {}
    for line in out.splitlines():
        if "[OK]" in line or "[FAIL]" in line:
            for k in KEYS:
                if k in line:
                    res[k] = "[OK]" if "[OK]" in line else "[FAIL]"
    res["_fail_total"] = str(out.count("[FAIL]"))
    return res


def main():
    saved = {}
    for f in FILES:
        with open(os.path.join(ROOT, f), "rb") as fh:
            saved[f] = fh.read()
    print("--- 当前（含 P3P4 改动）---")
    cur = run_smoke()
    for k in KEYS + ["_fail_total"]:
        print("  %-38s %s" % (k, cur.get(k)))
    try:
        for f in FILES:
            rel = f.replace("\\", "/")
            r = subprocess.run(["git", "show", "stash@{0}:%s" % rel],
                               capture_output=True, cwd=ROOT)
            assert r.returncode == 0, r.stderr
            with open(os.path.join(ROOT, f), "wb") as fh:
                fh.write(r.stdout)
        print("--- P3P4 改动前（stash@{0}）---")
        base = run_smoke()
        for k in KEYS + ["_fail_total"]:
            print("  %-38s %s" % (k, base.get(k)))
    finally:
        for f in FILES:
            with open(os.path.join(ROOT, f), "wb") as fh:
                fh.write(saved[f])
        for f in FILES:
            with open(os.path.join(ROOT, f), "rb") as fh:
                assert fh.read() == saved[f], "还原失败: %s" % f
        print("已字节级还原当前版本")

    third = "D5黑+D4绿 时固件 wp 明写 N8"
    print("\n结论：第三条失败在改动前 %s ⇒ %s"
          % (base.get(third), "**既有**（不是本次引入）" if base.get(third) == "[FAIL]"
             else "**是本次引入的，要查**"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
