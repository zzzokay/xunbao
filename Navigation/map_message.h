#ifndef __MAP_MESSAGE_H
#define __MAP_MESSAGE_H

#include "config.h"     /* 所有开关/场地参数集中在这里 */
#include "sys.h"
#include "map.h"
#include "nav_planner.h"   /* NavEdge 类型、NAV_MAX_PATH */

#define NAV_EDGE_COUNT 124
extern const NavEdge NavEdgeTbl[NAV_EDGE_COUNT];   /* 单张自描述边表（唯一人工编辑源，见 map_message.c） */

/* Node[]/ConnectionNum[]/Address[] 已由 nav_planner.c 的 nav_init() 统一构建并导出 */

#endif
