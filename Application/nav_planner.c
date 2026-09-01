#include "nav_planner.h"   /* 引入本模块头文件：NavEdge 结构、函数声明、权重宏 */
#include <math.h>          /* fabsf 绝对值、1e30f 常量用 */
#include <string.h>        /* memset 清零用 */

/* ---------------- 权重表（按 map.h enum barriers 编号 1..19 索引） ---------------- */
/* 下标 0 恒为 0（"空"，无对应障碍）；下标对应 barrier 枚举值，取值含义见表内注释。 */
static const float NavObsPenalty[20] = {
    0.0f,   /* 0 空 */
    0.0f,   /* 1 NONE */
    60.0f,  /* 2 UpStage 平台(去完要往返，含爬坡) */
    40.0f,  /* 3 Bridge 桥 */
    30.0f,  /* 4 Hill 山 */
    50.0f,  /* 5 LBHill */
    120.0f, /* 6 SM 刀山(round2 用权重避开 N11) */
    100.0f, /* 7 View 景点支路(不应被当捷径) */
    100.0f, /* 8 View1 景点支路 */
    1000.0f,/* 9 BACK 后退桩(绝不该选为前进路径) */
    90.0f,  /* 10 BSoutPole 南极 */
    80.0f,  /* 11 QQB 跷跷板(单相) */
    60.0f,  /* 12 BLBS 短波动板 */
    70.0f,  /* 13 BLBL 长波动板 */
    0.0f,   /* 14 DOOR 门(用必经点处理，不靠权重) */
    90.0f,  /* 15 BHM 高山 */
    0.0f,   /* 16 IGNORE */
    0.0f,   /* 17 Special_node */
    0.0f,   /* 18 DOOR1 */
    60.0f,  /* 19 UpStageHome */
};

/* 查询某个 barrier 类型对应的障碍惩罚代价（等效 cm）。越障成本越高，路径越被算法回避。 */
float nav_obs_penalty(unsigned char func)
{
    if (func >= 20u) return 0.0f;          /* 越界保护：未知/非法类型一律按无障碍处理 */
    return NavObsPenalty[func];            /* 查表返回对应惩罚值 */
}

/* 求两个航向角 a、b 的差值，并归一化到 (-180, 180] 度，表示"从 a 转到 b 需要转多少度"（带符号）。 */
float nav_need2turn(float a, float b)
{
    float d = b - a;                       /* 先直接相减得到裸差值 */
    while (d > 180.0f)  d -= 360.0f;       /* 若超过 180°，减去一圈，缩到 (-180,180] 范围 */
    while (d < -180.0f) d += 360.0f;       /* 若小于 -180°，加回一圈，保证左右转向取最省的那条路 */
    return d;
}

/* ---------------- 内部图状态（启动时由 nav_init 填好，之后只读） ---------------- */
static NavEdge s_edges[NAV_MAX_EDGES];       /* 副本：全部有向边，按 from 节点分组连续存放 */
static uint16_t s_out_start[NAV_MAX_NODES+1];/* CSR：节点 v 的出边为 s_edges[s_out_start[v] .. s_out_start[v+1]) */
static uint16_t s_n = 0;                     /* 实际有效的边总数 */
static uint8_t  s_nodes = 0;                 /* 节点总数（节点编号 0..s_nodes-1） */
static uint8_t  s_ready = 0;                 /* 初始化完成标志：1=nav_init 已成功调用过，可查询 */

/* Dijkstra 运行时数组：注意下标是"线路图节点"（= 原图的一条有向边），不是地图节点 —— 这是线路图(line-graph) Dijkstra。
   之所以用"边当点"，是因为转弯代价取决于"上一条路→这一条路"这一对，用路当点才能在转移时算转弯费。 */
static float    s_dist[NAV_MAX_EDGES];       /* dist[u]：到"线路图节点 u(=一条路)"的累计代价 */
static int16_t  s_prev[NAV_MAX_EDGES];       /* prev[u]：最优路径中 u 的前一条路(线路图节点)，-1=起点 */
static uint8_t  s_done[NAV_MAX_EDGES];       /* done[u]：u 是否已确定最短代价(1=已弹出，不再更新) */

/* ---- 线路图(显式建出来，读起来就是普通点式 Dijkstra) ---- */
/* 原图每条有向边 = 线路图的一个"点"。若 边u 的终点 == 边v 的起点，则 u、v 在新图里相连。
   这个连接的权 = base(v) + 转弯费(u,v)，在 nav_init 里就"加好"了（转弯权重在此并入）。 */
static uint16_t lg_start[NAV_MAX_EDGES+1];   /* CSR：线路图节点 u 的邻居为 lg_succ[lg_start[u]..lg_start[u+1]) */
static uint16_t lg_succ[NAV_MAX_TRANS];      /* 邻居线路图节点(即下一条路的边号) */
static float    lg_w[NAV_MAX_TRANS];         /* 连接权 = base(邻居路) + 转弯费(u->邻居) */

/* 计算一条边的基础通行代价 = 长度代价 + 障碍惩罚（不含转弯代价）。 */
static float nav_edge_base_cost(const NavEdge *e)
{
    return NAV_W_STEP * (float)e->step + NAV_W_OBS * nav_obs_penalty(e->func);
    /* 长度(cm)*1.0 + 障碍惩罚*1.0，单位统一为"等效 cm" */
}

/* 用调用方给的边表初始化图：统计每个节点的出度 -> 算 CSR 行偏移 -> 按 from 分组填入 s_edges[]。 */
int nav_init(const NavEdge *edges, uint16_t n_edges, uint8_t n_nodes)
{
    uint16_t cnt[NAV_MAX_NODES];     /* cnt[v]：节点 v 的出边条数（计数排序用） */
    uint16_t cur[NAV_MAX_NODES];     /* cur[v]：节点 v 当前已填入的边位置游标 */
    uint16_t i, v;                   /* 循环变量：i=边序号，v=节点序号 */

    if (n_edges > NAV_MAX_EDGES || n_nodes > NAV_MAX_NODES) return -1;
    /* 参数超限保护：边数/节点数超过静态数组容量直接失败 */

    memset(cnt, 0, sizeof(cnt));                     /* 出度计数数组清零 */
    for (i = 0; i < n_edges; i++) {
        if (edges[i].from < n_nodes) cnt[edges[i].from]++;   /* 只统计 from 合法的边，累加各节点出度 */
    }
    s_out_start[0] = 0;                              /* CSR 第一行偏移从 0 开始 */
    for (v = 0; v < n_nodes; v++) s_out_start[v+1] = s_out_start[v] + cnt[v];
    /* 前缀和：节点 v 的出边在 s_edges[] 中的起始下标 = 前 v 个节点出边总数 */
    for (v = 0; v < n_nodes; v++) cur[v] = s_out_start[v];
    /* 每个节点的"写入游标"初始指向自己的行首 */

    for (i = 0; i < n_edges; i++) {
        uint8_t f = edges[i].from;                   /* 取这条边的起点 */
        if (f < n_nodes) {                           /* 起点合法才拷贝 */
            uint16_t dst = cur[f]++;                 /* 写入位置=该节点当前游标，游标后移 */
            s_edges[dst] = edges[i];                 /* 整条边拷入内部数组，完成分组 */
        }
    }
    s_n = (uint16_t)s_out_start[n_nodes];            /* 实际边总数 = 最后一行的偏移 */
    s_nodes = n_nodes;                               /* 记录节点数 */

    /* ---- 构建线路图：每条路当作一个点，相邻可连的路之间加一条边，权 = base(后路) + 转弯费 ---- */
    {
        uint16_t tcnt[NAV_MAX_EDGES];      /* tcnt[u]：线路图节点 u 的邻居数 = 边 u 的终点节点的出度 */
        uint16_t tcur[NAV_MAX_EDGES];      /* tcur[u]：u 当前写入游标 */
        uint16_t i2;
        for (i2 = 0; i2 < s_n; i2++) tcnt[i2] = (uint16_t)(s_out_start[s_edges[i2].to + 1] - s_out_start[s_edges[i2].to]);
        lg_start[0] = 0;
        for (i2 = 0; i2 < s_n; i2++) lg_start[i2+1] = lg_start[i2] + tcnt[i2];
        if (lg_start[s_n] > NAV_MAX_TRANS) return -1;   /* 线路图过大，超出静态数组容量 */
        for (i2 = 0; i2 < s_n; i2++) tcur[i2] = lg_start[i2];
        for (i2 = 0; i2 < s_n; i2++) {
            uint8_t b = s_edges[i2].to;                 /* 从边 u(i2) 的终点节点出发 */
            uint16_t j;
            for (j = s_out_start[b]; j < s_out_start[b+1]; j++) {
                uint16_t dst = tcur[i2]++;
                float turn = NAV_W_TURN * fabsf(nav_need2turn(s_edges[i2].angle, s_edges[j].angle));
                lg_succ[dst] = j;                       /* 邻居 = 下一条路(边号) */
                lg_w[dst]    = nav_edge_base_cost(&s_edges[j]) + turn;   /* 长度+障碍+转弯 一次性算好 */
            }
        }
    }

    s_ready = 1;                                     /* 置就绪标志，允许查询 */
    return 0;
}

/* 直接查从节点 from 到节点 to 是否存在一条有向边，返回边号，不存在返回 -1（供外部校验连通性）。 */
int8_t nav_find_edge(uint8_t from, uint8_t to)
{
    uint16_t i;
    if (!s_ready || from >= s_nodes) return -1;      /* 未初始化或起点越界视为找不到 */
    for (i = s_out_start[from]; i < s_out_start[from+1]; i++) {
        /* 遍历节点 from 的所有出边（CSR 行区间） */
        if (s_edges[i].to == to) return (int8_t)i;  /* 找到目标节点，返回边号 */
    }
    return -1;                                       /* 遍历完没找到，返回 -1 */
}

/* 核心算法：线路图(line-graph)上的标准点式 Dijkstra，求 from->to 最短路径。
   这里"点"= 原图的一条有向边(一条路)。由于把每条路当成一个点，才能在"路 u -> 路 v"的
   转移里算转弯代价；而转弯代价已被 nav_init 提前加进连接权 lg_w，所以主循环就是最朴素的点式 Dijkstra。 */
uint8_t nav_shortest_path(uint8_t from, uint8_t to, uint8_t *out, uint8_t max_len)
{
    uint16_t u, v, best;       /* i=扫描用；u=本次距离出发点最近且为标记的点；v=u的邻居点；best=当前最小点；kk=遍历邻居用 */
    float bestDis;                         /* bestDis=当前扫描到的最小距离 */
    int16_t target_edge;              /* 落到目标节点的最优"路"，-1=没找到路 */
    uint16_t stack[NAV_MAX_EDGES];    /* 回溯栈：倒序压入最优路的序列 */
    int top = 0;                      /* 栈顶游标 */

    /* ---- 入口保护 ---- */
    if (!s_ready || from >= s_nodes || to >= s_nodes) return 0;  /* 未初始化或节点越界，无路 */
    if (from == to) { if (max_len >= 1) { out[0] = from; return 1; } return 0; }

    /* ---- 初始化：所有"点(路)"距离无穷大、无前驱、未完成 ---- */
    for (uint16_t i = 0; i < s_n; i++) { s_dist[i] = 1e30f; s_prev[i] = -1; s_done[i] = 0; }

    /* ---- 起点：从 from 节点出发的每条路，代价 = 它自身基础代价（第一段没有转弯费） ---- */
    for (uint16_t i = s_out_start[from]; i < s_out_start[from+1]; i++) {
        s_dist[i] = nav_edge_base_cost(&s_edges[i]);
    }

    target_edge = -1;                                /* 先假定找不到路 */
    for (;;) {                                       /* 标准点式 Dijkstra 主循环 */
        bestDis = 1e30f; best = 0xFFFFu;                  /* bestDis=无穷大，best=无效点号 */
        for (uint16_t i = 0; i < s_n; i++) {
            if (!s_done[i] && s_dist[i] < bestDis) { bestDis = s_dist[i]; best = i; }
        }
        if (best == 0xFFFFu) break;                  /* 没有未完成的点了 -> 搜完 */
        u = best; s_done[u] = 1;                     /* 弹出当前最小点 u，其最短代价已确定 */
        if (s_edges[u].to == to) { target_edge = (int16_t)u; break; }
        /* 提前终止：点 u 直接落到目标节点。Dijkstra 按代价递增弹出，第一次弹出的必是最优解 */

        for (uint16_t kk = lg_start[u]; kk < lg_start[u+1]; kk++) {          /* 遍历 u 的线路图邻居(可接的路) */
            v = lg_succ[kk];                                         /* 邻居点 = 下一条路 */
            float nd = s_dist[u] + lg_w[kk];                        /* 转弯费已算进 lg_w，直接相加 */
            if (nd < s_dist[v]) { s_dist[v] = nd; s_prev[v] = (int16_t)u; }
            /* 比现有更优则更新点 v 的距离，并记录前驱点 u（即"经由 u 到达 v"） */
        }
    }

    if (target_edge < 0) return 0;                   /* 图不连通，无路 */

    /* ---- 回溯：沿 s_prev 从目标路一路压栈到起点路 ---- */
    {
        int16_t e = target_edge;
        while (e >= 0) { stack[top++] = (uint16_t)e; e = s_prev[e]; }
        /* 压栈顺序是"目标路→起点路"，栈顶是起点路，后面正序取出即恢复路径顺序 */
    }
                
    uint8_t k = 0;   /* 输出节点序列的长度计数 */
    if (k < max_len) out[k++] = from;                /* 先写起点节点 */
    
    {
        int i2;
        for (i2 = top - 1; i2 >= 0; i2--) {
            if (k >= max_len) break;                 /* 缓冲区写满即停，防越界 */
            out[k++] = s_edges[stack[i2]].to;        /* 每条路输出它的终点节点 */
        }
    }
    return k;                                        /* 返回节点序列长度（= 路数 + 起点） */
}

/* 拼接 nsegs 段节点序列(每段以 0xFF 结尾)进 route[]，去掉相邻段之间重复的连接点，0xFF 收尾。 */
uint8_t nav_stitch(uint8_t *route, uint8_t max_len,
                   const uint8_t *const *segs, const uint8_t *seg_lens, uint8_t nsegs)
{
    uint8_t k = 0;       /* route[] 当前写入位置/长度 */
    uint8_t s;           /* 段序号 */
    for (s = 0; s < nsegs && k < max_len; s++) {     /* 逐段处理，缓冲满则停 */
        uint8_t len = seg_lens[s];                   /* 本段节点数 */
        uint8_t j = (k > 0 && len > 0 && segs[s][0] == route[k-1]) ? 1u : 0u;
        /* 若本段首节点 == 已写 route 的末节点(上一段的连接点)，则跳过它，避免重复 */
        for (; j < len && k < max_len; j++) route[k++] = segs[s][j];
        /* 把本段剩余节点依次拷入 route */
    }
    if (k < max_len) route[k++] = 0xFF;              /* 结尾写入哨兵 0xFF，标记 route 结束 */
    return k;                                        /* 返回实际写入的节点数(不含 0xFF) */
}

/* 必经点规划：依次求相邻两个 waypoint 之间的最短路，并拼接成整条 route（0xFF 收尾）。 */
uint8_t nav_plan_waypoints(uint8_t *route, uint8_t max_len,
                           const uint8_t *wps, uint8_t nwp)
{
    uint8_t segbuf[NAV_MAX_PATH];    /* 单段最短路结果的临时缓冲 */
    uint8_t k = 0;                   /* route 写入位置/长度 */
    uint8_t i;                       /* waypoint 序号 */
    if (nwp < 2) return 0;           /* 必经点不足两个，无法构成路径 */
    for (i = 0; i + 1 < nwp; i++) {  /* 对每对相邻必经点 (wps[i] -> wps[i+1]) */
        uint8_t len = nav_shortest_path(wps[i], wps[i+1], segbuf, sizeof(segbuf));
        /* 求这一段的最短节点序列，len=节点数；len==0 表示这一段无路 */
        if (len == 0) return 0;      /* 任意一段无路则整条规划失败 */
        {
            uint8_t j = (k > 0 && segbuf[0] == route[k-1]) ? 1u : 0u;
            /* 若本段首节点与已写 route 末节点相同(相邻段的连接点)，跳过避免重复 */
            for (; j < len && k < max_len; j++) route[k++] = segbuf[j];
            /* 把本段剩余节点接入 route */
        }
    }
    if (k < max_len) route[k++] = 0xFF;   /* 结尾写哨兵 0xFF */
    return k;                             /* 返回节点数(不含 0xFF) */
}

/* 生成执行用的 route[]：规划出的完整路径去掉起点 from，只留后续目标节点序列(0xFF 收尾)。 */
uint8_t nav_build_route(uint8_t *route, uint8_t max_len,
                        const uint8_t *wps, uint8_t nwp)
{
    uint8_t path[NAV_MAX_PATH];    /* 暂存含起点的完整路径 */
    uint8_t n = nav_plan_waypoints(path, sizeof(path), wps, nwp);
    /* 先求出完整节点序列(含起点 from)，n=节点数 */
    uint8_t j = 0, i;              /* j=route 写入位置，i=path 遍历下标 */
    if (n == 0) return 0;          /* 规划失败直接返回 0 */
    for (i = 1; i < n && j < max_len; i++) route[j++] = path[i];
    /* 从下标 1 开始拷贝：跳过起点 path[0]，只留后续目标节点；缓冲满则停 */
    return j;                      /* 返回去掉起点后的节点数 */
}
