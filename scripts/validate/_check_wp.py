import _weight_calib as W
import sys

edges = W.parse_graph(); adj = W.build_adj(edges)
def plan(wp): return W.build_route_mirror(edges, adj, wp, 1.0, 0.6, 1.0)
CAN, ONE, NO = 'CAN','ONE','NO'
def can_pass(c): return c in (CAN, ONE)
def build_wp(door, treasure, red=False):
    p6 = (treasure == 6); wp = ["N2","P1","P3","P4","N5"]
    if can_pass(door[0]): wp.append("N12")
    elif can_pass(door[1]):
        wp.append("N8")
        if not p6: wp.append("N12")
    elif can_pass(door[2]):
        if not red: wp.append("N4")
        wp += ["N3","N8"]
        if not p6: wp.append("N12")
    else: return None
    if p6:
        seg = (["P6","P8","P7","P5","N12"] if red else ["N9","P6","N9","P8","P7","N13","P5","N13","N12"])
        wp += seg
    else:
        seg = (["P5","P7","P8","P6","N10"] if red else ["N13","P5","P7","P8","N9","P6","N9","N10"])
        wp += seg
    # return
    if door[0]==CAN: wp.append("N5")
    elif door[0]==ONE and door[3]==CAN: wp += ["N10","N3"]
    elif door[0]==NO and door[1]==CAN: wp += ["N8","N5"]
    elif door[0]==NO and door[1]==NO and door[2]==CAN: wp += ["N8","N3"]
    wp.append("P2"); return wp

all_ok = True
def cmp(tag, door, treasure):
    global all_ok
    old = build_wp(door, treasure, red=False); new = build_wp(door, treasure, red=True)
    ro, rn = plan(old), plan(new)
    ok = (ro == rn) and ro is not None
    print(f"[{'DELETE OK 路线一致' if ok else 'MISMATCH!'}] {tag}")
    if not ok:
        print("  旧:", " ".join(ro) if ro else "None"); print("  新:", " ".join(rn) if rn else "None")
        all_ok = False

for tag,door,tre in [
    ("D2全通,非P6",(CAN,NO,NO,NO,NO),5),
    ("D3,非P6",(NO,CAN,NO,NO,NO),5),
    ("far(D4),非P6",(NO,NO,CAN,NO,NO),5),
    ("D2全通,P6优先",(CAN,NO,NO,NO,NO),6),
    ("far(D4),P6优先",(NO,NO,CAN,NO,NO),6),
]:
    cmp(tag, door, tre)

sys.exit(0 if all_ok else 1)  # 返回 exit code：全部通过=0，失败=1
