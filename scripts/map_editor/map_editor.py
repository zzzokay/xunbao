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
LEFT_W = 318      # 左栏固定宽度
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
ROUTE_COLOR = "#1e88e5"
BG = "#fbfbf8"
EDGE_HIT_WIDTH = 14               # 边的"隐形命中区"宽度(px)：点它附近即可选中

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
        self.sel_edge = None          # 选中的 Edge 对象
        self.selected_nodes = set()   # Ctrl 框选后用于整体移动的节点
        self.route = []               # 规划出来的路线（节点名列表）
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
        sep()
        chk("连线模式", self.connect_mode)
        chk("双向", self.var_quick_both)

        # ---------------- 第二行：视图 ----------------
        btn, sep, chk, lab = mk(row2)
        chk("网格", self.show_grid, cmd=self.redraw, pad=(2, 3))
        chk("底图", self.show_bg, cmd=self.redraw, pad=(2, 3))
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
        ttk.Button(row2, text="读config", command=self.wp_from_config).pack(side="left", padx=2)
        ttk.Button(row2, text="清路线", command=self.clear_route).pack(side="left")
        cost_row = ttk.Frame(bot)
        cost_row.pack(fill="x", padx=4, pady=(0, 2))
        ttk.Label(cost_row, text="路线成本:").pack(side="left")
        self.cost_mode = tk.StringVar(value="full")
        ttk.Combobox(cost_row, textvariable=self.cost_mode, width=8, state="readonly",
                     values=["len", "turn", "full"]).pack(side="left")

        self.txt_route = tk.Text(bot, height=9, wrap="word")
        self.txt_route.pack(fill="both", expand=True, padx=4, pady=(3, 0))
        row3 = ttk.Frame(bot)
        row3.pack(fill="x", padx=4, pady=4)
        ttk.Button(row3, text="复制 route[]", command=self.copy_route_array).pack(side="left")
        ttk.Button(row3, text="复制调试宏", command=self.copy_debug_macros).pack(
            side="left", padx=3)

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
        ttk.Button(q, text="从选中节点连线（点两下 / 或按 A）",
                   command=self.start_connect_from_sel).pack(fill="x", padx=4, pady=2)
        ttk.Button(q, text="＋ 补反向边（复制选中边参数）",
                   command=self.make_reverse_edge).pack(fill="x", padx=4, pady=2)
        ttk.Button(q, text="－ 删除这一对（双向都删）",
                   command=self.delete_sel_pair).pack(fill="x", padx=4, pady=2)
        ttk.Label(q, text="点图形即可选中边（命中区已加宽到 ±7px）；\n"
                          "选中后 Delete 删除、A 从它续连。",
                  foreground="#666666", justify="left").pack(anchor="w", padx=4, pady=(2, 4))
        r += 1

        # 数值辅助
        g = ttk.LabelFrame(f, text="辅助")
        g.grid(row=r, column=0, columnspan=2, sticky="we", pady=6)
        ttk.Button(g, text="按图上位置算角度", command=self.calc_angle_geo).pack(
            fill="x", padx=4, pady=2)
        ttk.Button(g, text="按图上位置算 step(px÷0.884)", command=self.calc_step_geo).pack(
            fill="x", padx=4, pady=2)
        ttk.Button(g, text="整条边取反（from/to 互换，角度+180）",
                   command=self.reverse_edge_sel).pack(fill="x", padx=4, pady=2)

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
        self._draw_route()
        self._draw_nodes()
        self._draw_drag_overlay()
        self.zoom_var.set("%d%%" % round(self.scale * 100))

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
            lw = 3 if sel else 1.6
            oc = EDGE_COLOR_SEL if sel else outline
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
                                     lambda e, nm=n.name: self._on_node_menu(e, nm))

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
        # 反向边存在时，两条线各偏移一点点，避免完全重叠
        off = 0.0
        if self.model.has_reverse(e):
            off = 4.0
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
            special = (e.func not in ("NONE", "", None))
            warned = e.tag in warnings
            col = "#e74c3c" if warned else (EDGE_COLOR_SEL if sel else (
                EDGE_COLOR_FUNC if special else EDGE_COLOR))
            w = 3.2 if warned else (2.6 if sel else (2.0 if special else 1.3))
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
                length_cm = seg / self._unit_k() if self._unit_k() > 0 else None
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
                    fill="#e74c3c" if warned else ("#333333" if not sel else EDGE_COLOR_SEL)))
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

    def _draw_route(self):
        if len(self.route) < 2:
            return
        pts = []
        for name in self.route:
            n = self.model.node(name)
            if n:
                pts.extend(self.w2s(n.x, n.y))
        if len(pts) >= 4:
            item = self.canvas.create_line(*pts, fill=ROUTE_COLOR, width=4, dash=(7, 4),
                                           arrow="last", arrowshape=(12, 14, 5))
            # 只把这条线压到节点下面（别动底图，别用 tag_lower("all")）
            first_node = None
            for items in self._canvas_items["nodes"].values():
                if items:
                    first_node = items[0]
                    break
            if first_node is not None:
                self.canvas.tag_lower(item, first_node)
            else:
                self.canvas.tag_lower(item)

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
        if self.connect_mode.get():
            # 「连线模式」= 点两下连线：第一下选起点，第二下成边
            if self.connect_from is None:
                self.connect_from = name
                self.select_node(name)
                self.status("连线模式：起点 = %s　→ 再点另一个节点即可建边（Esc 取消）"
                            % name)
            elif self.connect_from == name:
                self.connect_from = None
                self.status("连线模式：已取消起点")
            else:
                src = self.connect_from
                self.connect_from = None
                self.create_edge_quick(src, name)
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
        if getattr(self, "_marquee", None):
            box = self._marquee
            if box.get("item"):
                self.canvas.delete(box["item"])
            self._marquee = None
            x0, x1 = sorted((box["x0"], ev.x))
            y0, y1 = sorted((box["y0"], ev.y))
            self.selected_nodes = {
                n.name for n in self.model.nodes
                if x0 <= self.w2s(n.x, n.y)[0] <= x1
                and y0 <= self.w2s(n.x, n.y)[1] <= y1
            }
            self.sel_node = None
            self.sel_edge = None
            self.refresh_props()
            self.redraw()
            self.status("已框选 %d 个节点；拖动其中任一节点可整体移动" %
                        len(self.selected_nodes))
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
        if ev.state & 0x0004:       # Ctrl + 空白拖动：框选节点
            self._marquee = {"x0": ev.x, "y0": ev.y, "item": None}
            return "break"
        self.selected_nodes.clear()
        self.sel_node = None
        self.sel_edge = None
        self.refresh_props()
        self.redraw()
        # 空白处按下也支持平移
        self._pan = (ev.x, ev.y, self.ox, self.oy)

    def _edge_near(self, sx, sy, tol=6.0):
        """屏幕坐标附近有没有边（点到线段的距离 < tol）。用于避免"双击边却建了节点"。"""
        best = None
        for e in self.model.edges:
            a, b = self.model.node(e.frm), self.model.node(e.to)
            if not a or not b:
                continue
            x1, y1 = self.w2s(a.x, a.y)
            x2, y2 = self.w2s(b.x, b.y)
            dx, dy = x2 - x1, y2 - y1
            L2 = dx * dx + dy * dy
            if L2 < 1e-9:
                continue
            t = max(0.0, min(1.0, ((sx - x1) * dx + (sy - y1) * dy) / L2))
            px, py = x1 + t * dx, y1 + t * dy
            d = math.hypot(sx - px, sy - py)
            if tol + EDGE_HIT_WIDTH / 2.0 >= d and (best is None or d < best[0]):
                best = (d, e)
        return best[1] if best else None

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

    def _on_node_double(self, ev, name):
        """双击节点 = 打开"编辑边"不方便，改为：以它为起点快速连线。"""
        self.start_connect_from(name)
        return "break"

    def _on_edge_press(self, ev, e):
        # 「连线模式」下点边 → 把它当作起点，快速续连
        if self.connect_mode.get():
            self.start_connect_from(e.to)
            return "break"
        self.sel_edge = e
        self.sel_node = None
        self.refresh_props()
        self.redraw()
        self.status("已选中边 %s（双击=编辑 / Delete 删除 / 右键更多）" % e.label())
        return "break"

    def _on_edge_double(self, ev, e):
        """双击边 = 选中并在右侧属性栏编辑。"""
        self.sel_edge = e
        self.sel_node = None
        self.refresh_props()
        self.redraw()
        self.status("已选中边 %s，右侧属性栏可直接编辑" % e.label())
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
        """进入"点两下连线"，并把起点设为 name。"""
        self.connect_mode.set(True)
        self.connect_from = name
        self.select_node(name)
        self.status("连线：起点 = %s　→ 现在点另一个节点即可建边（Esc 取消）" % name)

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
            "长度显示 = 图上像素 ÷ K（K = %.4g px/cm）；角度只作信息显示。"
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
        a, b = self.model.node(frm), self.model.node(to)
        ang = math.degrees(math.atan2(b.x - a.x, -(b.y - a.y)))
        if ang > 180:
            ang -= 360
        rng = ang - 180 if ang >= 0 else ang + 180
        snap = self.model.snapshot()
        try:
            e = self.model.add_edge(frm, to, flag="NO", angle="%g" % round(ang, 1),
                                    step="0", speed="SPEED2", func="NONE")
            if both and not self.model.edge(to, frm):
                self.model.add_edge(to, frm, flag="NO", angle="%g" % round(rng, 1),
                                    step="0", speed="SPEED2", func="NONE")
            self.sel_edge = e
            self.sel_node = None
            self._apply_change(snap)
            self.status("已建%s边 %s → %s（角度按图上位置自动算 %g°；"
                        "step 默认 0，请在属性面板改成实测值）"
                        % ("双向" if both else "", frm, to, round(ang, 1)))
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
        if not self.sel_edge:
            return
        e = self.sel_edge
        a, b = self.model.node(e.frm), self.model.node(e.to)
        if not a or not b:
            return
        dx, dy = b.x - a.x, -(b.y - a.y)
        import math
        ang = math.degrees(math.atan2(dx, dy))
        if ang > 180:
            ang -= 360
        if ang <= -180:
            ang += 360
        e.angle = "%g" % round(ang, 1)
        self.refresh_props()
        self.status("按图上位置算出 %.1f°（注意：节点图是示意图，角度仅供参考）" % ang)

    def calc_step_geo(self):
        if not self.sel_edge:
            return
        e = self.sel_edge
        a, b = self.model.node(e.frm), self.model.node(e.to)
        if not a or not b:
            return
        d = ((b.x - a.x) ** 2 + (b.y - a.y) ** 2) ** 0.5
        cm = d / 0.884
        e.step = "%g" % round(cm)
        self.refresh_props()
        self.status("图上 %.0f px ÷ 0.884 = %g cm（⚠️ 只是估算，务必实测标定）" % (d, round(cm)))

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
    def select_node(self, name):
        self.sel_node = name
        self.sel_edge = None
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
        else:
            frm, to = iid[2:].split("->")
            e = self.model.edge(frm, to)
        if not e:
            return
        if self.sel_edge is not None and self.sel_edge.tag == e.tag:
            return
        self.sel_edge = e
        self.sel_node = None
        self.refresh_props()
        self.redraw()
        rev = self.model.edge(e.to, e.frm)
        if rev is not None:
            self.status("已选中线段 %s ↔ %s（两个方向都在：正向 %s / 反向 %s）"
                        % (e.frm, e.to, e.label(), rev.label()))
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
    def do_validate(self):
        items = self.model.validate()
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
        self.txt_route.delete("1.0", "end")
        self.redraw()

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

    def _patch_edge_table(self, backup_dir, ts):
        path = M.PATH_EDGE_C
        src = open(path, encoding="utf-8").read()
        m = re.search(r"(const\s+NavEdge\s+NavEdgeTbl\s*\[[^\]]*\]\s*=\s*\{)", src)
        if not m:
            raise RuntimeError("在 map_message.c 里找不到 NavEdgeTbl[] 起始位置")
        start = m.start(1)
        end = src.index("};", m.end()) + 2
        new_block = self.model.export_edge_table(with_header=False)
        new_src = src[:start] + new_block + src[end:]
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

    def load_layout_file(self, path, quiet=False):
        try:
            with open(path, encoding="utf-8") as f:
                self.model.load_json(f.read())
            self.sel_node = self.sel_edge = None
            self.route = []
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
            self.undo_stack.clear()
            self.redo_stack.clear()
            self._apply_model_background()
            self.refresh_all()
            self._fit_view()
            self.status("已重新载入源码：%d 节点 / %d 边（布局位置已保留）"
                        % (len(self.model.nodes), len(self.model.edges)))
        except Exception as ex:
            messagebox.showerror("载入失败", str(ex), parent=self)

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
  左键点节点 / 边    选中（边的命中区已加宽到 ±7px，点线附近就算选中）
  左键拖节点         移动节点（只是示意图位置，不影响固件任何数值）
  双击【边】         直接打开这条边的编辑框
  双击【节点】       以它为起点开始连线（等同按 A）
  Shift + 双击空白   在空白处新建节点（防误触）
  中键拖 / 空白拖    平移画布
  滚轮               以鼠标为中心缩放
  右键节点/边/空白   各自的快捷菜单（删边、补反向边、连到…、在此新建节点等）

【选边 / 增删边（不用手选 from-to）】
  点图形即可选中边        <- 边的命中区已加宽（±7px），不用精确点中细线
  双击边 = 编辑；Delete = 删除选中的边
  A                       以选中节点（或选中边的 to 端）为起点开始续连
  连线模式（工具栏）      点两个节点直接建边；点边则以它的 to 端起继续连
  Esc                     退出连线模式
  右键节点                删除它全部入边/出边、补反向边、从这里连到…
  右键边                  删除这条边 / 删除这一对（双向都删）/ 补反向边 / 从任一端续连
  快捷建边按图上位置自动算角度；「双向」勾选框决定是否同时建反向边。
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
