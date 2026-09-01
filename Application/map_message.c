#include "map_message.h"
#include "chassis_api.h"

/*
 * 单张自描述边表 = 唯一人工编辑源（含 from/to/flag/angle/step/speed/function，均用原 map_message 宏/名）。
 * 启动时 nav_graph_init() 由本表自动构建执行层 Node[]/ConnectionNum/Address，无需手工同步这三个数组。
 * 增删边：编辑 NavEdgeTbl[] 并同步 map_message.h 的 NAV_EDGE_COUNT；增删节点：还需在 map.h MapNode 枚举加名。
 */

const NavEdge NavEdgeTbl[NAV_EDGE_COUNT] = {
    { S1, N3, CLEFT|DLEFT|MUL2MUL, 160, 216, SPEED4, NONE },  /* S1->N3 */
    { P1, N1, CRIGHT|LEFT_LINE, 180, 36, SPEED0, NONE },  /* P1->N1 */
    { N1, P1, RIGHT_LINE, 0, 48, SPEED2, UpStage },  /* N1->P1 */
    { N1, B1, RESTMPUZ|LEFT_LINE, 180, 24, 15, Bridge },  /* N1->B1 */
    { N1, B2, NO, 135, 36, 15, Hill },  /* N1->B2 */
    { B1, N1, RIGHT_LINE|MCLEFT|CLEFT|DLEFT, 0, 6, SPEED2, NONE },  /* B1->N1 */
    { B1, N2, LEFT_LINE|CRIGHT|MUL2SING, 180, 40, SPEED0, NONE },  /* B1->N2 */
    { B2, N1, LEFT_LINE|CRIGHT|STOPTURN, -40, 30, SPEED0, NONE },  /* B2->N1 */
    { B2, N4, DLEFT|CLEFT|LEFT_LINE, 140, 12, SPEED2, NONE },  /* B2->N4 */
    { B3, N2, RIGHT_LINE|CLEFT|STOPTURN, -150, 40, SPEED0, NONE },  /* B3->N2 */
    { B3, N4, CLEFT, 30, 52, SPEED1, NONE },  /* B3->N4 */
    { N2, B1, RESTMPUZ|RIGHT_LINE, 0, 24, SPEED0, Bridge },  /* N2->B1 */
    { N2, B3, NO, 30, 36, SPEED1, BLBS },  /* N2->B3 */
    { N2, P2, LEFT_LINE, 180, 12, 15, UpStageHome },  /* N2->P2 */
    { P2, N2, CLEFT|RIGHT_LINE, 0, 12, SPEED1, NONE },  /* P2->N2 */
    { S2, N6, MUL2MUL|RIGHT_LINE|CLEFT|STOPTURN, 45, 120, SPEED4, NONE },  /* S2->N6 */
    { P3, N3, DRIGHT|RIGHT_LINE, 180, 246, SPEED4, NONE },  /* P3->N3 */
    { N3, S1, NO, -25, 216, SPEED4, View },  /* N3->S1 */
    { N3, P3, LEFT_LINE, 0, 320, SPEED4, UpStage },  /* N3->P3 */
    { N3, N4, CLEFT|LEFT_LINE|Temp_R, 180, 130, SPEED3, NONE },  /* N3->N4 */
    { N3, N8, DRIGHT|DLEFT|NEAR_CENTER, ANGLE_N3N8, DOOR_LEN_N3N8/2, SPEED1, DOOR },  /* N3->N8 */
    { N3, N10, CLEFT|DLEFT|RIGHT_LINE, 90, DOOR_LEN_N3N10, SPEED3, NONE },  /* N3->N10 */
    { N4, B2, NO, -40, 40, SPEED1, Hill },  /* N4->B2 */
    { N4, B3, NEAR_CENTER, -140, 84, 15, BLBS },  /* N4->B3 */
    { N4, N3, DLEFT|TEMP_NEAR_CENTER|LEFT_LINE, 0, 108, SPEED3, NONE },  /* N4->N3 */
    { N4, N5, MUL2SING|RIGHT_LINE|Temp_L, 180, 130, SPEED3, NONE },  /* N4->N5 */
    { N5, N4, RIGHT_LINE|Temp_L|MUL2SING, 0, 84, SPEED3, NONE },  /* N5->N4 */
    { N5, N6, MUL2SING|CLEFT|CRIGHT, 180, 150, SPEED2, NONE },  /* N5->N6 */
    { N5, N8, CLEFT| DLEFT | DRIGHT, ANGLE_N5N8, DOOR_LEN_N5N8/2, SPEED1, DOOR },  /* N5->N8 */
    { N5, N12, DLEFT | LEFT_LINE, 90, DOOR_LEN_N5N12/2, SPEED1, DOOR },  /* N5->N12 */
    { N6, S2, NO, -140, 120, SPEED4, View },  /* N6->S2 */
    { N6, N5, DLEFT|RIGHT_LINE, 0, 114, SPEED3, NONE },  /* N6->N5 */
    { N6, P4, NEAR_CENTER, 180, 50, SPEED1, UpStage },  /* N6->P4 */
    { N6, C1, CLEFT|DLEFT, 50, 180, SPEED1, NONE },  /* N6->C1 */
    { P4, N6, LEFT_LINE|MUL2SING|NOTURN, 0, 66, SPEED3, NONE },  /* P4->N6 */
    { N7, P6, NO, 90, 24, 15, UpStage },  /* N7->P6 */
    { N7, B8, LEFT_LINE|NOTURN, 10, 1, SPEED1, QQB },  /* N7->B8 */
    { P6, N7, DLEFT|DRIGHT|AWHITE|STOPTURN, -90, 18, SPEED1, NONE },  /* P6->N7 */
    { B8, N9, MUL2MUL|MUL2SING|STOPTURN|CLEFT, 160, 1, 15, NONE },  /* B8->N9 */
    { B9, N7, DLEFT|CLEFT|STOPTURN, -80, 1, SPEED1, NONE },  /* B9->N7 */
    { N8, N3, CLEFT|CRIGHT|NEAR_CENTER|MUL2MUL, ANGLE_N8N3, DOOR_LEN_N3N8/2, SPEED0, DOOR },  /* N8->N3 */
    { N8, N5, STOPTURN|CLEFT, ANGLE_N8N5, DOOR_LEN_N5N8/2, SPEED0, DOOR },  /* N8->N5 */
    { N8, N10, MUL2MUL|NEAR_CENTER, ANGLE_N8N10, DOOR_LEN_N8N10, SPEED4, NONE },  /* N8->N10 */
    { N8, N12, MUL2MUL, ANGLE_N8N12, DOOR_LEN_N8N12, SPEED3, NONE },  /* N8->N12 */
    { C1, N6, CRIGHT, -50, 180, SPEED1, NONE },  /* C1->N6 */
    { C1, C2, DRIGHT|DLEFT, 125, 36, SPEED1, NONE },  /* C1->C2 */
    { C2, C1, CLEFT, 170, 185, SPEED1, NONE },  /* C2->C1 */
    { C2, N13, DRIGHT|DLEFT|CLEFT|CRIGHT|DRIFT, 120, 24, SPEED1, NONE },  /* C2->N13 */
    { C3, N9, RIGHT_LINE|MUL2SING|NOTURN, 180, 24, SPEED1, NONE },  /* C3->N9 */
    { C3, N14, DLEFT|MCLEFT|CLEFT, 90, 0, SPEED0, NONE },  /* C3->N14 */
    { N9, B9, LEFT_LINE|NOTURN, -170, 0, SPEED1, QQB },  /* N9->B9 */
    { N9, C3, DLEFT|LEFT_LINE, 0, 48, SPEED2, NONE },  /* N9->C3 */
    { N9, N10, DLEFT|DRIGHT|NEAR_CENTER, 180, 180, SPEED3, NONE },  /* N9->N10 */
    { N10, N3, DRIGHT|DLEFT|RIGHT_LINE|STOPTURN, -90, DOOR_LEN_N3N10/2, SPEED1, DOOR },  /* N10->N3 */
    { N10, N8, CLEFT|CRIGHT|DLEFT|DRIGHT, ANGLE_N10N8, DOOR_LEN_N8N10, SPEED3, NONE },  /* N10->N8 */
    { N10, N9, LEFT_LINE|CRIGHT|MUL2SING|STOPTURN, 0, 156, SPEED3, NONE },  /* N10->N9 */
    { N10, N12, DRIGHT|RIGHT_LINE, -180, 264, SPEED1, NONE },  /* N10->N12 */
    { N10, N15, DRIGHT|STOPTURN, 90, 24, SPEED2, NONE },  /* N10->N15 */
    { N10, N11, NO, 180, 70, SPEED1, SM },  /* N10->N11 */
    { N12, N5, AWHITE|RIGHT_LINE|RESTMPUZ, -90, 222, SPEED4, NONE },  /* N12->N5 */
    { N12, N8, CRIGHT|DLEFT, ANGLE_N12N8, 180, 60, 1 },  /* N12->N8 */
    { N12, N13, CLEFT|CRIGHT|MUL2SING|NEAR_CENTER, 180, 80, SPEED4, NONE },  /* N12->N13 */
    { N12, P5, NEAR_CENTER, 180, 288, 64, UpStage },  /* N12->P5 */
    { N12, N16, DRIGHT|STOPTURN, 90, 18, SPEED0, NONE },  /* N12->N16 */
    { N12, N11, LEFT_LINE, 0, 70, SPEED1, SM },  /* N12->N11 */
    { N13, C2, NONE, NONE, NONE, NONE, NONE },  /* N13->C2 (原表退化桩，保留) */
    { N13, N12, DLEFT|DRIGHT|NEAR_CENTER, 0, 72, SPEED3, NONE },  /* N13->N12 */
    { N13, P5, NEAR_CENTER, 180, 90, SPEED3, UpStage },  /* N13->P5 */
    { N13, N18, CRIGHT|CLEFT, 45, 144, SPEED3, NONE },  /* N13->N18 */
    { P5, N13, MUL2SING|CLEFT|CRIGHT|NEAR_CENTER, 0, 60, SPEED2, NONE },  /* P5->N13 */
    { N14, C3, DRIGHT|STOPTURN, -90, 18, SPEED0, NONE },  /* N14->C3 */
    { N14, S3, NO, -180, 2, SPEED1, View1 },  /* N14->S3 */
    { N14, B10, NO, 90, 100, SPEED3, BLBL },  /* N14->B10 */
    { S3, N14, INGNORE, 180, 2, -SPEED0, BACK },  /* S3->N14 */
    { S4, N15, INGNORE, 0, 1, -SPEED0, BACK },  /* S4->N15 */
    { N15, N10, DLEFT|DRIGHT, -90, 24, SPEED2, NONE },  /* N15->N10 */
    { N15, S4, NO, 0, 1, SPEED1, View1 },  /* N15->S4 */
    { N15, C5, DLEFT, 90, 36, SPEED2, NONE },  /* N15->C5 */
    { S5, N16, INGNORE, 0, 1, -SPEED0, BACK },  /* S5->N16 */
    { C4, N20, CRIGHT|MUL2MUL, 155, 170, SPEED4, NONE },  /* C4->N20 */
    { C4, B11, NO, 90, 90, SPEED2, BLBL },  /* C4->B11 */
    { C5, N15, DLEFT|STOPTURN, -90, 36, SPEED2, NONE },  /* C5->N15 */
    { C5, N18, DLEFT|CLEFT, 180, 324, SPEED4, NONE },  /* C5->N18 */
    { B4, C5, DRIGHT, 0, 174, SPEED1, NONE },  /* B4->C5 */
    { B4, N18, DLEFT|CLEFT|RESTMPUZ, 180, 120, SPEED1, NONE },  /* B4->N18 */
    { B5, N18, DRIGHT, 0, 12, SPEED1, NONE },  /* B5->N18 */
    { B5, N19, DRIGHT, 180, LEN_B5N19, SPEED3, NONE },  /* B5->N19 */
    { B6, N20, CRIGHT|DRIGHT|RESTMPUZ|LEFT_LINE, 0, 36, SPEED2, NONE },  /* B6->N20 */
    { B6, N22, DRIGHT|RESTMPUZ, 180, 36, SPEED3, NONE },  /* B6->N22 */
    { B7, N22, DLEFT|RESTMPUZ, 0, 84, SPEED3, NONE },  /* B7->N22 */
    { B7, C6, DLEFT, 180, LEN_B7C6, SPEED3, NONE },  /* B7->C6 */
    { N16, N12, DLEFT|DRIGHT, -90, 20, SPEED2, NONE },  /* N16->N12 */
    { N16, S5, NO, 0, 1, SPEED1, View1 },  /* N16->S5 */
    { N16, N18, DRIGHT|RIGHT_LINE|STOPTURN, 90, 18, SPEED0, NONE },  /* N16->N18 */
    { N18, C5, DRIGHT|CRIGHT, 0, 324, SPEED3, NONE },  /* N18->C5 */
    { N18, B5, RIGHT_LINE, 180, LEN_N18B5, SPEED1, Hill },  /* N18->B5 */
    { N18, N16, DLEFT|CLEFT|STOPTURN, -90, 20, SPEED2, NONE },  /* N18->N16 */
    { N19, B5, NO, 0, 54, SPEED3, Hill },  /* N19->B5 */
    { N19, C6, DRIGHT|STOPTURN, 90, 24, SPEED2, NONE },  /* N19->C6 */
    { P7, C9, DRIGHT, 0, 180, SPEED25, NONE },  /* P7->C9 */
    { P7, G1, NO, 0, 144, SPEED3, NONE },  /* P7->G1 */
    { N20, C4, CLEFT|MCLEFT|STOPTURN|RIGHT_LINE, -35, 180, SPEED4, NONE },  /* N20->C4 */
    { N20, B6, NO, 180, 24, SPEED1, SM },  /* N20->B6 */
    { N20, P8, NEAR_CENTER|RESTMPUZ, 0, 12, SPEED0, BHM },  /* N20->P8 */
    { N22, B6, RESTMPUZ, 0, 18, SPEED1, SM },  /* N22->B6 */
    { N22, B7, NO, 180, LEN_N22B7, SPEED2, Hill },  /* N22->B7 */
    { N22, C9, DLEFT, 90, 18, SPEED0, NONE },  /* N22->C9 */
    { C6, B7, RESTMPUZ, 0, 72, SPEED25, Hill },  /* C6->B7 */
    { C6, N19, DLEFT, -90, 30, SPEED3, NONE },  /* C6->N19 */
    { C7, C8, DLEFT|STOPTURN, 180, 108, SPEED25, NONE },  /* C7->C8 */
    { C7, B10, NO, -90, 45, SPEED1, BLBL },  /* C7->B10 */
    { C8, C7, DRIGHT|CRIGHT|STOPTURN, 0, 96, SPEED2, NONE },  /* C8->C7 */
    { C8, B11, NO, -90, 30, SPEED3, BLBL },  /* C8->B11 */
    { C9, P7, NONE, 180, 260, SPEED2, BSoutPole },  /* C9->P7 */
    { C9, N22, DLEFT|DRIGHT|STOPTURN, -90, 18, SPEED0, NONE },  /* C9->N22 */
    { C9, G1, NO, 180, 144, SPEED3, NONE },  /* C9->G1 */
    { P8, N20, MCLEFT|RIGHT_LINE|STOPTURN, 180, 12, SPEED0, NONE },  /* P8->N20 */
    { N11, N10, LEFT_LINE|DLEFT, 0, 60, SPEED25, NONE },  /* N11->N10 */
    { N11, N12, RIGHT_LINE|AWHITE|DRIGHT, 180, 60, SPEED3, NONE },  /* N11->N12 */
    { G1, P7, RESTMPUZ, 180, 144, SPEED3, BSoutPole },  /* G1->P7 */
    { G1, C9, DRIGHT|CRIGHT, 0, 144, SPEED25, NONE },  /* G1->C9 */
    { B10, N14, DRIGHT|STOPTURN, -90, 100, SPEED1, NONE },  /* B10->N14 */
    { B10, C7, DLEFT|CLEFT, 90, 10, SPEED1, NONE },  /* B10->C7 */
    { B11, C4, CRIGHT, -90, 50, SPEED2, NONE },  /* B11->C4 */
    { B11, C8, DRIGHT|CRIGHT, 90, 10, SPEED1, NONE },  /* B11->C8 */
};

/* 启动时：从本表自动构建执行层 CSR（Node[]/ConnectionNum/Address）。 */
void nav_graph_init(void)
{
    unsigned short cnt[64] = {0}, cur[64] = {0};
    unsigned short i, v;
    for (i = 0; i < NAV_EDGE_COUNT; i++) if (NavEdgeTbl[i].from < 54) cnt[NavEdgeTbl[i].from]++;
    Address[0] = 0;
    for (v = 0; v < 54; v++) ConnectionNum[v] = (unsigned char)cnt[v];
    for (v = 0; v < 54; v++) Address[v+1] = Address[v] + (unsigned char)cnt[v];
    for (v = 0; v < 54; v++) cur[v] = Address[v];
    for (i = 0; i < NAV_EDGE_COUNT; i++) {
        unsigned char f = NavEdgeTbl[i].from;
        if (f < 54) {
            unsigned short p = cur[f]++;
            Node[p].nodenum = NavEdgeTbl[i].to;
            Node[p].flag     = NavEdgeTbl[i].flag;
            Node[p].angle    = NavEdgeTbl[i].angle;
            Node[p].step     = NavEdgeTbl[i].step;
            Node[p].speed    = NavEdgeTbl[i].speed;
            Node[p].function = NavEdgeTbl[i].func;
        }
    }
}

/* 执行层图数据（空全局，由 nav_graph_init 填充） */
NODE Node[132];
uint8_t ConnectionNum[54];
uint8_t Address[55];
