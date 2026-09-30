# -*- coding: utf-8 -*-
"""
map_editor.py — 寻宝地图图形化编辑器（Tkinter，零依赖）

用法（仓库根）：
    python scripts/map_editor/map_editor.py

打开即从固件源码读取当前地图（Navigation/map.h 的 enum MapNode +
Navigation/map_message.c 的 NavEdgeTbl[]），可以：
  * 拖动节点摆位置（纯示意图，不写回固件）
  * 双击节点/边改属性；右键加/删节点、加/删边、加双向边
  * 从节点 Shift+拖动 或「连线模式」拉出一条新边
  * 一键校验（孤立节点/单向边/重名/宏能否求值）
  * 必经点最短路规划（与固件同一套 Dijkstra），导出 route[] 数组
  * 导出 NavEdgeTbl[] / enum MapNode / NAV_EDGE_COUNT 文本（可粘贴回源码）
  * 导出/载入 .json 地图工程

⚠️ 本工具默认**只读源码**；「写回固件」是显式菜单项，会先自动备份。
"""
import os
import re
import sys
import json
import math
import copy
import time
import shutil
import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import map_model as M   # noqa: E402

# 背景底图（可选）：PIL 能读 jpg/png 并缩放；没有 PIL 时退回 tk.PhotoImage（只认 png/gif）
try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except Exception:
    Image = ImageTk = None
    HAS_PIL = False

# 底图坐标参考系 = 原图「寻宝地图/节点图.jpg」的像素坐标（1729x1080）。
# 实测：SEED_POSITIONS 就是这张原图的像素坐标（P8(96,510) 与 N12(645,340) 的
# 像素差 549/170 与模型坐标差完全一致），所以底图按 1:1 铺在 (0,0)-(1729,1080)
# 即可和节点对齐，不需要任何缩放换算。
BG_REF_W, BG_REF_H = 1729.0, 1080.0
DEFAULT_BG = os.path.join(M.ROOT, "寻宝地图", "节点图.jpg")
LEFT_W = 380      # 左栏固定宽度，保证路线按钮和文字不被裁切
RIGHT_W = 344     # 右栏固定宽度
# 各旋转档下，"表里 0°" 在屏幕上指向哪（用于下拉框提示）
ZERO_DIR = {"0°": "上", "90°": "右", "180°": "下", "270°": "左"}
# 视图旋转：世界坐标(节点图原始像素系, y 向下) → 视图坐标
#   view_x = sx*x + sy*y ;  view_y = sy*x - sx*y
#
# ⚠️ 实测记录（`_dbg_rot2/rot3.py` 量过，别凭感觉改）：
#   把"节点图上两点连线在屏幕上的角度"与边表 angle 对比，**只有 90°/(0,1) 自洽**
#   （有符号偏差中位 0.0°、55/77 条边在 ±10° 内；0°/180° 中位 90°，270° 中位 161.7°）。
#   也就是：rot=90° 时图上画的边与表里 angle 完全对得上。
#   但该档下"表里 0°"在**屏幕上是向上**的。
#
#   ⚠️ 用户明确要求「0 就是向左」，所以默认用 270°/(0,-1)：
#     该档下 view_x=-y, view_y=-x → 表里 0° 方向 (sin,-cos)=(0,-1)
#     映射到屏幕是向左（已实测确认）。
#     代价：此时节点摆放与节点图相差 180°（图会被上下颠倒），
#     但**数值/角度/长度全都不受影响**，只是显示朝向不同。
# 视角旋转：世界坐标(节点图原图像素系，y 向下) → 视图坐标。
# 约定（每个档位都是"把原图顺时针转 r 度"）：
#   rot=0°   : view = ( x,  y)   ← **恒等**，完全沿用原图角度（默认）
#   rot=90°  : view = ( y, -x)
#   rot=180° : view = (-x, -y)
#   rot=270° : view = (-y,  x)
# 各矩阵都是正交的，逆 = 转置（见 view_to_world）。
#
# ⚠️ 之前的实现里 0° 档也不是恒等（把 y 取反了），导致节点被翻到负坐标区、
#    底图/节点整体对不上 —— 这是"背景偏/歪"的真正原因。
#
# 实测（|屏幕方向 − 表里angle| 中位 / 符合≤10° 的边数，仅作参考）：
#   0° → 90.0° / 0-77      90° → 5.6° / 55-77
#   180° → 90.0° / 0-77    270° → 174.4° / 0-77
# 用户确认「原图角度是正确的」，故默认 0°。
ROT_MATRIX = {
    "0°": (1, 0, 0, 1),
    "90°": (0, 1, -1, 0),
    "180°": (-1, 0, 0, -1),
    "270°": (0, -1, 1, 0),
}
ROT_CHOICES = ROT_MATRIX          # 兼容旧名字
ROT_DEFAULT = "0°"

# ================================================================
#  拖动"引导线"的角度偏移（**只影响拖动约束/引导线，不影响显示与数值**）
# ================================================================
# 用户实测：拖动时那条引导线的角度与"表里 angle"差 90°（引导线看着是垂直的），
# 需要把引导线再转 90°。做法：约束用的方向向量按 (angle + DRAG_ANGLE_OFFSET) 算。
#
# 注意这里有个**同一坐标系的歧义**：表里 angle 的编码是"单向图"，而拖动引导线
# 是双向直线，两者同轴时还差一个方向朝外的选择。用户已明确要求转 90°，故默认 90°。
# 想还原成"直接用表里 angle"就把这里改成 0。
DRAG_ANGLE_OFFSET = 90.0

# 共线锚定容差（°）：新建边时，若起点已有一条出边与新边几乎共线，就沿用那条边的 angle。
# 依据：表里 angle 只能由几何定出**直线**、定不出**方向感**；实测本图 109 条边里
# 52 条是「几何+90°」、31 条是「几何−90°」（同一根直线、方向相反），所以"看图算方向"天生有歧义。
ANGLE_ANCHOR_TOL = 8.0
# 吸附容差（°）：算出来的角度离 0/±90/180 很近就吸成整数（"完全水平"就该写成 0/180）
ANGLE_SNAP_TOL = 5.0


def _norm180(a):
    """把角度归一到 (-180, 180]。"""
    while a > 180.0:
        a -= 360.0
    while a <= -180.0:
        a += 360.0
    return a


def _angdiff(a, b):
    """两个方向的最小夹角（0~180°）。"""
    return abs(_norm180(a - b))


def _snap90(a, tol=ANGLE_SNAP_TOL):
    """接近 0/±90/180 就吸附成整数；否则返回 None。"""
    for c in (0.0, 90.0, 180.0, -90.0):
        if _angdiff(a, c) <= tol:
            return _norm180(c)
    return None

# ================================================================
#  拖动吸附模式（比"硬锁表里角度"更实用）
# ================================================================
#  * "跟随角度表"：约束方向 = 边表 angle + DRAG_ANGLE_OFFSET（原来的行为）
#  * "吸附水平/竖直"：把边**尽量拉到 0°/90°（水平或竖直）**；离得近就直接吸附上去。
#    这是默认 —— 因为节点图本来就不按角度表精确画（图上方向与表里 angle 整体差 90°，
#    且用户明确希望"更偏好水平和竖直的线，到一定范围就自动吸附"）。
#  * "自由"：不做任何方向约束（长度约束仍可单独生效）。
SNAP_MODES = ("吸附水平/竖直", "跟随角度表", "自由")
SNAP_DEFAULT = "吸附水平/竖直"
SNAP_TOL_DEFAULT = 8.0        # 吸附阈值(°)：方向与水平/竖直差这么多以内 → 直接吸正
SNAP_NEAR_DEFAULT = 25.0      # 软偏好范围(°)：这以内按偏差平方惩罚（越近越被拉正）
AXIS_ANGLES = (0.0, 90.0, 180.0, -90.0)

# ---------------------------------------------------------------- 视觉参数
NODE_STYLE = {
    # kind: (填充色, 边框色, 半径, 形状)
    "P": ("#ffd9d9", "#c0392b", 20, "rect"),
    "S": ("#e8e8e8", "#7f8c8d", 18, "diamond"),
    "N": ("#d6ecff", "#2471a3", 17, "circle"),
    "C": ("#fff3cf", "#b7950b", 15, "circle"),
    "B": ("#e2f7d4", "#4e8b2a", 15, "square"),
    "G": ("#efe0ff", "#7d3c98", 15, "circle"),
    "?": ("#f2f2f2", "#888888", 15, "circle"),
}
EDGE_COLOR = "#555555"
EDGE_COLOR_FUNC = "#c0392b"      # 带特殊功能(障碍/门/平台)的边
EDGE_COLOR_SEL = "#e67e22"
BATCH_COLOR = "#8e44ad"          # 框选批量选中（节点/边通用）：紫，不撞单选橙、路线蓝/青、告警红
ROUTE_COLOR = "#1e88e5"           # 路线·去程（蓝）
ROUTE_COLOR_BACK = "#00897b"      # 路线·回程（青绿）—— 与去程区分，且不撞边的红/橙/选中色
TURN_FOCUS_COLOR = "#d81b60"      # 「转弯补偿…」选中三元组的高亮色（洋红，不撞蓝/青/橙/紫/红）
# 补偿表里"这一行到底会不会生效"的三档配色（画面上必须一眼分开）
TURN_OK_COLOR = "#2e7d32"         # 生效
TURN_DEAD_COLOR = "#c62828"       # 死值（分支不成立 / 边不存在）
TURN_WAIT_COLOR = "#ef6c00"       # 吃默认值（没实测、没算出来）
# 画布显示过滤：去程/回程叠在一起看不清时，只画其中一段
ROUTE_VIEW_MODES = ("去程+回程", "只看去程", "只看回程")
ROUND2_CRUISE_PF = ("P5", "P6", "P7", "P8")   # 第二轮巡游的 4 个东区平台
BG = "#fbfbf8"
EDGE_HIT_WIDTH = 14               # 边的"隐形命中区"宽度(px)：点它附近即可选中
EDGE_PAIR_OFFSET = 6.0            # 双向边两条线的**垂直间距**一半(px)：各偏 6 ⇒ 相隔 12px，看得清也点得开

KIND_ZH = {"P": "平台 P", "S": "景点 S", "N": "节点 N", "C": "拐点 C",
           "B": "桥/障碍 B", "G": "其它 G", "?": "其它"}


# ======================================================================
#  背景底图管理
# ======================================================================
class BackgroundManager:
    """底图（节点图/场地图）的加载、对齐标定与绘制。

    **对齐标定（calib）**：把底图 0..BG_REF_W / 0..BG_REF_H 的坐标线性映射到模型坐标：
        模型x = off_x + rx * scale_x
        模型y = off_y + ry * scale_y
    默认值是"1:1 且对齐到节点包围盒中心"，可用「用节点反推」做最小二乘拟合，
    也能用 ×/+ 微调，标定结果会随 JSON 工程一起保存。

    ⚠️ 底图只是**对齐参考**：不参与任何长度计算（长度只认 step 数值）。
    """

    def __init__(self, app):
        self.app = app
        self.path = DEFAULT_BG
        self.src = None                 # 原始 PIL.Image
        self.img = None                 # 已按视图旋转过的 PIL.Image
        self.photo = None               # 防止被 GC
        self.opacity = 0.55             # 0..1，越大越清楚（会盖住线）
        self.scale_x = 1.0
        self.scale_y = 1.0
        self.off_x = 0.0
        self.off_y = 0.0
        self.rot = "90°"                # 当前图像已应用的旋转档
        self._cache = (None, None)

    # ---------- 加载 ----------
    def load(self, path, quiet=False):
        self.src = None
        self.img = None
        self.photo = None
        self._cache = (None, None)
        if not path or not os.path.isfile(path):
            if not quiet:
                self.app.status("底图文件不存在或不是文件：%s" % path)
                messagebox.showwarning("底图", "找不到这个图片文件：\n%s" % path,
                                       parent=self.app)
            return False
        if not HAS_PIL:
            if not quiet:
                messagebox.showwarning(
                    "底图", "没装 pillow，只能用 png/gif 底图。\n"
                            "装了就能用 jpg：\n  pip install pillow", parent=self.app)
            return False
        try:
            from PIL import Image
            im = Image.open(path)
            im.load()
            self.src = im.convert("RGBA")
            self.img = self.src
            self.rot = "0°"
            self.path = path
            if not quiet:
                self.app.status("已载入底图 %s（%d×%d）"
                                % (os.path.basename(path), im.width, im.height))
            return True
        except Exception as ex:
            self.src = None
            self.img = None
            if not quiet:
                messagebox.showerror("底图载入失败", "%s\n\n文件：%s" % (ex, path),
                                     parent=self.app)
            return False

    def set_rotation(self, rot_name, rot_xy):
        """让底图跟着视图一起转，保证图和节点始终贴合。

        节点坐标转视图用 (sx,sy)；图片要跟着转同一个角度：
        PIL 的 ROTATE_90 是逆时针，正好对上 (0,1)/90° 这一档。
        """
        if self.src is None:
            self.rot = rot_name
            return
        if self.rot == rot_name:
            return
        from PIL import Image
        tbl = {"0°": None, "90°": Image.ROTATE_90,
               "180°": Image.ROTATE_180, "270°": Image.ROTATE_270}
        op = tbl.get(rot_name)
        self.img = self.src if op is None else self.src.transpose(op)
        self.rot = rot_name
        self._cache = (None, None)

    def ref_size(self):
        if self.img is None:
            return (BG_REF_W, BG_REF_H)
        return (float(self.img.width), float(self.img.height))

    # ---------- 标定（全部在"视图坐标系"里做：底图已跟着旋转过）----------
    def reset_calib(self):
        """默认标定：底图按**原图像素 1:1** 铺（因为 SEED_POSITIONS 就是原图像素坐标）。

        只做一次平移让底图与节点包围盒的中心对齐；正常情况下
        （首次打开、未手动调过）偏移量应当接近 0。
        """
        vpts = [self.app.world_to_view(n.x, n.y) for n in self.app.model.nodes]
        if not vpts:
            vpts = [(0.0, 0.0)]
        xs = [p[0] for p in vpts]
        ys = [p[1] for p in vpts]
        cxm, cym = (min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0
        rw, rh = self.ref_size()
        self.scale_x = self.scale_y = 1.0
        # 1:1 对齐：底图左上角放在节点包围盒中心 - 半张图 处
        self.off_x = cxm - (rw / 2.0) if self.scale_x == 1.0 else 0.0
        self.off_y = cym - (rh / 2.0) if self.scale_y == 1.0 else 0.0
        # 若底图比节点范围大很多，直接让它按图左上角对齐（1:1 铺原图即贴合）
        if rw >= (max(xs) - min(xs)) and rh >= (max(ys) - min(ys)):
            self.off_x = 0.0
            self.off_y = 0.0

    def fit_to_nodes(self, include_estimated=False):
        """用"图上量过的节点坐标"反推最佳仿射标定（最小二乘，视图坐标系）。

        对每个有 seed 坐标的节点：seed 是原图像素 → 先转到视图坐标，
        再与节点当前视图坐标做线性拟合 模型 = off + ref * scale。
        返回 (用到的点数, 平均残差 px)。
        """
        seed = M.load_seed_positions()
        pts = []
        for n in self.app.model.nodes:
            if n.name in M.MISSING_SEED and not include_estimated:
                continue                       # 图上没画的点不能用来拟合
            if n.name in seed:
                vx, vy = self.app.world_to_view(n.x, n.y)
                sx, sy = self.app.world_to_view(seed[n.name][0], seed[n.name][1])
                pts.append((sx, sy, vx, vy))
        if len(pts) < 2:
            return 0, 0.0

        def lsq(rs, ms):
            k = len(rs)
            sr = sum(rs)
            sm = sum(ms)
            srr = sum(r * r for r in rs)
            srm = sum(r * m for r, m in zip(rs, ms))
            den = k * srr - sr * sr
            if abs(den) < 1e-9:
                return 1.0, (sm - sr) / k
            a = (k * srm - sr * sm) / den
            b = (sm - a * sr) / k
            return a, b

        self.scale_x, self.off_x = lsq([p[0] for p in pts], [p[2] for p in pts])
        self.scale_y, self.off_y = lsq([p[1] for p in pts], [p[3] for p in pts])
        tot = 0.0
        for rx, ry, mx, my in pts:
            ex = self.off_x + rx * self.scale_x - mx
            ey = self.off_y + ry * self.scale_y - my
            tot += (ex * ex + ey * ey) ** 0.5
        return len(pts), tot / len(pts)

    def rect(self):
        """底图在**视图坐标系**里覆盖的范围 (x0,y0,x1,y1)。"""
        rw, rh = self.ref_size()
        return (self.off_x, self.off_y,
                self.off_x + rw * self.scale_x,
                self.off_y + rh * self.scale_y)

    def calib_snapshot(self):
        return {"scale_x": self.scale_x, "scale_y": self.scale_y,
                "off_x": self.off_x, "off_y": self.off_y,
                "opacity": self.opacity, "rot": self.rot}

    def apply_calib(self, d):
        for k in ("scale_x", "scale_y", "off_x", "off_y", "opacity"):
            if k in d and d[k] is not None:
                setattr(self, k, float(d[k]))
        # rot 由 App 统一处理（要先转图再算矩形）
        self._cache = (None, None)

    # ---------- 绘制 ----------
    def draw(self, canvas, w2s):
        if self.img is None or not self.app.show_bg.get():
            return
        x0, y0, x1, y1 = self.rect()
        sx0, sy0 = w2s(x0, y0)
        sx1, sy1 = w2s(x1, y1)
        w, h = max(1, int(round(sx1 - sx0))), max(1, int(round(sy1 - sy0)))
        try:
            if self._cache[0] == (w, h) and self._cache[1] is not None:
                self.photo = self._cache[1]
            else:
                from PIL import Image, ImageTk, ImageEnhance
                im = self.img.resize((w, h), Image.BILINEAR)
                if self.opacity < 0.999:
                    # 用白色兑淡：opacity=1 → 原图；越小越淡
                    white = Image.new("RGBA", im.size, (255, 255, 255, 255))
                    im = Image.blend(white, im, max(0.0, min(1.0, self.opacity)))
                self.photo = ImageTk.PhotoImage(im)
                self._cache = ((w, h), self.photo)
            canvas.create_image(sx0, sy0, image=self.photo, anchor="nw", tags="bg")
        except Exception:
            pass


def list_bg_candidates():
    """列出可选的底图（寻宝地图/ 下的图片）。"""
    out = []
    d = os.path.join(M.ROOT, "寻宝地图")
    if os.path.isdir(d):
        for fn in sorted(os.listdir(d)):
            if fn.lower().endswith((".jpg", ".jpeg", ".png", ".gif", ".bmp")):
                out.append(os.path.join(d, fn))
    return out



class App(tk.Tk):
    def __init__(self, bg_path=None):
        super().__init__()
        self.title("寻宝地图编辑器 — xunbao map editor")
        self.geometry("1760x940")
        # 最小宽度：工具栏三行最宽约 1163px，留点余量
        self.minsize(1200, 720)

        self.model = M.MapModel.load_from_sources()
        self.sel_node = None          # 选中的节点名
        self.sel_edge = None          # 选中的 Edge 对象（赋值非 None 会自动清空批量选择，见属性定义）
        self.selected_nodes = set()   # Ctrl 框选后用于整体移动的节点
        self.selected_edges = set()   # Ctrl 框选同时选中的边，元素是 (frm, to) 键 ——「按图上位置算角度/step」批量作用对象
        self.route = []               # 规划出来的路线（节点名列表）
        self.route_split = None       # 回程起始下标（仅"第一轮完整路线"用；其余为 None）
        self.route_view = tk.StringVar(value=ROUTE_VIEW_MODES[0])   # 画布只画哪段（去程/回程分开看）
        # 「转弯补偿…」对话框里选中的三元组 (last, now, next)：在画布上高亮出来（None=不画）
        self.turn_focus = None
        self.clue_route_cfg = {}      # 「线索路线…」对话框上次用的配置（随布局一起保存/恢复）
        self.round2_cfg = {}          # 「二轮路线…」对话框上次用的配置（随布局一起保存/恢复）
        self.waypoints = []           # 必经点
        self.undo_stack = []
        self.redo_stack = []
        self._suspend_ui = False      # 刷新面板时别触发编辑回调

        # 视图变换
        self.scale = 1.0
        self.ox = 40.0
        self.oy = 40.0
        self.label_mode = tk.StringVar(value="标准")   # 无/标准/详细
        self.show_edge_lengths = tk.BooleanVar(value=False)
        self.show_geometry_warnings = tk.BooleanVar(value=False)
        self.geometry_len_tol = tk.DoubleVar(value=30.0)
        self.geometry_ang_tol = tk.DoubleVar(value=15.0)
        self.show_grid = tk.BooleanVar(value=True)
        self.connect_mode = tk.BooleanVar(value=False)
        self.var_quick_both = tk.BooleanVar(value=True)   # 快捷建边是否同时建反向边
        self.show_bg = tk.BooleanVar(value=True)
        self.adjust_bg = tk.BooleanVar(value=False)
        self.bg = BackgroundManager(self)      # 底图（含对齐标定）
        self._did_refit = False
        self.user_zoomed = False       # 用户手动缩放/平移过就不再自动适配

        self._drag = None             # 拖动状态
        self._pan = None
        self._link = None             # 连线状态
        self.connect_from = None      # 「点两下连线」的起点节点
        self._syncing_tree = False    # 代码同步树选中时抑制回调（防递归）
        self._suspend_ui = False
        self._canvas_items = {"nodes": {}, "edges": {}}

        # ---- 拖动约束（用户要求：角度严格按表、长度不得小于 step）----
        # 单位长度 K = 每 1cm 对应多少"图坐标单位"（= px）。
        #   约束①（角度锁定）：拖动节点时，它与每个相邻节点的方向被投影到该边表里
        #                     的 angle 所确定的直线上（双向边两个方向都合法）。
        #   约束②（最小长度）：|该边图上长度| >= step(cm) * K。
        # ⚠️ 节点图**不是等比例的**（px/step 比值从 0.17 到 94.9），所以任何 K 都会
        #    有一部分边本来就不满足②。界面会把违规边标红/列出，让你自己取舍 K。
        # ---- 拖动吸附（用户要求：更偏好水平/竖直，到一定范围就自动吸附）----
        self.snap_mode = tk.StringVar(value=SNAP_DEFAULT)
        self.snap_tol = tk.DoubleVar(value=SNAP_TOL_DEFAULT)    # 硬吸正阈值(°)
        self.snap_near = tk.DoubleVar(value=SNAP_NEAR_DEFAULT)  # 软拉扯范围(°)
        # 兼容旧开关（"跟随角度表"以外的模式都按吸附处理）
        self.lock_angle = tk.BooleanVar(value=True)
        self.enforce_min_len = tk.BooleanVar(value=True)
        self.unit_px_per_cm = tk.DoubleVar(value=0.884)
        self._drag_info = None

        # ---- 视图旋转（用户约定：表里 0° 在屏幕上朝左）----
        # 默认 270°；理由与实测数据见文件顶部 ROT_CHOICES 的注释。
        self.rot = tk.StringVar(value=ROT_DEFAULT)

        self._build_ui()
        # 底图：命令行给了就用命令行那个，否则用默认节点图
        if bg_path:
            self.bg.load(bg_path, quiet=False)
        else:
            self.bg.load(self.bg.path, quiet=True)
        # 视图旋转（节点图与表里 angle 差 90°，默认转 90° 让 0° 指屏幕左侧）
        self.bg.set_rotation(self.rot.get(), self._rot_xy())
        self.bg.reset_calib()
        self._update_bg_rect()
        # 有保存过的布局就自动载入（节点位置 + 底图标定），省得每次重拖
        auto = self._layout_path()
        self._auto_loaded = False
        if os.path.isfile(auto):
            self._auto_loaded = self.load_layout_file(auto, quiet=True)
        self.refresh_all()
        # 窗口还没映射时 canvas 尺寸不可信（会报 1 或很小的值）→ 开局先给个
        # 兜底适配，等窗口真正显示出来再由 <Configure> / _refit_once 用真实尺寸重算。
        self._fit_view_fallback()
        self.after(60, self._refit_once)
        self.after(300, self._refit_once)
        if self._auto_loaded:
            _items, _short = self._source_diff_items()
            if _short:
                # 布局盖掉了固件地图 —— 必须说清楚，否则"显示的路线"会与车上不一致
                self.status("⚠ 已自动载入布局，但它与固件源码不一致（%s）："
                            "点「校验」看明细，点「重新载入源码」回到固件版" % _short)
            else:
                self.status("已自动载入保存过的布局（%s）｜%d 节点 / %d 边"
                            "　｜　拖动节点只改示意图，不影响 step/angle"
                            % (os.path.basename(auto), len(self.model.nodes),
                               len(self.model.edges)))
        else:
            self.status("已载入：%d 个节点 / %d 条边（源：Navigation/map_message.c，场地 %s）"
                        "　｜　节点位置只是示意图：拖动不影响 step/angle 数值"
                        % (len(self.model.nodes), len(self.model.edges),
                           self.model.field_name))
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self):
        """关闭时提醒保存布局（只提醒，不强制）。"""
        if self.model.dirty:
            ans = messagebox.askyesnocancel(
                "保存布局？",
                "布局有改动还没保存。\n\n"
                "「是」= 保存并退出（下次打开自动载入）\n"
                "「否」= 直接退出（改动丢失）\n"
                "「取消」= 回去继续编辑",
                parent=self)
            if ans is None:
                return
            if ans:
                if not self.save_layout(show_msg=False):
                    return
        self.destroy()

    def apply_rotation(self):
        """切换视图旋转：节点坐标与底图一起转，保证两者仍然贴合。"""
        name = self.rot.get()
        self.bg.set_rotation(name, self._rot_xy())
        self.bg.reset_calib()
        self.refresh_bg_panel()
        self._fit_view()
        self.status("视图已旋转到 %s（表里 angle 的 0° 现在指向：%s）"
                    % (name, ZERO_DIR.get(name, "?")))

    def _fit_view_fallback(self):
        """窗口尺寸还不可信时的兜底：按窗口请求尺寸估算画布宽度。"""
        cw = max(500, int(self.winfo_reqwidth()) - 310 - 336 - 20)
        ch = max(400, int(self.winfo_reqheight()) - 90)
        self._fit_to(cw, ch)

    def _refit_once(self):
        if not self._did_refit:
            self._did_refit = True
            self._fit_view()

    # ================================================================ UI 搭建
    def _build_ui(self):
        self._build_toolbar()

        # 三栏用 pack：左右固定宽 + 中间 expand 吸收剩余宽度。
        # （试过 ttk.Panedwindow / grid columnconfigure：都被左右栏里 Notebook 的
        #   请求宽度顶开，把画布挤到 400px —— 就是"揉成一坨"的根因。）
        outer = ttk.Frame(self)
        outer.pack(fill="both", expand=True)

        left = ttk.Frame(outer, width=LEFT_W)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)          # 宽度锁死
        self._frame_left = left
        self._build_left(left)

        right = ttk.Frame(outer, width=RIGHT_W)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)
        self._frame_right = right
        self._build_right(right)

        mid = ttk.Frame(outer)
        mid.pack(side="left", fill="both", expand=True)
        self._frame_mid = mid
        mid.rowconfigure(0, weight=1)
        mid.columnconfigure(0, weight=1)
        self.canvas = tk.Canvas(mid, bg=BG, highlightthickness=0, cursor="arrow")
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self._bind_canvas()

        # ---- 状态栏 ----
        bar = ttk.Frame(self)
        bar.pack(fill="x", side="bottom")
        self.status_var = tk.StringVar(value="")
        ttk.Label(bar, textvariable=self.status_var, anchor="w").pack(
            fill="x", padx=8, pady=3)
        self.zoom_var = tk.StringVar(value="100%")
        ttk.Label(bar, textvariable=self.zoom_var, width=8).pack(side="right", padx=6)

    def _build_toolbar(self):
        """工具栏分**三行**。

        ⚠️ 一行放不下：加了旋转/吸附/限长度/单位长/违反约束之后总宽度远超窗口，
        右侧控件会跑到屏幕外。现在按语义分行：
          第1行 文件 / 编辑 / 校验
          第2行 视图（网格·底图·标注·旋转）
          第3行 拖动吸附 / 长度 / 导出
        每行都远小于 `minsize` 宽度（`_guismoke.py` 有断言守着）。
        """
        wrap = ttk.Frame(self)
        wrap.pack(fill="x", side="top")
        row1 = ttk.Frame(wrap)
        row1.pack(fill="x")
        row2 = ttk.Frame(wrap)
        row2.pack(fill="x")
        row3 = ttk.Frame(wrap)
        row3.pack(fill="x")

        def mk(tb):
            def btn(text, cmd, width=None):
                b = ttk.Button(tb, text=text, command=cmd, width=width)
                b.pack(side="left", padx=2, pady=2)
                return b

            def sep():
                ttk.Separator(tb, orient="vertical").pack(side="left", fill="y",
                                                          padx=4, pady=3)

            def chk(text, var, cmd=None, pad=(2, 0)):
                c = ttk.Checkbutton(tb, text=text, variable=var)
                if cmd:
                    c.configure(command=cmd)
                c.pack(side="left", padx=pad)
                return c

            def lab(text, pad=(6, 1)):
                ttk.Label(tb, text=text).pack(side="left", padx=pad)

            return btn, sep, chk, lab

        # ---------------- 第一行：文件 / 编辑 ----------------
        btn, sep, chk, lab = mk(row1)
        btn("重载源码", self.reload_sources)
        btn("载入JSON", self.load_json)
        sep()
        btn("保存布局", self.save_layout)
        btn("另存为", self.save_layout_as)
        btn("载入布局", self.load_layout_picker)
        sep()
        btn("撤销", self.undo)
        btn("重做", self.redo)
        sep()
        btn("＋节点", self.add_node_dialog)
        btn("＋边", self.add_edge_dialog)
        btn("＋双向边", lambda: self.add_edge_dialog(both=True))
        btn("删除选中", self.delete_selected)
        # ⚠️ 「平台快速交换」不放在这一行：加了之后本行宽 1254px > minsize 1200，会在最小窗口下溢出。
        #    它的入口在左栏「总览 → 地图级快捷操作」。
        sep()
        chk("连线模式", self.connect_mode)
        chk("双向", self.var_quick_both)

        # ---------------- 第二行：视图 ----------------
        btn, sep, chk, lab = mk(row2)
        chk("网格", self.show_grid, cmd=self.redraw, pad=(2, 3))
        chk("底图", self.show_bg, cmd=self.redraw, pad=(2, 3))
        chk("调整背景", self.adjust_bg, cmd=self.redraw, pad=(2, 3))
        btn("换底图…", self.pick_bg_image)
        lab("标注:")
        cb = ttk.Combobox(row2, textvariable=self.label_mode, width=4, state="readonly",
                          values=["无", "标准", "详细"])
        cb.pack(side="left")
        cb.bind("<<ComboboxSelected>>", lambda e: self.redraw())
        chk("边长(cm)", self.show_edge_lengths, cmd=self.redraw, pad=(5, 3))
        chk("报警标红", self.show_geometry_warnings, cmd=self.redraw, pad=(2, 3))
        lab("旋转:", (6, 1))
        rotcb = ttk.Combobox(row2, textvariable=self.rot, width=4, state="readonly",
                             values=list(ROT_CHOICES.keys()))
        rotcb.pack(side="left")
        rotcb.bind("<<ComboboxSelected>>", lambda e: self.apply_rotation())
        sep()
        btn("适配", self._fit_view)
        btn("校验", self.do_validate)
        btn("违反约束", self.report_violations)
        btn("查看代码差异", self.report_source_diff)
        # ⚠️ 场地选择器放这一行（不是第一行）：第一行加它会到 1266px > minsize 1200，最小窗口下溢出。
        #    它改的是 Mission/config.h 的 USE_FIELD，会动所有 LEN_*/ANGLE_*/DOOR_LEN_* 的取值。
        lab("场地:", (6, 1))
        self.field_var = tk.StringVar(
            value="比赛场地" if self.model.field_name == "FIELD_COMP" else "学校场地")
        field_cb = ttk.Combobox(row2, textvariable=self.field_var, width=6, state="readonly",
                                values=["比赛场地", "学校场地"])
        field_cb.pack(side="left")
        field_cb.bind("<<ComboboxSelected>>", lambda e: self.on_field_change())

        # ---------------- 第三行：拖动吸附 / 长度 / 导出 ----------------
        btn, sep, chk, lab = mk(row3)
        lab("吸附:", (2, 1))
        cbs = ttk.Combobox(row3, textvariable=self.snap_mode, width=11, state="readonly",
                           values=list(SNAP_MODES))
        cbs.pack(side="left")
        cbs.bind("<<ComboboxSelected>>", lambda e: self.redraw())
        lab("阈值:", (6, 1))
        spt = ttk.Spinbox(row3, from_=1, to=45, increment=1, width=4,
                          textvariable=self.snap_tol, command=self.redraw)
        spt.pack(side="left")
        spt.bind("<Return>", lambda e: self.redraw())
        lab("°", (1, 2))
        chk("限长度", self.enforce_min_len, cmd=self.redraw)
        lab("单位长:", (6, 1))
        sp = ttk.Spinbox(row3, from_=0.05, to=20.0, increment=0.05, width=6,
                         textvariable=self.unit_px_per_cm, command=self.redraw)
        sp.pack(side="left")
        sp.bind("<Return>", lambda e: self.redraw())
        sp.bind("<FocusOut>", lambda e: self.redraw())
        lab("px/cm", (1, 2))
        lab("角度阈值:", (5, 1))
        ttk.Spinbox(row3, from_=1, to=180, increment=5, width=4,
                textvariable=self.geometry_ang_tol, command=self.redraw).pack(side="left")
        lab("°", (1, 2))
        sep()
        btn("几何报警", self.report_geometry_warnings)
        btn("导出C代码", self.export_c_dialog)
        btn("宏定义", self.edit_macros_dialog)
        btn("写回固件", self.patch_firmware_dialog)
        btn("帮助", self.show_help)

    def _build_left(self, parent):
        """左栏：上半「总览」（节点/边两张表），下半「路线规划」。"""
        pane = ttk.Panedwindow(parent, orient="vertical")
        pane.pack(fill="both", expand=True)

        # ---------------- 上半：总览 ----------------
        top = ttk.Frame(pane)
        pane.add(top, weight=3)
        ttk.Label(top, text="节点（双击定位 / 右键菜单）").pack(
            anchor="w", padx=4, pady=(4, 0))
        self.tree_nodes = ttk.Treeview(top, columns=("idx", "kind", "deg"),
                                       show="tree headings", height=10)
        self.tree_nodes.heading("#0", text="节点")
        self.tree_nodes.heading("idx", text="#")
        self.tree_nodes.heading("kind", text="类型")
        self.tree_nodes.heading("deg", text="出/入")
        self.tree_nodes.column("#0", width=104)
        self.tree_nodes.column("idx", width=30, anchor="e")
        self.tree_nodes.column("kind", width=48)
        self.tree_nodes.column("deg", width=44, anchor="center")
        self.tree_nodes.pack(fill="both", expand=True, padx=4)
        self.tree_nodes.bind("<<TreeviewSelect>>", self._on_tree_node_select)

        ttk.Label(top, text="边（双击定位 / 右键菜单）").pack(
            anchor="w", padx=4, pady=(6, 0))
        # 展示模式：逐条 / 合并双向（同一条线段只占一行，两个方向并列显示）/ 只看双向
        mrow = ttk.Frame(top)
        mrow.pack(fill="x", padx=4)
        ttk.Label(mrow, text="边显示:").pack(side="left")
        self.edge_view = tk.StringVar(value="合并双向")
        cbv = ttk.Combobox(mrow, textvariable=self.edge_view, width=8, state="readonly",
                           values=["合并双向", "逐条", "只看双向"])
        cbv.pack(side="left", padx=(2, 0))
        cbv.bind("<<ComboboxSelected>>", lambda e: self.refresh_trees())
        # 平台快速交换（function 随平台切换，长度/角度全沿用）。
        # ⚠️ 必须挂在**这一行**：pack 顺序靠前的才拿得到空间 —— 之前放在边表下面，
        #    父容器已被两个 expand 的 Treeview 占满，结果整块 frame 根本没被映射（看不到）。
        ttk.Button(mrow, text="⇄ 平台交换…",
                   command=self.platform_swap_dialog).pack(side="left", padx=(8, 0))
        # 转弯前补偿（map.c 的两张表 + 公式参数）：同样必须挂在这一行（见上面的 pack 说明）
        ttk.Button(mrow, text="⟲ 转弯补偿…",
                   command=self.turn_comp_dialog).pack(side="left", padx=(6, 0))

        self._edge_cols = ("a1", "s1", "a2", "s2")
        self.tree_edges = ttk.Treeview(top, columns=self._edge_cols,
                                       show="tree headings", height=10)
        # （表头文字在 _apply_edge_columns() 里按展示模式重设）
        self.tree_edges.column("#0", width=92, stretch=False)
        self.tree_edges.pack(fill="both", expand=True, padx=4, pady=(0, 4))
        self.tree_edges.bind("<<TreeviewSelect>>", self._on_tree_edge_select)
        self._apply_edge_columns()

        # ---------------- 下半：路线规划 ----------------
        bot = ttk.Frame(pane)
        pane.add(bot, weight=2)
        ttk.Label(bot, text="必经点（顺序执行；首=起点，末=终点）").pack(
            anchor="w", padx=4, pady=(6, 0))
        self.lst_wp = tk.Listbox(bot, height=6, exportselection=False)
        self.lst_wp.pack(fill="x", padx=4)

        row = ttk.Frame(bot)
        row.pack(fill="x", padx=4, pady=3)
        ttk.Button(row, text="＋选中", width=7, command=self.wp_add_sel).pack(side="left")
        ttk.Button(row, text="－", width=3, command=self.wp_del).pack(side="left", padx=2)
        ttk.Button(row, text="↑", width=3, command=lambda: self.wp_move(-1)).pack(side="left")
        ttk.Button(row, text="↓", width=3, command=lambda: self.wp_move(1)).pack(side="left")
        ttk.Button(row, text="清空", width=5, command=self.wp_clear).pack(side="left", padx=2)

        row2 = ttk.Frame(bot)
        row2.pack(fill="x", padx=4, pady=2)
        ttk.Button(row2, text="规划路线", command=self.plan_route).pack(side="left")
        ttk.Button(row2, text="常规路线", command=self.plan_normal_route).pack(side="left", padx=2)
        ttk.Button(row2, text="清路线", command=self.clear_route).pack(side="left", padx=2)
        row2b = ttk.Frame(bot)
        row2b.pack(fill="x", padx=4, pady=(0, 2))
        ttk.Button(row2b, text="线索路线…", command=self.plan_clue_route_dialog).pack(side="left")
        ttk.Button(row2b, text="二轮路线…", command=self.plan_round2_route_dialog).pack(
            side="left", padx=4)
        ttk.Button(row2b, text="读 config.h", command=self.wp_from_config).pack(side="left", padx=4)
        cost_row = ttk.Frame(bot)
        cost_row.pack(fill="x", padx=4, pady=(0, 2))
        ttk.Label(cost_row, text="路线成本:").pack(side="left")
        self.cost_mode = tk.StringVar(value="full")
        ttk.Combobox(cost_row, textvariable=self.cost_mode, width=8, state="readonly",
                     values=["len", "turn", "full"]).pack(side="left")
        view_row = ttk.Frame(bot)
        view_row.pack(fill="x", padx=4, pady=(0, 2))
        ttk.Label(view_row, text="画布显示:").pack(side="left")
        vcb = ttk.Combobox(view_row, textvariable=self.route_view, width=10,
                           state="readonly", values=list(ROUTE_VIEW_MODES))
        vcb.pack(side="left")
        vcb.bind("<<ComboboxSelected>>", lambda _e: self._route_view_changed())

        self.txt_route = tk.Text(bot, height=9, wrap="word")
        self.txt_route.pack(fill="both", expand=True, padx=4, pady=(3, 0))
        row3 = ttk.Frame(bot)
        row3.pack(fill="x", padx=4, pady=4)
        ttk.Button(row3, text="复制 route[]", command=self.copy_route_array).pack(side="left")
        ttk.Button(row3, text="复制调试宏", command=self.copy_debug_macros).pack(
            side="left", padx=6)

    def _build_right(self, parent):
        """右栏：上=属性，中=底图对齐，下=校验结果。"""
        # 右栏内容较多，整体滚动避免底部控件被窗口高度截断。
        viewport = tk.Canvas(parent, highlightthickness=0, borderwidth=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=viewport.yview)
        viewport.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        viewport.pack(side="left", fill="both", expand=True)
        content = ttk.Frame(viewport)
        content_id = viewport.create_window((0, 0), window=content, anchor="nw")

        def update_scrollregion(_event=None):
            viewport.configure(scrollregion=viewport.bbox("all"))

        def resize_content(event):
            viewport.itemconfigure(content_id, width=event.width)

        content.bind("<Configure>", update_scrollregion)
        viewport.bind("<Configure>", resize_content)

        def wheel(event):
            viewport.yview_scroll(-1 if event.delta > 0 else 1, "units")

        viewport.bind("<MouseWheel>", wheel)
        content.bind("<MouseWheel>", wheel)

        pane = ttk.Panedwindow(content, orient="vertical")
        pane.pack(fill="both", expand=True)

        top = ttk.Frame(pane)
        pane.add(top, weight=5)
        self.prop = ttk.Frame(top)
        self.prop.pack(fill="both", expand=True, padx=6, pady=6)
        self._prop_widgets = {}
        self._build_prop_widgets()

        mid = ttk.Frame(pane)
        pane.add(mid, weight=3)
        self._build_bg_panel(mid)

        bot = ttk.Frame(pane)
        pane.add(bot, weight=2)
        brow = ttk.Frame(bot)
        brow.pack(fill="x", padx=6, pady=(4, 2))
        ttk.Label(brow, text="校验结果").pack(side="left")
        ttk.Button(brow, text="重新校验", command=self.do_validate).pack(side="right")
        self.txt_val = tk.Text(bot, height=7, wrap="word")
        self.txt_val.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        self.txt_val.tag_configure("error", foreground="#c0392b")
        self.txt_val.tag_configure("warn", foreground="#b9770e")
        self.txt_val.tag_configure("info", foreground="#2471a3")

    # ---- 底图对齐面板 ----
    def _build_bg_panel(self, parent):
        f = ttk.LabelFrame(parent, text="底图对齐（只影响显示，不影响任何数值）")
        f.pack(fill="both", expand=True, padx=6, pady=4)
        self._bg_widgets = {}
        self._bg_suspend = False

        # 选图
        r0 = ttk.Frame(f)
        r0.pack(fill="x", padx=4, pady=(4, 2))
        cands = list_bg_candidates()
        self._bg_cands = cands

        def short(p):
            return os.path.basename(p)

        self._bg_choice = tk.StringVar(value=short(self.bg.path))
        cb = ttk.Combobox(r0, textvariable=self._bg_choice, width=18, state="readonly",
                          values=[short(p) for p in cands] or [short(self.bg.path)])
        cb.pack(side="left")
        cb.bind("<<ComboboxSelected>>", self._on_bg_choice)
        ttk.Button(r0, text="浏览…", width=6, command=self.pick_bg_image).pack(
            side="left", padx=3)
        r0b = ttk.Frame(f)
        r0b.pack(fill="x", padx=4, pady=(0, 4))
        ttk.Checkbutton(r0b, text="显示底图", variable=self.show_bg,
                        command=self.redraw).pack(side="left")
        ttk.Button(r0b, text="贴到节点", command=self.bg_fit_to_nodes).pack(
            side="left", padx=3)
        ttk.Button(r0b, text="居中", command=self.bg_reset).pack(side="left")

        # 位置/缩放/透明度：滑条 + 数字框（数字框可直接输入任意值，滑条快速调）
        def control(row, key, label, lo, hi, fmt="%.4g"):
            box = ttk.Frame(f)
            box.pack(fill="x", padx=4, pady=1)
            ttk.Label(box, text=label, width=7).pack(side="left")
            var = tk.DoubleVar(value=0.0)
            lab = ttk.Label(box, width=8, anchor="e")

            def apply(v, k=key, l=lab, fm=fmt):
                if self._bg_suspend:
                    return
                setattr(self.bg, k, float(v))
                self.bg._cache = (None, None)
                l.configure(text=fm % float(v))
                self.redraw()

            def on_move(_v, v=var, ap=apply):
                ap(v.get())
            sc = ttk.Scale(box, from_=lo, to=hi, variable=var, command=on_move)
            sc.pack(side="left", fill="x", expand=True, padx=3)
            lab.pack(side="left")
            # 数字框：直接输入精确值（滑条拖不准时用这个）
            ent = ttk.Entry(box, width=8)
            ent.pack(side="left", padx=(3, 0))

            def on_entry(_e=None, k=key, en=ent, v=var, ap=apply):
                try:
                    val = float(en.get())
                except ValueError:
                    return
                v.set(val)
                ap(val)

            ent.bind("<Return>", on_entry)
            ent.bind("<FocusOut>", on_entry)
            self._bg_widgets[key] = (var, lab, fmt, ent)
            return sc

        control(0, "off_x", "偏移 X", -3000, 3000, "%.0f")
        control(1, "off_y", "偏移 Y", -3000, 3000, "%.0f")
        control(2, "scale_x", "缩放 X", 0.3, 2.0, "%.4f")
        control(3, "scale_y", "缩放 Y", 0.3, 2.0, "%.4f")
        control(4, "opacity", "透明度", 0.05, 1.0, "%.2f")

        ttk.Label(f, text="滑条范围有限；数字框可直接填任意值（含负几千）。\n"
                          "「贴到节点」把底图摆到与节点最佳重合的位置。",
                  foreground="#666666", justify="left").pack(anchor="w", padx=4, pady=(4, 4))
        self.refresh_bg_panel()

    def refresh_bg_panel(self):
        if not hasattr(self, "_bg_widgets"):
            return
        self._bg_suspend = True
        try:
            for key, tup in self._bg_widgets.items():
                var, lab, fmt, ent = tup[0], tup[1], tup[2], tup[3]
                v = float(getattr(self.bg, key))
                var.set(v)
                lab.configure(text=fmt % v)
                ent.delete(0, "end")
                ent.insert(0, fmt % v)
            self._bg_choice.set(os.path.basename(self.bg.path))
        finally:
            self._bg_suspend = False

    def _on_bg_choice(self, _ev):
        name = self._bg_choice.get()
        for p in self._bg_cands:
            if os.path.basename(p) == name:
                self.set_bg_image(p)
                return

    def bg_reset(self):
        self.bg.reset_calib()
        self.refresh_bg_panel()
        self.redraw()
        self.status("底图标定已重置为 1:1 居中")

    def bg_fit_to_nodes(self):
        n, resid = self.bg.fit_to_nodes()
        if n < 2:
            self.status("节点坐标不足，无法反推")
            return
        self.refresh_bg_panel()
        self.redraw()
        self.status("已用 %d 个有图上坐标的节点反推标定：scale=(%.4f, %.4f) "
                    "off=(%.0f, %.0f)，平均残差 %.1f px（残差大=原图本身就不是等比例的）"
                    % (n, self.bg.scale_x, self.bg.scale_y,
                       self.bg.off_x, self.bg.off_y, resid))

    # ---- 属性面板控件 ----
    def _build_prop_widgets(self):
        f = self.prop
        for w in f.winfo_children():
            w.destroy()
        self._prop_widgets = {}

        self.lbl_sel = ttk.Label(f, text="（未选中）", font=("", 10, "bold"))
        self.lbl_sel.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))

        r = 1

        def lab(text):
            nonlocal r
            ttk.Label(f, text=text).grid(row=r, column=0, sticky="w", pady=1)
            return r

        # 通用文本字段
        for key, title in (("name", "节点名/log"), ("comment", "说明")):
            lab(title)
            e = ttk.Entry(f, width=26)
            e.grid(row=r, column=1, sticky="we", pady=1)
            self._prop_widgets[key] = e
            r += 1

        lab("from")
        self._prop_widgets["from"] = ttk.Combobox(f, width=24, state="readonly")
        self._prop_widgets["from"].grid(row=r, column=1, sticky="we", pady=1)
        r += 1
        lab("to")
        self._prop_widgets["to"] = ttk.Combobox(f, width=24, state="readonly")
        self._prop_widgets["to"].grid(row=r, column=1, sticky="we", pady=1)
        r += 1

        for key, title in (("angle", "角度 angle"), ("step", "长度 step"),
                           ("speed", "速度 speed")):
            lab(title)
            e = ttk.Entry(f, width=26)
            e.grid(row=r, column=1, sticky="we", pady=1)
            self._prop_widgets[key] = e
            r += 1

        lab("功能 function")
        cb = ttk.Combobox(f, width=24, values=M.FUNC_ORDER)
        cb.grid(row=r, column=1, sticky="we", pady=1)
        self._prop_widgets["func"] = cb
        r += 1

        lab("flag")
        self._prop_widgets["flag"] = ttk.Entry(f, width=26)
        self._prop_widgets["flag"].grid(row=r, column=1, sticky="we", pady=1)
        r += 1

        # flag 勾选板
        self.flag_frame = ttk.LabelFrame(f, text="flag 位（勾选即改 flag 文本）")
        self.flag_frame.grid(row=r, column=0, columnspan=2, sticky="we", pady=6)
        self.flag_vars = {}
        cols = 2
        for i, name in enumerate(M.FLAG_ORDER):
            v = tk.BooleanVar(value=False)
            self.flag_vars[name] = v
            ttk.Checkbutton(self.flag_frame, text=name, variable=v,
                            command=self._flags_to_text).grid(
                row=i // cols, column=i % cols, sticky="w", padx=2)
        r += 1

        # 按钮行
        brow = ttk.Frame(f)
        brow.grid(row=r, column=0, columnspan=2, sticky="we", pady=6)
        ttk.Button(brow, text="应用修改", command=self.apply_props).pack(side="left")
        ttk.Button(brow, text="删除选中", command=self.delete_selected).pack(side="left", padx=3)
        r += 1

        # 快捷增删（不用手选 from/to）
        q = ttk.LabelFrame(f, text="快捷增删边（不用手选 from/to）")
        q.grid(row=r, column=0, columnspan=2, sticky="we", pady=6)
        ttk.Button(q, text="从选中节点连线（或右键节点 / 按 A）",
                   command=self.start_connect_from_sel).pack(fill="x", padx=4, pady=2)
        ttk.Button(q, text="＋ 补反向边（复制选中边参数）",
                   command=self.make_reverse_edge).pack(fill="x", padx=4, pady=2)
        ttk.Button(q, text="－ 删除这一对（双向都删）",
                   command=self.delete_sel_pair).pack(fill="x", padx=4, pady=2)
        ttk.Label(q, text="点图形即可选中边（命中区已加宽到 ±7px）；\n"
                          "右键节点 = 以它为起点连线（Shift+右键 = 节点菜单）。",
                  foreground="#666666", justify="left").pack(anchor="w", padx=4, pady=(2, 4))
        r += 1

        # 数值辅助
        g = ttk.LabelFrame(f, text="辅助")
        g.grid(row=r, column=0, columnspan=2, sticky="we", pady=6)
        ttk.Button(g, text="按图上位置算角度", command=self.calc_angle_geo).pack(
            fill="x", padx=4, pady=2)
        ttk.Button(g, text="按图上位置算 step(px÷K)", command=self.calc_step_geo).pack(
            fill="x", padx=4, pady=2)
        ttk.Label(g, text="Ctrl+拖空白框选（紫色）后，上面两个按钮会一次改\n"
                          "所有「两端都在框内」的边；点空白/点单条边则恢复单选。",
                  foreground="#666666", justify="left").pack(anchor="w", padx=4, pady=(0, 2))
        ttk.Button(g, text="整条边取反（from/to 互换，角度+180）",
                   command=self.reverse_edge_sel).pack(fill="x", padx=4, pady=2)

    def platform_swap_dialog(self):
        """平台快速交换：把两个平台节点的**名字互换**。

        * `angle`/`step`/`flag`/`speed` **全部沿用原值** ⇒ 长度不变；
        * 每条相关边的 `func` 换成"新名字那个平台"的入口/出口动作 ⇒ **function 随平台切换**
          （例：`P5↔P7` ⇒ `N13→P7` 变 `BSoutPole`、`B7→P5` 变 `UpStage`，step 一个都不动）；
        * 默认**位置不动**（"其他沿用原来的"），可勾选"连坐标一起换"。
        ⚠️ 换完必须自己复核 `mission_planner.c` 的 `wp` / 门逻辑 / 宝物表（它们都按平台名走）。
        """
        plats = [n.name for n in self.model.nodes if n.name[:1] == "P"]
        if len(plats) < 2:
            messagebox.showerror("平台快速交换", "地图里少于 2 个 P 平台节点，换不了。", parent=self)
            return
        last = getattr(self, "_plat_swap_last", None)
        dlg = tk.Toplevel(self)
        dlg.title("平台快速交换（长度不变，function 随平台切换）")
        dlg.geometry("620x430")
        dlg.transient(self)
        frm = ttk.Frame(dlg, padding=12)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, wraplength=580, justify="left",
                  text="互换两个平台的名字：**只改 from/to**，长度/角度/flag 全部沿用；"
                       "每条相关边的 func 换成新平台的动作。位置默认不动。").pack(anchor="w")

        row = ttk.Frame(frm)
        row.pack(fill="x", pady=(10, 4))
        ttk.Label(row, text="平台 A").pack(side="left")
        a_var = tk.StringVar(value=(last[0] if last and last[0] in plats else plats[0]))
        ttk.Combobox(row, textvariable=a_var, values=plats, state="readonly",
                     width=8).pack(side="left", padx=(4, 14))
        ttk.Label(row, text="⇄").pack(side="left")
        ttk.Label(row, text="平台 B").pack(side="left", padx=(14, 0))
        b_var = tk.StringVar(value=(last[1] if last and last[1] in plats else plats[-1]))
        ttk.Combobox(row, textvariable=b_var, values=plats, state="readonly",
                     width=8).pack(side="left", padx=4)

        xy_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(frm, text="连图上的坐标也一起换（默认不换，只换平台身份）",
                        variable=xy_var).pack(anchor="w", pady=(2, 6))

        ttk.Label(frm, text="改动预览：").pack(anchor="w")
        prev = tk.Text(frm, height=12, wrap="word")
        prev.pack(fill="both", expand=True, pady=(2, 8))

        def refresh(*_a):
            try:
                ch = self.model.swap_platforms(a_var.get(), b_var.get(), xy_var.get(),
                                               dry_run=True)
                txt = "\n".join(ch) if ch else "（这两个平台的相关边完全一样，换了没有变化）"
            except ValueError as ex:
                txt = "⚠ %s" % ex
            prev.configure(state="normal")
            prev.delete("1.0", "end")
            prev.insert("end", txt)
            prev.configure(state="disabled")

        a_var.trace_add("write", refresh)
        b_var.trace_add("write", refresh)
        xy_var.trace_add("write", refresh)
        refresh()

        def do_it():
            snap = self.model.snapshot()
            try:
                ch = self.model.swap_platforms(a_var.get(), b_var.get(), xy_var.get())
            except ValueError as ex:
                messagebox.showerror("平台快速交换", str(ex), parent=dlg)
                return
            self._plat_swap_last = (a_var.get(), b_var.get())
            self.sel_node = self.sel_edge = None
            self._apply_change(snap)
            self.refresh_all()
            self.status("已交换平台 %s ⇄ %s（%d 处改动）；⚠ 请复核 mission_planner.c 的 "
                        "wp / 门逻辑 / 宝物表" % (a_var.get(), b_var.get(), len(ch)))
            dlg.destroy()

        btns = ttk.Frame(frm)
        btns.pack(fill="x")
        ttk.Button(btns, text="交换", command=do_it).pack(side="left")
        ttk.Button(btns, text="取消", command=dlg.destroy).pack(side="left", padx=8)
        ttk.Label(btns, text="⚠ 会直接改当前模型（可 Ctrl+Z 撤销；写回固件才动源码）",
                  foreground="#a04000").pack(side="left", padx=12)

    # ================================================================ 视图变换
    def _rot_xy(self):
        """返回 (a, b, c, d)，变换为 view = (a*x + b*y, c*x + d*y)。"""
        return ROT_MATRIX.get(self.rot.get(), (1, 0, 0, 1))

    def world_to_view(self, x, y):
        """世界坐标(原图像素系) → 视图坐标。0° 档是恒等变换。"""
        a, b, c, d = self._rot_xy()
        return (a * x + b * y, c * x + d * y)

    def view_to_world(self, vx, vy):
        """world_to_view 的逆（矩阵正交，逆 = 转置）。"""
        a, b, c, d = self._rot_xy()
        return (a * vx + c * vy, b * vx + d * vy)

    def w2s(self, x, y):
        vx, vy = self.world_to_view(x, y)
        return (self.ox + vx * self.scale, self.oy + vy * self.scale)

    def s2w(self, sx_, sy_):
        vx = (sx_ - self.ox) / self.scale
        vy = (sy_ - self.oy) / self.scale
        return self.view_to_world(vx, vy)

    def _fit_view(self):
        """把整张图缩放到窗口里（自动适配）。"""
        if not self.model.nodes or getattr(self, "_fitting", False):
            return
        self._fitting = True
        try:
            cw = self.canvas.winfo_width()
            ch = self.canvas.winfo_height()
            if cw <= 60 or ch <= 60:
                # 还没有真实尺寸：这轮先不动，等下次 <Configure>
                return
            self._fit_to(cw, ch)
        finally:
            self._fitting = False

    def _fit_to(self, cw, ch):
        """按给定视口尺寸让整张图居中铺满（在**视图坐标系**里算，已含旋转）。"""
        if not self.model.nodes:
            return
        vpts = [self.world_to_view(n.x, n.y) for n in self.model.nodes]
        xs = [p[0] for p in vpts]
        ys = [p[1] for p in vpts]
        pad = 60.0
        w = max(1.0, max(xs) - min(xs) + 2 * pad)
        h = max(1.0, max(ys) - min(ys) + 2 * pad)
        # 再留 3% 余量，避免贴边/被节点半径顶出去
        self.scale = max(0.15, min(cw / w, ch / h) * 0.97)
        cxm, cym = (min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0
        self.ox = cw / 2.0 - cxm * self.scale
        self.oy = ch / 2.0 - cym * self.scale
        self.user_zoomed = False
        self.redraw()

    # ---- 背景底图 ----
    def pick_bg_image(self):
        path = filedialog.askopenfilename(
            title="选择底图（节点图 / 场地规则图 / 你自己画的图）",
            initialdir=os.path.join(M.ROOT, "寻宝地图"),
            filetypes=[("图片", "*.jpg *.jpeg *.png *.gif *.bmp"), ("所有文件", "*.*")],
            parent=self)
        if path:
            self.set_bg_image(path)

    def set_bg_image(self, path):
        """换一张底图并重算标定。"""
        if self.bg.load(path, quiet=False):
            self.bg.reset_calib()          # 换图后必须重新标定
            self.refresh_bg_panel()
            self.redraw()
            self.status("已换底图：%s（用右侧「底图」面板微调对齐）"
                        % os.path.basename(path))

    def _draw_bg(self):
        self.bg.draw(self.canvas, self.w2s)

    def model_bounds(self, with_pad=False, include_bg=False):
        """节点（可选：含底图范围）的模型坐标包围盒。"""
        xs = [n.x for n in self.model.nodes] or [0.0]
        ys = [n.y for n in self.model.nodes] or [0.0]
        x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
        if include_bg and self.bg.img is not None:
            bx0, by0, bx1, by1 = self.bg.rect()
            x0, y0 = min(x0, bx0), min(y0, by0)
            x1, y1 = max(x1, bx1), max(y1, by1)
        pad = 46.0 if with_pad else 0.0
        return (x0 - pad, y0 - pad, x1 + pad, y1 + pad)

    def _update_bg_rect(self):
        """仅在没有有效标定时给一个默认标定（有标定就不动，避免覆盖用户调好的）。"""
        if self.bg.img is None:
            return
        if self.bg.off_x == 0.0 and self.bg.off_y == 0.0 and self.bg.scale_x == 1.0:
            self.bg.reset_calib()

    # ================================================================ 绘制
    def redraw(self):
        c = self.canvas
        c.delete("all")
        self._canvas_items = {"nodes": {}, "edges": {}}
        if self.show_grid.get():
            self._draw_grid()
        self._draw_bg()
        self._draw_edges()
        self._draw_nodes()
        self._draw_route()
        self._draw_turn_focus()
        self._draw_drag_overlay()
        self._draw_bg_handles()
        self.zoom_var.set("%d%%" % round(self.scale * 100))

    def _bg_handle_points(self):
        if self.bg.img is None:
            return []
        x0, y0, x1, y1 = self.bg.rect()
        return [("nw", *self.w2s(x0, y0)), ("ne", *self.w2s(x1, y0)),
                ("sw", *self.w2s(x0, y1)), ("se", *self.w2s(x1, y1))]

    def _draw_bg_handles(self):
        if not self.adjust_bg.get() or not self.show_bg.get():
            return
        for _name, x, y in self._bg_handle_points():
            self.canvas.create_rectangle(x - 6, y - 6, x + 6, y + 6,
                                         fill="#2980b9", outline="white",
                                         width=1, tags="bg_handle")

    def _bg_handle_at(self, sx, sy):
        for name, x, y in self._bg_handle_points():
            if math.hypot(sx - x, sy - y) <= 11:
                return name
        return None

    def _start_bg_drag(self, ev, handle=None):
        self._snap_before = self.model.snapshot()
        self._bg_drag = {"handle": handle, "start": (ev.x, ev.y),
                         "rect": self.bg.rect(),
                         "calib": self.bg.calib_snapshot(), "moved": False}

    def _move_bg_drag(self, ev):
        d = self._bg_drag
        x0, y0, x1, y1 = d["rect"]
        wx, wy = self.s2w(ev.x, ev.y)
        ox0, oy0, ox1, oy1 = x0, y0, x1, y1
        if d["handle"]:
            h = d["handle"]
            if "w" in h:
                x0 = min(wx, x1 - 1.0)
            else:
                x1 = max(wx, x0 + 1.0)
            if "n" in h:
                y0 = min(wy, y1 - 1.0)
            else:
                y1 = max(wy, y0 + 1.0)
            rw, rh = self.bg.ref_size()
            self.bg.off_x = x0
            self.bg.off_y = y0
            self.bg.scale_x = max(0.01, (x1 - x0) / rw)
            self.bg.scale_y = max(0.01, (y1 - y0) / rh)
        else:
            start_x, start_y = d["start"]
            dx, dy = self.s2w(ev.x, ev.y)[0] - self.s2w(start_x, start_y)[0], \
                     self.s2w(ev.x, ev.y)[1] - self.s2w(start_x, start_y)[1]
            self.bg.off_x = ox0 + dx
            self.bg.off_y = oy0 + dy
        self.bg._cache = (None, None)
        d["moved"] = True
        self.model.dirty = True
        self.refresh_bg_panel()
        self.redraw()

    def _draw_grid(self):
        """网格：在**视图坐标系**里画（跟随旋转）。"""
        step = 50
        x0, y0 = self.s2w(0, 0)
        x1, y1 = self.s2w(self.canvas.winfo_width(), self.canvas.winfo_height())
        xa, xb = min(x0, x1), max(x0, x1)
        ya, yb = min(y0, y1), max(y0, y1)
        vx = int(xa // step) * step
        while vx <= xb:
            sx, _ = self.w2s(*self.view_to_world(vx, 0))
            self.canvas.create_line(sx, 0, sx, self.canvas.winfo_height(),
                                    fill="#eeeeee", tags="grid")
            vx += step
        vy = int(ya // step) * step
        while vy <= yb:
            _, sy = self.w2s(*self.view_to_world(0, vy))
            self.canvas.create_line(0, sy, self.canvas.winfo_width(), sy,
                                    fill="#eeeeee", tags="grid")
            vy += step

    def _node_radius(self, name):
        """屏幕半径：随缩放变化，但夹在 [5, 26]，避免缩小时全糊在一起。"""
        n = self.model.node(name)
        k = n.kind if n else "?"
        base = NODE_STYLE.get(k, NODE_STYLE["?"])[2]
        return max(5.0, min(26.0, base * self.scale / 0.55))

    @staticmethod
    def _font(size, bold=False):
        return ("", int(round(size)), "bold") if bold else ("", int(round(size)))

    def _draw_nodes(self):
        m = self.label_mode.get()
        show_label = (m != "无") and (self.scale >= 0.30)
        for n in self.model.nodes:
            sx, sy = self.w2s(n.x, n.y)
            fill, outline, _base, shape = NODE_STYLE.get(n.kind, NODE_STYLE["?"])
            rad = self._node_radius(n.name)
            sel = (n.name == self.sel_node)
            batch = n.name in self.selected_nodes
            lw = 3 if sel else (2.4 if batch else 1.6)
            oc = EDGE_COLOR_SEL if sel else (BATCH_COLOR if batch else outline)
            if shape == "rect":
                items = [self.canvas.create_rectangle(
                    sx - rad * 1.15, sy - rad * 0.68, sx + rad * 1.15, sy + rad * 0.68,
                    fill=fill, outline=oc, width=lw)]
            elif shape == "diamond":
                items = [self.canvas.create_polygon(
                    sx, sy - rad, sx + rad, sy, sx, sy + rad, sx - rad, sy,
                    fill=fill, outline=oc, width=lw)]
            elif shape == "square":
                items = [self.canvas.create_rectangle(
                    sx - rad * 0.85, sy - rad * 0.85, sx + rad * 0.85, sy + rad * 0.85,
                    fill=fill, outline=oc, width=lw)]
            else:
                items = [self.canvas.create_oval(
                    sx - rad, sy - rad, sx + rad, sy + rad,
                    fill=fill, outline=oc, width=lw)]
            if show_label and rad >= 7:
                t = self.canvas.create_text(sx, sy, text=n.name,
                                            font=self._font(min(11, max(6, rad * 0.78)),
                                                            bold=True),
                                            fill="#222222")
                items.append(t)
            self._canvas_items["nodes"][n.name] = items
            for it in items:
                self.canvas.tag_bind(it, "<ButtonPress-1>",
                                     lambda e, nm=n.name: self._on_node_press(e, nm))
                self.canvas.tag_bind(it, "<Double-Button-1>",
                                     lambda e, nm=n.name: self._on_node_double(e, nm))
                self.canvas.tag_bind(it, "<Button-3>",
                                     lambda e, nm=n.name: self._on_node_right(e, nm))

    def _edge_endpoints(self, e, rad_from, rad_to):
        a = self.model.node(e.frm)
        b = self.model.node(e.to)
        if not a or not b:
            return None
        x1, y1 = self.w2s(a.x, a.y)
        x2, y2 = self.w2s(b.x, b.y)
        dx, dy = x2 - x1, y2 - y1
        d = (dx * dx + dy * dy) ** 0.5
        if d < 1e-6:
            return None
        ux, uy = dx / d, dy / d
        # 反向边存在时，两条线各往两边偏一点（相隔 2×EDGE_PAIR_OFFSET），否则完全重叠看不出方向
        off = 0.0
        if self.model.has_reverse(e):
            off = EDGE_PAIR_OFFSET
            ux2, uy2 = -uy, ux
        else:
            ux2, uy2 = 0.0, 0.0
        x1o, y1o = x1 + ux * (rad_from + 2) + ux2 * off, y1 + uy * (rad_from + 2) + uy2 * off
        x2o, y2o = x2 - ux * (rad_to + 6) + ux2 * off, y2 - uy * (rad_to + 6) + uy2 * off
        return (x1o, y1o, x2o, y2o, ux, uy)

    def _draw_edges(self):
        m = self.label_mode.get()
        warnings = self._geometry_warning_map() if self.show_geometry_warnings.get() else {}
        for e in self.model.edges:
            ep = self._edge_endpoints(e, self._node_radius(e.frm), self._node_radius(e.to))
            if not ep:
                continue
            x1, y1, x2, y2, ux, uy = ep
            sel = (self.sel_edge is not None and self.sel_edge.tag == e.tag)
            batch = (e.frm, e.to) in self.selected_edges
            special = (e.func not in ("NONE", "", None))
            warned = e.tag in warnings
            col = "#e74c3c" if warned else (EDGE_COLOR_SEL if sel else (
                BATCH_COLOR if batch else (EDGE_COLOR_FUNC if special else EDGE_COLOR)))
            w = 3.2 if warned else (2.6 if (sel or batch) else (
                2.0 if special else 1.3))
            seg = math.hypot(x2 - x1, y2 - y1)
            # 命中区：先用一条**透明粗线**铺在底下，这样点在边附近（±7px 左右）就能选中，
            # 不用精确点中那条 1.3px 的细线。
            hit = self.canvas.create_line(x1, y1, x2, y2, fill="", width=EDGE_HIT_WIDTH,
                                          capstyle="round")
            items = [hit,
                     self.canvas.create_line(x1, y1, x2, y2, fill=col, width=w,
                                             arrow="last", arrowshape=(9, 11, 4))]
            if (m != "无" or self.show_edge_lengths.get()) and seg >= 46:
                mx, my = (x1 + x2) / 2.0, (y1 + y2) / 2.0
                ang = self.model.ang(e)
                stp = self.model.step(e)
                length_cm = self._world_len_cm(e)   # 用世界坐标 ⇒ 不随缩放变化
                if m == "详细" and seg >= 80:
                    txt = "%s\n%.0f° %s" % (
                        e.func, ang if ang is not None else 0,
                        ("%.0f" % stp) if stp is not None else "?")
                elif m != "无":
                    txt = ("%.0f°" % ang) if ang is not None else "?"
                else:
                    txt = ""
                # 沿法线让开一点，避免压在线上
                nx, ny = -uy * 8, ux * 8
                if self.show_edge_lengths.get():
                    length_txt = "图 %.1fcm" % length_cm if length_cm is not None else "图 ?cm"
                    txt = (txt + "\n" if txt else "") + length_txt
                    # 蓝色标尺代表表中 step 的图上长度：
                    # 蓝尺/原边 = (step*K)/图上长度，不能直接复用原边长度。
                    target_world = stp * self._unit_k() if stp is not None else None
                    target_screen = (target_world * self.scale
                                     if target_world is not None else None)
                    if target_screen is not None and target_screen > 0:
                        dim_off = 16
                        # 从 from 端发出单向射线，箭头明确指向 to 方向。
                        dx1 = x1 + (-uy) * dim_off
                        dy1 = y1 + ux * dim_off
                        dx2 = dx1 + ux * target_screen
                        dy2 = dy1 + uy * target_screen
                        items.append(self.canvas.create_line(
                            dx1, dy1, dx2, dy2, fill="#2980b9", width=1,
                            arrow="last", arrowshape=(7, 8, 3), dash=(3, 2)))
                items.append(self.canvas.create_text(
                    mx + nx, my + ny, text=txt,
                    font=self._font(min(9, max(6, 7 * self.scale / 0.4))),
                    fill="#e74c3c" if warned else (
                        EDGE_COLOR_SEL if sel else (BATCH_COLOR if batch else "#333333"))))
            elif warned:
                mx, my = (x1 + x2) / 2.0, (y1 + y2) / 2.0
                nx, ny = -uy * 8, ux * 8
                items.append(self.canvas.create_text(
                    mx + nx, my + ny, text="⚠",
                    font=self._font(9, bold=True), fill="#e74c3c"))
            self._canvas_items["edges"][e.tag] = items
            for it in items:
                self.canvas.tag_bind(it, "<ButtonPress-1>",
                                     lambda ev, ed=e: self._on_edge_press(ev, ed))
                self.canvas.tag_bind(it, "<Double-Button-1>",
                                     lambda ev, ed=e: self._on_edge_double(ev, ed))
                self.canvas.tag_bind(it, "<Button-3>",
                                     lambda ev, ed=e: self._on_edge_menu(ev, ed))

    def _route_split_ok(self):
        """当前路线是否真有去程/回程分色（有 split 且落在路线中间）。"""
        return (self.route_split is not None
                and 0 < self.route_split < len(self.route) - 1)

    def _draw_route(self):
        if len(self.route) < 2:
            return
        split = self.route_split
        if not self._route_split_ok():
            segs = [(self.route, ROUTE_COLOR, "去程")]
        else:
            # 去程/回程分开上色（共享交接点，避免中间断一截）
            segs = [(self.route[:split + 1], ROUTE_COLOR, "去程"),
                    (self.route[split:], ROUTE_COLOR_BACK, "回程")]
        # 去程/回程叠在一条走廊上时看不清 —— 按面板上的「画布显示」只画其中一段
        mode = self.route_view.get()
        if mode == "只看去程":
            segs = [s for s in segs if s[2] == "去程"]
        elif mode == "只看回程":
            segs = [s for s in segs if s[2] == "回程"]
        if not segs:
            return
        drawn, allpts = [], []
        for names, col, tag in segs:
            pts = []
            for name in names:
                n = self.model.node(name)
                if n:
                    pts.extend(self.w2s(n.x, n.y))
            if len(pts) < 4:
                continue
            allpts.extend(zip(pts[0::2], pts[1::2]))
            self.canvas.create_line(*pts, fill=col, width=7, dash=(10, 5),
                                    arrow="last", arrowshape=(12, 14, 5))
            for i in range(0, len(pts), 2):
                self.canvas.create_oval(pts[i] - 5, pts[i + 1] - 5,
                                        pts[i] + 5, pts[i + 1] + 5,
                                        fill=col, outline="white", width=2)
            drawn.append((tag, col, len(names)))
        # 交接点（回程起点）单独标一圈
        if len(segs) > 1:
            n = self.model.node(self.route[split])
            if n:
                x, y = self.w2s(n.x, n.y)
                self.canvas.create_oval(x - 11, y - 11, x + 11, y + 11,
                                        outline=ROUTE_COLOR_BACK, width=3)
        # 图例画在路线包围盒左上角外侧（跟着路线走，不受平移/缩放影响）
        if len(drawn) > 1 and allpts:
            lx = min(p[0] for p in allpts) - 4
            ly = min(p[1] for p in allpts) - 16 - 16 * len(drawn)
            for i, (tag, col, n) in enumerate(drawn):
                yy = ly + i * 16
                self.canvas.create_line(lx, yy, lx + 26, yy, fill=col, width=6, dash=(8, 4))
                self.canvas.create_text(lx + 32, yy, anchor="w",
                                        text="%s（%d 跳）" % (tag, n - 1),
                                        font=self._font(8), fill=col)

    def _draw_turn_focus(self):
        """把「转弯补偿…」对话框里选中的三元组 (last → now → next) 画在画布上。

        只按**节点位置**画示意折线（不依赖边本身画得出来），并把真正拐弯的那个节点
        （`now`）套一圈 + 标出转弯角 —— 一眼看清"这一项管的是哪个弯"。
        """
        if not self.turn_focus:
            return
        last, now, nxt = self.turn_focus
        nl, nn, nx = self.model.node(last), self.model.node(now), self.model.node(nxt)
        if not (nl and nn and nx):
            return
        col = TURN_FOCUS_COLOR
        pts = []
        for nd in (nl, nn, nx):
            pts.extend(self.w2s(nd.x, nd.y))
        self.canvas.create_line(*pts, fill=col, width=5, dash=(8, 4),
                                arrow="last", arrowshape=(12, 14, 5), tags="turn_focus")
        for nd, name in ((nl, last), (nx, nxt)):
            x, y = self.w2s(nd.x, nd.y)
            self.canvas.create_oval(x - 9, y - 9, x + 9, y + 9,
                                    outline=col, width=2, tags="turn_focus")
            self.canvas.create_text(x, y - 19, text=name, font=self._font(8),
                                    fill=col, tags="turn_focus")
        x, y = self.w2s(nn.x, nn.y)
        self.canvas.create_oval(x - 15, y - 15, x + 15, y + 15,
                                outline=col, width=3, tags="turn_focus")
        e_in, e_out = self.model.edge(last, now), self.model.edge(now, nxt)
        d = M.need2turn(self.model.ang(e_in) if e_in else None,
                        self.model.ang(e_out) if e_out else None)
        self.canvas.create_text(x, y + 24,
                                text="转弯 %s" % (("%+.1f°" % d) if d is not None else "?"),
                                font=self._font(8), fill=col, tags="turn_focus")

    def _draw_drag_overlay(self):
        """拖动时：把被拖节点的相邻边标出状态（角度/长度是否达标）。"""
        info = self._drag_info
        if not info or not info.get("edges"):
            return
        for it in info["edges"]:
            a, b = self.model.node(it["edge"].frm), self.model.node(it["edge"].to)
            if not a or not b:
                continue
            x1, y1 = self.w2s(a.x, a.y)
            x2, y2 = self.w2s(b.x, b.y)
            locked = (self.snap_mode.get() != "自由")
            ok = it["len_ok"] and (not locked or it["ang_ok"])
            col = "#27ae60" if ok else "#e74c3c"
            self.canvas.create_line(x1, y1, x2, y2, fill=col, width=2, dash=(3, 3))
            mx, my = (x1 + x2) / 2.0, (y1 + y2) / 2.0
            txt = "%.0fpx / %.0fcm" % (it["d"], it["cm"])
            if not it["len_ok"]:
                txt += "  需≥%.0f" % it["Lmin"]
            elif it["ang_dev"] is not None:
                txt += "  偏离%.1f°" % it["ang_dev"]
            self.canvas.create_text(mx, my - 14, text=txt, font=self._font(7),
                                    fill=col)
            if info.get("snapped"):
                self.canvas.create_text(mx, my - 25, text="已吸正", font=self._font(7),
                                        fill="#27ae60")
            if not it["len_ok"]:
                self.canvas.create_text(mx, my - (36 if info.get("snapped") else 25),
                                        text="⚠长度不足", font=self._font(7),
                                        fill="#e74c3c")

    # ================================================================ 鼠标交互
    def _bind_canvas(self):
        c = self.canvas
        c.bind("<ButtonPress-1>", self._on_bg_press)
        c.bind("<B1-Motion>", self._on_motion)
        c.bind("<ButtonRelease-1>", self._on_release)
        c.bind("<Double-Button-1>", self._on_bg_double)
        c.bind("<Button-3>", self._on_bg_menu)
        # 中键 / 空格拖 = 平移
        c.bind("<ButtonPress-2>", self._pan_start)
        c.bind("<B2-Motion>", self._pan_move)
        c.bind("<ButtonPress-3>", lambda e: None, add="+")
        c.bind("<MouseWheel>", self._on_wheel)          # Windows / macOS
        c.bind("<Button-4>", lambda e: self._zoom(1.12, e))   # Linux
        c.bind("<Button-5>", lambda e: self._zoom(1 / 1.12, e))
        c.bind("<Configure>", self._on_canvas_configure)

    def _on_canvas_configure(self, ev):
        """画布尺寸变化（窗口拉伸/布局落定）时重新适配。

        启动阶段 ttk.Panedwindow 还没布局完，canvas 会先报一个很小的宽度
        （约 394px）——如果只用那时的尺寸算 fit，整张图会被压成一小坨。
        所以只要用户没手动缩放，就在尺寸变化时重新 fit。"""
        if ev.width < 60 or ev.height < 60:
            return
        if getattr(self, "user_zoomed", False):
            self.redraw()
        else:
            self._fit_view()

    def _pan_start(self, ev):
        self._pan = (ev.x, ev.y, self.ox, self.oy)

    def _pan_move(self, ev):
        if not self._pan:
            return
        x0, y0, ox, oy = self._pan
        self.ox = ox + (ev.x - x0)
        self.oy = oy + (ev.y - y0)
        self.redraw()

    def _on_wheel(self, ev):
        self._zoom(1.12 if ev.delta > 0 else 1 / 1.12, ev)

    def _zoom(self, f, ev):
        wx, wy = self.s2w(ev.x, ev.y)
        self.user_zoomed = True
        self.scale = max(0.15, min(6.0, self.scale * f))
        self.ox = ev.x - wx * self.scale
        self.oy = ev.y - wy * self.scale
        self.redraw()

    def _on_node_press(self, ev, name):
        # 待连线状态（右键起点 / 连线模式起点）：左键点目标节点也能把边建出来
        if self.connect_from is not None or self.connect_mode.get():
            self._connect_pick(name)
            return "break"
        shift = bool(ev.state & 0x0001)
        if shift:
            self._link = {"from": name, "sx": ev.x, "sy": ev.y, "item": None}
            self.status("从 %s 拉出连线…松手在目标节点上完成" % name)
            return "break"
        if name in self.selected_nodes and len(self.selected_nodes) > 1:
            sx, sy = self.s2w(ev.x, ev.y)
            self._drag = {"group": tuple(self.selected_nodes),
                          "start": (sx, sy), "origin": {
                              nm: self._node_xy(nm) for nm in self.selected_nodes},
                          "moved": False}
            self._snap_before = self.model.snapshot()
            return "break"
        self.select_node(name)
        n = self.model.node(name)
        self._drag = {"name": name, "dx": n.x - self.s2w(ev.x, ev.y)[0],
                      "dy": n.y - self.s2w(ev.x, ev.y)[1], "moved": False}
        self._snap_before = self.model.snapshot()
        return "break"

    def _on_motion(self, ev):
        if getattr(self, "_bg_drag", None):
            self._move_bg_drag(ev)
            return "break"
        if getattr(self, "_marquee", None):
            box = self._marquee
            if box.get("item"):
                self.canvas.delete(box["item"])
            box["item"] = self.canvas.create_rectangle(
                box["x0"], box["y0"], ev.x, ev.y,
                outline="#2980b9", dash=(4, 2), width=1)
            return "break"
        if self._link:
            d = self._link
            x1, y1 = self.w2s(*self._node_xy(d["from"]))
            if d["item"]:
                self.canvas.delete(d["item"])
            d["item"] = self.canvas.create_line(x1, y1, ev.x, ev.y,
                                                fill=EDGE_COLOR_SEL, width=2, dash=(4, 3))
            return "break"
        if self._drag:
            d = self._drag
            if d.get("group"):
                sx, sy = d["start"]
                wx, wy = self.s2w(ev.x, ev.y)
                dx, dy = wx - sx, wy - sy
                for name in d["group"]:
                    n = self.model.node(name)
                    ox, oy = d["origin"][name]
                    n.x, n.y = ox + dx, oy + dy
                d["moved"] = True
                self.redraw()
                return "break"
            wx, wy = self.s2w(ev.x, ev.y)
            want = (wx + d["dx"], wy + d["dy"])
            pt, info = self.solve_drag_position(d["name"], want)
            n = self.model.node(d["name"])
            n.x, n.y = pt
            d["moved"] = True
            d["info"] = info
            self._drag_info = info
            self.redraw()
            self._show_drag_readout(info)
            return "break"
        return None

    # ---- 拖动约束求解 ----
    ANGLE_TOL = 1.0        # 判定"方向符合表里角度"的容差(°)

    def _unit_k(self):
        try:
            k = float(self.unit_px_per_cm.get())
        except Exception:
            k = 0.884
        return k if k > 1e-6 else 0.884

    def _edge_min_px(self, e):
        """该边要求的最小图长度（px）= step(cm) × K。"""
        st = self.model.step(e)
        if st is None or st <= 0:
            return 0.0
        return st * self._unit_k()

    def _world_len_cm(self, e):
        """该边在**图坐标**下的长度换算成 cm —— **与缩放无关**。

        ⚠️ 必须用世界坐标：`_edge_endpoints()` / `w2s()` 返回的是**屏幕**坐标，
        而屏px = 世界px × scale；直接拿屏幕距离 ÷ K 会让画布上那个"图 xx.xcm"
        随缩放一起变（踩过：放大就变大）。返回 None 表示算不了。
        """
        a, b = self.model.node(e.frm), self.model.node(e.to)
        k = self._unit_k()
        if a is None or b is None or k <= 0:
            return None
        return math.hypot(b.x - a.x, b.y - a.y) / k

    def _edge_pref_dirs(self, e, name):
        """这条边**偏好**的方向单位向量列表（从另一端指向 name 这一端）。

        按 `snap_mode` 决定：
        * **吸附水平/竖直**（默认）：偏好 0°/90°/180°/−90°（屏幕上的水平、竖直），
          这样拖动会**自动吸到水平或竖直**，而不是去对齐表里那个角度
          （节点图本来就不按角度表精确画，见 AI_CONTEXT §4.3）。
        * **跟随角度表**：偏好 = 边表 `angle + DRAG_ANGLE_OFFSET`（旧行为）。
        * **自由**：返回空（不做方向约束）。
        """
        if self.snap_mode.get() == "自由":
            return []
        if self.snap_mode.get() == "吸附水平/竖直":
            out = []
            for ang in AXIS_ANGLES:
                r = math.radians(ang)
                out.append((math.sin(r), -math.cos(r)))
            return out
        a, b = self.model.node(e.frm), self.model.node(e.to)
        if not a or not b:
            return []
        ang = self.model.ang(e)
        if ang is None:
            return []
        r = math.radians(ang + DRAG_ANGLE_OFFSET)
        rx, ry = math.sin(r), -math.cos(r)
        return [(rx, ry), (-rx, -ry)]

    # 兼容旧名字（外部/测试里可能还在用）
    def _allowed_dirs(self, e, name):
        return self._edge_pref_dirs(e, name)

    def _snap_thresholds(self):
        """(吸附阈值°, 软偏好范围°)。"""
        def _f(var, dflt):
            try:
                v = float(var.get())
            except Exception:
                return dflt
            return v if v > 0 else dflt
        return _f(self.snap_tol, SNAP_TOL_DEFAULT), _f(self.snap_near, SNAP_NEAR_DEFAULT)

    @staticmethod
    def _ang_dev(a1, a2):
        """两个角度之间的最小偏差（按"有向直线"：0 或 180 都算同向）。"""
        d = (a1 - a2) % 360.0
        if d > 180:
            d -= 360
        return abs(d)

    def solve_drag_position(self, name, want):
        """把"想拖到哪儿"吸附成"合法位置"。

        按 `snap_mode` 有三种行为：

        * **吸附水平/竖直**（默认）：
          - 方向偏好屏幕上的 **0°/90°/180°/−90°**（即水平或竖直）；
          - **软拉扯**：方向落在 `snap_near(默认25°)` 内 → 按"偏离偏好的平方"施压，
            越近拉得越紧；
          - **硬吸正**：原始鼠标位置离某条轴线在 `snap_tol(默认8°)` 以内 → 直接
            把该边**精确吸到水平或竖直**（这是"到一定范围就自动吸附"）。
        * **跟随角度表**：方向偏好 = 边表 `angle + DRAG_ANGLE_OFFSET`（旧行为）。
        * **自由**：不做方向约束。

        长度约束（`enforce_min_len`）独立生效：`|点-other| >= step × K`。
        **不移动其它节点**（只动被拖的那个），否则整张图会跑。

        实现：候选点 = 各偏好的射线（软拉扯只能落在这些方向上）+ 最小长度圆，
        逐个打分（离 want 的距离² + 偏好权重 × 垂距² + 长度违反惩罚），
        再按"硬吸正"做一次就近替换。返回 ((x, y), info)。
        """
        m = self.model
        k = self._unit_k()
        mode = self.snap_mode.get()
        dir_lock = (mode != "自由")
        tol_deg, near_deg = self._snap_thresholds()
        info = {"k": k, "edges": [], "mode": mode, "locked": dir_lock,
                "min_len": bool(self.enforce_min_len.get()), "moved": 0.0,
                "feasible": True, "note": "", "snapped": False,
                "tol": tol_deg, "near": near_deg}

        inc = [e for e in m.edges if e.frm == name or e.to == name]
        if not inc:
            return want, info

        # ---- 每条**线段**一条约束（S1→N3 与 N3→S1 是同一条线段，只算一次）----
        cons = []
        seen_seg = set()
        for e in inc:
            other = e.to if e.frm == name else e.frm
            on = m.node(other)
            if not on:
                continue
            key = frozenset((e.frm, e.to))
            if key in seen_seg:
                continue
            seen_seg.add(key)
            Lmin = self._edge_min_px(e) if self.enforce_min_len.get() else 0.0
            dirs = self._edge_pref_dirs(e, name) if dir_lock else []
            cons.append({"e": e, "on": on, "Lmin": Lmin, "dirs": dirs, "key": key})

        if not cons:
            return want, info

        # ---- 候选点：偏好射线（软拉扯的落点只能在这些方向上）+ 最小长度圆 ----
        cands = [want]
        R = max([c["Lmin"] for c in cons] + [1.0]) * 12.0
        R = max(R, 400.0)
        for c in cons:
            on = c["on"]
            for ux, uy in c["dirs"]:
                t0 = (want[0] - on.x) * ux + (want[1] - on.y) * uy
                for t in (max(t0, c["Lmin"]), c["Lmin"]):
                    if t >= c["Lmin"] - 1e-9:
                        cands.append((on.x + ux * t, on.y + uy * t))
                t, step_len = c["Lmin"], max(6.0, R / 60.0)
                while t <= R:
                    cands.append((on.x + ux * t, on.y + uy * t))
                    t += step_len
            if c["Lmin"] > 0:
                d0 = math.hypot(want[0] - on.x, want[1] - on.y)
                if d0 > 1e-9:
                    cands.append((on.x + (want[0] - on.x) / d0 * c["Lmin"],
                                  on.y + (want[1] - on.y) / d0 * c["Lmin"]))
                for i in range(24):
                    aa = 2 * math.pi * i / 24
                    cands.append((on.x + math.cos(aa) * c["Lmin"],
                                  on.y + math.sin(aa) * c["Lmin"]))

        # ---- 打分：离 want 越近越好；偏离偏好方向越少越好；长度不足要罚 ----
        # 偏好权重按 tan(near)² 取（同一量级）；最终的吸附由下面的"按范围确定性吸附"兜底。
        w_dir = math.tan(math.radians(max(1.0, near_deg))) ** 2
        TOL_LEN = 0.5

        def score(p):
            c = (p[0] - want[0]) ** 2 + (p[1] - want[1]) ** 2
            for cc in cons:
                on = cc["on"]
                dx, dy = p[0] - on.x, p[1] - on.y
                d = math.hypot(dx, dy)
                # 垂距（到最近的一条偏好方向所在直线）
                if cc["dirs"] and d > 1e-9:
                    perp = min(abs(dx * uy - dy * ux) for ux, uy in cc["dirs"])
                    c += w_dir * perp * perp
                if cc["Lmin"] > 0 and d + TOL_LEN < cc["Lmin"]:
                    c += (cc["Lmin"] - d) ** 2 * 100.0    # 长度不足重罚
            return c

        final = min(cands, key=score)

        # ---- 按"离最近轴的角度"确定性吸附 ----
        #  |偏离| <= 阈值(默认8°) → **精确吸正**（水平或竖直）
        #  |偏离| <= 软范围(25°)  → 投到该轴上（软拉扯；越近越像吸正）
        #  再远                   → 不干预，用上面打分的结果
        # ⚠️ 不要试图用"权重 × 垂距²"来实现软拉扯：实测权重 tan(near)² 太小
        #    （轴候选分数比原始位置大 4.6 倍），根本拉不动。用范围判断才可靠。
        if dir_lock and cons:
            cc = cons[0]
            o = cc["on"]
            raw_ang = math.degrees(math.atan2(want[0] - o.x, -(want[1] - o.y)))
            best_dir, best_dev = None, None
            for ux, uy in cc["dirs"]:
                dev = self._ang_dev(raw_ang, math.degrees(math.atan2(ux, -uy)))
                if best_dev is None or dev < best_dev:
                    best_dev, best_dir = dev, (ux, uy)
            if best_dir is not None and best_dev <= near_deg:
                ux, uy = best_dir
                snaps = []
                for c in cons:
                    oc = c["on"]
                    t = (want[0] - oc.x) * ux + (want[1] - oc.y) * uy
                    t = max(t, c["Lmin"])
                    snaps.append((oc.x + ux * t, oc.y + uy * t))
                final = min(snaps, key=lambda p: math.hypot(p[0] - want[0],
                                                            p[1] - want[1]))
                if best_dev <= tol_deg:
                    info["snapped"] = True     # 精确吸正
                else:
                    info["note"] = "已拉向最近轴（偏 %.0f°）" % best_dev
        info["moved"] = math.hypot(final[0] - want[0], final[1] - want[1])

        # ---- 硬吸正：原始位置已经"离某条轴线很近"时，直接吸到正 ----
        # ⚠️ 不能"逐方向试 + 比分数"：偏 5° 时"垂足"和"轴线上的点"分数几乎相同
        #    （差 < 1e-9），会被容差挡掉，导致吸不住（实测踩过）。
        #    正确做法：**明确挑出离得最近的那条轴**，然后无条件吸到它上面。
        if dir_lock and cons:
            cc = cons[0]
            on0 = cc["on"]
            raw_ang = math.degrees(math.atan2(want[0] - on0.x, -(want[1] - on0.y)))
            best_dir, best_dev = None, None
            for ux, uy in cc["dirs"]:
                axis_ang = math.degrees(math.atan2(ux, -uy))
                dev = self._ang_dev(raw_ang, axis_ang)
                if best_dev is None or dev < best_dev:
                    best_dev, best_dir = dev, (ux, uy, axis_ang)
            if best_dir is not None and best_dev <= tol_deg:
                ux, uy, _ = best_dir
                # 对每条约束都取"在该轴向上、且满足最小长度"的最近点，
                # 多条边时取离 want 最近的（避免把其它边拉长太多）
                picks = []
                for c in cons:
                    o = c["on"]
                    t = (want[0] - o.x) * ux + (want[1] - o.y) * uy
                    t = max(t, c["Lmin"])
                    picks.append((o.x + ux * t, o.y + uy * t))
                final = min(picks, key=lambda p: math.hypot(p[0] - want[0],
                                                            p[1] - want[1]))
                info["snapped"] = True
                info["moved"] = math.hypot(final[0] - want[0], final[1] - want[1])

        # ---- 诊断：逐边报方向与偏好差多少、长度够不够 ----
        for cc in cons:
            e, on = cc["e"], cc["on"]
            dx, dy = final[0] - on.x, final[1] - on.y
            d = math.hypot(dx, dy)
            real = math.degrees(math.atan2(dx, -dy)) if d > 1e-9 else None
            dev = None
            if real is not None and cc["dirs"]:
                dev = min(self._ang_dev(real, math.degrees(math.atan2(ux, -uy)))
                          for ux, uy in cc["dirs"])
            Lmin = self._edge_min_px(e)
            info["edges"].append({
                "edge": e, "other": on.name,
                "d": d, "cm": d / k if k else 0.0, "step": m.step(e), "Lmin": Lmin,
                "len_ok": d + 1e-6 >= Lmin,
                "real_ang": real, "tab_ang": m.ang(e),
                "ang_dev": dev,
                "ang_ok": (dev is None) or (dev <= max(self.ANGLE_TOL, 1.0)),
            })
        info["edges"].sort(key=lambda it: it["edge"].label())
        return final, info

    def _show_drag_readout(self, info):
        if not info or not info.get("edges"):
            return
        parts = []
        for it in info["edges"][:4]:
            e = it["edge"]
            step = it["step"] or 0
            flags = ""
            if not it["len_ok"]:
                flags += " ⚠长度%.0f<需%.0f" % (it["d"], it["Lmin"])
            if it["ang_dev"] is not None and it["real_ang"] is not None:
                if it["ang_ok"]:
                    flags += " ✓%.1f°" % it["real_ang"]
                else:
                    flags += " ⚠偏离%.1f°" % it["ang_dev"]
            parts.append("%s-%s %.0fpx(%.0fcm,step=%.0f)%s"
                         % (e.frm, e.to, it["d"], it["cm"], step, flags))
        head = "拖动 %s【%s" % (self._drag["name"], info.get("mode", "?"))
        if info.get("snapped"):
            head += "·已吸正"
        head += "】："
        self.status(head + "；".join(parts))

    def _on_release(self, ev):
        if getattr(self, "_bg_drag", None):
            moved = self._bg_drag.get("moved")
            self._bg_drag = None
            if moved:
                self._push_undo(self._snap_before)
                self.status("底图已调整，点击“保存布局”可保存位置和缩放")
            return "break"
        if getattr(self, "_marquee", None):
            box = self._marquee
            if box.get("item"):
                self.canvas.delete(box["item"])
            self._marquee = None
            x0, x1 = sorted((box["x0"], ev.x))
            y0, y1 = sorted((box["y0"], ev.y))
            scr = {n.name: self.w2s(n.x, n.y) for n in self.model.nodes}
            self.selected_nodes = {
                nm for nm, (sx, sy) in scr.items() if x0 <= sx <= x1 and y0 <= sy <= y1
            }
            # 边：**两端节点都在框内**才算选中（同一条线段的正反两个方向会成对进来）。
            # 判据与节点框选一致（按节点中心）；只被框切到一部分的长边不动，免得改到框外的边。
            self.selected_edges = {
                (e.frm, e.to) for e in self.model.edges
                if e.frm in self.selected_nodes and e.to in self.selected_nodes
            }
            self.sel_node = None
            self.sel_edge = None
            self.refresh_props()
            self.redraw()
            msg = "已框选 %d 个节点" % len(self.selected_nodes)
            if self.selected_edges:
                msg += "、%d 条边（紫色；「按图上位置算角度/step」将作用于这些边）" % \
                       len(self.selected_edges)
            if len(self.selected_nodes) > 1:
                msg += "；拖动其中任一节点可整体移动"
            self.status(msg)
            return "break"
        if self._link:
            d = self._link
            if d.get("item"):
                self.canvas.delete(d["item"])
            self._link = None
            tgt = self.node_at(ev.x, ev.y)
            if tgt and tgt != d["from"]:
                self.create_edge_quick(d["from"], tgt)
            else:
                self.status("连线取消（没落在别的节点上）")
            self.redraw()
            return "break"
        if self._drag:
            moved = self._drag["moved"]
            self._drag = None
            if moved:
                self._push_undo(self._snap_before)
            self.refresh_trees()
            return "break"
        self._pan = None

    def _on_bg_press(self, ev):
        if self._link or self._drag:
            return "break"
        if self.adjust_bg.get() and self.show_bg.get():
            handle = self._bg_handle_at(ev.x, ev.y)
            if handle:
                self._start_bg_drag(ev, handle)
                return "break"
            x0, y0, x1, y1 = self.bg.rect()
            wx, wy = self.s2w(ev.x, ev.y)
            if x0 <= wx <= x1 and y0 <= wy <= y1:
                self._start_bg_drag(ev)
                return "break"
        if ev.state & 0x0004:       # Ctrl + 空白拖动：框选节点
            self._marquee = {"x0": ev.x, "y0": ev.y, "item": None}
            return "break"
        if self.connect_from is not None:      # 空白左键 = 放弃待连线的起点
            self.connect_from = None
            self.status("已取消连线起点（Esc 同效）")
        self.selected_nodes.clear()
        self.selected_edges.clear()
        self.sel_node = None
        self.sel_edge = None
        self.refresh_props()
        self.redraw()
        # 空白处按下也支持平移
        self._pan = (ev.x, ev.y, self.ox, self.oy)

    def _edges_near(self, sx, sy, tol=None):
        """屏幕点附近**所有**边，按到该边自身画线（含双向偏移）的距离排序。

        ⚠️ 为什么不能只靠 Tk 的"最上面那个 item"：双向边的两条线是同一线段、
        只差十几像素，命中区（±7px）会重叠 ⇒ 永远命中后画的那条。用户反馈正是
        "老是选到一条线，另一条线点不开"。这里自己列出候选，配合
        `_on_edge_press` 的"同一处再点一次 = 换下一条（切换方向）"。
        """
        if tol is None:
            tol = EDGE_HIT_WIDTH / 2.0 + 1.0
        out = []
        for e in self.model.edges:
            ep = self._edge_endpoints(e, self._node_radius(e.frm), self._node_radius(e.to))
            if not ep:
                continue
            x1, y1, x2, y2, _ux, _uy = ep
            dx, dy = x2 - x1, y2 - y1
            L2 = dx * dx + dy * dy
            if L2 < 1e-9:
                continue
            t = max(0.0, min(1.0, ((sx - x1) * dx + (sy - y1) * dy) / L2))
            d = math.hypot(sx - (x1 + t * dx), sy - (y1 + t * dy))
            if d <= tol:
                out.append((d, e.frm, e.to, e))
        out.sort(key=lambda it: it[:3])          # 距离优先，同距离按 from/to 稳定排序
        return [it[3] for it in out]

    def _edge_near(self, sx, sy, tol=6.0):
        """屏幕坐标附近最近的那条边（含双向偏移）。用于"双击边却建了节点"的判定。"""
        got = self._edges_near(sx, sy, tol + EDGE_HIT_WIDTH / 2.0)
        return got[0] if got else None

    def _on_bg_double(self, ev):
        """双击：**先判断落点是什么**，再做对应动作。

        ⚠️ 之前这里无条件建节点 → 双击边（想编辑）时会**同时**弹出"新建节点"，
        两个动作冲突。现在的分派：
          * 落在节点上   → 忽略（交给节点自己的处理）
          * 落在边附近   → 打开该边的编辑框
          * 空白 + Shift → 新建节点（避免误触；建节点还有工具栏「＋节点」和右键菜单）
          * 空白         → 只提示，不弹窗
        """
        shift = bool(ev.state & 0x0001)
        if self.node_at(ev.x, ev.y):
            return "break"
        e = self._edge_near(ev.x, ev.y, tol=6.0)
        if e is not None:
            self.sel_edge = e
            self.sel_node = None
            self.refresh_props()
            self.redraw()
            self.status("已选中边 %s，右侧属性栏可直接编辑" % e.label())
            return "break"
        if shift:
            nx, ny = self.s2w(ev.x, ev.y)
            self.create_node_dialog(nx, ny)
        else:
            self.status("空白处双击不建节点（防误触）：要新建节点请用工具栏「＋节点」、"
                        "右键「在此新建节点」，或按住 Shift 双击空白")
        return "break"

    def _connect_pick(self, name):
        """连线取点（左键/右键共用）：第一下选起点，第二下成边，再点自己取消。"""
        if self.connect_from is None:
            self.connect_from = name
            self.select_node(name)
            self.status("连线起点 = %s　→ 左键或右键点另一个节点即可建边"
                        "（再点自己 / Esc 取消；Shift+右键 = 节点菜单）" % name)
        elif self.connect_from == name:
            self.connect_from = None
            self.status("已取消连线起点")
        else:
            src = self.connect_from
            self.connect_from = None
            self.create_edge_quick(src, name)

    def _on_node_right(self, ev, name):
        """右键节点：默认 = 开始/完成连线；**Shift+右键 = 原来的节点快捷菜单**。

        原因：原来"左键双击节点开始连线"经常点不中（一歪就变成选中/拖动/框选），
        右键单击更稳。菜单里的功能（重命名/删除/补反向边/设为必经点…）一个没少，只是挪到 Shift+右键。
        """
        if bool(ev.state & 0x0001):                 # Shift 按下 → 老菜单
            self._on_node_menu(ev, name)
            return "break"
        self._connect_pick(name)
        return "break"

    def _on_node_double(self, ev, name):
        """双击节点 = 打开"编辑边"不方便，改为：以它为起点快速连线。"""
        self.start_connect_from(name)
        return "break"

    def _on_edge_press(self, ev, e):
        # 「连线模式」下点边 → 把它当作起点，快速续连
        if self.connect_mode.get():
            self.start_connect_from(e.to)
            return "break"
        cands = self._edges_near(ev.x, ev.y)
        if e not in cands:
            cands.insert(0, e)
        # 双击的第二次按下别当成"切换"，否则双击编辑会跳到另一条边上去
        now = time.monotonic()
        last = getattr(self, "_edge_click", None)
        is_dbl = (last is not None and (now - last[0]) < 0.35
                  and abs(ev.x - last[1]) <= 3 and abs(ev.y - last[2]) <= 3)
        self._edge_click = (now, ev.x, ev.y)
        if is_dbl:
            extra = ""
        elif len(cands) > 1 and self.sel_edge is not None and self.sel_edge in cands:
            # 同一处再点一次 ⇒ 换下一条（双向边就是"切换方向"）
            e = cands[(cands.index(self.sel_edge) + 1) % len(cands)]
            extra = "；同一处共 %d 条，再点一次继续切换" % len(cands)
        else:
            e = cands[0]
            extra = ("；同一处还有 %d 条，再点一次切换（双向边=切换方向）"
                     % (len(cands) - 1)) if len(cands) > 1 else ""
        self.sel_edge = e
        self.sel_node = None
        self.refresh_props()
        self.redraw()
        self.status("已选中边 %s → %s%s（双击=编辑 / Delete 删除 / 右键更多）"
                    % (e.frm, e.to, extra))
        return "break"

    def _on_edge_double(self, ev, e):
        """双击边 = 选中并在右侧属性栏编辑（尊重"再点一次切换"切出来的那条）。"""
        cands = self._edges_near(ev.x, ev.y)
        if self.sel_edge is not None and self.sel_edge in cands:
            e = self.sel_edge
        self.sel_edge = e
        self.sel_node = None
        self.refresh_props()
        self.redraw()
        self.status("已选中边 %s → %s，右侧属性栏可直接编辑" % (e.frm, e.to))
        return "break"

    def node_at(self, sx, sy):
        best, bd = None, 1e9
        for n in self.model.nodes:
            x, y = self.w2s(n.x, n.y)
            d = ((x - sx) ** 2 + (y - sy) ** 2) ** 0.5
            if d < self._node_radius(n.name) + 4 and d < bd:
                best, bd = n.name, d
        return best

    def _node_xy(self, name):
        n = self.model.node(name)
        return (n.x, n.y) if n else (0, 0)

    # ---- 右键菜单 ----
    def _on_node_menu(self, ev, name):
        self.select_node(name)
        outs = len(self.model.edges_of(name, True))
        ins = len(self.model.edges_of(name, False))
        m = tk.Menu(self, tearoff=0)
        # --- 快捷连线（不用手选 from/to）---
        m.add_command(label="从这里连到…（选中目标节点后按 A）",
                      command=lambda: self.start_connect_from(name))
        m.add_command(label="连出新边（弹窗…）",
                      command=lambda: self.create_edge_dialog(name, None))
        m.add_separator()
        m.add_command(label="＋ 补一条反向边（复制参数）", command=self.make_reverse_edge)
        m.add_command(label="－ 删除该节点全部入边（%d 条）" % ins,
                      command=lambda: self.delete_edges(name, incoming=True))
        m.add_command(label="－ 删除该节点全部出边（%d 条）" % outs,
                      command=lambda: self.delete_edges(name, incoming=False))
        m.add_command(label="断开该节点所有边（%d 条）" % (outs + ins),
                      command=lambda: self.disconnect_node(name))
        m.add_separator()
        m.add_command(label="重命名…", command=lambda: self.rename_node_dialog(name))
        m.add_command(label="删除节点", command=lambda: self.delete_node(name))
        m.add_separator()
        m.add_command(label="设为必经点", command=lambda: self.wp_add(name))
        m.tk_popup(ev.x_root, ev.y_root)

    def _on_edge_menu(self, ev, e):
        self.sel_edge = e
        self.refresh_props()
        rev = self.model.edge(e.to, e.frm)
        m = tk.Menu(self, tearoff=0)
        m.add_command(label="编辑…", command=self.edit_edge_dialog)
        m.add_separator()
        # --- 快捷增删 ---
        m.add_command(label="从 %s 继续连一条边（不要手选 from）" % e.to,
                      command=lambda: self.start_connect_from(e.to))
        m.add_command(label="从 %s 继续连一条边" % e.frm,
                      command=lambda: self.start_connect_from(e.frm))
        if rev is None:
            m.add_command(label="＋ 补反向边（复制本边参数）", command=self.make_reverse_edge)
        else:
            m.add_command(label="－ 删除反向边 %s→%s" % (e.to, e.frm),
                          command=lambda: self._del_edge(e.to, e.frm))
        m.add_separator()
        m.add_command(label="－ 删除这条边（%s）" % e.label(),
                      command=lambda: self._del_edge(e.frm, e.to))
        m.add_command(label="－ 删除这一对（双向都删）",
                      command=lambda: self.delete_edge_pair(e.frm, e.to))
        m.add_separator()
        m.add_command(label="方向取反（互换 from/to）", command=self.reverse_edge_sel)
        m.tk_popup(ev.x_root, ev.y_root)

    # ---- 快捷增删 ----
    def start_connect_from(self, name):
        """进入"点两下连线"，并把起点设为 name。（右键节点 / 双击节点 / 按 A 都走这里）"""
        self.connect_mode.set(True)
        self.connect_from = name
        self.select_node(name)
        self.status("连线起点 = %s　→ 点另一个节点即可建边（左键/右键都行；Esc 取消）" % name)

    def start_connect_from_sel(self):
        """快捷键 A：以当前选中节点（或选中边的 to 端）为起点开始连线。"""
        if self.sel_node:
            self.start_connect_from(self.sel_node)
        elif self.sel_edge:
            self.start_connect_from(self.sel_edge.to)
        else:
            self.status("先点一个节点（或一条边）再按 A")

    def delete_edges(self, name, incoming=True):
        lst = self.model.edges_of(name, incoming)
        if not lst:
            self.status("没有可删的%s边" % ("入" if incoming else "出"))
            return
        if not messagebox.askyesno("删除边",
                                   "删除 %s 的 %d 条%s边？\n%s"
                                   % (name, len(lst), "入" if incoming else "出",
                                      "、".join(e.label() for e in lst[:8])
                                      + ("…" if len(lst) > 8 else "")), parent=self):
            return
        snap = self.model.snapshot()
        for e in lst:
            self.model.remove_edge(e.frm, e.to)
        self._apply_change(snap)
        self.status("已删除 %d 条边" % len(lst))

    def delete_edge_pair(self, frm, to):
        lst = [e for e in (self.model.edge(frm, to), self.model.edge(to, frm)) if e]
        if not lst:
            return
        if not messagebox.askyesno("删除双向边",
                                   "删除 %s ↔ %s 的两条边？" % (frm, to), parent=self):
            return
        snap = self.model.snapshot()
        for e in lst:
            self.model.remove_edge(e.frm, e.to)
        self.sel_edge = None
        self._apply_change(snap)
        self.status("已删除 %s ↔ %s 两条边" % (frm, to))

    def delete_sel_edge(self):
        """键盘 Delete：优先删选中的边。"""
        if self.sel_edge:
            self._del_edge(self.sel_edge.frm, self.sel_edge.to)
        elif self.sel_node:
            self.delete_node(self.sel_node)

    def delete_sel_pair(self):
        """按钮：删掉选中边所在的一对（双向都删）。"""
        if not self.sel_edge:
            self.status("先选中一条边")
            return
        self.delete_edge_pair(self.sel_edge.frm, self.sel_edge.to)

    def cancel_connect(self):
        if self.connect_from or self.connect_mode.get():
            self.connect_from = None
            self.connect_mode.set(False)
            self.status("已退出连线模式")

    def _on_bg_menu(self, ev):
        if self.connect_from is not None:      # 空白右键 = 放弃待连线的起点，再弹菜单
            self.connect_from = None
            self.status("已取消连线起点")
        m = tk.Menu(self, tearoff=0)
        nx, ny = self.s2w(ev.x, ev.y)
        m.add_command(label="在此新建节点…", command=lambda: self.create_node_dialog(nx, ny))
        m.add_command(label="新建边…", command=self.add_edge_dialog)
        m.add_separator()
        m.add_command(label="适配窗口", command=self._fit_view)
        m.add_command(label="重新载入源码", command=self.reload_sources)
        m.tk_popup(ev.x_root, ev.y_root)

    # ---- 约束诊断 ----
    def _geometry_warning_data(self):
        """返回图上长度小于边表数值的边。

        地图示意图不是等比例工程图，因此长度只检查硬下限 step*K；
        图上长度大于等于 step 时不报警。角度只作为诊断信息，不单独触发报警。
        """
        k = self._unit_k()
        ang_tol = max(0.0, float(self.geometry_ang_tol.get()))
        result = []
        for e in self.model.edges:
            a, b = self.model.node(e.frm), self.model.node(e.to)
            if not a or not b:
                continue
            d = math.hypot(b.x - a.x, b.y - a.y)
            step = self.model.step(e)
            angle = self.model.ang(e)
            length_cm = d / k if k > 0 else None
            len_error = (abs(length_cm - step) / abs(step)
                         if length_cm is not None and step not in (None, 0) else None)
            raw_angle = math.degrees(math.atan2(b.x - a.x, -(b.y - a.y)))
            # DRAG_ANGLE_OFFSET 只用于拖动引导线；报警比较图面与边表的实际方向。
            if angle is not None:
                # 线段没有固定朝向：from->to 与 to->from 应视为同一条线。
                angle_error = min(self._ang_dev(raw_angle, angle),
                                  self._ang_dev(raw_angle, angle + 180.0))
            else:
                angle_error = None
            required_px = step * k if step is not None and step > 0 else 0.0
            length_bad = (length_cm is not None and step is not None and step > 0
                          and length_cm + 1e-9 < step)
            angle_bad = angle_error is not None and angle_error > ang_tol
            if length_bad:
                result.append({"edge": e, "px": d, "length_cm": length_cm,
                               "step": step, "len_error": len_error,
                               "required_px": required_px,
                               "image_angle": raw_angle, "angle": angle,
                               "angle_error": angle_error,
                               "length_bad": length_bad, "angle_bad": angle_bad})
        return result

    def _geometry_warning_map(self):
        return {item["edge"].tag: item for item in self._geometry_warning_data()}

    def report_geometry_warnings(self):
        """显示图上几何量与边表数值的偏差，并在画布标红对应边。"""
        items = self._geometry_warning_data()
        self.show_geometry_warnings.set(True)
        self.redraw()
        lines = [
            "报警条件：图上长度(cm) < 边表 step；图上长度 ≥ step 不报警。",
            "长度显示 = 图坐标距离 ÷ K（K = %.4g px/cm，**与缩放无关**）；角度只作信息显示。"
            % self._unit_k(),
            "超差边：%d / %d" % (len(items), len(self.model.edges)), ""]
        if items:
            lines.append("%-8s %-8s %8s %8s %8s %9s %9s %8s" %
                         ("from", "to", "图上px", "图上cm", "step", "长度误差", "图上角", "角度偏差"))
            for item in items:
                lines.append("%-8s %-8s %8.1f %8.1f %8s %8s %9s %8s" % (
                    item["edge"].frm, item["edge"].to, item["px"],
                    item["length_cm"] if item["length_cm"] is not None else "?",
                    "%.1f" % item["step"] if item["step"] is not None else "?",
                    ("%.1f%%" % (item["len_error"] * 100))
                    if item["len_error"] is not None else "?",
                    ("%.1f°" % item["image_angle"])
                    if item["image_angle"] is not None else "?",
                    ("%.1f°" % item["angle_error"])
                    if item["angle_error"] is not None else "?"))
        else:
            lines.append("当前没有超过阈值的边。")
        dlg = tk.Toplevel(self)
        dlg.title("地图几何报警")
        dlg.geometry("900x560")
        t = tk.Text(dlg, wrap="none")
        t.insert("1.0", "\n".join(lines))
        t.pack(fill="both", expand=True, padx=8, pady=8)
        ttk.Button(dlg, text="关闭", command=dlg.destroy).pack(pady=(0, 8))
        self.status("几何报警：%d 条超差边，已在图上标红" % len(items))

    def constraint_violations(self):
        """列出所有「图上长度 < step × K」的边（这类边拖不出合法位置）。"""
        k = self._unit_k()
        bad = []
        for e in self.model.edges:
            a, b = self.model.node(e.frm), self.model.node(e.to)
            if not a or not b:
                continue
            Lmin = self._edge_min_px(e)
            if Lmin <= 0:
                continue
            d = math.hypot(b.x - a.x, b.y - a.y)
            if d + 1e-6 < Lmin:
                bad.append((e, d, Lmin))
        bad.sort(key=lambda r: r[1] / r[2] if r[2] else 0)
        return bad, k

    def report_violations(self):
        bad, k = self.constraint_violations()
        txt = []
        txt.append("单位长度 K = %.4g px/cm（可改）" % k)
        txt.append("当前布局里「图上长度 < step×K」的边：%d / %d"
                   % (len(bad), len(self.model.edges)))
        txt.append("")
        txt.append("这些边**本来就拖不出满足约束的位置** —— 因为节点图不是等比例的")
        txt.append("（实测 px/step 比值从 0.17 到 94.9，差 500 倍）。")
        txt.append("要么调大/调小 K，要么接受这些边违规（它们通常本来就不按比例画）。")
        txt.append("")
        txt.append("%-7s %-7s %9s %8s %9s %s" %
                   ("from", "to", "图上px", "step", "需≥px", "func"))
        for e, d, Lmin in bad[:60]:
            txt.append("%-7s %-7s %9.1f %8.0f %9.1f %s"
                       % (e.frm, e.to, d, self.model.step(e) or 0, Lmin, e.func))
        if len(bad) > 60:
            txt.append("...（共 %d 条，只列前 60）" % len(bad))
        body = "\n".join(txt)
        dlg = tk.Toplevel(self)
        dlg.title("违反长度约束的边")
        dlg.geometry("720x560")
        t = tk.Text(dlg, wrap="none")
        t.insert("1.0", body)
        t.pack(fill="both", expand=True, padx=8, pady=8)
        ttk.Button(dlg, text="关闭", command=dlg.destroy).pack(pady=(0, 8))
        self.status("违反长度约束的边：%d 条（K=%.4g px/cm）" % (len(bad), k))

    # ================================================================ 撤销
    def _push_undo(self, snap=None):
        snap = snap if snap is not None else self.model.snapshot()
        self.undo_stack.append(snap)
        if len(self.undo_stack) > 120:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def _apply_change(self, snap_before=None):
        """所有编辑动作统一入口：记录撤销点 + 刷新界面。"""
        if snap_before is not None:
            self._push_undo(snap_before)
        else:
            self._push_undo()
        self.model.dirty = True
        self.refresh_all()

    def undo(self):
        if not self.undo_stack:
            self.status("没有可撤销的操作")
            return
        self.redo_stack.append(self.model.snapshot())
        self.model.restore(self.undo_stack.pop())
        self.sel_node = self.sel_edge = None
        self.refresh_all()
        self.status("已撤销")

    def redo(self):
        if not self.redo_stack:
            self.status("没有可重做的操作")
            return
        self.undo_stack.append(self.model.snapshot())
        self.model.restore(self.redo_stack.pop())
        self.sel_node = self.sel_edge = None
        self.refresh_all()
        self.status("已重做")

    # ================================================================ 编辑动作
    def add_node_dialog(self):
        """工具栏「＋节点」：在视图中央新建。"""
        cx, cy = self.s2w(self.canvas.winfo_width() / 2, self.canvas.winfo_height() / 2)
        self.create_node_dialog(cx, cy)

    def create_node_dialog(self, x, y):
        name = simpledialog.askstring("新建节点", "节点名（C 标识符，如 C10）：", parent=self)
        if not name:
            return
        name = name.strip()
        cmt = simpledialog.askstring("新建节点", "说明（可空）：", parent=self) or ""
        try:
            self._push_undo()
            self.model.add_node(name, x, y, cmt)
            self.sel_node, self.sel_edge = name, None
            self.refresh_all()
            self.status("已新建节点 %s（记得在 enum MapNode 里也会自动出现在导出里）" % name)
        except ValueError as ex:
            messagebox.showerror("新建失败", str(ex), parent=self)

    def rename_node_dialog(self, name):
        new = simpledialog.askstring("重命名节点", "新名字：", initialvalue=name, parent=self)
        if not new or new.strip() == name:
            return
        try:
            self._push_undo()
            self.model.rename_node(name, new.strip())
            self.sel_node = new.strip()
            self.refresh_all()
        except ValueError as ex:
            messagebox.showerror("重命名失败", str(ex), parent=self)

    def delete_node(self, name):
        outs = len(self.model.edges_of(name, True))
        ins = len(self.model.edges_of(name, False))
        if not messagebox.askyesno("删除节点",
                                   "删除 %s？\n会同时删掉它的 %d 条出边 / %d 条入边。"
                                   % (name, outs, ins), parent=self):
            return
        self._push_undo()
        self.model.remove_node(name)
        self.sel_node = self.sel_edge = None
        self.refresh_all()
        self.status("已删除节点 %s" % name)

    def disconnect_node(self, name):
        n = len(self.model.edges_of(name, True)) + len(self.model.edges_of(name, False))
        if not messagebox.askyesno("断开节点", "删掉 %s 的 %d 条边？（节点保留）" % (name, n)):
            return
        self._push_undo()
        self.model.edges = [e for e in self.model.edges if e.frm != name and e.to != name]
        self.refresh_all()
        self.status("已断开 %s 的所有边" % name)

    def edit_edge_dialog(self):
        """右键「编辑…」：弹窗改一条边的全部字段。"""
        e = self.sel_edge
        if not e:
            return
        names = self.model.names()
        dlg = tk.Toplevel(self)
        dlg.title("编辑边  %s" % e.label())
        dlg.transient(self)
        dlg.grab_set()
        frm = ttk.Frame(dlg, padding=10)
        frm.pack(fill="both", expand=True)
        w = {}

        def row(r, label, widget, hint=None):
            ttk.Label(frm, text=label).grid(row=r, column=0, sticky="w", pady=2)
            widget.grid(row=r, column=1, sticky="we", pady=2, padx=4)
            if hint:
                ttk.Label(frm, text=hint, foreground="#777777").grid(
                    row=r, column=2, sticky="w")

        def entry(key, val, hint=None):
            en = ttk.Entry(frm, width=26)
            en.insert(0, str(val))
            w[key] = en
            return en

        cb_from = ttk.Combobox(frm, values=names, width=24, state="readonly")
        cb_from.set(e.frm)
        w["from"] = cb_from
        row(0, "from", cb_from)
        cb_to = ttk.Combobox(frm, values=names, width=24, state="readonly")
        cb_to.set(e.to)
        w["to"] = cb_to
        row(1, "to", cb_to)
        row(2, "flag", entry("flag", e.flag), "位或，如 CLEFT|DLEFT")
        row(3, "angle", entry("angle", e.angle), "可写宏 ANGLE_N3N8；求值 = %s"
            % self.model.ang(e))
        row(4, "step", entry("step", e.step), "可写宏 LEN_B7C6；求值 = %s"
            % self.model.step(e))
        cb_sp = ttk.Combobox(frm, values=M.SPEED_NAMES, width=24)
        cb_sp.set(e.speed)
        w["speed"] = cb_sp
        row(5, "speed", cb_sp, "可填数字或 SPEED0~5")
        cb_fn = ttk.Combobox(frm, values=M.FUNC_ORDER, width=24)
        cb_fn.set(e.func)
        w["func"] = cb_fn
        row(6, "func", cb_fn, "BSoutPole=南极平台 / DOOR=门 / Hill=坡")
        row(7, "comment", entry("comment", e.comment), "行尾注释")

        res = {"ok": False}

        def ok():
            if not w["from"].get() or not w["to"].get():
                messagebox.showerror("错误", "from/to 必填", parent=dlg)
                return
            if w["from"].get() == w["to"].get():
                messagebox.showerror("错误", "不能自环", parent=dlg)
                return
            res.update(ok=True, **{k: v.get().strip() for k, v in w.items()})
            dlg.destroy()

        brow = ttk.Frame(frm)
        brow.grid(row=8, column=0, columnspan=3, pady=10)
        ttk.Button(brow, text="确定", command=ok).pack(side="left", padx=4)
        ttk.Button(brow, text="删除这条边",
                   command=lambda: (self._del_edge(e.frm, e.to), dlg.destroy())
                   ).pack(side="left", padx=4)
        ttk.Button(brow, text="取消", command=dlg.destroy).pack(side="left", padx=4)
        self.wait_window(dlg)
        if not res["ok"]:
            return
        other = self.model.edge(res["from"], res["to"])
        if other is not None and other.tag != e.tag:
            messagebox.showerror("失败", "边 %s->%s 已存在" % (res["from"], res["to"]),
                                 parent=self)
            return
        snap = self.model.snapshot()
        e.frm, e.to = res["from"], res["to"]
        e.flag = res["flag"] or "NO"
        e.angle = res["angle"] or "0"
        e.step = res["step"] or "0"
        e.speed = res["speed"] or "SPEED0"
        e.func = res["func"] or "NONE"
        e.comment = res["comment"]
        self._apply_change(snap)
        self.status("已修改边 %s" % e.label())

    def _del_edge(self, frm, to):
        self._push_undo()
        self.model.remove_edge(frm, to)
        if self.sel_edge and self.sel_edge.key() == (frm, to):
            self.sel_edge = None
        self.refresh_all()

    def _auto_edge_angle(self, frm, to, ignore=None):
        """给 `frm→to` 算一个**边表约定**的 angle（而不是图上裸几何角）。

        表里 angle 是"单向图"编码：几何只能定出**直线**，定不出**方向感**。实测本图 109 条边里，
        52 条是「几何 + 90°」、31 条是「几何 − 90°」（同一根直线、方向相反），其余是示意图不准的边。
        所以按优先级：
          ① **共线锚定**：起点 `frm` 已有一条出边与 `frm→to` 几乎共线（≤ `ANGLE_ANCHOR_TOL`）
             ⇒ 沿用它的 angle —— 这是地图自己的方向约定，最可靠；
          ② **几何 + `DRAG_ANGLE_OFFSET`**（与「跟随角度表」同一套：view = angle + offset）；
          ③ 把接近 0/±90/180 的值**吸附成整数**（"完全水平"就该是 0/180）。
        `ignore`：不参与①的参照的边 —— 单个 Edge（重算它自己时排除它）或一批 Edge
        （框选批量重算时**整批互不参照**；否则"先改的边"会变成"后改边"的锚，
        结果依赖处理顺序，且一条错的老角度会污染整批。批外的共线边仍可锚定）。
        返回 (angle, 说明文本)。
        """
        a, b = self.model.node(frm), self.model.node(to)
        if not a or not b:
            return 0.0, "缺节点，退回 0°"
        if ignore is None:
            skip = set()
        elif hasattr(ignore, "frm"):                             # 单个 Edge
            skip = {(ignore.frm, ignore.to)}
        else:                                                    # 一批 Edge
            skip = {(x.frm, x.to) for x in ignore}
        g = math.degrees(math.atan2(b.x - a.x, -(b.y - a.y)))
        for e in self.model.edges_of(frm, True):                 # ① 共线锚定
            if (e.frm, e.to) in skip or e.to == to:
                continue
            dst = self.model.node(e.to)
            ea = self.model.ang(e)
            if dst is None or ea is None:
                continue
            g2 = math.degrees(math.atan2(dst.x - a.x, -(dst.y - a.y)))
            if _angdiff(g2, g) <= ANGLE_ANCHOR_TOL:
                v = _norm180(ea)
                return v, "沿用共线边 %s→%s 的 %g°" % (e.frm, e.to, v)
        # ② 几何 + 偏移，再**取反**。实测边表真值：朝下=90、朝上=-90、朝右=180、朝左=0
        #   （map_message.c：N7→P6=90、P6→N7=-90、N3→N4=180、N4→N3=0）。
        #   几何角 g：朝下=180、朝上=0、朝右=90、朝左=-90 ⇒ -(g+90) 正好给出地图约定。
        raw = _norm180(-(g + DRAG_ANGLE_OFFSET))
        snap = _snap90(raw)                                      # ③ 吸附整数
        if snap is not None:
            return snap, "图上 %+.1f° → 取反偏移 → 吸附为 %g°" % (g, snap)
        return round(raw, 1), "图上 %+.1f° → 取反偏移 → %g°" % (g, round(raw, 1))

    def create_edge_quick(self, frm, to, both=None):
        """快捷建边（选中两点即建，**不弹对话框**）。

        * 角度：按两点在**图上**的位置自动算（这样新边方向和图上一致）
        * step / speed / func：给保守默认值，建完用右侧「属性」面板再改
        * both：None = 跟随工具栏「双向」选项（默认双向，因为多数路段车两边都跑）
        建完会选中新边，方便接着改数值或继续用 A 键续连。
        """
        if self.model.edge(frm, to):
            self.status("边 %s → %s 已存在" % (frm, to))
            return None
        if both is None:
            both = bool(self.var_quick_both.get())
        # 角度按**边表约定**算（不是图上裸几何角）—— 否则"完全水平"会写成 88/90° 而不是 180/0°
        ang, how = self._auto_edge_angle(frm, to)
        rng, how_rev = self._auto_edge_angle(to, frm)
        snap = self.model.snapshot()
        try:
            e = self.model.add_edge(frm, to, flag="NO", angle="%g" % ang,
                                    step="0", speed="SPEED2", func="NONE")
            if both and not self.model.edge(to, frm):
                self.model.add_edge(to, frm, flag="NO", angle="%g" % rng,
                                    step="0", speed="SPEED2", func="NONE")
            self.sel_edge = e
            self.sel_node = None
            self._apply_change(snap)
            self.status("已建%s边 %s → %s（%s%s；step 默认 0，请在属性面板改成实测值）"
                        % ("双向" if both else "", frm, to, how,
                           "；反向 %g°（%s）" % (rng, how_rev) if both else ""))
            return e
        except ValueError as ex:
            messagebox.showerror("建边失败", str(ex), parent=self)
            return None

    def create_edge_dialog(self, frm, to):
        self.add_edge_dialog(pre_from=frm, pre_to=to)

    def add_edge_dialog(self, both=False, pre_from=None, pre_to=None):
        names = self.model.names()
        dlg = tk.Toplevel(self)
        dlg.title("新建双向边" if both else "新建边")
        dlg.transient(self)
        dlg.grab_set()
        frm = ttk.Frame(dlg, padding=10)
        frm.pack(fill="both", expand=True)

        vars_ = {}

        def row(r, label, widget):
            ttk.Label(frm, text=label).grid(row=r, column=0, sticky="w", pady=2)
            widget.grid(row=r, column=1, sticky="we", pady=2, padx=4)

        def combo(key, values, default=None, readonly=True):
            cb = ttk.Combobox(frm, values=values, width=24,
                              state="readonly" if readonly else "normal")
            if default:
                cb.set(default)
            vars_[key] = cb
            return cb

        row(0, "from", combo("from", names, pre_from or (self.sel_node or "")))
        row(1, "to", combo("to", names, pre_to or ""))
        row(2, "angle", combo("angle", [str(v) for v in range(-180, 181, 5)], "0", False))
        row(3, "step", combo("step", ["0", "10", "20", "60", "120", "180", "240"],
                             "0", False))
        row(4, "speed", combo("speed", M.SPEED_NAMES, "SPEED2"))
        row(5, "func", combo("func", M.FUNC_ORDER, "NONE"))

        # step/angle 也允许输入宏（下拉是 normal 的，可以手打 LEN_xxx）
        ttk.Label(frm, text="（angle/step 允许直接写宏，如 ANGLE_N3N8 / LEN_B7C6）",
                  foreground="#666666").grid(row=6, column=0, columnspan=2, sticky="w")

        if both:
            ttk.Label(frm, text="反向边将自动用「角度+180、flag 去掉 STOPTURN/DLEFT/DRIGHT」"
                                "\n生成，建好后可在属性面板里改。",
                      foreground="#666666", justify="left").grid(
                row=7, column=0, columnspan=2, sticky="w", pady=(6, 0))

        res = {"ok": False}

        def ok():
            a = vars_["from"].get().strip()
            b = vars_["to"].get().strip()
            if not a or not b:
                messagebox.showerror("错误", "from / to 必填", parent=dlg)
                return
            if a == b:
                messagebox.showerror("错误", "不能自环", parent=dlg)
                return
            res.update(ok=True, frm=a, to=b,
                       angle=vars_["angle"].get().strip(),
                       step=vars_["step"].get().strip(),
                       speed=vars_["speed"].get().strip(),
                       func=vars_["func"].get().strip())
            dlg.destroy()

        brow = ttk.Frame(frm)
        brow.grid(row=8, column=0, columnspan=2, pady=8)
        ttk.Button(brow, text="确定", command=ok).pack(side="left", padx=4)
        ttk.Button(brow, text="取消", command=dlg.destroy).pack(side="left")

        self.wait_window(dlg)
        if not res["ok"]:
            return
        snap = self.model.snapshot()
        try:
            e = self.model.add_edge(res["frm"], res["to"], flag="NO", angle=res["angle"],
                                    step=res["step"], speed=res["speed"],
                                    func=res["func"])
            if both:
                ang = M.eval_c_expr(res["angle"], self.model.macros)
                rang = "" if ang is None else ("%g" % ((ang - 180) if ang >= 0 else (ang + 180)))
                if not rang:
                    rang = res["angle"]
                if not self.model.edge(res["to"], res["frm"]):
                    self.model.add_edge(res["to"], res["frm"], flag="NO", angle=rang,
                                        step=res["step"], speed=res["speed"],
                                        func=res["func"])
            self.sel_edge = e
            self.sel_node = None
            self._apply_change(snap)
            self.status("已新建 %s" % ("双向边" if both else "边"))
        except ValueError as ex:
            messagebox.showerror("新建失败", str(ex), parent=self)

    def make_reverse_edge(self):
        if not self.sel_edge:
            return
        e = self.sel_edge
        if self.model.edge(e.to, e.frm):
            self.status("反向边 %s->%s 已存在" % (e.to, e.frm))
            return
        snap = self.model.snapshot()
        ang = M.eval_c_expr(e.angle, self.model.macros)
        rang = "" if ang is None else ("%g" % ((ang - 180) if ang >= 0 else (ang + 180)))
        flag = "|".join(t for t in re.split(r"[|,]", e.flag or "")
                        if t.strip() and t.strip() not in ("STOPTURN", "DLEFT", "DRIGHT"))
        try:
            ne = self.model.add_edge(e.to, e.frm, flag=flag or "NO",
                                     angle=rang or e.angle, step=e.step,
                                     speed=e.speed, func=e.func)
            self._apply_change(snap)
            self.sel_edge = ne
            self.refresh_props()
            self.status("已补反向边 %s" % ne.label())
        except ValueError as ex:
            messagebox.showerror("失败", str(ex), parent=self)

    def reverse_edge_sel(self):
        if not self.sel_edge:
            return
        e = self.sel_edge
        snap = self.model.snapshot()
        if self.model.edge(e.to, e.frm):
            messagebox.showerror("失败", "反向边 %s->%s 已存在，无法取反"
                                 % (e.to, e.frm), parent=self)
            return
        ang = M.eval_c_expr(e.angle, self.model.macros)
        e.frm, e.to = e.to, e.frm
        if ang is not None:
            e.angle = "%g" % ((ang - 180) if ang >= 0 else (ang + 180))
        self._apply_change(snap)
        self.refresh_props()
        self.status("已取反：%s" % e.label())

    def calc_angle_geo(self):
        """按图上位置重算角度：有框选批量 → 一次改**框内所有边**；否则只改单选那条。"""
        if self.selected_edges:
            self._calc_angle_geo_batch()
            return
        if not self.sel_edge:
            return
        e = self.sel_edge
        a, b = self.model.node(e.frm), self.model.node(e.to)
        if not a or not b:
            return
        # 与「快捷建边」同一套：边表约定（共线锚定 → 几何+90° → 吸附整数），不是裸几何角
        snap = self.model.snapshot()             # 记录撤销点（改角度是可撤销编辑，别只刷新属性面板）
        ang, how = self._auto_edge_angle(e.frm, e.to, ignore=e)
        e.angle = "%g" % ang
        self._apply_change(snap)                 # 撤销点 + 刷新树/属性/画布（否则左边边表那行不刷新）
        self.status("按图上位置算出 %g°（%s；节点图是示意图，仅供参考）" % (ang, how))

    def _calc_angle_geo_batch(self):
        """框选批量的「按图上位置算角度」。

        整批**先算后写**，且 `ignore=targets` 让批内各边**互不做共线锚定参照**
        （见 `_auto_edge_angle`）：否则改一条算一条时，先改的边会变成后改边的锚 ⇒
        结果依赖处理顺序。批外的共线边仍可锚定，地图的方向约定得以保留。
        """
        targets = [e for e in (self.model.edge(f, t) for f, t in sorted(self.selected_edges))
                   if e is not None]
        if not targets:
            self.selected_edges = set()
            self.status("框选的边已不存在（可能被删过），批量选择已清空")
            return
        snap = self.model.snapshot()             # 整批只记一个撤销点：Ctrl+Z 一次全回退
        done, skipped = [], 0
        for e in targets:
            if self.model.node(e.frm) is None or self.model.node(e.to) is None:
                skipped += 1
                continue
            ang, how = self._auto_edge_angle(e.frm, e.to, ignore=targets)
            done.append((e, ang, how))
        for e, ang, _how in done:
            e.angle = "%g" % ang
        self._apply_change(snap)
        anchored = sum(1 for _e, _a, how in done if "沿用共线边" in how)
        msg = ("已按图上位置重算 %d 条边的角度（%d 条沿用批外共线边，%d 条按几何）"
               % (len(done), anchored, len(done) - anchored))
        if skipped:
            msg += "；%d 条因缺节点未改" % skipped
        self.status(msg + "；节点图是示意图，仅供参考")

    def calc_step_geo(self):
        """按图上位置重算 step（px ÷ K）：有框选批量 → 一次改**框内所有边**；否则只改单选那条。"""
        if self.selected_edges:
            self._calc_step_geo_batch()
            return
        if not self.sel_edge:
            return
        e = self.sel_edge
        a, b = self.model.node(e.frm), self.model.node(e.to)
        if not a or not b:
            return
        d = ((b.x - a.x) ** 2 + (b.y - a.y) ** 2) ** 0.5
        k = self._unit_k()                  # 用工具栏里那个可改的 K，别再硬编码 0.884
        cm = d / k
        snap = self.model.snapshot()             # 记录撤销点（改 step 也是可撤销编辑）
        e.step = "%g" % round(cm)
        self._apply_change(snap)                 # 撤销点 + 刷新树/属性/画布（否则左边边表那行不刷新）
        self.status("图上 %.0f px ÷ K(%.4g px/cm) = %g cm（⚠️ 只是估算，务必实测标定）"
                    % (d, k, round(cm)))

    def _calc_step_geo_batch(self):
        """框选批量的「按图上位置算 step」。纯几何、无顺序问题；整批一个撤销点。"""
        k = self._unit_k()
        snap = self.model.snapshot()
        done, skipped = 0, 0
        for f, t in sorted(self.selected_edges):
            e = self.model.edge(f, t)
            if e is None:
                continue
            a, b = self.model.node(e.frm), self.model.node(e.to)
            if not a or not b:
                skipped += 1
                continue
            e.step = "%g" % round(math.hypot(b.x - a.x, b.y - a.y) / k)
            done += 1
        self._apply_change(snap)
        msg = "已按图上位置重算 %d 条边的 step（px ÷ K(%.4g px/cm)）" % (done, k)
        if skipped:
            msg += "；%d 条因缺节点未改" % skipped
        self.status(msg + "；⚠️ 只是估算，务必实测标定")

    def delete_selected(self):
        if self.sel_edge:
            self._del_edge(self.sel_edge.frm, self.sel_edge.to)
        elif self.sel_node:
            self.delete_node(self.sel_node)

    def _apply_edge_columns(self):
        """按展示模式重设边表表头/列宽。

        合并双向模式：同一条线段只占一行，两个方向的角度/step 并列显示。
        """
        t = self.tree_edges
        mode = self.edge_view.get()
        if mode == "合并双向":
            heads = ("边(线段)", "→角度", "→step", "←角度", "←step")
            widths = ((92, False), (46, False), (46, False), (46, False), (46, False))
        else:
            heads = ("边", "角度", "step", "功能", "")
            widths = ((104, True), (46, False), (46, False), (64, True), (1, False))
        t.heading("#0", text=heads[0])
        for col, h in zip(("a1", "s1", "a2", "s2"), heads[1:]):
            t.heading(col, text=h)
        for col, (w, stretch) in zip(("a1", "s1", "a2", "s2"), widths[1:]):
            t.column(col, width=w, anchor="e", stretch=stretch)
        t.column("#0", width=widths[0][0], stretch=widths[0][1])

    # ================================================================ 选择与属性
    @property
    def sel_edge(self):
        return self._sel_edge

    @sel_edge.setter
    def sel_edge(self, e):
        """单选一条边 ⇒ 清空框选批量（否则按钮仍作用于旧的一批，而画面上只显示单选）。"""
        self._sel_edge = e
        if e is not None:
            self.selected_edges = set()

    def select_node(self, name):
        self.sel_node = name
        self.sel_edge = None
        self.selected_edges = set()   # 只点了一个节点 ⇒ 取消框选的边批量（同理：别让按钮按旧批量作用）
        self.refresh_props()
        self.redraw()
        self._tree_select("node", name)

    def _tree_select(self, kind, key):
        """从代码里同步树选中项。

        ⚠️ selection_set 会触发 <<TreeviewSelect>>；若处理函数再调 select_node，
        就会「select_node -> _tree_select -> 事件 -> select_node」无限重绘。
        用 _syncing_tree 标记把这次事件吃掉。"""
        tree = self.tree_nodes if kind == "node" else self.tree_edges
        if kind == "node":
            iid = "n:" + str(key)
        else:
            # 边：合并模式下两个方向共用一条 iid 为 "b:A<->B" 的行
            frm, to = str(key).split("->")
            both = (self.edge_view.get() == "合并双向"
                    and self.model.edge(frm, to) and self.model.edge(to, frm))
            iid = ("b:%s<->%s" % (frm, to)) if both else ("e:%s->%s" % (frm, to))
        try:
            self._syncing_tree = True
            tree.selection_set(iid)
            tree.see(iid)
        except tk.TclError:
            pass
        finally:
            self._syncing_tree = False

    def _on_tree_node_select(self, _ev):
        if self._suspend_ui or getattr(self, "_syncing_tree", False):
            return
        sel = self.tree_nodes.selection()
        if not sel:
            return
        name = sel[0][2:]
        if name == self.sel_node:
            return
        # 只更新状态 + 重绘，不再回写树选中（避免递归）
        self.sel_node = name
        self.sel_edge = None
        self.refresh_props()
        self.redraw()

    def _on_tree_edge_select(self, _ev):
        if self._suspend_ui or getattr(self, "_syncing_tree", False):
            return
        sel = self.tree_edges.selection()
        if not sel:
            return
        iid = sel[0]
        if iid.startswith("b:"):                    # 合并行 A<->B
            frm, to = iid[2:].split("<->")
            e = self.model.edge(frm, to) or self.model.edge(to, frm)
            # 同一合并行再点一次 = 在正/反两个方向间切换（和画布上的"再点一次"一致）
            rev = self.model.edge(to, frm)
            if (e is not None and rev is not None and self.sel_edge is not None
                    and self.sel_edge.tag == e.tag):
                e = rev
        else:
            frm, to = iid[2:].split("->")
            e = self.model.edge(frm, to)
        if not e:
            return
        if self.sel_edge is not None and self.sel_edge.tag == e.tag:
            self.status("已选中边 %s → %s" % (e.frm, e.to))
            return
        self.sel_edge = e
        self.sel_node = None
        self.refresh_props()
        self.redraw()
        rev = self.model.edge(e.to, e.frm)
        if rev is not None:
            self.status("已选中线段 %s ↔ %s（当前方向 %s → %s；再点这一行可切换方向 / "
                        "画布上同一处再点一次也行）"
                        % (e.frm, e.to, e.frm, e.to))
        else:
            self.status("已选中边 %s（**没有反向边**，可在属性面板「补反向边」）" % e.label())

    def refresh_all(self):
        self.refresh_trees()
        self.refresh_props()
        self.redraw()

    def refresh_trees(self):
        self._suspend_ui = True
        try:
            self.tree_nodes.delete(*self.tree_nodes.get_children())
            for i, n in enumerate(self.model.nodes):
                deg = "%d/%d" % (len(self.model.edges_of(n.name, True)),
                                 len(self.model.edges_of(n.name, False)))
                self.tree_nodes.insert("", "end", iid="n:" + n.name,
                                       text=n.name, values=(i, KIND_ZH.get(n.kind, "?"), deg))
            self.tree_edges.delete(*self.tree_edges.get_children())
            self._apply_edge_columns()
            mode = self.edge_view.get()
            if mode == "合并双向":
                self._fill_edges_merged()
            else:
                only_both = (mode == "只看双向")
                for e in self.model.edges:
                    if only_both and not self.model.has_reverse(e):
                        continue
                    a, s = self.model.ang(e), self.model.step(e)
                    rev = self.model.edge(e.to, e.frm)
                    mark = "↔" if rev is not None else "→"
                    self.tree_edges.insert(
                        "", "end", iid="e:%s->%s" % (e.frm, e.to),
                        text="%s %s%s%s" % (mark, e.frm, "→" if rev is None else "↔",
                                            e.to),
                        values=("%.0f" % a if a is not None else "?",
                                "%.0f" % s if s is not None else "?", e.func, ""))
        finally:
            self._suspend_ui = False

    def _fill_edges_merged(self):
        """合并双向：每**条线段**一行，两个方向的角度/step 并列。

        - 两个方向都存在 → 一行显示 `A↔B`，并列出 →角度/→step/←角度/←step
        - 只有单向        → 一行显示 `A→B`，反向列填「—」
        选中这一行 → 选中正向边；没有反向边时可在属性面板一键补上。
        """
        m = self.model
        done = set()
        rows = []
        for e in m.edges:
            key = frozenset((e.frm, e.to))
            if key in done:
                continue
            done.add(key)
            rev = m.edge(e.to, e.frm)
            # 让 A→B 用"字母序在前"的方向当正向，列表更稳（不随源码顺序跳）
            fwd = e
            if e.frm > e.to and rev is not None:
                fwd, rev = rev, e
            rows.append((fwd, rev))
        rows.sort(key=lambda r: (r[0].frm, r[0].to))

        def fmt(x, is_ang):
            if x is None:
                return "—"
            return ("%.0f°" % x) if is_ang else ("%.0f" % x)

        for fwd, rev in rows:
            a1, s1 = m.ang(fwd), m.step(fwd)
            a2, s2 = (m.ang(rev), m.step(rev)) if rev is not None else (None, None)
            both = rev is not None
            label = "%s %s↔%s" % ("↔" if both else "→", fwd.frm, fwd.to)
            self.tree_edges.insert(
                "", "end",
                iid=("b:%s<->%s" % (fwd.frm, fwd.to)) if both
                    else ("e:%s->%s" % (fwd.frm, fwd.to)),
                text=label,
                values=(fmt(a1, True), fmt(s1, False),
                        fmt(a2, True), fmt(s2, False)))

    def refresh_props(self):
        self._suspend_ui = True
        try:
            w = self._prop_widgets
            for key in ("name", "comment", "from", "to", "angle", "step", "speed",
                        "func", "flag"):
                w[key].configure(state="normal")
            names = self.model.names()
            w["from"].configure(values=names)
            w["to"].configure(values=names)

            if self.sel_edge:
                e = self.sel_edge
                rev = self.model.edge(e.to, e.frm)
                if rev is not None:
                    a2, s2 = self.model.ang(rev), self.model.step(rev)
                    self.lbl_sel.configure(
                        text="线段 %s ↔ %s　【反向边参数】%s：%.0f° / step %s / %s"
                             % (e.frm, e.to, rev.label(),
                                a2 if a2 is not None else 0,
                                ("%.0f" % s2) if s2 is not None else "?",
                                rev.func))
                else:
                    self.lbl_sel.configure(text="边  %s　（⚠ 没有反向边）" % e.label())
                w["name"].delete(0, "end")
                w["name"].insert(0, "")          # 边的"名"不可改（改 from/to）
                w["name"].configure(state="disabled")
                w["from"].set(e.frm)
                w["to"].set(e.to)
                w["angle"].delete(0, "end"); w["angle"].insert(0, e.angle)
                w["step"].delete(0, "end"); w["step"].insert(0, e.step)
                w["speed"].delete(0, "end"); w["speed"].insert(0, e.speed)
                w["func"].set(e.func)
                w["flag"].delete(0, "end"); w["flag"].insert(0, e.flag)
                w["comment"].delete(0, "end"); w["comment"].insert(0, e.comment)
                flagset = {t.strip() for t in re.split(r"[|,]", e.flag or "") if t.strip()}
                for k, v in self.flag_vars.items():
                    v.set(k in flagset)
            elif self.sel_node:
                n = self.model.node(self.sel_node)
                self.lbl_sel.configure(text="节点  %s（%s，索引 %d）"
                                            % (n.name, KIND_ZH.get(n.kind, "?"),
                                               self.model.node_index(n.name)))
                w["name"].delete(0, "end"); w["name"].insert(0, n.name)
                w["comment"].delete(0, "end"); w["comment"].insert(0, n.comment)
                for key in ("from", "to", "angle", "step", "speed", "flag"):
                    w[key].set("") if key in ("from", "to", "func") else None
                w["angle"].delete(0, "end")
                w["step"].delete(0, "end")
                w["speed"].delete(0, "end")
                w["flag"].delete(0, "end")
                w["func"].set("")
                for v in self.flag_vars.values():
                    v.set(False)
            else:
                self.lbl_sel.configure(text="（未选中）")
                for key in ("name", "comment", "angle", "step", "speed", "flag"):
                    w[key].delete(0, "end")
                w["from"].set(""); w["to"].set(""); w["func"].set("")
                for v in self.flag_vars.values():
                    v.set(False)
        finally:
            self._suspend_ui = False

    def _flags_to_text(self):
        if self._suspend_ui or not self.sel_edge:
            return
        chosen = [k for k in M.FLAG_ORDER if self.flag_vars[k].get()]
        self._prop_widgets["flag"].delete(0, "end")
        self._prop_widgets["flag"].insert(0, "|".join(chosen) if chosen else "NO")

    def apply_props(self):
        snap = self.model.snapshot()
        try:
            if self.sel_edge:
                e = self.sel_edge
                w = self._prop_widgets
                nf, nt = w["from"].get().strip(), w["to"].get().strip()
                if not nf or not nt:
                    raise ValueError("from / to 不能为空")
                if nf == nt:
                    raise ValueError("不能自环")
                other = self.model.edge(nf, nt)
                if other is not None and other.tag != e.tag:
                    raise ValueError("边 %s->%s 已存在" % (nf, nt))
                e.frm, e.to = nf, nt
                e.angle = w["angle"].get().strip() or "0"
                e.step = w["step"].get().strip() or "0"
                e.speed = w["speed"].get().strip() or "SPEED0"
                e.func = w["func"].get().strip() or "NONE"
                e.flag = w["flag"].get().strip() or "NO"
                e.comment = w["comment"].get().strip()
            elif self.sel_node:
                w = self._prop_widgets
                old = self.sel_node
                new = w["name"].get().strip()
                if new != old:
                    self.model.rename_node(old, new)
                    self.sel_node = new
                self.model.node(self.sel_node).comment = w["comment"].get().strip()
            else:
                self.status("没选中东西")
                return
            self._apply_change(snap)
            self.status("已应用修改")
        except ValueError as ex:
            messagebox.showerror("修改失败", str(ex), parent=self)

    # ================================================================ 校验
    def _source_diff_items(self):
        """把「当前模型」与「固件源码」比一比 —— 启动自动载入的布局可能已经不是固件地图了。

        很实际的坑：`App.__init__` 会自动载入 `layouts/default.json`，**它会盖掉固件地图**。
        那份布局若是旧的/试验性的（例如做过演示改动），那么"显示的路线 / 校验 / 导出的 C 代码"
        全都基于布局，而不是车上的地图 —— 于是就会出现"上位机算的路线和车上跑的不一样"。
        返回 (items, short)：items 给校验面板用；short 是不一致时的一句话摘要（一致为 None）。
        """
        try:
            src = M.MapModel.load_from_sources()
        except Exception as ex:                                   # noqa: BLE001
            return [("warn", "无法读取固件源码做对比：%s" % ex)], None
        cur = self.model
        add_n = sorted({n.name for n in cur.nodes} - {n.name for n in src.nodes})
        del_n = sorted({n.name for n in src.nodes} - {n.name for n in cur.nodes})
        add_e = sorted({(e.frm, e.to) for e in cur.edges} - {(e.frm, e.to) for e in src.edges})
        del_e = sorted({(e.frm, e.to) for e in src.edges} - {(e.frm, e.to) for e in cur.edges})
        if not (add_n or del_n or add_e or del_e):
            return ([("info", "当前地图与固件源码一致（%d 节点 / %d 条边）"
                      % (len(src.nodes), len(src.edges)))], None)
        items = [("warn", "⚠ 当前地图 ≠ 固件源码：启动自动载入的 "
                          "layouts/default.json 会盖掉固件地图，下面所有路线/校验/导出"
                          "都基于【当前地图】。要回到固件版请点工具栏「重新载入源码」。")]
        if add_n:
            items.append(("warn", "多出节点（当前地图有、固件没有）：%s" % ", ".join(add_n)))
        if del_n:
            items.append(("warn", "缺少节点（固件有、当前地图没有）：%s" % ", ".join(del_n)))
        if add_e:
            items.append(("warn", "多出边 %d 条：%s"
                          % (len(add_e), ", ".join("%s→%s" % p for p in add_e[:10]))))
        if del_e:
            items.append(("warn", "缺少边 %d 条：%s"
                          % (len(del_e), ", ".join("%s→%s" % p for p in del_e[:10]))))
        return items, "＋%d节点 / －%d节点 / ＋%d边 / －%d边" % (
            len(add_n), len(del_n), len(add_e), len(del_e))

    def do_validate(self):
        items = self.model.validate()
        items += self._source_diff_items()[0]
        self.txt_val.delete("1.0", "end")
        n_err = sum(1 for lv, _ in items if lv == "error")
        n_warn = sum(1 for lv, _ in items if lv == "warn")
        for lv, msg in items:
            self.txt_val.insert("end", "[%s] %s\n" % (lv, msg), lv)
        self.status("校验完成：%d error / %d warn" % (n_err, n_warn))
        return items

    # ================================================================ 路线规划
    def wp_add_sel(self):
        if self.sel_node:
            self.wp_add(self.sel_node)

    def wp_add(self, name):
        self.waypoints.append(name)
        self._refresh_wp()

    def wp_del(self):
        sel = self.lst_wp.curselection()
        if sel:
            del self.waypoints[sel[0]]
            self._refresh_wp()

    def wp_move(self, d):
        sel = self.lst_wp.curselection()
        if not sel:
            return
        i = sel[0]
        j = i + d
        if 0 <= j < len(self.waypoints):
            self.waypoints[i], self.waypoints[j] = self.waypoints[j], self.waypoints[i]
            self._refresh_wp()
            self.lst_wp.selection_set(j)

    def wp_clear(self):
        self.waypoints = []
        self._refresh_wp()

    def wp_from_config(self):
        try:
            src = open(M.PATH_CONFIG, encoding="utf-8").read()
        except OSError as ex:
            messagebox.showerror("失败", str(ex), parent=self)
            return
        g = lambda k: (re.search(r"#define\s+%s\s+([A-Za-z_]\w*|\d+)" % k, src) or [None, None])[1]
        first, via, end = g("FIRST_POINT"), g("VIA_POINT"), g("END_POINT")
        self.waypoints = [x for x in (first, via, end) if x and x != "0"]
        self._refresh_wp()
        self.status("已从 config.h 读入 FIRST=%s VIA=%s END=%s" % (first, via, end))

    def _refresh_wp(self):
        self.lst_wp.delete(0, "end")
        for i, w in enumerate(self.waypoints):
            tag = "起" if i == 0 else ("终" if i == len(self.waypoints) - 1 else "途")
            self.lst_wp.insert("end", "%s  %s" % (tag, w))

    def plan_route(self):
        if len(self.waypoints) < 2:
            messagebox.showinfo("提示", "至少要有 2 个必经点（起点+终点）", parent=self)
            return
        self.route_split = None          # 普通规划不分去程/回程
        path, why = self.model.plan_route(self.waypoints, self.cost_mode.get())
        if path is None:
            self.txt_route.delete("1.0", "end")
            self.txt_route.insert("end", "规划失败：%s\n" % why)
            self.route = []
            self.redraw()
            self.status("规划失败：%s" % why)
            return
        self.route = path
        self.show_route_text(path)
        self.redraw()

    def plan_normal_route(self):
        """显示固件 mapInit 的常规第一轮路线：N2 -> P1 -> N5。"""
        waypoints = [name for name in ("N2", "P1", "N5")
                     if self.model.node(name) is not None]
        if len(waypoints) != 3:
            messagebox.showerror("常规路线不可用",
                                 "当前地图缺少 N2、P1 或 N5，无法复现固件常规路线。",
                                 parent=self)
            return
        self.waypoints = waypoints
        self._refresh_wp()
        self.route_split = None          # 常规路线不分去程/回程
        path, why = self.model.plan_route(waypoints, self.cost_mode.get())
        if path is None:
            self.route = []
            self.txt_route.delete("1.0", "end")
            self.txt_route.insert("end", "常规路线规划失败：%s\n" % why)
            self.redraw()
            self.status("常规路线规划失败：%s" % why)
            return
        self.route = path
        self.show_route_text(path)
        self.redraw()
        self.status("已显示固件常规路线：N2 -> P1 -> N5，共 %d 跳" % (len(path) - 1))

    def _fmt_planned(self, wp, path, why, blocked=None):
        """把一条规划结果格式化成若干行（含逐段角度/长度/flag）。"""
        lines = ["wp: %s" % " -> ".join(wp)]
        if blocked:
            lines.append("禁用边（nav_set_edge_blocked）: %s"
                         % ", ".join("%s->%s" % b for b in sorted(blocked)))
        if path is None:
            lines.append("⚠ 规划失败：%s" % why)
            return lines
        lines.append("路线（%d 跳）: %s" % (len(path) - 1, " -> ".join(path)))
        lines.append("route[]: %s" % self.model.export_route_array(path).strip())
        lines.append("逐段明细:")
        for i in range(len(path) - 1):
            e = self.model.edge(path[i], path[i + 1])
            if e is None:
                lines.append("    %-6s -> %-6s  ⚠ 无边！" % (path[i], path[i + 1]))
                continue
            a, s = self.model.ang(e), self.model.step(e)
            lines.append("    %-6s -> %-6s %7.1f° %6s cm  %-10s %s" % (
                path[i], path[i + 1], a if a is not None else 0,
                ("%.0f" % s) if s is not None else "?", e.func, e.flag))
        if len(path) > 1:
            e1 = self.model.edge(path[0], path[1])
            if e1 is not None:
                lines.append("注：固件起点 = wp[0]（%s）；摆车时车头顺 %s->%s，"
                             "陀螺仪参考角 = 该边 angle = %s°"
                             % (path[0], path[0], path[1], self.model.ang(e1)))
        # 两类告警（与 show_route_text 同源）：DOOR 边会清空 route[]；180° 原路折返
        for i in range(len(path) - 1):
            e = self.model.edge(path[i], path[i + 1])
            if e is not None and e.func == "DOOR":
                lines.append("    ⚠ %s -> %s 是 DOOR 边：到点后 door() 先 map.point=0、"
                             "route[0]=0xFF，再按读到的灯重写 route[] / 改 nowNode"
                             % (path[i], path[i + 1]))
        for i in range(1, len(path) - 1):
            e1 = self.model.edge(path[i - 1], path[i])
            e2 = self.model.edge(path[i], path[i + 1])
            if e1 is None or e2 is None:
                continue
            a1, a2 = self.model.ang(e1), self.model.ang(e2)
            if a1 is None or a2 is None:
                continue
            d = (a2 - a1) % 360.0
            if d > 180:
                d -= 360
            if abs(abs(d) - 180) < 3:
                lines.append("    ⚠ %s 处 180° 原路折返" % path[i])
        return lines

    def _macro_value(self, name):
        """求 Mission/config.h 里的宏（按当前 USE_FIELD 展开）。求不出来返回 None。"""
        try:
            return M.eval_c_expr(name, self.model.macros)
        except Exception:                                        # noqa: BLE001
            return None

    def _doors_after_entry_read(self, doors):
        """回程梯子的输入：只有"进门时真读到的门"算已知，其余按固件初值 0（未读）算。

        门是按**边顺序**读的（N5→N12 读 D2、N5→N8 读 D3、N3→N8 读 D4）。D2 能过就直接落 N12，
        N5→N8 那条边根本不会走 ⇒ 车不知道 D3 是什么颜色，固件里 door_pass[1] 一直是 0。
        而梯子把 0 当"非绿非黑"，跟"设成黑"结果不同 ⇒ 不能拿对话框填的值直接进梯子。
        返回 (doors_eff, read_set, warn_lines)。
        """
        read = M.door_read_names(doors)
        eff = M.doors_known_only(doors, read)
        unread = [n for i, n in enumerate(M.DOOR_SLOT_NAME)
                  if i < len(doors) and doors[i] != 0 and eff[i] == 0]
        warn = []
        if unread:
            warn.append("⚠ %s 填了灯色但第一轮读不到（门按边顺序读：N5→N12 读 D2、"
                        "N5→N8 读 D3、N3→N8 读 D4）⇒ 固件眼里是「未读 = 0」，"
                        "下面按未读算，不是按你填的算。" % "/".join(unread))
        return eff, read, warn

    def _append_after_door(self, sections, enter, ab, doors, treasure, mode):
        """过门之后：stageAB（平台 A/B）+ 宝物回程。返回可上画布的 path（或 None）。"""
        a, b = ab
        wp1, why1 = M.stageab_waypoints(enter, a, b)
        if wp1 is None:
            sections.append(("过门后 stageAB / update_route_at_door_for_stageAB()",
                             ["⚠ %s" % why1]))
            return None
        p1, e1 = self.model.plan_route(wp1, mode)
        sections.append((
            "过门后 stageAB / update_route_at_door_for_stageAB()（过门落在 %s）" % enter,
            self._fmt_planned(wp1, p1, e1)))
        if p1 is None:
            return None
        canvas = list(p1)
        if treasure is None:
            sections.append(("宝物回程 / plan_treasure_return()", [
                "宝物线索「未定」：固件读不到宝物编号时会 CarBrake_Stop()。"]))
            return canvas
        doors_eff, _read, warn_doors = self._doors_after_entry_read(doors)
        wp2, why2 = M.treasure_return_waypoints("P%d" % b, doors_eff, treasure)
        if wp2 is None:
            sections.append(("宝物回程 / plan_treasure_return()", ["⚠ %s" % why2]))
            return canvas
        p2, e2 = self.model.plan_route(wp2, mode)
        sections.append(("宝物回程 / plan_treasure_return(P%d)" % b,
                         warn_doors + self._fmt_planned(wp2, p2, e2)))
        if p2 is not None:
            merged = list(p1) + list(p2[1:])
            sections.append(("车上连续执行（两段拼接）", [
                "路线（%d 跳）: %s" % (len(merged) - 1, " -> ".join(merged)),
                "route[]: %s" % self.model.export_route_array(merged).strip()]))
            canvas = merged
        return canvas

    def _door_trace_lines(self, doors, with_back=True):
        """door() 内部推演 → 文本行（读灯推进 + 手写路线 + 退回距离 + 回家过门分支）。"""
        lines = ["【进门读灯推进】barrier.c:door() —— 路线/节点改动都写在 door() 内部，不经规划器"]
        steps, enter, err = M.door_read_flow(doors)
        for name, edge, st, verdict, act in steps:
            lines.append("  %-6s 在 %-8s 读灯 = %-10s %s" % (name, edge, M.DOOR_STATE_NAME[st], verdict))
            lines.append("         └ %s" % act)
        for macro, who in (("DOOR_RETREAT_N5N8", "D2 黑退回"), ("DOOR_RETREAT_N5N4", "D3 黑退回"),
                           ("DOOR_RETREAT_N10N8", "D5 黑退回"), ("DOOR_RETREAT_N8N5", "D4回程黑退回")):
            v = self._macro_value(macro)
            if v is not None:
                lines.append("  %s距离：%s = %s cm" % (who, macro, ("%.0f" % v)))
        if err:
            lines.append("  → ⚠ %s" % err)
        else:
            lines.append("  → 过门后 nodes.nowNode 落在 %s" % enter)

        bsteps, hazards = M.door_back_flow(doors)
        if with_back:
            lines.append("")
            lines.append("【回家路上过门】door() 的 D5_BACK(N10→N3) / D4_BACK(N8→N3)"
                         "（只有回程真的被送到该门时才走）")
            for name, edge, st, verdict, act in bsteps:
                lines.append("  %-10s 在 %-8s 读灯 = %-10s %s"
                             % (name, edge, M.DOOR_STATE_NAME[st], verdict))
                lines.append("         └ %s" % act)
            for h in hazards:
                lines.append("  ⚠ %s" % h)
        return lines, enter, err

    def _write_route_report(self, sections):
        """sections = [(标题, 行列表)]，写入主路线面板（关掉对话框后仍可见）。"""
        t = self.txt_route
        t.delete("1.0", "end")
        for title, lines in sections:
            t.insert("end", "=== %s ===\n" % title)
            for ln in lines:
                t.insert("end", ln + "\n")
            t.insert("end", "\n")

    @staticmethod
    def _join(seq, add):
        """把 add 接到 seq 后面；首节点与 seq 末尾重复时跳过（拼接点去重）。"""
        add = list(add)
        if seq and add and add[0] == seq[-1]:
            add = add[1:]
        return list(seq) + add

    def _round1_complete(self, clue, ab, doors, treasure, mode="full"):
        """第一轮**完整路线**：起步 → P1 → 门区 → 东区 → 回程，逐段拼接成一条。

        拼接依据（都是固件真实交接点）：
          ① mapInit() 把 nowNode 置成 P2→N2，之后 route[] = nav_build_route({N2,P1,N5})；
             在 P1 平台里 update_route_at_P1() 用手写数组**整条覆盖** route[]，
             其前 4 跳与 mapInit 完全相同 ⇒ 完整路线 = P2 → N2 → 手写数组。
          ② 手写数组一律以 N12 结尾（在 N5→N12 上读 D2）⇒ 门区从 N12 接着走。
          ③ 过门后 update_route_at_door_for_stageAB() 的 wp[0] 就是过门落点 ⇒ 自然接上。
          ④ 到第二个平台(P7/P8)读宝物 ⇒ plan_treasure_return() 的 wp[0] 就是该平台。
          ⑤ 回程若穿过 BACK 门(N10→N3 / N8→N3)，door() 会再调 route_return_home() 覆盖 ⇒ 再拼一段。

        返回 (sections, flat_nodes, split_idx, err)：split_idx = 回程起始下标（画布分色用）。
        """
        sections = []
        # ---- ① 起步 + P1 ----
        if clue is None:
            base, _w = self.model.plan_route(["N2", "P1", "N5"], mode)
            arr = list(base[1:]) if base else []
            note1 = ("P1 线索不在 {0,3,4} ⇒ update_route_at_P1() 不改路线："
                     "车走到 N5 就结束第一轮（不进东区、不过门）。")
        else:
            arr = list(M.p1_route(clue) or [])
            note1 = ("P1 线索 = %d ⇒ update_route_at_P1() 的手写数组"
                     "（前 4 跳与 mapInit 的 N2→P1→N5 完全相同）" % clue)
        if not arr:
            return sections, [], None, ("无法拼接", "P1 之后的路线取不到（缺节点或线索组合不可用）")
        leg1 = ["P2", "N2"] + arr
        sections.append(("① 去程·起步与 P1 / mapInit() + update_route_at_P1()", [
            note1,
            "序列（%d 跳）: %s" % (len(leg1) - 1, " -> ".join(leg1))]))
        if clue is None:
            return sections, leg1, None, None

        # ---- ② 门区读灯（退回重读的额外节点）----
        hops, enter, err = M.door_read_hops(doors)
        if err:
            return sections, [], None, ("固件会停车", err)
        trace, _e, _er = self._door_trace_lines(doors, with_back=False)
        sections.append(("② 去程·门区读灯 / barrier.c:door()", list(trace) + [
            "门区额外节点: %s" % (" -> ".join(hops) if hops else "（无，D2 直接过门）"),
            "过门落点: %s" % enter]))
        outbound = self._join(leg1, hops)

        # ---- ③ 东区（stageAB）----
        a, b = ab
        wp1, why1 = M.stageab_waypoints(enter, a, b)
        if wp1 is None:
            return sections, [], None, ("线索组合不合法", str(why1))
        p1, e1 = self.model.plan_route(wp1, mode)
        if p1 is None:
            return sections, [], None, ("规划失败", "stageAB：%s" % e1)
        sections.append(("③ 去程·东区平台 / update_route_at_door_for_stageAB()",
                         self._fmt_planned(wp1, p1, e1)))
        outbound = self._join(outbound, p1)
        split = len(outbound) - 1          # 回程从 P_B（东区第二个平台）开始

        # ---- ④ 回程 ----
        if treasure is None:
            sections.append(("④ 回程", ["宝物线索「未定」：固件读不到宝物编号会 CarBrake_Stop()，"
                                        "回程算不出来。"]))
            return sections, outbound, None, None
        doors_eff, read_entry, warn_doors = self._doors_after_entry_read(doors)
        wp2, why2 = M.treasure_return_waypoints("P%d" % b, doors_eff, treasure)
        if wp2 is None:
            return sections, [], None, ("固件会停车", str(why2))
        p2, e2 = self.model.plan_route(wp2, mode)
        if p2 is None:
            return sections, [], None, ("规划失败", "宝物回程：%s" % e2)
        ret = list(p2)
        lines4 = warn_doors + self._fmt_planned(wp2, p2, e2)
        sections.append(("④ 回程·宝物 / plan_treasure_return(P%d)" % b, lines4))
        # 回程穿过 BACK 门 ⇒ 固件在那里用 route_return_home() 覆盖路线，再拼一段
        idx = None
        for i in range(len(ret) - 1):
            e = self.model.edge(ret[i], ret[i + 1])
            if e is not None and e.func == "DOOR" and ret[i + 1] == "N3" and ret[i] in ("N10", "N8"):
                idx = i
                break
        if idx is not None:
            edge = (ret[idx], ret[idx + 1])
            lines4.append("↑ 这段走到 %s→%s 就作废了：固件在这里调 route_return_home()，"
                          "见下面 ④b" % edge)
            chain, start, allow, note = self._back_branch_from_edge(doors, read_entry, edge)
            wp3, blocked = M.door_return_home_waypoints(start, treasure, allow)
            p3, e3 = self.model.plan_route(wp3, mode, blocked)
            lines = ["回程在 %s→%s 上撞到 BACK 门 ⇒ door() 会重写路线：" % edge, "  " + note]
            foot = list(ret[:idx + 1]) + list(chain)
            if p3 is not None:
                foot = self._join(foot, p3)
                lines += self._fmt_planned(wp3, p3, e3, blocked)
            else:
                lines.append("  ⚠ 重规划失败：%s" % e3)
            ret = foot
            sections.append(("④b 回程·门区（door() 的 BACK 分支重规划）", lines))

        flat = self._join(outbound, ret)
        front = flat[:split + 1]
        back = flat[split:]
        bad = [(front[i], front[i + 1]) for i in range(len(front) - 1)
               if self.model.edge(front[i], front[i + 1]) is None]
        sections.append(("第一轮·完整路线（去程 + 回程拼接，共 %d 跳）" % (len(flat) - 1), [
            "去程（蓝）%d 跳: %s" % (len(front) - 1, " -> ".join(front)),
            "回程（青绿）%d 跳: %s" % (len(back) - 1, " -> ".join(back)),
            "route[]: %s" % self.model.export_route_array(flat).strip()] +
            (["⚠ 去程里有 %d 处相邻节点在边表里没有边（门区退回是「退+转」动作，"
              "不代表边表缺边）：%s"
              % (len(bad), ", ".join("%s→%s" % p for p in bad))] if bad else [])))
        return sections, flat, split, None

    def _back_branch_from_edge(self, doors, read_set, edge):
        """按「4 格门灯 + 进门读到的灯」推 BACK 门之后怎么走（④b 与「门区回程」阶段共用）。

        走到 N10→N3 会读 D5、退回后 N8→N3 会重读 D4 ⇒ 这两盏此刻按真值算；
        D2/D3 仍只有进门时读到的值（没读到就是 0=未读）。
        """
        doors_back = M.doors_known_only(doors, set(read_set) | {"D4", "D5"})
        return M.door_back_chain(doors_back, edge)

    def _back_door_edge(self, doors):
        """回程会不会撞 BACK 门、撞哪条 —— 镜像 plan_treasure_return() 的梯子（只看进门读到的门）。

        返回 (kind, edge_or_None, why)：kind ∈ {"back", "none", "stop"}。
        """
        read = M.door_read_names(doors)
        eff = M.doors_known_only(doors, read)
        d2, d3, d4 = eff[0], eff[1], eff[2]
        if d2 == M.CAN_PASS:
            return "none", None, "进门读到 D2 绿 ⇒ 回程走 N12→N5（D2 那扇门），不经过 BACK 门"
        if d3 == M.CAN_PASS:
            return "none", None, "进门读到 D3 绿 ⇒ 回程走 N8→N5（D3 那扇门），不经过 BACK 门"
        if d4 == M.CAN_PASS:
            return "back", ("N8", "N3"), "进门读到 D4 绿 ⇒ 回程必经点钉住 N8→N3（走 D4 回家）"
        if M.ONE_WAY_PASS in (d2, d3, d4):
            return "back", ("N10", "N3"), ("D2/D3/D4 没有一个是绿、但读到过蓝（单相）⇒ "
                                           "回程必经点押 N10→N3（到门口才读 D5）")
        return "stop", None, "D2/D3/D4 都不能过 ⇒ 固件 plan_treasure_return() 直接 CarBrake_Stop()"

    def _input_section(self, stage, clue, ab, doors, treasure):
        """报告头：把这次的输入原样回显（免得以后分不清这份报告是哪套灯算的）。"""
        clue_txt = {None: "不指定（固件不改路线）", 0: "0（跳过 P3/P4）",
                    3: "3（经过 P3）", 4: "4（经过 P4）"}.get(clue, str(clue))
        lights = "  ".join("%s=%s" % (M.DOOR_SLOT_NAME[i], M.DOOR_STATE_NAME[doors[i]])
                           for i in range(min(4, len(doors))))
        return ("本次输入（这份报告按这套算）",
                ["阶段：%s" % stage,
                 "P1 线索 = %s ｜ 平台 A/B = P%d/P%d ｜ 宝物 = %s"
                 % (clue_txt, ab[0], ab[1],
                    "未定" if treasure is None else "P%d" % treasure),
                 "门灯：%s（绿=能过 / 蓝=单相 / 黑=不能过）" % lights])

    def _clue_route_sections(self, stage, clue, ab, doors, treasure, mode="full"):
        """线索/门灯/宝物 → 固件分支的路线（**纯计算，不碰 UI**；对话框与冒烟测试共用）。

        参数：stage=阶段文本；clue=P1 线索(0/3/4/None)；ab=(平台A, 平台B)；
              doors=[D2,D3,D4,D5] 状态（**唯一输入**：回程走哪个门区入口也由它自动推）；
              treasure=宝物编号或 None。
        返回 (sections, canvas_path, err)：sections=[(标题, 行列表)]；err=(标题, 说明) 或 None。
        第一段固定是「本次输入」回显，方便对上报告是哪套灯算的。
        """
        sections = [self._input_section(stage, clue, ab, doors, treasure)]
        canvas = []
        self.route_split = None          # 每次重算；只有「第一轮·完整路线」会设它（画布分色用）

        def plan(wp, blocked=None):
            return self.model.plan_route(wp, mode, blocked)

        if stage.startswith("第一轮·完整路线"):
            sub, flat, split, err = self._round1_complete(clue, ab, doors, treasure, mode)
            sections += sub
            if err:
                return sections, [], err
            self.route_split = split
            return sections, flat, None

        if stage.startswith("第一轮·P1"):
            arr = M.p1_route(clue) if clue is not None else None
            if arr is None:
                # 固件不改路线 → 保持 mapInit() 的 N2→P1→N5，这里把它算出来显示
                wp0 = [w for w in ("N2", "P1", "N5") if self.model.node(w)]
                s0 = ["固件在这里不改路线（只有线索 = 0 / 3 / 4 才改写 route[]），",
                      "保持 mapInit() 的 N2 → P1 → N5。"]
                if len(wp0) == 3:
                    p0, e0 = plan(wp0)
                    s0 += self._fmt_planned(wp0, p0, e0)
                    if p0:
                        canvas = list(p0)
                sections.append(("第一轮·P1 之后 / update_route_at_P1()", s0))
            else:
                sections.append((
                    "第一轮·P1 之后 / update_route_at_P1()（线索=%d）" % clue, [
                        "⚠ 这段是固件里的手写数组，不走规划器；按源码逐字列出。",
                        "route[]: %s" % self.model.export_route_array(arr).strip(),
                        "序列（%d 跳）: %s" % (len(arr) - 1, " -> ".join(arr))]))
                canvas = list(arr)

        elif stage.startswith("第一轮·门区全流程"):
            trace, enter, err = self._door_trace_lines(doors)
            sections.append(("第一轮·门区全流程 / barrier.c:door()（进门读灯 + 手写路线）", trace))
            if err:
                return sections, canvas, None
            canvas = self._append_after_door(sections, enter, ab, doors, treasure, mode) or []

        elif stage.startswith("第一轮·过门"):
            trace, enter, err = self._door_trace_lines(doors, with_back=False)
            if err:
                return sections, canvas, ("固件会停车", err)
            sections.append(("门区读灯推进（door()，路线写在门里）", trace))
            canvas = self._append_after_door(sections, enter, ab, doors, treasure, mode) or []

        elif stage.startswith("第一轮·门区回程"):
            bsteps, hazards = M.door_back_flow(doors)
            head = ["回家路上过门（door() 内部）："]
            for name, edge, st, verdict, act in bsteps:
                head.append("  %-10s 在 %-8s 读灯 = %-10s %s"
                            % (name, edge, M.DOOR_STATE_NAME[st], verdict))
                head.append("         └ %s" % act)
            for h in hazards:
                head.append("  ⚠ %s" % h)
            base = "门区回程 / route_return_home()（入口由 4 格门灯自动推）"
            kind, edge, why = self._back_door_edge(doors)
            if kind != "back":
                head.append("⚠ %s" % why)
                head.append("⇒ %s" % ("固件会停车，route_return_home() 不会被调用；"
                                      "没有可画的回程段。" if kind == "stop" else
                                      "回程不撞 BACK 门（N10→N3 / N8→N3），"
                                      "route_return_home() 不会被调用；没有可画的回程段。"))
                sections.append((base, head))
                return sections, [], None
            chain, start, allow, note = self._back_branch_from_edge(
                doors, M.door_read_names(doors), edge)
            wp, blocked = M.door_return_home_waypoints(start, treasure, allow)
            path, why = plan(wp, blocked)
            head.append("回程在 %s→%s 上撞 BACK 门：%s" % (edge[0], edge[1], note))
            head.append("门区 8 条边在规划层全禁（nav_set_edge_blocked），"
                        "防止回程又拐进门区 / 在门口穿门掉头。")
            if chain:
                head.append("退回跳 %s 是 door_retreat() 的「后退+转身」动作，"
                            "不是边表里的边。" % " → ".join(chain))
            if treasure is None:
                head.append("⚠ 宝物线索「未定」：固件在东区平台就会停车，"
                            "下面这条只示意 route_return_home() 本身。")
            sections.append((
                "%s｜起点 %s%s" % (base, start, "，放行 N8→N3" if allow else ""),
                head + self._fmt_planned(wp, path, why, blocked)))
            canvas = list(chain)
            if path:
                canvas = self._join(canvas, path)

        else:
            wp, why = M.round2_waypoints(doors, treasure if treasure is not None else 0)
            if wp is None:
                return sections, canvas, ("固件会停车", str(why))
            path, e = plan(wp)
            sections.append(("第二轮·完整路线 / get_newroute()", self._fmt_planned(wp, path, e)))
            canvas = list(path) if path else []

        return sections, canvas, None

    def plan_clue_route_dialog(self):
        """按固件真实分支显示路线：每盏门灯(D2~D5) + 宝物线索 + P1/平台线索。

        每个「阶段」= 固件里一条确定的代码路径，逐条镜像（map_model 里的同名函数）：
          · 第一轮 P1 之后     -> mission_planner.c: update_route_at_P1()   （手写数组，非规划器）
          · 第一轮 过门→平台→回程 -> update_route_at_door_for_stageAB() + plan_treasure_return()
          · 第一轮 门区回程     -> route_return_home()（门区 8 边全禁；door_2 额外放行 N8->N3）
          · 第二轮 完整路线     -> get_newroute()
        """
        dlg = tk.Toplevel(self)
        dlg.title("线索 / 门灯 / 宝物 → 显示固件会跑的路线")
        dlg.geometry("660x430")
        dlg.transient(self)
        frm = ttk.Frame(dlg, padding=12)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, wraplength=620, justify="left",
                  text="灯按 barrier.h 的通行语义填：绿=能过(CAN_PASS)、蓝=单相(ONE_WAY_PASS)、"
                       "黑=不能过(NO_PASS)。选哪个阶段，就只镜像固件里那条分支；"
                       "结果（含逐段明细）写到主界面路线框。").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

        def combo(row, label, values, default, width=36):
            ttk.Label(frm, text=label).grid(row=row, column=0, sticky="w", pady=3, padx=(0, 6))
            var = tk.StringVar(value=default)
            ttk.Combobox(frm, textvariable=var, values=values, state="readonly",
                         width=width).grid(row=row, column=1, sticky="w", pady=3)
            return var

        STAGES = [
            "第一轮·完整路线（去程+门区+东区+回程 自动拼接，画布分色）",
            "第一轮·P1 之后（update_route_at_P1）",
            "第一轮·门区全流程（door() 状态机 + 门里的手写路线）",
            "第一轮·过门→平台A/B→宝物回程（stageAB + plan_treasure_return）",
            "第一轮·门区回程（route_return_home，门区禁用）",
            "第二轮·完整路线（get_newroute）",
        ]
        P1_VALS = ["不指定（固件不改路线）", "线索=0：跳过 P3、P4",
                   "线索=3：经过 P3", "线索=4：经过 P4"]
        AB_VALS = ["A=5,B=7：P5 -> P7", "A=5,B=8：P5 -> P8",
                   "A=6,B=7：P6 -> P7", "A=6,B=8：P6 -> P8"]
        TREASURE_VALS = ["未定", "2 · P1", "3 · P3", "4 · P4", "5 · P5", "6 · P6"]
        light_vals = [M.DOOR_STATE_NAME[s] for s in M.DOOR_STATE_ORDER]

        # 上次用的配置（内存里记着；随「保存布局」写进 constraints.clue_route，重启也能恢复）
        _cfg = dict(self.clue_route_cfg or {})

        def _pick(key, values, default):
            v = _cfg.get(key)
            return v if v in values else default

        stage = combo(1, "阶段", STAGES, _pick("stage", STAGES, STAGES[0]), width=54)
        p1clue = combo(2, "P1 平台线索", P1_VALS,
                       _pick("p1clue", P1_VALS, P1_VALS[0]))
        stg = combo(3, "平台 A/B 线索", AB_VALS, _pick("stg", AB_VALS, AB_VALS[0]))

        # 每盏灯一格（door_pass[0..3] = D2/D3/D4/D5）—— 固件 get_newroute() 全靠这 4 个值分支
        ttk.Label(frm, text="门灯状态").grid(row=4, column=0, sticky="nw", pady=(8, 3), padx=(0, 6))
        lights = ttk.Frame(frm)
        lights.grid(row=4, column=1, sticky="w", pady=(8, 3))
        _cdoors = _cfg.get("doors")
        light_vars = []
        for i, name in enumerate(M.DOOR_SLOT_NAME):
            dv = M.DOOR_STATE_NAME[M.NO_PASS]
            if isinstance(_cdoors, (list, tuple)) and i < len(_cdoors) \
                    and _cdoors[i] in light_vals:
                dv = _cdoors[i]
            var = tk.StringVar(value=dv)
            ttk.Label(lights, text=name).pack(side="left", padx=(0 if i == 0 else 10, 2))
            ttk.Combobox(lights, textvariable=var, values=light_vals, state="readonly",
                         width=10).pack(side="left")
            light_vars.append(var)

        treasure = combo(5, "宝物线索", TREASURE_VALS,
                         _pick("treasure", TREASURE_VALS, TREASURE_VALS[0]))
        ttk.Label(frm, text="（回程走哪个门区入口不用选：由上面 4 格门灯自动推；"
                            "这些选择会记住，随「保存布局」一起存，重启也在）",
                  foreground="#666666").grid(row=6, column=0, columnspan=2,
                                             sticky="w", pady=(6, 0))

        def light_state(i):
            for s in M.DOOR_STATE_ORDER:
                if M.DOOR_STATE_NAME[s] == light_vars[i].get():
                    return s
            return M.NO_PASS

        def run():
            doors = [light_state(i) for i in range(4)]
            tsel = treasure.get()
            tval = int(tsel.split(" ")[0]) if tsel != "未定" else None
            clue = {"不指定（固件不改路线）": None, "线索=0：跳过 P3、P4": 0,
                    "线索=3：经过 P3": 3, "线索=4：经过 P4": 4}[p1clue.get()]
            ab = (int(stg.get().split(",")[0].split("=")[1]),
                  int(stg.get().split(",")[1].split("：")[0].split("=")[1]))
            # 记住这次的选择（下次打开就是这套；也会随「保存布局」写进 constraints）
            self.clue_route_cfg = {
                "stage": stage.get(),
                "p1clue": p1clue.get(),
                "stg": stg.get(),
                "doors": [light_vars[i].get() for i in range(4)],
                "treasure": tsel,
            }
            sections, canvas, err = self._clue_route_sections(
                stage.get(), clue, ab, doors, tval, self.cost_mode.get())
            if err:
                self._write_route_report(sections)      # 先把已经算出来的段落给出来
                messagebox.showerror(err[0], err[1], parent=dlg)
                return
            if canvas:
                self.route = canvas
                self.redraw()
            else:
                self.route = []
                self.route_split = None
                self.redraw()
            self._write_route_report(sections)
            self.status("已按固件分支显示路线（%s）" % stage.get().split("（")[0])
            dlg.destroy()

        buttons = ttk.Frame(frm)
        buttons.grid(row=8, column=0, columnspan=2, sticky="w", pady=(14, 0))
        ttk.Button(buttons, text="显示路线", command=run).pack(side="left")
        ttk.Button(buttons, text="取消", command=dlg.destroy).pack(side="left", padx=8)

    def _round2_route_sections(self, doors, treasure, cruise=None, mode="full"):
        """第二轮（get_newroute）路线：**纯计算，不碰 UI**（对话框与冒烟测试共用）。

        doors=[D2,D3,D4,D5]；treasure=宝物编号或 None；cruise=自定义巡游顺序或 None（固件默认）。
        返回 (sections, flat_nodes, split_idx, err)：split_idx = 回程起始下标（画布分色用）。
        """
        wp, why = M.round2_waypoints(doors, treasure if treasure is not None else 0, cruise)
        if wp is None:
            return [], [], None, ("固件会停车", str(why))
        order = [w for w in wp if w in ROUND2_CRUISE_PF]
        k = max(i for i, name in enumerate(wp) if name in ROUND2_CRUISE_PF)
        # 去程 = 起步 → 巡游末站；回程 = 巡游末站 → P2。
        # 两段分开规划再拼 == 整条 wp 一次规划（plan_route 就是逐跳最短路），
        # 但只有这样才知道 split 落在哪 —— 画布要靠它分色。
        out, why1 = self.model.plan_route(wp[:k + 1], mode)
        if out is None:
            return [], [], None, ("规划失败", "去程（到 %s）：%s" % (order[-1], why1))
        back, why2 = self.model.plan_route(wp[k:], mode)
        if back is None:
            return [], [], None, ("规划失败", "回程（从 %s）：%s" % (order[-1], why2))
        flat = self._join(out, back)
        split = len(out) - 1
        lines = self._fmt_planned(wp, flat, None)
        lines.append("去程（蓝）%d 跳 = 起步 → 巡游末站 %s；回程（青绿）%d 跳 = %s → P2"
                     % (split, order[-1], len(flat) - 1 - split, order[-1]))
        if treasure == 6:
            lines.append("巡游方向：宝物 = 6 ⇒ 固件反向（逆时针）")
        elif treasure is None:
            lines.append("宝物线索「未定」⇒ 巡游方向按顺时针（固件读到宝物编号前不反向）")
        fw = M.round2_waypoints(doors, treasure if treasure is not None else 0)[0]
        fw_order = [w for w in (fw or []) if w in ROUND2_CRUISE_PF]
        if cruise is not None and fw_order and fw_order != order:
            lines.append("⚠ 巡游顺序 %s 与固件 get_newroute() 写死的 %s 不同：这里只改软件里的"
                         "显示/规划；要让车按这个顺序跑，得同步改 Mission/mission_planner.c 的 wp。"
                         % ("→".join(order), "→".join(fw_order)))
        return ([("第二轮·完整路线 / get_newroute()（巡游 %s）" % "→".join(order), lines)],
                flat, split, None)

    def plan_round2_route_dialog(self):
        """第二轮（get_newroute）：查看固件默认路线 + 改巡游顺序。

        平台交换（⇄）之后二轮平台的走法经常要跟着换，所以顺序做成可改的；
        门区节点仍按固件规则（4 盏灯）自动取。
        ⚠️ 只动软件里的显示/规划：要让车按新顺序跑，还得同步改 Mission/mission_planner.c。
        """
        dlg = tk.Toplevel(self)
        dlg.title("第二轮路线（get_newroute）：查看 + 改巡游顺序")
        dlg.geometry("700x330")
        dlg.transient(self)
        frm = ttk.Frame(dlg, padding=12)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, wraplength=660, justify="left",
                  text="第二轮 = get_newroute()：N2→P1→P3→P4→N5 → 过门 → 东区巡游 4 个平台"
                       " → 回程 → P2。门区节点按固件规则（4 盏灯）自动取；巡游顺序可以改"
                       " —— 平台交换（⇄）之后二轮平台的走法经常要跟着换。"
                       "结果显示在主界面路线框 + 画布（去程蓝 / 回程青绿；"
                       "画布叠在一起看不清时用「画布显示」单独看一段）。").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

        _cfg = dict(self.round2_cfg or {})
        light_vals = [M.DOOR_STATE_NAME[s] for s in M.DOOR_STATE_ORDER]

        ttk.Label(frm, text="门灯状态").grid(row=1, column=0, sticky="nw",
                                             pady=(2, 3), padx=(0, 6))
        lights = ttk.Frame(frm)
        lights.grid(row=1, column=1, sticky="w", pady=(2, 3))
        _cdoors = _cfg.get("doors")
        light_vars = []
        for i, name in enumerate(M.DOOR_SLOT_NAME):
            dv = M.DOOR_STATE_NAME[M.NO_PASS]
            if isinstance(_cdoors, (list, tuple)) and i < len(_cdoors) \
                    and _cdoors[i] in light_vals:
                dv = _cdoors[i]
            var = tk.StringVar(value=dv)
            ttk.Label(lights, text=name).pack(side="left", padx=(0 if i == 0 else 10, 2))
            ttk.Combobox(lights, textvariable=var, values=light_vals, state="readonly",
                         width=10).pack(side="left")
            light_vars.append(var)

        TREASURE_VALS = ["未定", "2 · P1", "3 · P3", "4 · P4", "5 · P5", "6 · P6"]
        _ctre = _cfg.get("treasure")
        tsel = tk.StringVar(value=_ctre if _ctre in TREASURE_VALS else TREASURE_VALS[0])
        ttk.Label(frm, text="宝物线索").grid(row=2, column=0, sticky="w", pady=3, padx=(0, 6))
        ttk.Combobox(frm, textvariable=tsel, values=TREASURE_VALS, state="readonly",
                     width=36).grid(row=2, column=1, sticky="w", pady=3)

        ttk.Label(frm, text="巡游顺序").grid(row=3, column=0, sticky="nw",
                                             pady=(6, 3), padx=(0, 6))
        ofrm = ttk.Frame(frm)
        ofrm.grid(row=3, column=1, sticky="w", pady=(6, 3))
        _corder = _cfg.get("order")
        order_vars, order_cbs = [], []
        for i in range(4):
            dv = ROUND2_CRUISE_PF[i]
            if isinstance(_corder, (list, tuple)) and len(_corder) == 4 \
                    and _corder[i] in ROUND2_CRUISE_PF:
                dv = _corder[i]
            var = tk.StringVar(value=dv)
            ttk.Label(ofrm, text="第%d站" % (i + 1)).pack(side="left",
                                                          padx=(0 if i == 0 else 8, 2))
            cb = ttk.Combobox(ofrm, textvariable=var, values=list(ROUND2_CRUISE_PF),
                              state="readonly", width=5)
            cb.pack(side="left")
            order_vars.append(var)
            order_cbs.append(cb)

        auto_var = tk.BooleanVar(value=bool(_cfg.get("auto", True)))
        ttk.Checkbutton(frm, text="按固件规则自动（宝物 = 6 时反向 ⇒ P6→P8→P7→P5）",
                        variable=auto_var).grid(row=4, column=1, sticky="w", pady=(0, 3))

        def treasure_num():
            s = tsel.get()
            return int(s.split(" ")[0]) if s != "未定" else None

        def on_auto(*_a):
            if auto_var.get():
                for v, p in zip(order_vars, M.round2_firmware_cruise(treasure_num() or 0)):
                    v.set(p)
            for cb in order_cbs:
                cb.configure(state="disabled" if auto_var.get() else "readonly")

        tsel.trace_add("write", on_auto)
        auto_var.trace_add("write", on_auto)
        on_auto()

        def light_state(i):
            for s in M.DOOR_STATE_ORDER:
                if M.DOOR_STATE_NAME[s] == light_vars[i].get():
                    return s
            return M.NO_PASS

        def run():
            doors = [light_state(i) for i in range(4)]
            if len({v.get() for v in order_vars}) != 4:
                messagebox.showerror("巡游顺序不合法", "4 个平台必须各站一次（不能重复）：%s"
                                     % "→".join(v.get() for v in order_vars), parent=dlg)
                return
            cruise = None if auto_var.get() else [v.get() for v in order_vars]
            self.round2_cfg = {"doors": [light_vars[i].get() for i in range(4)],
                               "treasure": tsel.get(),
                               "order": [v.get() for v in order_vars],
                               "auto": bool(auto_var.get())}
            secs, flat, split, err = self._round2_route_sections(
                doors, treasure_num(), cruise, self.cost_mode.get())
            if err:
                self._write_route_report(secs)
                messagebox.showerror(err[0], err[1], parent=dlg)
                return
            self.route = flat
            self.route_split = split
            self._write_route_report(secs)
            self.redraw()
            self.status("第二轮路线已显示（巡游 %s：去程 %d 跳 / 回程 %d 跳）"
                        % ("→".join(self.round2_cfg["order"]),
                           split, len(flat) - 1 - split))

        btns = ttk.Frame(frm)
        btns.grid(row=5, column=0, columnspan=2, sticky="w", pady=(14, 0))
        ttk.Button(btns, text="显示路线", command=run).pack(side="left")
        ttk.Button(btns, text="关闭", command=dlg.destroy).pack(side="left", padx=8)
        ttk.Label(btns, text="⚠ 只改软件里的显示；要让车按新顺序跑，需同步改固件 wp",
                  foreground="#a04000").pack(side="left", padx=10)

    def show_route_text(self, path):
        t = self.txt_route
        t.delete("1.0", "end")
        t.insert("end", "必经点: %s\n\n" % " -> ".join(self.waypoints))
        t.insert("end", "路线（%d 跳）:\n" % (len(path) - 1))
        t.insert("end", " -> ".join(path) + "\n\n")
        t.insert("end", "route[] 数组:\n")
        t.insert("end", self.model.export_route_array(path) + "\n\n")
        # 逐段明细
        t.insert("end", "逐段明细:\n")
        for i in range(len(path) - 1):
            e = self.model.edge(path[i], path[i + 1])
            if e:
                a, s = self.model.ang(e), self.model.step(e)
                t.insert("end", "  %-6s -> %-6s  %6.1f°  %6s cm  %-8s %s\n" % (
                    path[i], path[i + 1], a if a is not None else 0,
                    "%.0f" % s if s is not None else "?", e.func, e.flag))
            else:
                t.insert("end", "  %-6s -> %-6s  ⚠ 无边！\n" % (path[i], path[i + 1]))
        t.insert("end", "\n⚠️ 与固件一致性：固件起点=Dijkstra 的 wp[0]，"
                        "陀螺仪参考角 = 第一跳那条边的 angle。\n")
        # 告警：180°掉头 / 经过门
        for i in range(1, len(path) - 1):
            e1 = self.model.edge(path[i - 1], path[i])
            e2 = self.model.edge(path[i], path[i + 1])
            if not e1 or not e2:
                continue
            a1, a2 = self.model.ang(e1), self.model.ang(e2)
            if a1 is None or a2 is None:
                continue
            d = (a2 - a1) % 360
            if d > 180:
                d -= 360
            if abs(abs(d) - 180) < 3:
                t.insert("end", "  ⚠ %s 处 180° 原路折返（补偿表里通常没有这条，且转向由噪声决定）\n"
                         % path[i])
            if e2.func == "DOOR":
                t.insert("end", "  ⚠ %s -> %s 是 DOOR 边：到点后 door() 会清空 route[] 并跑门逻辑\n"
                         % (path[i], path[i + 1]))

    def clear_route(self):
        self.route = []
        self.route_split = None
        self.txt_route.delete("1.0", "end")
        self.redraw()

    def _route_view_changed(self):
        """「画布显示」换档：不用重新规划，重画一次即可。"""
        self.redraw()
        if self.route_view.get() != ROUTE_VIEW_MODES[0] and not self._route_split_ok():
            self.status("当前路线没有去程/回程分色（只有一条），「%s」画不出线；"
                        "「线索路线…/二轮路线…」的完整路线才有分色" % self.route_view.get())
        else:
            self.status("画布显示：%s" % self.route_view.get())

    def copy_route_array(self):
        if not self.route:
            self.status("还没有规划出路线")
            return
        self._copy(self.model.export_route_array(self.route))

    def copy_debug_macros(self):
        if len(self.waypoints) < 2:
            return
        first = self.waypoints[0]
        end = self.waypoints[-1]
        via = self.waypoints[1] if len(self.waypoints) == 3 else "0"
        self._copy(self.model.export_debug_macros(first, via, end))

    def _copy(self, text):
        self.clipboard_clear()
        self.clipboard_append(text)
        self.status("已复制到剪贴板")

    # ================================================================ 导出
    def export_c_dialog(self):
        dlg = tk.Toplevel(self)
        dlg.title("导出 C 代码")
        dlg.geometry("1000x720")
        nb = ttk.Notebook(dlg)
        nb.pack(fill="both", expand=True, padx=6, pady=6)
        blobs = {
            "NavEdgeTbl（整段）": self.model.export_edge_table(),
            "边表表体（只粘表格）": self.model.export_edges_only(),
            "enum MapNode": self.model.export_enum(),
            "NAV_EDGE_COUNT": self.model.export_nav_edge_count() + "\n",
            "求值自检（宏是否都能算）": self.model.export_eval_report(),
        }
        texts = {}
        for name, blob in blobs.items():
            fr = ttk.Frame(nb)
            nb.add(fr, text=name)
            txt = tk.Text(fr, wrap="none")
            txt.insert("1.0", blob)
            ys = ttk.Scrollbar(fr, orient="vertical", command=txt.yview)
            xs = ttk.Scrollbar(fr, orient="horizontal", command=txt.xview)
            txt.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
            txt.grid(row=0, column=0, sticky="nsew")
            ys.grid(row=0, column=1, sticky="ns")
            xs.grid(row=1, column=0, sticky="we")
            fr.rowconfigure(0, weight=1)
            fr.columnconfigure(0, weight=1)
            texts[name] = txt

        brow = ttk.Frame(dlg)
        brow.pack(fill="x", padx=6, pady=(0, 6))

        def copy_current():
            name = nb.tab(nb.select(), "text")
            self._copy(texts[name].get("1.0", "end").rstrip("\n") + "\n")

        def save_all():
            outdir = filedialog.askdirectory(title="选择导出目录", parent=dlg)
            if not outdir:
                return
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            files = {
                "NavEdgeTbl_%s.c" % ts: blobs["NavEdgeTbl（整段）"],
                "enum_MapNode_%s.txt" % ts: blobs["enum MapNode"],
                "NAV_EDGE_COUNT_%s.txt" % ts: blobs["NAV_EDGE_COUNT"],
            }
            for fn, blob in files.items():
                with open(os.path.join(outdir, fn), "w", encoding="utf-8") as fh:
                    fh.write(blob)
            with open(os.path.join(outdir, "map_%s.json" % ts), "w", encoding="utf-8") as fh:
                fh.write(self.model.to_json())
            self.status("已导出到 %s" % outdir)
            messagebox.showinfo("导出完成", "已写入：\n" + "\n".join(files), parent=dlg)

        ttk.Button(brow, text="复制当前页", command=copy_current).pack(side="left")
        ttk.Button(brow, text="全部另存到目录…", command=save_all).pack(side="left", padx=6)
        ttk.Button(brow, text="关闭", command=dlg.destroy).pack(side="right")
        nb.select(0)

    def patch_firmware_dialog(self):
        """把当前模型写回 map_message.c / map.h（先备份）。显式确认才动。"""
        msg = ("即将把当前模型写回固件源码：\n\n"
               "  Navigation/map_message.c  <- NavEdgeTbl[]（整段替换）\n"
               "  Navigation/map.h          <- enum MapNode\n"
               "  Navigation/map_message.h  <- NAV_EDGE_COUNT\n\n"
               "⚠️ 两个文件都会先自动备份到 scripts/map_editor/backups/。\n"
               "⚠️ 你现在的工作树里本来就有未提交改动，写回后请用 git diff 复核。\n\n"
               "确认继续？")
        if not messagebox.askyesno("写回固件", msg, parent=self, icon="warning"):
            return
        issues = self.model.validate()
        errs = [m for lv, m in issues if lv == "error"]
        if errs:
            messagebox.showerror("有致命错误，已中止",
                                 "校验发现 error，先修好再写回：\n\n" + "\n".join(errs[:10]),
                                 parent=self)
            return
        try:
            backup_dir = os.path.join(HERE, "backups")
            os.makedirs(backup_dir, exist_ok=True)
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            results = []
            results.append(self._patch_edge_table(backup_dir, ts))
            results.append(self._patch_enum(backup_dir, ts))
            results.append(self._patch_count(backup_dir, ts))
            messagebox.showinfo("写回完成",
                                "已写回：\n" + "\n".join(results)
                                + "\n\n备份目录：\n" + backup_dir, parent=self)
            self.status("已写回固件源码（备份在 %s）" % backup_dir)
        except Exception as ex:
            messagebox.showerror("写回失败", "%s" % ex, parent=self)

    def edit_macros_dialog(self):
        """编辑当前模型中的 config.h 宏，并可显式写回 config.h。"""
        names = sorted(self.model.macros)
        if not names:
            messagebox.showinfo("宏定义", "当前没有解析到可编辑的宏。", parent=self)
            return
        dlg = tk.Toplevel(self)
        dlg.title("编辑 config.h 宏定义")
        dlg.geometry("760x620")
        dlg.transient(self)

        outer = ttk.Frame(dlg, padding=8)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="“读取源码”=重新从 config.h 读取（丢弃当前编辑）；修改后先”应用到当前模型“预览，确认无误再”写回 config.h“。").pack(
            anchor="w", pady=(0, 6))
        body = ttk.Frame(outer)
        body.pack(fill="both", expand=True)
        canvas = tk.Canvas(body, highlightthickness=0)
        scroll = ttk.Scrollbar(body, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        form = ttk.Frame(canvas)
        win = canvas.create_window((0, 0), window=form, anchor="nw")
        form.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win, width=e.width))

        entries = {}

        def rebuild_form():
            nonlocal names
            names = sorted(self.model.macros)
            for w in form.winfo_children():
                w.destroy()
            entries.clear()
            for row, name in enumerate(names):
                ttk.Label(form, text=name, width=30).grid(row=row, column=0, sticky="w", padx=(2, 8), pady=2)
                ent = ttk.Entry(form, width=48)
                ent.insert(0, str(self.model.macros[name]))
                ent.grid(row=row, column=1, sticky="ew", pady=2)
                entries[name] = ent

        def read_source():
            try:
                macros, field_name = M.parse_config_macros()
            except Exception as ex:
                messagebox.showerror("读取 config.h 失败", str(ex), parent=dlg)
                return
            self.model.macros = dict(macros)
            self.model.field_name = field_name
            self.field_var.set("比赛场地" if field_name == "FIELD_COMP" else "学校场地")
            rebuild_form()
            self.model.dirty = True
            self.refresh_all()
            self.status("已从 config.h 重新读取 %d 个宏（当前未保存的编辑已丢弃）" % len(macros))

        rebuild_form()
        form.columnconfigure(1, weight=1)

        def collect():
            return {name: ent.get().strip() for name, ent in entries.items()}

        def apply_model():
            values = collect()
            old = dict(self.model.macros)
            self.model.macros.update(values)
            bad = []
            for edge in self.model.edges:
                if self.model.ang(edge) is None:
                    bad.append("%s->%s angle=%s" % (edge.frm, edge.to, edge.angle))
                if self.model.step(edge) is None:
                    bad.append("%s->%s step=%s" % (edge.frm, edge.to, edge.step))
            if bad:
                self.model.macros = old
                messagebox.showerror("宏表达式无效", "以下边无法求值：\n\n" + "\n".join(bad[:12]), parent=dlg)
                return False
            self.model.dirty = True
            self.refresh_all()
            self.status("宏已应用到当前模型（尚未写回 config.h）")
            return True

        def write_config():
            if not apply_model():
                return
            path = M.PATH_CONFIG
            try:
                source = open(path, encoding="utf-8").read()
                backup_dir = os.path.join(HERE, "backups")
                os.makedirs(backup_dir, exist_ok=True)
                ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                self._backup(path, backup_dir, ts)
                changed = 0
                for name, value in collect().items():
                    source, count = self._rewrite_config_macro(source, name, value)
                    changed += count
                open(path, "w", encoding="utf-8", newline="").write(source)
                dlg.destroy()
                self.status("已写回 %d 个宏到 config.h（备份：%s）" % (changed, backup_dir))
            except Exception as ex:
                messagebox.showerror("写回 config.h 失败", str(ex), parent=dlg)

        buttons = ttk.Frame(outer)
        buttons.pack(fill="x", pady=(8, 0))
        ttk.Button(buttons, text="读取源码", command=read_source).pack(side="left")
        ttk.Button(buttons, text="应用到当前模型", command=apply_model).pack(side="left", padx=6)
        ttk.Button(buttons, text="写回 config.h", command=write_config).pack(side="left", padx=6)
        ttk.Button(buttons, text="取消", command=dlg.destroy).pack(side="right")

    def report_source_diff(self):
        """只读比较当前内存模型与固件源码，不写回任何文件。"""
        try:
            source_nodes = M.parse_map_enum()
            source_names = [row[0] for row in source_nodes]
            current_names = self.model.names()
            edge_problems = self.model.roundtrip_report()
            source_rows, declared_count = M.parse_edge_table()
        except Exception as ex:
            messagebox.showerror("读取差异失败", "%s" % ex, parent=self)
            return

        added_nodes = [name for name in current_names if name not in source_names]
        removed_nodes = [name for name in source_names if name not in current_names]
        order_changed = (not added_nodes and not removed_nodes
                         and current_names != source_names)
        lines = [
            "当前编辑器模型 vs 固件源码",
            "（本窗口只读，不会写回文件）",
            "",
            "节点：当前 %d，源码 %d" % (len(current_names), len(source_names)),
            "边：当前 %d，源码 %d，源码 NAV_EDGE_COUNT=%s"
            % (len(self.model.edges), len(source_rows), declared_count),
            "布局/属性是否有未保存改动：%s" % ("是" if self.model.dirty else "否"),
        ]
        if added_nodes:
            lines.append("新增节点：%s" % ", ".join(added_nodes))
        if removed_nodes:
            lines.append("删除节点：%s" % ", ".join(removed_nodes))
        if order_changed:
            lines.append("节点顺序：有变化（enum 顺序会影响节点索引）")
        lines.append("")
        if edge_problems:
            lines.append("边表差异：%d 项" % len(edge_problems))
            lines.extend("  - " + item for item in edge_problems)
        else:
            lines.append("边表差异：无")
        if not added_nodes and not removed_nodes and not order_changed and not edge_problems \
                and len(self.model.edges) == len(source_rows):
            lines.extend(["", "当前模型与源码内容一致。"])

        dlg = tk.Toplevel(self)
        dlg.title("当前模型与固件源码的差异")
        dlg.geometry("860x620")
        text = tk.Text(dlg, wrap="none")
        text.insert("1.0", "\n".join(lines))
        text.configure(state="disabled")
        text.pack(fill="both", expand=True, padx=8, pady=8)
        ttk.Button(dlg, text="关闭", command=dlg.destroy).pack(pady=(0, 8))
        self.status("已生成代码差异报告：%d 项边表差异" % len(edge_problems))

    def _backup(self, path, backup_dir, ts):
        if os.path.isfile(path):
            dst = os.path.join(backup_dir, "%s.%s.bak" % (os.path.basename(path), ts))
            with open(path, encoding="utf-8") as a:
                data = a.read()
            with open(dst, "w", encoding="utf-8") as b:
                b.write(data)
            return dst
        return None

    @staticmethod
    def _splice_edge_table(src, block):
        """把导出块替换进 map_message.c 源码里（**纯函数**，便于测试）。

        ⚠️ 踩过的坑：`export_edge_table(with_header=False)` 的输出**自带尾部**
        （`};` + 编译期检查 typedef + "已移至" 说明注释），而原文件在 `};` 之后
        **本来就有那一段**。早期直接整块拼接 ⇒ **`NavEdgeTbl_size_check` 变成两份**，
        而且**每写回一次就多一份**（实测：写回前备份 1 份 → 写回后 2 份）。
        所以这里只取到表体结束的 `};` 为止，尾部一律沿用原文件。
        """
        m = re.search(r"(const\s+NavEdge\s+NavEdgeTbl\s*\[[^\]]*\]\s*=\s*\{)", src)
        if not m:
            raise RuntimeError("在 map_message.c 里找不到 NavEdgeTbl[] 起始位置")
        start = m.start(1)
        end = src.index("};", m.end()) + 2          # 原文件表体的收尾
        cut = block.index("};") + 2                 # 导出块只取到表体收尾
        return src[:start] + block[:cut] + src[end:]

    @staticmethod
    def _rewrite_config_macro(src, name, value):
        """把 config.h 里某个 `#define` 的值换掉，**保留行尾注释**（纯函数，便于测试）。

        ⚠️ 踩过的坑：早期直接用"define 名 + 行内任意内容 + 换行"三段替换，
        中间那段是非贪婪但**一路吃到行尾**的，于是
        `#define VIA_POINT P3 /* 调试途径点…` 这一行的 `/*` 连同注释被整段吃掉，
        而注释的后续行（含收尾 `*/`）还在 ⇒ C 编译器把注释正文当代码解析，
        报出 `identifier "注意" is undefined` 和一串级联错误（2026-09-15 实测编挂整份工程）。
        所以这里把**行尾注释**（`/* … */` 或 `// …`，含多行注释的 `/*` 开头）
        单独分成一组原样保留。返回 (新源码, 替换处数)。
        """
        pattern = re.compile(r"^(\s*#define\s+" + re.escape(name) + r"\s+)" +
                             r"([^\r\n]*?)" +
                             r"([ \t]*(?:/\*|//)[^\r\n]*)?" +
                             r"(\r?\n|$)", re.M)
        return pattern.subn(lambda m: m.group(1) + value + (m.group(3) or "") + m.group(4),
                            src, count=1)

    def _patch_edge_table(self, backup_dir, ts):
        path = M.PATH_EDGE_C
        src = open(path, encoding="utf-8").read()
        new_block = self.model.export_edge_table(with_header=False)
        new_src = self._splice_edge_table(src, new_block)
        self._backup(path, backup_dir, ts)
        open(path, "w", encoding="utf-8", newline="").write(new_src)
        return "Navigation/map_message.c（%d 条边）" % len(self.model.edges)

    def _patch_enum(self, backup_dir, ts):
        path = M.PATH_MAP_H
        src = open(path, encoding="utf-8").read()
        m = re.search(r"enum\s+MapNode\s*\{.*?\}\s*;", src, re.S)
        if not m:
            raise RuntimeError("在 map.h 里找不到 enum MapNode")
        new_src = src[:m.start()] + self.model.export_enum() + src[m.end():]
        # 导出里第一行缩进与注释风格对齐原文件
        self._backup(path, backup_dir, ts)
        open(path, "w", encoding="utf-8", newline="").write(new_src)
        return "Navigation/map.h（%d 个节点）" % len(self.model.nodes)

    def _patch_count(self, backup_dir, ts):
        path = M.PATH_MSG_H
        src = open(path, encoding="utf-8").read()
        if not re.search(r"#define\s+NAV_EDGE_COUNT\s+\d+", src):
            raise RuntimeError("在 map_message.h 里找不到 NAV_EDGE_COUNT")
        new_src = re.sub(r"#define\s+NAV_EDGE_COUNT\s+\d+",
                         "#define NAV_EDGE_COUNT %d" % len(self.model.edges), src)
        self._backup(path, backup_dir, ts)
        open(path, "w", encoding="utf-8", newline="").write(new_src)
        return "Navigation/map_message.h（NAV_EDGE_COUNT=%d）" % len(self.model.edges)

    # ================================================================ 转弯前补偿（map.c）
    def _patch_turn_tables(self, backup_dir, ts):
        """把两张补偿表 + 公式参数写回 `Navigation/map.c`（先备份）。

        ⚠️ **"没改就不重排格式"**：表项与源码逐项相同 ⇒ 整段不动。否则缩进/空格一旦被
        归一化，每点一次写回都会产生一堆无意义 diff（本工程工作树常年带未提交改动，
        这种噪声会让 `git diff` 复核失效）。只有新增/编辑表项时才整段重排。
        """
        path = M.PATH_MAP_C
        src = open(path, encoding="utf-8").read()
        src_turn = M.parse_turn_tables()
        cur = self.model.turn
        same = (M.turn_rows_equal(src_turn["stop"], cur.get("stop")) and
                M.turn_rows_equal(src_turn["gyro"], cur.get("gyro")))
        new_src = src if same else self.model.splice_turn_tables(src)
        n_const = 0
        for name, val in (cur.get("consts") or {}).items():
            old = src_turn["consts"].get(name)
            if old is None or abs(float(old) - float(val)) > 1e-9:
                new_src, n = self._rewrite_config_macro(new_src, name, "( %.1ff)" % float(val))
                n_const += n
        if new_src == src and not n_const:
            return "Navigation/map.c：无改动（表项与公式参数都与源码一致）"
        self._backup(path, backup_dir, ts)
        open(path, "w", encoding="utf-8", newline="").write(new_src)
        return ("Navigation/map.c（表1 %d 条 / 表2 %d 条 / 公式参数改了 %d 个）"
                % (len(cur.get("stop") or []), len(cur.get("gyro") or []), n_const))

    def turn_comp_dialog(self):
        """「转弯前补偿」可视化编辑器 —— 把 map.c 里两张**硬编码表**搬进界面。

        对应固件（`Navigation/map.c`，原理见 `项目讲解文档/project_reference.md` §14）：
          ① `kTurnTbl[]`                       停车原地转分支（走补偿距离→停车→原地转）
          ② `GetForwardDistanceBeforeGyroTurn` 陀螺不停车转分支
          ③ `TURN_L_PIVOT / TURN_GATE_CM / TURN_D_*`（Tier2 公式）与 config.h 的 `TURN_CALC_ENABLE`

        四个页签：两张表可增删改、覆盖总览（地图里每个转弯当前生效多少 cm）、公式参数。
        改完必须点「写回 map.c」才动源码（自动备份）；只改内存随时可撤销。
        """
        old = getattr(self, "_turn_dlg", None)
        if old is not None and old.winfo_exists():
            old.lift()
            old.focus_set()
            return
        dlg = tk.Toplevel(self)
        self._turn_dlg = dlg
        dlg.title("转弯前补偿（Navigation/map.c）")
        dlg.geometry("1060x720")
        dlg.transient(self)

        outer = ttk.Frame(dlg, padding=8)
        outer.pack(fill="both", expand=True)
        head = ttk.Label(outer, text="", justify="left", foreground="#0d47a1")
        head.pack(anchor="w", pady=(0, 6))

        nb = ttk.Notebook(outer)
        nb.pack(fill="both", expand=True)
        tab_stop = ttk.Frame(nb)
        tab_gyro = ttk.Frame(nb)
        tab_cov = ttk.Frame(nb)
        tab_cst = ttk.Frame(nb)
        nb.add(tab_stop, text="① 停车原地转（kTurnTbl）")
        nb.add(tab_gyro, text="② 陀螺不停车转（if 链）")
        nb.add(tab_cov, text="③ 覆盖总览（地图里全部转弯）")
        nb.add(tab_cst, text="④ 公式参数 / 开关")
        self._turn_nb = nb
        self._turn_head = head

        def rows_of(table):
            return self.model.turn.setdefault(table, [])

        def refresh_head():
            cov = self.model.turn_coverage()
            self._turn_cov = cov
            s = cov["stats"]
            head.configure(text=(
                "map.c 里两张表：表1 停车转 %d 条 / 表2 陀螺转 %d 条　｜　"
                "「能算就算」Tier2：%s　｜　L=%.1fcm 闸门=%.1fcm\n"
                "地图里共 %d 个转弯组合：直行 %d / 停车转 %d / 陀螺转 %d"
                "（停车转里实测 %d、公式 %d、吃默认 19 的 %d；陀螺转里实测 %d、默认 0 的 %d）"
                % (len(rows_of("stop")), len(rows_of("gyro")),
                   "开" if self.model.turn.get("calc_enable") else
                   ("关" if self.model.turn.get("calc_enable") is not None else "?"),
                   float(self.model.turn["consts"].get("TURN_L_PIVOT", 19.0)),
                   float(self.model.turn["consts"].get("TURN_GATE_CM", 5.0)),
                   s["total"], s["straight"], s["stop"], s["gyro"],
                   s["stop_meas"], s["stop_calc"], s["stop_default"],
                   s["gyro_meas"], s["gyro_default"])))

        ST_COL = {"ok": TURN_OK_COLOR, "branch": TURN_DEAD_COLOR,
                  "edge": TURN_DEAD_COLOR, "unknown": TURN_WAIT_COLOR}

        # ------------------------------------------------ 通用：可编辑的表
        def build_table_tab(parent, table):
            hint = ("表里每一行 = 一个 (上一步, 当前, 下一步) 三元组 → 补偿距离(cm)。"
                    "「状态」列标出它**当前会不会生效**：绿色=生效、红色=死值、橙色=判不出来。"
                    "改完记得点「写回 map.c」。" if table == "stop" else
                "这是“陀螺不停车转”分支的 if 链（末尾固定 return 0）。"
                "同理，红字行表示当前地图根本不走这个组合。")
            ttk.Label(parent, text=hint, justify="left", foreground="#37474f").pack(
                anchor="w", padx=6, pady=(6, 2))
            cols = ("last", "now", "next", "dist", "delta", "branch", "status")
            tree = ttk.Treeview(parent, columns=cols, show="headings", height=13)
            for c, txt, w, anc in (("last", "上一步", 70, "center"), ("now", "当前", 70, "center"),
                                   ("next", "下一步", 70, "center"), ("dist", "补偿值cm", 80, "e"),
                                   ("delta", "转弯角", 76, "e"), ("branch", "分支", 92, "center"),
                                   ("status", "状态", 300, "w")):
                tree.heading(c, text=txt)
                tree.column(c, width=w, anchor=anc, stretch=(c == "status"))
            tree.pack(fill="both", expand=True, padx=6, pady=(0, 2))
            tree.tag_configure("ok", foreground=TURN_OK_COLOR)
            tree.tag_configure("dead", foreground=TURN_DEAD_COLOR)
            tree.tag_configure("wait", foreground=TURN_WAIT_COLOR)

            edit = ttk.Frame(parent)
            edit.pack(fill="x", padx=6, pady=(0, 2))
            ttk.Label(edit, text="上一步").pack(side="left")
            cb_last = ttk.Combobox(edit, width=6, values=self.model.names())
            cb_last.pack(side="left", padx=(2, 6))
            ttk.Label(edit, text="当前").pack(side="left")
            cb_now = ttk.Combobox(edit, width=6, values=self.model.names())
            cb_now.pack(side="left", padx=(2, 6))
            ttk.Label(edit, text="下一步").pack(side="left")
            cb_next = ttk.Combobox(edit, width=6, values=self.model.names())
            cb_next.pack(side="left", padx=(2, 6))
            ttk.Label(edit, text="值(cm)").pack(side="left")
            ent = ttk.Entry(edit, width=8)
            ent.pack(side="left", padx=(2, 8))

            state = {"sel": None, "iid": None}

            def fill_edit(row):
                for cb, key in ((cb_last, "last"), (cb_now, "now"), (cb_next, "next")):
                    cb.set(row.get(key, "") if row else "")
                ent.delete(0, "end")
                if row is not None:
                    ent.insert(0, "%g" % float(row.get("dist", 0)))

            def redraw(sync_pending=False):
                rows = rows_of(table)
                tree.delete(*tree.get_children())
                stat = self.model.turn_status(rows, table)
                for i, (r, (st, det)) in enumerate(zip(rows, stat)):
                    ie, oe = self.model.edge(r["last"], r["now"]), self.model.edge(r["now"], r["next"])
                    d = M.need2turn(self.model.ang(ie) if ie else None,
                                    self.model.ang(oe) if oe else None)
                    br = M.turn_branch(d, ie.flag if ie else "",
                                       ie.func if ie else "NONE")
                    tree.insert("", "end", iid=str(i), tags=(ST_COL.get(st, "wait"),),
                                values=(r["last"], r["now"], r["next"], "%g" % float(r["dist"]),
                                        "-" if d is None else "%+.1f°" % d,
                                        M.TURN_BRANCH_NAME.get(br, br), det))
                if state["iid"] is not None and tree.exists(state["iid"]):
                    tree.selection_set(state["iid"])
                if not sync_pending:
                    refresh_head()

            def on_select(_e=None):
                sel = tree.selection()
                if not sel:
                    return
                i = int(sel[0])
                rows = rows_of(table)
                if i >= len(rows):
                    return
                state["iid"] = str(i)
                fill_edit(rows[i])
                r = rows[i]
                self.turn_focus = (r["last"], r["now"], r["next"])
                self.redraw()

            def on_double(_e=None):
                """双击直接改值：选中行 → 只弹一个数字框（最常用操作，别让它点三下）。"""
                on_select()
                try:
                    cur = float(ent.get() or 0)
                except ValueError:
                    cur = 0.0
                v = simpledialog.askfloat("改补偿值", "该三元组的补偿距离（cm）：",
                                          initialvalue=cur, parent=dlg)
                if v is None:
                    return
                ent.delete(0, "end")
                ent.insert(0, "%g" % v)
                apply_row()

            def apply_row():
                r = {"last": cb_last.get().strip(), "now": cb_now.get().strip(),
                     "next": cb_next.get().strip()}
                if not (r["last"] and r["now"] and r["next"]):
                    messagebox.showwarning("参数不全", "三个节点都要选。", parent=dlg)
                    return
                try:
                    r["dist"] = float(ent.get().strip())
                except ValueError:
                    messagebox.showwarning("值不对", "补偿距离要填数字（cm）。", parent=dlg)
                    return
                rows = rows_of(table)
                sel = tree.selection()
                if state["iid"] is not None and sel and int(sel[0]) < len(rows):
                    rows[int(sel[0])] = r
                else:
                    rows.append(r)
                    state["iid"] = str(len(rows) - 1)
                self.model.dirty = True
                redraw()

            def add_row():
                rows_of(table).append({"last": cb_last.get().strip() or self.model.names()[0],
                                       "now": cb_now.get().strip() or self.model.names()[0],
                                       "next": cb_next.get().strip() or self.model.names()[0],
                                       "dist": 0.0})
                state["iid"] = str(len(rows_of(table)) - 1)
                self.model.dirty = True
                redraw()

            def del_row():
                sel = tree.selection()
                if not sel:
                    return
                i = int(sel[0])
                if 0 <= i < len(rows_of(table)):
                    del rows_of(table)[i]
                state["iid"] = None
                self.model.dirty = True
                redraw()

            def move(delta):
                sel = tree.selection()
                if not sel:
                    return
                i, rows = int(sel[0]), rows_of(table)
                j = i + delta
                if 0 <= i < len(rows) and 0 <= j < len(rows):
                    rows[i], rows[j] = rows[j], rows[i]
                    state["iid"] = str(j)
                    self.model.dirty = True
                    redraw()

            def apply_to_canvas():
                on_select()

            btns = ttk.Frame(parent)
            btns.pack(fill="x", padx=6, pady=(0, 6))
            ttk.Button(btns, text="＋ 新增一行", command=add_row).pack(side="left")
            ttk.Button(btns, text="改这一行", command=apply_row).pack(side="left", padx=4)
            ttk.Button(btns, text="删除选中", command=del_row).pack(side="left", padx=4)
            ttk.Button(btns, text="↑", width=3, command=lambda: move(-1)).pack(side="left", padx=2)
            ttk.Button(btns, text="↓", width=3, command=lambda: move(1)).pack(side="left", padx=2)
            ttk.Button(btns, text="在画布上高亮", command=apply_to_canvas).pack(side="left", padx=4)
            self._turn_table_redraw[table] = redraw
            tree.bind("<<TreeviewSelect>>", on_select)
            tree.bind("<Double-1>", on_double)
            return tree

        self._turn_table_redraw = {}
        build_table_tab(tab_stop, "stop")
        build_table_tab(tab_gyro, "gyro")

        # ------------------------------------------------ ③ 覆盖总览
        ttk.Label(tab_cov, justify="left", foreground="#37474f", text=(
            "地图里**所有** (入边, 出边) 转弯组合，以及它当前实际生效的补偿值（单位 cm）。\n"
            "「来源」= 表1 实测 / Tier2 公式 / Tier3 默认 19 / 表2 实测 / 默认 0 —— "
            "橙色那些就是“没数据、只能吃默认值”的弯（占绝大多数）。"
            "点一行 → 画布上高亮这个弯。")).pack(anchor="w", padx=6, pady=(6, 2))
        covbar = ttk.Frame(tab_cov)
        covbar.pack(fill="x", padx=6)
        only_def = tk.BooleanVar(value=False)
        ttk.Checkbutton(covbar, text="只看“吃默认值/没数据”的", variable=only_def).pack(side="left")
        cov_stat = ttk.Label(covbar, text="", foreground="#0d47a1")
        cov_stat.pack(side="left", padx=10)
        ccols = ("last", "now", "next", "delta", "branch", "value", "source", "note")
        ctree = ttk.Treeview(tab_cov, columns=ccols, show="headings", height=15)
        for c, txt, w, anc in (("last", "上一步", 60, "center"), ("now", "当前", 60, "center"),
                               ("next", "下一步", 60, "center"), ("delta", "转弯角", 74, "e"),
                               ("branch", "分支", 90, "center"), ("value", "生效值cm", 74, "e"),
                               ("source", "来源", 100, "w"), ("note", "说明", 260, "w")):
            ctree.heading(c, text=txt)
            ctree.column(c, width=w, anchor=anc, stretch=(c == "note"))
        ctree.pack(fill="both", expand=True, padx=6, pady=(2, 6))
        ctree.tag_configure("wait", foreground=TURN_WAIT_COLOR)

        def redraw_cov():
            cov = getattr(self, "_turn_cov", None) or self.model.turn_coverage()
            ctree.delete(*ctree.get_children())
            rows = [r for r in cov["rows"]
                    if (not only_def.get()) or r["source"] in ("Tier3 默认 19", "默认 0",
                                                               "角度求不出（宏没定义）")]
            for i, r in enumerate(rows):
                val = "" if r["value"] is None else "%g" % r["value"]
                ctree.insert("", "end", iid=str(i),
                             tags=("wait",) if r["source"] in ("Tier3 默认 19", "默认 0") else (),
                             values=(r["last"], r["now"], r["next"],
                                     "-" if r["delta"] is None else "%+.1f°" % r["delta"],
                                     M.TURN_BRANCH_NAME.get(r["branch"], r["branch"]),
                                     val, r["source"], r["note"]))
            cov_stat.configure(text="显示 %d / %d 条" % (len(rows), cov["stats"]["total"]))
            self._turn_cov_rows = rows

        def on_cov_select(_e=None):
            sel = ctree.selection()
            if not sel:
                return
            r = self._turn_cov_rows[int(sel[0])]
            self.turn_focus = (r["last"], r["now"], r["next"])
            self.redraw()

        ctree.bind("<<TreeviewSelect>>", on_cov_select)
        only_def.trace_add("write", lambda *_a: redraw_cov())

        # ------------------------------------------------ ④ 公式参数 / 开关
        ttk.Label(tab_cst, justify="left", foreground="#37474f", text=(
            "「能算就算」Tier2 的公式：  Δ = TURN_L_PIVOT × (1 − cosφ) + d(判据)\n"
            "命中条件：入边 func ∈ {NONE, DOOR} 且 step ≥ 20cm 且 100° ≤ |转弯| < 178°；"
            "表1 里已有实测值且 |公式−实测| > 闸门 ⇒ 一律用实测（机制自保护）。\n"
            "⚠️ 各判据的 d 可信度差别极大（DLEFT 5/5 最可信；CLEFT 只 9 条里过 5 条），"
            "改之前先看 project_reference.md §14.3。")).pack(anchor="w", padx=6, pady=(6, 4))
        cform = ttk.Frame(tab_cst)
        cform.pack(fill="x", padx=6)
        const_entries = {}
        cnames = [("TURN_L_PIVOT", "旋转中心→传感器板中心 纵向距离 L"),
                  ("TURN_GATE_CM", "5cm 闸门：公式与实测差超过它就不用公式"),
                  ("TURN_D_CRIGHT", "判据 CRIGHT 的检测滞后 d"),
                  ("TURN_D_CLEFT", "判据 CLEFT 的检测滞后 d"),
                  ("TURN_D_DLEFT", "判据 DLEFT 的检测滞后 d"),
                  ("TURN_D_DEFAULT", "其它判据回退用的缺省 d")]
        for i, (name, desc) in enumerate(cnames):
            ttk.Label(cform, text=name, width=16).grid(row=i, column=0, sticky="w", pady=2)
            e = ttk.Entry(cform, width=10)
            e.insert(0, "%g" % float(self.model.turn["consts"].get(name, 0.0)))
            e.grid(row=i, column=1, sticky="w", pady=2)
            const_entries[name] = e
            ttk.Label(cform, text=desc).grid(row=i, column=2, sticky="w", padx=8)

        calc_var = tk.BooleanVar(value=bool(self.model.turn.get("calc_enable")))
        ttk.Checkbutton(cform, text="TURN_CALC_ENABLE（config.h）：启用“能算就算”Tier2 公式",
                        variable=calc_var).grid(row=len(cnames), column=0, columnspan=3,
                                                sticky="w", pady=(8, 2))

        def apply_consts():
            for name, e in const_entries.items():
                try:
                    self.model.turn["consts"][name] = float(e.get().strip())
                except ValueError:
                    messagebox.showwarning("值不对", "%s 要填数字。" % name, parent=dlg)
                    return
            self.model.turn["calc_enable"] = 1 if calc_var.get() else 0
            self.model.dirty = True
            refresh_head()
            redraw_cov()
            self.status("转弯补偿参数已记到当前模型（点「写回」才动源码）")

        def write_config_switch():
            path = M.PATH_CONFIG
            try:
                src = open(path, encoding="utf-8").read()
                new_src, n = self._rewrite_config_macro(
                    src, "TURN_CALC_ENABLE", "1" if calc_var.get() else "0")
                if not n:
                    messagebox.showwarning("没找到", "config.h 里没有 TURN_CALC_ENABLE。", parent=dlg)
                    return
                backup_dir = os.path.join(HERE, "backups")
                os.makedirs(backup_dir, exist_ok=True)
                ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                self._backup(path, backup_dir, ts)
                open(path, "w", encoding="utf-8", newline="").write(new_src)
                self.model.turn["calc_enable"] = 1 if calc_var.get() else 0
                refresh_head()
                redraw_cov()
                self.status("已写回 Mission/config.h（TURN_CALC_ENABLE=%d）" % int(calc_var.get()))
            except Exception as ex:                                # noqa: BLE001
                messagebox.showerror("写回失败", "%s" % ex, parent=dlg)

        cbtns = ttk.Frame(tab_cst)
        cbtns.pack(fill="x", padx=6, pady=8)
        ttk.Button(cbtns, text="应用到当前模型", command=apply_consts).pack(side="left")
        ttk.Button(cbtns, text="只把开关写回 config.h", command=write_config_switch).pack(
            side="left", padx=6)

        # ------------------------------------------------ 底部
        def reload_from_source():
            try:
                t = M.parse_turn_tables()
            except Exception as ex:                                # noqa: BLE001
                messagebox.showerror("重读失败", "%s" % ex, parent=dlg)
                return
            self.model.turn.update(t)
            self.model.turn["consts_src"] = dict(t["consts"])
            state_reset()
            self.status("已从 Navigation/map.c 重新读取转弯补偿表")

        def state_reset():
            for name, e in const_entries.items():
                e.delete(0, "end")
                e.insert(0, "%g" % float(self.model.turn["consts"].get(name, 0.0)))
            calc_var.set(bool(self.model.turn.get("calc_enable")))
            for redraw in self._turn_table_redraw.values():
                redraw()
            refresh_head()
            redraw_cov()

        def writeback():
            msg = ("即将把转弯补偿写回固件源码：\n\n"
                   "  Navigation/map.c  ← 表1 kTurnTbl[]（%d 条）\n"
                   "                    ← 表2 GetForwardDistanceBeforeGyroTurn（%d 条）\n"
                   "                    ← kTurnTbl_node_check 的节点号护栏（跟随表项重生成）\n"
                   "                    ← TURN_* 公式参数（只改真的变了的）\n\n"
                   "⚠️ 会先自动备份到 backups/。\n"
                   "⚠️ 若表项有改动，整段表会按统一格式重排（值不变，只是缩进归一化）。\n"
                   "⚠️ 工作树里本来就有未提交改动，写回后请用 git diff 复核。\n\n"
                   "确认继续？" % (len(rows_of("stop")), len(rows_of("gyro"))))
            if not messagebox.askyesno("写回 map.c", msg, parent=dlg, icon="warning"):
                return
            try:
                backup_dir = os.path.join(HERE, "backups")
                os.makedirs(backup_dir, exist_ok=True)
                ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                res = self._patch_turn_tables(backup_dir, ts)
                messagebox.showinfo("写回完成", "已写回：\n" + res + "\n\n备份目录：\n" + backup_dir,
                                    parent=dlg)
                self.status("转弯补偿已写回 " + res)
            except Exception as ex:                                # noqa: BLE001
                messagebox.showerror("写回失败", "%s" % ex, parent=dlg)

        def clear_focus():
            self.turn_focus = None
            self.redraw()

        def on_close():
            self.turn_focus = None
            self._turn_dlg = None
            dlg.destroy()
            self.redraw()

        foot = ttk.Frame(outer)
        foot.pack(fill="x", pady=(8, 0))
        ttk.Button(foot, text="从 map.c 重读", command=reload_from_source).pack(side="left")
        ttk.Button(foot, text="在画布上清掉高亮", command=clear_focus).pack(side="left", padx=6)
        ttk.Button(foot, text="写回 map.c…", command=writeback).pack(side="right")
        ttk.Button(foot, text="关闭", command=on_close).pack(side="right", padx=6)
        dlg.protocol("WM_DELETE_WINDOW", on_close)

        state_reset()

    # ---- JSON / 布局 ----
    def _layouts_dir(self):
        return os.path.join(HERE, "layouts")

    def _layout_path(self):
        """默认布局文件：启动时若存在会自动载入。"""
        return os.path.join(self._layouts_dir(), "default.json")

    def _sync_state_to_model(self):
        """把界面上的底图/约束状态写进 model（保存时会一起存）。"""
        self.model.background = {
            "path": self.bg.path,
            **self.bg.calib_snapshot(),
            "show": bool(self.show_bg.get()),
        }
        self.model.constraints = {
            "lock_angle": bool(self.lock_angle.get()),
            "snap_mode": self.snap_mode.get(),
            "snap_tol": float(self.snap_tol.get()),
            "snap_near": float(self.snap_near.get()),
            "enforce_min_len": bool(self.enforce_min_len.get()),
            "unit_px_per_cm": float(self._unit_k()),
            "rot": self.rot.get(),
            "edge_view": self.edge_view.get(),      # 边列表展示模式
            "label_mode": self.label_mode.get(),
            # 「线索路线…」上次用的配置：省得每次点开都重新配一遍
            "clue_route": dict(self.clue_route_cfg or {}),
            # 「二轮路线…」上次用的配置（巡游顺序等）
            "round2_route": dict(self.round2_cfg or {}),
        }

    def save_layout(self, show_msg=True, path=None):
        """保存布局（默认存到"默认布局"，下次启动自动载入），并保留多版本快照。

        path 参数给测试用：可写入沙箱文件，绝不碰真实布局。
        ⚠️ 为什么有多版本：曾经因为只保留一个文件、又误删，把用户调好的布局弄丢了。
        现在每次保存都会额外写一份 `layouts/snapshots/<时间戳>.json`（保留最近 30 份）。
        """
        return self._write_layout(path or self._layout_path(), show_msg=show_msg,
                                  default_label="默认布局")

    def save_layout_as(self):
        """另存为：把当前布局存成另一个名字（可以有多套布局）。"""
        path = filedialog.asksaveasfilename(
            title="布局另存为", defaultextension=".json",
            initialdir=self._layouts_dir(),
            initialfile="layout_%s.json" % datetime.datetime.now().strftime("%m%d_%H%M"),
            filetypes=[("布局 JSON", "*.json")], parent=self)
        if not path:
            return False
        return self._write_layout(path, show_msg=True, default_label="布局")

    def _write_layout(self, path, show_msg=True, default_label="布局"):
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            self._snapshot_layout(path)
            self._sync_state_to_model()
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.model.to_json())
            self.model.dirty = False
            self._current_layout = path
            if show_msg:
                self.status("%s已保存：%s（%d 节点 / %d 边 + 底图标定）"
                            % (default_label, path, len(self.model.nodes),
                               len(self.model.edges)))
            return True
        except Exception as ex:
            import traceback
            traceback.print_exc()          # 也打到 stderr，便于无人值守测试排查
            messagebox.showerror("保存失败", "%s" % ex, parent=self)
            return False

    def _snapshot_layout(self, path, keep=30):
        """把将要被覆盖的旧文件另存一份到**同目录下的 snapshots/**（多版本，永不丢）。

        快照放在被测文件旁边（而不是固定放 layouts/snapshots），这样测试写沙箱文件时
        快照也一起落在沙箱里，不会往真实 layouts/ 里丢垃圾。
        """
        if not os.path.isfile(path):
            return
        try:
            sdir = os.path.join(os.path.dirname(path), "snapshots")
            os.makedirs(sdir, exist_ok=True)
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            base = os.path.splitext(os.path.basename(path))[0]
            shutil.copy2(path, os.path.join(sdir, "%s.%s.json" % (base, ts)))
            olds = sorted(f for f in os.listdir(sdir)
                          if f.startswith(base + ".") and f.endswith(".json"))
            for f in olds[:-keep]:
                try:
                    os.remove(os.path.join(sdir, f))
                except OSError:
                    pass
        except Exception:
            pass          # 快照失败不阻塞保存

    def list_layouts(self):
        """列出可载入的布局（layouts/*.json + snapshots/*.json，按时间倒序）。"""
        out = []
        for sub in ("", "snapshots"):
            d = os.path.join(self._layouts_dir(), sub)
            if not os.path.isdir(d):
                continue
            for fn in os.listdir(d):
                if fn.lower().endswith(".json"):
                    p = os.path.join(d, fn)
                    out.append((os.path.getmtime(p), p))
        out.sort(reverse=True)
        return [p for _, p in out]

    def load_layout_picker(self):
        """从一个列表里挑一个布局载入（而不是每次翻文件对话框）。"""
        items = self.list_layouts()
        if not items:
            messagebox.showinfo("没有布局", "layouts/ 里还没有任何 .json 布局文件。", parent=self)
            return
        dlg = tk.Toplevel(self)
        dlg.title("载入布局")
        dlg.geometry("620x420")
        ttk.Label(dlg, text="layouts/ 下的布局（最近的在上；snapshots/ 是历史快照）").pack(
            anchor="w", padx=8, pady=(8, 2))
        lb = tk.Listbox(dlg)
        lb.pack(fill="both", expand=True, padx=8)
        cur = getattr(self, "_current_layout", None)
        for p in items:
            rel = os.path.relpath(p, self._layouts_dir())
            mark = "  ←当前" if cur and os.path.abspath(p) == os.path.abspath(cur) else ""
            lb.insert("end", "%s   (%s)%s"
                      % (rel, datetime.datetime.fromtimestamp(
                          os.path.getmtime(p)).strftime("%m-%d %H:%M"), mark))
        brow = ttk.Frame(dlg)
        brow.pack(fill="x", padx=8, pady=8)

        def do_load():
            sel = lb.curselection()
            if not sel:
                return
            p = items[sel[0]]
            self._push_undo()
            if self.load_layout_file(p):
                self._current_layout = p
                dlg.destroy()

        def do_del():
            sel = lb.curselection()
            if not sel:
                return
            p = items[sel[0]]
            if os.path.abspath(p) == os.path.abspath(self._layout_path()):
                messagebox.showwarning("不能删", "这是默认布局，请在关闭编辑器后手动处理。",
                                       parent=dlg)
                return
            if not messagebox.askyesno("删除快照", "删除\n%s ？" % p, parent=dlg):
                return
            try:
                os.remove(p)
            except OSError as ex:
                messagebox.showerror("删除失败", str(ex), parent=dlg)
                return
            dlg.destroy()
            self.load_layout_picker()

        ttk.Button(brow, text="载入选中", command=do_load).pack(side="left")
        ttk.Button(brow, text="删除选中", command=do_del).pack(side="left", padx=6)
        ttk.Button(brow, text="取消", command=dlg.destroy).pack(side="right")

    def _apply_model_background(self):
        """把工程里存的底图设置 + 拖动约束设置应用到界面。

        ⚠️ 顺序很重要：**先换图、再转图、最后套标定**。
        标定值是针对"转过之后的图"算的；如果先套标定再转图，图的尺寸/朝向一变，
        标定就对不上了（表现为"节点对、底图是歪的"）。
        """
        bgd = getattr(self.model, "background", None) or {}
        con = getattr(self.model, "constraints", None) or {}

        # 1) 约束设置里的旋转先定下来
        if con.get("rot") in ROT_CHOICES:
            self.rot.set(con["rot"])

        # 2) 换底图（load 会把 rot 重置为 0°）
        if bgd:
            path = bgd.get("path")
            if path and os.path.isfile(path) and \
                    os.path.abspath(path) != os.path.abspath(self.bg.path):
                self.bg.load(path, quiet=True)

        # 3) 按当前旋转档把图转正
        self.bg.set_rotation(self.rot.get(), self._rot_xy())

        # 4) 再套标定（此时 ref_size 已经是转正后的尺寸）
        if bgd:
            self.bg.apply_calib(bgd)
            if "show" in bgd:
                self.show_bg.set(bool(bgd["show"]))
        self.refresh_bg_panel()

        # 5) 其余约束设置
        if con:
            if "lock_angle" in con:
                self.lock_angle.set(bool(con["lock_angle"]))
            if con.get("snap_mode") in SNAP_MODES:
                self.snap_mode.set(con["snap_mode"])
            for key, var in (("snap_tol", self.snap_tol), ("snap_near", self.snap_near)):
                try:
                    if con.get(key):
                        var.set(float(con[key]))
                except (TypeError, ValueError):
                    pass
            if "enforce_min_len" in con:
                self.enforce_min_len.set(bool(con["enforce_min_len"]))
            if con.get("unit_px_per_cm"):
                self.unit_px_per_cm.set(float(con["unit_px_per_cm"]))
            if con.get("edge_view") in ("合并双向", "逐条", "只看双向"):
                self.edge_view.set(con["edge_view"])
            if con.get("label_mode") in ("无", "标准", "详细"):
                self.label_mode.set(con["label_mode"])
            if isinstance(con.get("clue_route"), dict):
                # 「线索路线…」上次的配置（值都当字符串存，用的时候再做合法性校验）
                self.clue_route_cfg = dict(con["clue_route"])
            if isinstance(con.get("round2_route"), dict):
                # 「二轮路线…」上次的配置（同上）
                self.round2_cfg = dict(con["round2_route"])

    def load_layout_file(self, path, quiet=False):
        try:
            with open(path, encoding="utf-8") as f:
                self.model.load_json(f.read())
            self.sel_node = self.sel_edge = None
            self.route = []
            self.route_split = None
            self._current_layout = path
            self._apply_model_background()
            self.refresh_all()
            self._update_title()
            if not quiet:
                self.status("已载入布局 %s" % path)
            return True
        except Exception as ex:
            if not quiet:
                messagebox.showerror("载入布局失败", "%s" % ex, parent=self)
            return False

    def _update_title(self):
        """标题栏显示当前布局文件名 + 未保存标记，避免"不知道在编辑哪一份"。"""
        cur = getattr(self, "_current_layout", None)
        name = os.path.basename(cur) if cur else "（未命名/出厂坐标）"
        star = " *" if self.model.dirty else ""
        self.title("寻宝地图编辑器 — %s%s" % (name, star))

    def load_layout(self):
        """载入布局（可用列表挑选）。"""
        self.load_layout_picker()

    def save_json(self):
        path = filedialog.asksaveasfilename(
            title="另存地图工程", defaultextension=".json",
            initialdir=os.path.dirname(self._layout_path()),
            initialfile="map_%s.json" % datetime.datetime.now().strftime("%Y%m%d"),
            filetypes=[("JSON", "*.json")], parent=self)
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.model.to_json())
            self.status("已另存 %s（%d 节点 / %d 边）"
                        % (path, len(self.model.nodes), len(self.model.edges)))
        except Exception as ex:
            messagebox.showerror("保存失败", "%s" % ex, parent=self)

    def load_json(self):
        self.load_layout()

    def reload_sources(self):
        if not messagebox.askyesno("重新载入",
                                   "从固件源码重新读取地图（节点/边/数值）？\n\n"
                                   "你拖好的布局不会丢：会按节点名把坐标搬过去。",
                                   parent=self):
            return
        try:
            old_pos = {n.name: (n.x, n.y) for n in self.model.nodes}
            old_bg = dict(getattr(self.model, "background", {}) or {})
            self.model = M.MapModel.load_from_sources()
            self.model.background = old_bg
            for n in self.model.nodes:                 # 保住已拖好的位置
                if n.name in old_pos:
                    n.x, n.y = old_pos[n.name]
            self.sel_node = self.sel_edge = None
            self.route = []
            self.route_split = None
            self.undo_stack.clear()
            self.redo_stack.clear()
            self._apply_model_background()
            self.field_var.set("比赛场地" if self.model.field_name == "FIELD_COMP" else "学校场地")
            self.refresh_all()
            self._fit_view()
            self.status("已重新载入源码：%d 节点 / %d 边（布局位置已保留）"
                        % (len(self.model.nodes), len(self.model.edges)))
        except Exception as ex:
            messagebox.showerror("载入失败", str(ex), parent=self)

    def on_field_change(self):
        """切换场地（比赛/学校）：改 config.h 的 USE_FIELD，重新解析宏。"""
        new_label = self.field_var.get()
        new_field = "FIELD_COMP" if new_label == "比赛场地" else "FIELD_SCHOOL"
        if new_field == self.model.field_name:
            return
        if not messagebox.askyesno("切换场地",
                                   "切换到%s？\n\n"
                                   "这会修改 Mission/config.h 的 USE_FIELD，"
                                   "影响所有 LEN_*/ANGLE_*/DOOR_LEN_* 宏的实际值。\n"
                                   "（改动会写入文件，可用 git 撤回）"
                                   % new_label,
                                   parent=self):
            self.field_var.set("比赛场地" if self.model.field_name == "FIELD_COMP" else "学校场地")
            return
        try:
            M.write_use_field(new_field)
            macros, field_name = M.parse_config_macros()
            self.model.macros = dict(macros)
            self.model.field_name = field_name
            self.model.dirty = True
            self.refresh_all()
            self.status("已切换到%s（config.h 已更新，%d 个宏重新解析）"
                        % (new_label, len(macros)))
        except Exception as ex:
            messagebox.showerror("切换失败", str(ex), parent=self)
            self.field_var.set("比赛场地" if self.model.field_name == "FIELD_COMP" else "学校场地")

    # ================================================================ 杂项
    def status(self, msg):
        self.status_var.set(msg)

    def show_help(self):
        txt = HELP_TEXT
        dlg = tk.Toplevel(self)
        dlg.title("帮助")
        dlg.geometry("820x640")
        t = tk.Text(dlg, wrap="word")
        t.insert("1.0", txt)
        t.pack(fill="both", expand=True, padx=8, pady=8)
        ttk.Button(dlg, text="关闭", command=dlg.destroy).pack(pady=(0, 8))


HELP_TEXT = """寻宝地图编辑器 — 操作说明

【它是干什么的】
  把固件里的地图（Navigation/map.h 的 enum MapNode + Navigation/map_message.c 的
  NavEdgeTbl[]）画成图，让你拖节点、连边、改参数，然后直接导出成 C 代码。
  这样你改地图（挪 P7、加 C10、切边）就不用再手抠几百行边表了。

【两条最重要的规矩】
  1) 节点位置只是「示意图」：图上远近不代表实际长度，长度只认每条边的 step 数值。
     → 所以节点随便拖，拖多远都不会改任何数值，也不会影响固件。
  2) 角度/长度最终真值靠实车标定；「辅助 → 按图上位置算」只是估算。

【鼠标 / 手势（特意分开，避免冲突）】
  左键点节点 / 边    选中（边的命中区已加宽到 ±7px，点线附近就算选中；双向边偏向哪条选哪条）
  左键拖节点         移动节点（只是示意图位置，不影响固件任何数值）
  双击【边】         直接打开这条边的编辑框
  右键【节点】       以它为起点开始连线 → 再右键另一个节点即建边（左键点目标也行）
                     再右键自己 / 点空白 / Esc = 取消起点
  Shift + 右键【节点】 节点快捷菜单（重命名/删除/补反向边/设为必经点…）
  双击【节点】       以它为起点开始连线（右键的备用方式，等同按 A）
  Shift + 双击空白   在空白处新建节点（防误触）
  中键拖 / 空白拖    平移画布
  滚轮               以鼠标为中心缩放
  右键边 / 右键空白  各自的快捷菜单（删边、补反向边、在此新建节点等）

【选边 / 增删边（不用手选 from-to）】
  点图形即可选中边        <- 边的命中区已加宽（±7px），不用精确点中细线
  ⭐ 双向边两条线相隔 12px：**偏向哪条就选哪条**；同一处**再点一次 = 切换方向**
     （双击不会被当成切换，仍是"编辑当前选中那条"）
  双击边 = 编辑；Delete = 删除选中的边
  A                       以选中节点（或选中边的 to 端）为起点开始续连
  连线模式（工具栏）      点两个节点直接建边；点边则以它的 to 端起继续连
  Esc                     退出连线模式 / 取消待连线的起点
  右键节点                以它为起点开始连线（再右键目标节点建边）
  Shift+右键节点          删除它全部入边/出边、补反向边、从这里连到…
  右键边                  删除这条边 / 删除这一对（双向都删）/ 补反向边 / 从任一端续连
  快捷建边按**边表约定**自动算角度（先看有没有共线边可沿用 → 否则图上几何 +90° → 再吸附整数）；
  「双向」勾选框决定是否同时建反向边。
  ⚠️ 快捷建边的 step 默认 0，建完请在「属性」面板改成实测值。

【常用快捷键】
  Ctrl+Z 撤销      Ctrl+Y 重做      Ctrl+S 保存布局      Delete 删除选中
  A 从选中节点续连   Esc 退出连线模式   F1 帮助

【保存布局 / 另存为 / 多版本】
  工具栏「保存布局」-> layouts/default.json，**下次打开自动载入**（Ctrl+S 同效）
  「布局另存为」-> 存成别的名字，可以在 layouts/ 下放多套布局
  「载入布局」  -> 弹出列表挑一个（含 snapshots/ 里的历史快照）
  每次保存前会自动把旧版快照到 layouts/snapshots/（保留最近 30 份），
  所以任何一版都能捞回来。标题栏会显示当前布局名 + *（有未保存改动）。

【换 / 调底图】
  右栏「底图对齐」面板：
    * 下拉框选 寻宝地图/ 里的图，或「浏览…」选任意图片（jpg 需要 pillow）；
    * 「用节点反推最佳位置」= 用图上量过坐标的那些节点做最小二乘拟合，自动贴合；
    * 「偏移 X/Y」「缩放 X/Y」「透明度」滑条微调；
    * 「重置」= 回到 1:1 居中。
  ⚠️ 底图只是对齐参考，不参与任何长度计算。
  ⚠️ C2 / B4 / C6 / C7 / C8 / G1 这 6 个节点在 节点图.jpg 上**没有画**，
     所以它们怎么对都对不上，坐标是估的，按你觉得对的位置拖即可。

【路线规划】
  左栏「路线规划」→ 把起点、途径点、终点依次加进必经点列表（顺序即执行顺序）
  → 「规划路线」。用的是和固件同一套 Dijkstra（长度 + 转弯代价 + 障碍惩罚），
  可直接对照 scripts/validate/_check_map_debug.py 的预测结果。

【改完怎么落到固件】
  ① 工具栏「导出 C 代码」→ 复制/另存 NavEdgeTbl 与 enum MapNode；
  ② 或「写回固件…」直接改源码（会先备份到 scripts/map_editor/backups/）。

【⚠️ 重要提醒】
  * 新增/删除节点后，导出的 enum MapNode 里新节点排在最后 —— 枚举顺序 = 节点编号，
    固件其它地方（mission_planner/barrier 的 wp、门逻辑、宝物表）都按编号走，
    所以必须**同步检查那些文件**。编辑器只保证导出文本正确，不保证业务自洽。
  * 改完请跑 scripts/validate/ 下的 7 个校验脚本，再 Keil 编译 0 error 才上车。
"""


def main():
    import argparse
    ap = argparse.ArgumentParser(
        description="寻宝地图图形化编辑器（改 NavEdgeTbl[] 用）")
    ap.add_argument("--bg", metavar="图片路径",
                    help="指定底图（jpg/png；默认用 寻宝地图/节点图.jpg）")
    ap.add_argument("--layout", metavar="JSON路径",
                    help="启动时载入指定的布局 json（默认自动载入 layouts/default.json）")
    ap.add_argument("--rot", choices=list(ROT_CHOICES.keys()), default=None,
                    help="视图旋转档（默认沿用上次保存的/0°）。点一下看哪个方向对就用哪个")
    args, _unknown = ap.parse_known_args()

    app = App(bg_path=args.bg)
    if args.rot:
        app.rot.set(args.rot)
        app.apply_rotation()
    if args.layout and os.path.isfile(args.layout):
        app.load_layout_file(args.layout)
        app._fit_view()
    app.bind_all("<Control-z>", lambda e: app.undo())
    app.bind_all("<Control-y>", lambda e: app.redo())
    app.bind_all("<Control-Z>", lambda e: app.redo())
    app.bind_all("<Control-s>", lambda e: app.save_layout())
    app.bind_all("<Delete>", lambda e: app.delete_sel_edge())
    app.bind_all("<Escape>", lambda e: app.cancel_connect())
    app.bind_all("<Key-a>", lambda e: app.start_connect_from_sel())
    app.bind_all("<Key-A>", lambda e: app.start_connect_from_sel())
    app.bind_all("<Control-Shift-R>", lambda e: app.make_reverse_edge())
    app.bind_all("<F1>", lambda e: app.show_help())
    app.mainloop()


if __name__ == "__main__":
    main()
