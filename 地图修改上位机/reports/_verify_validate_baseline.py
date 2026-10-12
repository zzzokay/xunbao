# -*- coding: utf-8 -*-
"""AI 过程脚本：验证 validate/ 里的 exit=1 是**既有**的，与本次改动无关。

做法：把 Mission/config.h 与 Mission/barrier.c **临时**换成改动前版本（stash@{0}），
跑同一批脚本、记录输出，然后**无论成败都还原**成当前版本（try/finally）。
"""
import os
import subprocess
import sys

ROOT = r"C:\Users\14166\Desktop\MC_32\robotcup\xunbao"
PY = r"C:\Users\14166\AppData\Local\Microsoft\WindowsApps\python.exe"
FILES = ["Mission/config.h", "Mission/barrier.c"]
SCRIPTS = ["_check_csr.py", "_check_wp.py", "_check_wp_east.py",
           "_weight_calib.py", "_check_door_logic.py", "_check_map_debug.py"]


def run_script(name):
    p = os.path.join(ROOT, "地图修改上位机", "validate", name)
    r = subprocess.run([PY, p], capture_output=True, text=True, cwd=os.path.dirname(p))
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def show(tag, res):
    print("---- %s ----" % tag)
    for name in SCRIPTS:
        code, out = res[name]
        tail = [l for l in out.strip().splitlines() if l.strip()]
        print("  %-22s exit=%d | %s" % (name, code, tail[-1] if tail else ""))


def main():
    saved = {}
    for f in FILES:
        with open(os.path.join(ROOT, f), "rb") as fh:
            saved[f] = fh.read()
    before = {n: run_script(n) for n in SCRIPTS}
    try:
        for f in FILES:
            rel = f.replace("\\", "/")
            r = subprocess.run(["git", "show", "stash@{0}:%s" % rel],
                               capture_output=True, cwd=ROOT)
            assert r.returncode == 0, "git show failed for %s: %s" % (rel, r.stderr)
            with open(os.path.join(ROOT, f), "wb") as fh:
                fh.write(r.stdout)
        after = {n: run_script(n) for n in SCRIPTS}
    finally:
        for f in FILES:
            with open(os.path.join(ROOT, f), "wb") as fh:
                fh.write(saved[f])
        for f in FILES:
            with open(os.path.join(ROOT, f), "rb") as fh:
                assert fh.read() == saved[f], "还原失败: %s" % f
        print("已还原当前版本（两个文件字节级一致）")

    show("改动后（当前）", before)
    show("改动前（stash@{0}）", after)
    same = all(before[n][0] == after[n][0] and before[n][1] == after[n][1]
               for n in SCRIPTS)
    print("\n结论：改动前/后 6 个脚本的退出码与输出 %s" % ("完全一致 ⇒ 这些 exit=1 是既有的" if same else "**不一致** ⇒ 需要复查！"))
    return 0 if same else 1


if __name__ == "__main__":
    sys.exit(main())
