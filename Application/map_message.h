#ifndef __MAP_MESSAGE_H
#define __MAP_MESSAGE_H

#include "sys.h"
#include "map.h"

/* 红绿灯门区段：全长（door_set_pass_node 用全长；map_message 中 DOOR 条目用 全长/2） */
#define DOOR_LEN_N5N12  200
#define DOOR_LEN_N5N8   190
#define DOOR_LEN_N8N10  190
#define DOOR_LEN_N3N10  200
#define DOOR_LEN_N3N8   190
#define DOOR_LEN_N8N12  190

/* door_retreat 后退距离（与路段全长无关，按”起点→目标”方向命名） */
#define DOOR_RETREAT_N5N8   75
#define DOOR_RETREAT_N5N4   85
#define DOOR_RETREAT_N10N8  100
#define DOOR_RETREAT_N8N5   75

/* 门区段角度宏（与 DOOR_LEN_* 同名段，按”起点→目标”命名，范围 -180~+180）
 * 正向基准：N3→N8 / N5→N8；门两侧平行，N8→N12=N3N8、N8→N10=N5N8
 * 反向：加 180 或减 180，结果保持在 [-180, 180] */
#define ANGLE_N3N8   145
#define ANGLE_N5N8   35
#define ANGLE_N8N12  ANGLE_N3N8
#define ANGLE_N8N10  ANGLE_N5N8

#define ANGLE_REV(a)  (((a) >= 0) ? ((a) - 180) : ((a) + 180))
#define ANGLE_N8N3   ANGLE_REV(ANGLE_N3N8)   /* = -35 */
#define ANGLE_N8N5   ANGLE_REV(ANGLE_N5N8)   /* = -145 */
#define ANGLE_N12N8  ANGLE_REV(ANGLE_N8N12)  /* = -35 */
#define ANGLE_N10N8  ANGLE_REV(ANGLE_N8N10)  /* = -145 */


extern unsigned char ConnectionNum[54];
extern unsigned char Address[55];


#endif



