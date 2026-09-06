#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""更新 Keil 工程文件以反映新的目录结构"""

import re

# 读取原文件
with open('test1.uvprojx', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. 更新 IncludePath，添加 Mission 和 Navigation
old_include = '../Core/Inc;../Drivers/STM32F7xx_HAL_Driver/Inc;../Drivers/STM32F7xx_HAL_Driver/Inc/Legacy;../Middlewares/Third_Party/FreeRTOS/Source/include;../Middlewares/Third_Party/FreeRTOS/Source/CMSIS_RTOS;../Middlewares/Third_Party/FreeRTOS/Source/portable/RVDS/ARM_CM7/r0p1;../Drivers/CMSIS/Device/ST/STM32F7xx/Include;../Drivers/CMSIS/Include;../Motor;../Task;../Math;../USMAT;../Application;../Module;../../xunbao'
new_include = '../Core/Inc;../Drivers/STM32F7xx_HAL_Driver/Inc;../Drivers/STM32F7xx_HAL_Driver/Inc/Legacy;../Middlewares/Third_Party/FreeRTOS/Source/include;../Middlewares/Third_Party/FreeRTOS/Source/CMSIS_RTOS;../Middlewares/Third_Party/FreeRTOS/Source/portable/RVDS/ARM_CM7/r0p1;../Drivers/CMSIS/Device/ST/STM32F7xx/Include;../Drivers/CMSIS/Include;../Motor;../Task;../Math;../USMAT;../Application;../Mission;../Navigation;../Module;../../xunbao'
content = content.replace(old_include, new_include)

# 2. 更新 Application 组 - 移除已迁移的文件
# 找到 Application 组的起始位置
app_group_start = content.find('<GroupName>Application</GroupName>')
if app_group_start != -1:
    # 找到下一个 </Group> 的位置
    app_group_end = content.find('</Group>', app_group_start)

    # 提取 Application 组的内容
    app_group = content[app_group_start:app_group_end]

    # 移除已迁移到 Mission 的文件
    files_to_remove = [
        r'<File>.*?<FileName>barrier\.c</FileName>.*?</File>',
        r'<File>.*?<FileName>barrier\.h</FileName>.*?</File>',
        r'<File>.*?<FileName>config\.h</FileName>.*?</File>',
        # 移除已迁移到 Navigation 的文件
        r'<File>.*?<FileName>map\.c</FileName>.*?</File>',
        r'<File>.*?<FileName>map\.h</FileName>.*?</File>',
        r'<File>.*?<FileName>map_message\.c</FileName>.*?</File>',
        r'<File>.*?<FileName>map_message\.h</FileName>.*?</File>',
        r'<File>.*?<FileName>nav_planner\.c</FileName>.*?</File>',
        r'<File>.*?<FileName>nav_planner\.h</FileName>.*?</File>',
    ]

    for pattern in files_to_remove:
        app_group = re.sub(pattern, '', app_group, flags=re.DOTALL)

    # 替换回原文件
    content = content[:app_group_start] + app_group + content[app_group_end:]

# 3. 在 Application 组后添加 Mission 组
mission_group = r'''        </Group>
        <Group>
          <GroupName>Mission</GroupName>
          <Files>
            <File>
              <FileName>barrier.c</FileName>
              <FileType>1</FileType>
              <FilePath>..\Mission\barrier.c</FilePath>
            </File>
            <File>
              <FileName>barrier.h</FileName>
              <FileType>5</FileType>
              <FilePath>..\Mission\barrier.h</FilePath>
            </File>
            <File>
              <FileName>config.h</FileName>
              <FileType>5</FileType>
              <FilePath>..\Mission\config.h</FilePath>
            </File>
          </Files>
        </Group>
        <Group>
          <GroupName>Navigation</GroupName>
          <Files>
            <File>
              <FileName>map.c</FileName>
              <FileType>1</FileType>
              <FilePath>..\Navigation\map.c</FilePath>
            </File>
            <File>
              <FileName>map.h</FileName>
              <FileType>5</FileType>
              <FilePath>..\Navigation\map.h</FilePath>
            </File>
            <File>
              <FileName>map_message.c</FileName>
              <FileType>1</FileType>
              <FilePath>..\Navigation\map_message.c</FilePath>
            </File>
            <File>
              <FileName>map_message.h</FileName>
              <FileType>5</FileType>
              <FilePath>..\Navigation\map_message.h</FilePath>
            </File>
            <File>
              <FileName>nav_planner.c</FileName>
              <FileType>1</FileType>
              <FilePath>..\Navigation\nav_planner.c</FilePath>
            </File>
            <File>
              <FileName>nav_planner.h</FileName>
              <FileType>5</FileType>
              <FilePath>..\Navigation\nav_planner.h</FilePath>
            </File>
          </Files>'''

# 找到 Application 组结束的位置并插入新组
app_end = content.find('</Group>', content.find('<GroupName>Application</GroupName>'))
if app_end != -1:
    content = content[:app_end] + mission_group + content[app_end:]

# 写入新文件
with open('test1.uvprojx', 'w', encoding='utf-8') as f:
    f.write(content)

print("Keil 工程文件更新完成！")
