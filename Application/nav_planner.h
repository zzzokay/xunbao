#ifndef __NAV_PLANNER_H
#define __NAV_PLANNER_H
/*
 * 导航规划器：在 带权有向图 上做「边状态(line-graph) Dijkstra」最短路，
 * 支持「必经点(waypoint) + 多段最短 + 拼接」生成 route[]。
 * 只负责算 route[]（节点序列），不负责执行；执行层 Navigation()/getNextConnectNode 不动。
 *
 * 图数据来源：一张带 from 的自描述边表（单数据源），由调用方在启动时传给 nav_init()。
 * 权重模型也在本模块（见 NAV_W_* 与 nav_obs_penalty）。
 */
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* 单条有向边（自描述：含 from）。flag/speed 仅用于执行层同步，规划只读 step/angle/func */
typedef struct {
    uint8_t  from;
    uint8_t  to;
    uint32_t flag;
    float    angle;   /* 本段航向角（进入目标时的朝向） */
    uint16_t step;    /* 长度(cm) */
    float    speed;
    uint8_t  func;    /* barrier 枚举 */
} NavEdge;

#define NAV_MAX_NODES   64
#define NAV_MAX_EDGES   170
#define NAV_MAX_PATH    200   /* route[] / 单段最大节点数 */
#define NAV_MAX_TRANS   2040  /* 线路图最大连接数上限(供静态数组；越界则 nav_init 返回 -1) */

/* ---- 权重模型：cost(边) = NAV_W_STEP*step + NAV_W_OBS*obs_penalty(func)；转弯另加 NAV_W_TURN*|Δangle| ---- */
#define NAV_W_STEP  1.0f      /* 长度权重（cost 以 cm 计） */
#define NAV_W_TURN  0.6f      /* 每度航向变化代价（90°≈54cm、180°≈108cm） */
#define NAV_W_OBS   1.0f      /* 障碍惩罚缩放 */

/* 障碍/风险惩罚（等效 cm，按 map.h enum barriers 编号 1..19 索引）。 */
float nav_obs_penalty(unsigned char func);
/* 角度差归一化到 (-180,180]（度） */
float nav_need2turn(float a, float b);

/* 用边表初始化邻接与内部状态。返回 0 成功，-1 边数/节点数超限。 */
int nav_init(const NavEdge *edges, uint16_t n_edges, uint8_t n_nodes);

/* 最短路径：写入节点序列到 out，返回节点个数；无路返回 0。 */
uint8_t nav_shortest_path(uint8_t from, uint8_t to, uint8_t *out, uint8_t max_len);

/* 拼接：把 nsegs 段节点序列(以 0xFF 结尾)接进 route，去掉相邻段的重复连接点，0xFF 收尾。 */
uint8_t nav_stitch(uint8_t *route, uint8_t max_len,
                   const uint8_t *const *segs, const uint8_t *seg_lens, uint8_t nsegs);

/* 必经点规划：依次求 wps 相邻点间最短路并拼接。返回 route 节点数(不含 0xFF)。 */
uint8_t nav_plan_waypoints(uint8_t *route, uint8_t max_len,
                           const uint8_t *wps, uint8_t nwp);

/* 生成 route[]：把包含起点的规划路径去掉起点、余下目标序列(0xFF 收尾)。 */
uint8_t nav_build_route(uint8_t *route, uint8_t max_len,
                        const uint8_t *wps, uint8_t nwp);

/* 直接查一条边是否在图中(供外部校验连通性) */
int8_t nav_find_edge(uint8_t from, uint8_t to);

#ifdef __cplusplus
}
#endif

#endif
