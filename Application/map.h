#ifndef __MAP_H
#define __MAP_H
#include "sys.h"

#include "config.h"     /* 所有开关/场地参数集中在这里 */
#include "map_message.h"

#define NO      	 (1<<0) 
#define DLEFT 		 (1<<1)				//左边横线
#define DRIGHT 		 (1<<2)				//右边横线   右半边天
#define CLEFT	     (1<<3)				//左边斜线  左分岔路 45°
#define CRIGHT		 (1<<4)				//右边斜线
#define MUL2SING	 (1<<5)				//多条变一条
#define MUL2MUL 	 (1<<6) 		    //多条变多条
#define AWHITE  	 (1<<7)			   	//全黑
					 
#define RESTMPUZ	 (1<<8)			    //陀螺仪校准
#define STOPTURN 	 (1<<9)				//停下来转弯
#define SLOWDOWN	 (1<<10)    		//减速

#define LEFT_LINE    (1<<11)   			//左循线(忽略右边白线干扰)
#define RIGHT_LINE	 (1<<12)   			//右循线

#define MCLEFT       (1<<13)
#define MCRIGHT      (1<<14)

#define DRIFT        (1<<15)    		//要用陀螺仪来转    		
#define L_follow     (1<<16)			//左循迹转弯（用来转弯
#define R_follow     (1<<17)			//右循迹转弯
#define MORELED      (1<<18)            //更多LED
#define NEAR_CENTER      (1<<19)			//中心就近跟踪
#define NOTURN       (1<<20)			//不转弯  

#define INGNORE      (1<<21)            //短直立景点后退
#define Temp_L		 (1<<22)			//临时左循迹
#define Temp_R		 (1<<23)			//临时右循迹
#define TEMP_NEAR_CENTER (1<<24)			//半程切换→中心就近跟踪

enum barriers {
	NONE = 1,
	UpStage,
	Bridge,
	Hill,
	LBHill,
	SM,
	View,
	View1,
	BACK,
	BSoutPole,
	QQB,
	BLBS,
	BLBL,
	DOOR,
	BHM,
	IGNORE,
	Special_node,
	DOOR1,
	UpStageHome
};

extern u8 route[100];
extern u8 door1route[100];
extern u8 door2route[100];
extern u8 door3_1route[50];
extern u8 door4route[100];
extern u8 door5route[100];
extern u8 door6route[100];
extern u8 door7route[100];
extern u8 door8route[100];
extern u8 door9route[100];
extern u8 door10route[100];
extern u8 door11route[100];
extern u8 door12route[100];

extern u8 rout_57[50];
extern u8 rout_58[50];
extern u8 rout_67[50];
extern u8 rout_68[50];
enum MapNode {	//MapNode
	S1, 	//0
	P1, 	//1
	N1,		//2
	B1,		//3
	B2,		//4
	B3,		//5
	N2,		//6
	P2,		//7
	S2,		//8
	P3,		//9
	N3, 	//10
	N4,		//11
	N5,		//12
	N6,		//13
	P4,		//14
	N7,		//15
	P6, 	//16
	B8, 	//17
	B9, 	//18
	N8, 	//19
	C1,		//20
	C2,		//21
	C3, 	//22
	N9, 	//23
	N10,	//24
	N12,	//25
	N13,	//26
	P5,		//27
	N14,	//28
	S3, 	//29
	S4,		//30
	N15,	//31
	S5,		//32
	C4,		//33
	C5, 	//34
	B4, 	//35
	B5, 	//36
	B6, 	//37
	B7, 	//38
	N16,	//39
	N18,	//40
	N19,	//41
	P7, 	//42
	N20,	//43
	N22,	//44
	C6,		//45
	C7, 	//46
	C8, 	//47
	C9,		//48
	P8,		//49
	N11,	//50
	G1,		//51
	B10,	//52	波动板节点：N14-C7段，位于板尾(C7侧)
	B11		//53	波动板节点：C8-C4段，位于板尾(C4侧)
};

/**************************************/
//结点信息
//flag 0位寻线方式：0左寻线，1右寻线
//flag 123位到达路口标志：	000最左边打到，001最右边打到，010左边数线，011右边数线，100线数由多变成一条	
//flag 45位，数线数目	
//flag 6位，寻线方式是否要切换，1需要切换，0不需要切换
//flag 7位	需要陀螺仪校正
//flag 8~11	
typedef struct _node{
	u8 nodenum;     //结点名称
	u32  flag;	    //结点标志位
	float angle;	//角度	
	u16	step;		//线长
	float speed;	//寻线速度
	u8 function;    //结点函数
}NODE;

extern NODE Node[132];
/*************************/
//flag 0位：1编码器清零请求，0清零完毕
//flag 1位：启动路口判断
//flag 2位：是否到达路口
typedef struct _nodes{
	NODE lastNode;		//边起点
	NODE nowNode;		//边终点 - 要到达的点
	NODE nextNode;		//下一条边的终点
}Nodes;

extern uint8_t Change_Route;
extern Nodes nodes;

/* 运行时阶段/事件标志 */
extern volatile uint8_t cross_event;
#define CROSS_EVENT_ARRIVED     (1<<0)  // 已到达节点
#define CROSS_EVENT_DOOR        (1<<1)  // 门结果就绪（红/绿灯统一）

/* 按一下跑一个节点调试：信号量/票计数（每按短一次累积，Navigation 每跑一条边-1，到0停下等票） */
extern volatile uint8_t nav_token;

struct Map_State {
	u8 point;
	u8 routetime;//第几次跑地图
};
extern struct Map_State map;
extern uint8_t Turn_Flag;
extern uint8_t mul2sing, sing2mul;

#define ROUTE_NOT_FOUND   0xFF   /* getNextConnectNode 查找失败哨兵值（Node 数组最大下标 131，0xFF 必越界） */

u8 getNextConnectNode(u8 nownode,u8 nextnode);
void Route_Error_Stop(u8 from, u8 to);   /* 兜底：查找路线失败直接停车（死循环，不返回） */
void mapInit(void);
void Navigation(void);
void map_function(u8 fun);
void select_speed(void);

extern u8 Clue1route[50];
extern u8 Clue2route[50];
extern u8 Clue3route[50];
extern u8 Clue4route[50];
extern u8 Clue5route[50];
extern u8 Clue6route[50];
extern u8 Clue7route[50];
extern u8 Clue8route[50];
extern u8 Clue9route[50];
extern u8 Clue10route[50];
extern u8 Clue11route[50];
extern u8 Clue12route[50];
extern u8 Clue13route[50];
extern u8 Clue14route[50];
extern u8 Clue15route[50];
extern u8 Clue16route[50];
extern u8 Clue17route[50];
extern u8 Clue18route[50];
extern u8 Clue19route[50];
extern u8 Clue20route[50];
extern u8 Clue21route[50];
extern u8 Clue22route[50];
extern u8 Clue23route[50];
extern u8 Clue24route[50];
extern u8 Clue25route[50];
extern u8 Clue26route[50];
extern u8 Clue27route[50];
extern u8 Clue28route[50];
extern u8 Clue29route[50];
extern u8 Clue30route[50];
extern u8 Clue31route[50];
extern u8 Clue32route[50];
extern u8 Clue33route[50];
extern u8 Clue34route[50];
extern u8 Clue35route[50];
extern u8 Clue36route[50];
extern u8 Clue37route[50];
extern u8 Clue38route[50];
extern u8 Clue39route[50];
extern u8 Clue40route[50];
extern u8 Clue41route[50];
extern u8 Clue42route[50];
extern u8 Clue43route[50];
extern u8 Clue44route[50];
extern u8 Clue45route[50];
extern u8 Clue46route[50];
extern u8 Clue47route[50];
extern u8 Clue48route[50];
extern u8 Clue49route[50];
extern u8 Clue50route[50];
extern u8 Clue51route[50];
extern u8 Clue52route[50];
extern u8 Clue53route[50];
extern u8 Clue54route[50];
extern u8 Clue55route[50];
extern u8 Clue56route[50];
extern u8 Clue57route[50];
extern u8 Clue58route[50];
extern u8 Clue59route[50];
extern u8 Clue60route[50];
extern u8 Clue61route[50];
extern u8 Clue62route[50];
extern u8 Clue63route[50];
extern u8 Clue64route[50];
extern u8 Clue65route[50];
extern u8 Clue66route[50];
extern u8 Clue67route[50];
extern u8 Clue68route[50];
extern u8 Clue69route[50];
extern u8 Clue70route[50];
extern u8 Clue71route[50];
extern u8 Clue72route[50];
extern u8 Clue73route[50];
extern u8 Clue74route[50];
extern u8 Clue75route[50];
extern u8 Clue76route[50];
extern u8 Clue77route[50];
extern u8 Clue78route[50];
extern u8 Clue79route[50];
extern u8 Clue80route[50];
extern u8 Clue1P4route[50];
extern u8 Clue2P4route[50];
extern u8 Clue3P4route[50];
extern u8 Clue4P4route[50];
extern u8 Clue5P4route[50];
extern u8 Clue6P4route[50];
extern u8 Clue7P4route[50];
extern u8 Clue8P4route[50];
extern u8 Clue9P4route[50];
extern u8 Clue10P4route[50];
extern u8 Clue11P4route[50];
extern u8 Clue12P4route[50];
extern u8 Clue13P4route[50];
extern u8 Clue14P4route[50];
extern u8 Clue15P4route[50];
extern u8 Clue16P4route[50];
extern u8 Clue17P4route[50];
extern u8 Clue18P4route[50];
extern u8 Clue19P4route[50];
extern u8 Clue20P4route[50];
extern u8 Clue21P4route[50];
extern u8 Clue22P4route[50];
extern u8 Clue23P4route[50];
extern u8 Clue24P4route[50];
extern u8 Clue25P4route[50];
extern u8 Clue26P4route[50];
extern u8 Clue27P4route[50];
extern u8 Clue28P4route[50];
extern u8 Clue29P4route[50];
extern u8 Clue30P4route[50];
extern u8 Clue31P4route[50];
extern u8 Clue32P4route[50];
extern u8 Clue33P4route[50];
extern u8 Clue34P4route[50];
extern u8 Clue35P4route[50];
extern u8 Clue36P4route[50];
extern u8 Clue37P4route[50];
extern u8 Clue38P4route[50];
extern u8 Clue39P4route[50];
extern u8 Clue40P4route[50];
extern u8 Clue41P4route[50];
extern u8 Clue42P4route[50];
extern u8 Clue43P4route[50];
extern u8 Clue44P4route[50];
extern u8 Clue45P4route[50];
extern u8 Clue46P4route[50];
extern u8 Clue47P4route[50];
extern u8 Clue48P4route[50];
extern u8 Clue49P4route[50];
extern u8 Clue50P4route[50];
extern u8 Clue51P4route[50];
extern u8 Clue52P4route[50];
extern u8 Clue53P4route[50];
extern u8 Clue54P4route[50];

extern uint8_t ErrorTimes[2];


extern u8 TempRoute[50];
#endif







