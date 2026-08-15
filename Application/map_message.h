#ifndef __MAP_MESSAGE_H
#define __MAP_MESSAGE_H

#include "sys.h"
#include "map.h"

/* 红绿灯门区段：全长（door_set_pass_node 用全长；map_message 中 DOOR 条目用 全长/2） */
#define DOOR_LEN_N5N12  200
#define DOOR_LEN_N5N8   160
#define DOOR_LEN_N8N10  160
#define DOOR_LEN_N3N10  200
#define DOOR_LEN_N3N8   160
#define DOOR_LEN_N8N12  160

/* door_retreat 后退距离（与路段全长无关，按“起点→目标”方向命名） */
#define DOOR_RETREAT_N5N8   64
#define DOOR_RETREAT_N5N4   64
#define DOOR_RETREAT_N10N8  80
#define DOOR_RETREAT_N8N5   65


extern unsigned char ConnectionNum[52];
extern unsigned char Address[53];


#endif



