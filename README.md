# Project Medieval: Society - 技术设计与开发计划书 (v3.7)

**版本**: 3.7 (Phase 3 完成版)
**核心理念**: 涌现式叙事 / 逻辑驱动 / 可观测性优先 (Observability First)
**主要变更**: 
- ✅ Phase 3 已完成：区域系统、任务系统、AI自主运行、物品搬运
- ✅ 区域可视化与设置模式指示器
- ✅ 技能系统与自动任务分发

---

## 1. 技术栈与工程结构 (Tech Stack & Structure)

### 1.1 核心技术栈
*   **Language**: Python 3.10+ (利用 Type Hinting 和 Pattern Matching)
*   **Engine/Framework**: `pygame-ce` (Community Edition) - 性能优于原版 pygame。
*   **Math/Data**: `NumPy` - 用于高性能地图数据处理 (Terrain, Fog of War, Pathfinding weights)。
*   **UI**: `pygame-gui` 或 自研简单 IMGUI (Debug 用)。

### 1.2 实际目录结构
```text
medival_village_v2/
├── main.py                 # 入口文件 (支持 --headless 模式)
├── config/                 # 配置文件
│   └── balance.json        # 数值配置 (热重载)
├── assets/                 # 资源文件
│   ├── sprites/
│   └── fonts/
├── docs/                   # 文档
│   └── HOW_TO_SET_ZONES.md # 区域设置指南
├── src/
│   ├── core/               # 核心引擎代码
│   │   ├── ecs.py          # EntityManager, Component, System 基类
│   │   ├── time_manager.py  # 游戏循环与时间控制
│   │   ├── config_manager.py # 配置管理器 (热重载)
│   │   └── input_manager.py  # 输入管理器
│   ├── components/         # 所有 Component 定义
│   │   ├── data_components.py # 数据组件 (Position, Movement, Action, Resource, Inventory, Item, Job)
│   │   ├── tags.py         # 标签组件 (IsPlayer, IsTree, IsSelectable, IsWalkable)
│   │   └── skill_component.py # 技能与熟练度组件
│   ├── systems/            # 所有 System 逻辑
│   │   ├── ai_system.py    # AI系统 (GOAP基础框架, 任务分配)
│   │   ├── action_system.py # 动作系统 (移动, 砍树, 拾取, 放置)
│   │   ├── render_system.py # 渲染循环 (含区域可视化)
│   │   ├── ui_system.py    # UI系统 (God Panel, Inspector, 区域模式指示器)
│   │   └── job_system.py   # 任务系统 (JobBoard)
│   ├── world/              # 地图与环境
│   │   ├── grid.py         # NumPy 地图数据封装 (含区域层)
│   │   ├── zone_manager.py # 区域管理器
│   │   └── pathfinding.py  # A* 寻路
│   └── utils/              # 工具函数
│       └── logger.py       # 结构化日志系统
└── tests/                  # 单元测试
```

---

## 2. 核心架构设计 (Core Architecture)

### 2.1 ECS 架构 (Entity-Component-System)
*   **Entity**: `int UID`。使用 `set` 或 `bitmap` 管理 ID 池。
*   **Component**: 纯数据类 (`@dataclass(slots=True)`), `slots` 优化内存占用。
*   **System**: 逻辑处理器。
    *   *查询优化*: 维护 `Archetype` 或 `Bitmask` 索引，避免每帧遍历所有实体。
    *   *示例*: `def process(self, dt: float): for entity, (pos, vel) in manager.get_components(Position, Velocity): ...`

### 2.2 全局管理器 (Global Managers)
*   **TimeManager**: 
    *   `delta_time`: 帧间隔 (秒)。
    *   `game_speed`: 0 (Pause), 1 (Normal), 5 (Fast)。
    *   `world_time`: 游戏内时间 (Day, Hour)。
    *   **Tick 与游戏时间关系 (Tick-to-Game-Time Mapping)**:
        *   **Tick Rate**: 默认 `60 ticks/秒` (可配置 `tick_rate`)
        *   **游戏日长度**: 默认 `60 秒 = 1 游戏天` (可配置 `day_length_seconds`)
        *   **计算公式**:
            *   `1 Tick = 1/tick_rate 秒` (例如: 1/60 ≈ 0.0167 秒)
            *   `1 游戏小时 = day_length_seconds / 24 秒` (例如: 60/24 = 2.5 秒)
            *   `1 游戏小时 = (day_length_seconds / 24) * tick_rate Ticks` (例如: 2.5 * 60 = 150 Ticks)
        *   **默认配置示例**:
            *   `tick_rate = 60`, `day_length_seconds = 60`:
                *   1 游戏天 = 60 秒 = 3600 Ticks
                *   1 游戏小时 = 2.5 秒 = 150 Ticks
                *   1 游戏分钟 = 0.0417 秒 = 2.5 Ticks
        *   **时间推进**: 每帧 `time_of_day += (delta_time / day_length_seconds) * 24.0`
        *   **用途**: 所有基于时间的系统 (饥饿度增长、作物生长、村民作息) 都应基于游戏时间而非Tick数，确保时间缩放时行为一致
*   **InputManager**: 将硬件输入 (Key_A, Mouse_Left) 映射为逻辑指令 (Command: "Build_Wall", "Select_Unit")。
*   **ConfigManager (Hot-Reload)**: 
    *   使用 `watchdog` 库监听 `data/balance.json`。
    *   **Safety**: 重载失败时回滚到上一次有效配置，并在控制台报错。
    *   **目的**: 方便测试与调试，防止数值过难导致"全村饿死"或过易导致无聊。
*   **Logger (Traceability)**: 
    *   **Event Log**: 记录主要游戏事件 ("Entity_1 chopped Tree_2", "Entity_3 starved to death")。
    *   **Format**: `[Time][Tick][Category] Message`。
    *   **Usage**: 方便追溯检查 AI 逻辑死锁或资源消失原因。

### 2.3 地图与空间 (Spatial Management)
*   **NumPy Grid**: 
    *   Shape: `(Width, Height, Layers)`
    *   Layers: 地形ID(0), 湿度(1), 移动消耗(2), 占用者ID(3), **区域ID(4)** ✅
*   **ZoneManager**: ✅
    *   管理区域标记与查询 (`mark_zone`, `get_nearest_zone_tile`)
    *   支持区域类型: `ZONE_STOCKPILE`, `ZONE_FARM`, `ZONE_RESIDENTIAL`
    *   区域可视化: 半透明覆盖层显示所有区域
*   **Spatial Hash**: 
    *   用于查询 "半径 N 格内有哪些树?"。
    *   字典结构: `Dict[(chunk_x, chunk_y), List[EntityID]]`。

---

## 3. AI 与 行为逻辑 (The Brain)

### 3.1 职业与技能 (Profession & Skills) ✅ [已实现]
村民不仅仅是通用的劳动力，他们有各自的专精。
*   **SkillComponent**: ✅
    *   `skills: Dict[str, float]` (例如 `{"logging": 0.1, "farming": 0.8}`)。
    *   熟练度 (`0.0 - 1.0`) 影响动作速度和产出概率。
    *   **Learning**: ✅ 成功执行动作会微量增加对应技能熟练度 (砍树 +0.01 logging)。
*   **Auto-Assignment**: ✅
    *   AI 会优先认领自己熟练度高的任务。
    *   如果没有熟练工，新手也会尝试去做 (效率低下)。

### 3.2 自主运行 (Autonomous Operation) ✅ [已实现]
村民不需要玩家微操，他们基于自身需求和环境驱动。
*   **JobSystem (任务公告板)**: ✅
    *   全局任务队列，支持 `chop` 和 `haul` 任务
    *   任务优先级与技能匹配
*   **AISystem (AI系统)**: ✅
    *   **Work Loop**: ✅
        *   Has Job? -> Execute Plan (Chop/Haul)
        *   Idle? -> Scan `JobBoard` -> Claim Task based on Skill
    *   **Job Execution**: ✅
        *   Chop: 移动到树 -> 砍树 -> 生成Log物品
        *   Haul: 移动到物品 -> 拾取 -> 移动到Stockpile -> 放置
*   **Self-Preservation Loop**: ⏳ (Phase 4)
    *   Hunger > 80? -> Find Food -> Eat.
    *   Tired? -> Find Bed -> Sleep.
*   **Daily Routine System**: ⏳ (Phase 4)
    *   **时间表驱动 (Schedule-Driven)**: 村民按照配置的时间表执行日常活动
    *   **需求驱动 (Needs-Driven)**: 紧急需求 (饥饿/疲劳) 会打断时间表
    *   **状态机**: `SLEEPING` -> `WAKING` -> `EATING` -> `WORKING` -> `SOCIALIZING` -> `SLEEPING`
    *   **季节适应**: 根据当前季节调整作息 (冬季早睡、夏季午休)
    *   **日夜适应**: 夜晚工作效率降低，优先安排睡眠和室内活动
*   **Player Role**: ✅ 玩家是"市长"而非"上帝"，只负责划定区域 (`Zoning`)，不直接控制村民移动。

### 3.3 GOAP (Goal-Oriented Action Planning) ✅ [基础实现]
*   **State**: `{"has_item": False, "at_stockpile": False}` ✅
*   **Goal**: `{"item_in_stockpile": True, "inventory_empty": True}` ✅
*   **Actions**: ✅
    *   `ChopTree`: Pre: `None`, Post: `has_log_on_ground`. Cost: `10 - skill_level * 5`. ✅
    *   `MoveTo`: Pre: `None`, Post: `at_target` ✅
    *   `Pickup`: Pre: `at_item`, Post: `has_item` ✅
    *   `StoreItem`: Pre: `has_item`, `at_stockpile`, Post: `!has_item`, `item_in_stockpile` ✅

### 3.4 传感器与社交 (Sensors & Social)
*   **VisionSensor**: 扫描周围 Entity。
*   **MemoryStream**: 记录最近感知到的资源位置 ("我在 (10,15) 看到过浆果") 和 社交互动 ("上次遇到 Entity_5 时他很生气")。
*   **Social System**: 
    *   村民闲暇时会聚集，交换 MemoryStream 中的信息 (如资源位置、八卦)。
    *   好感度影响交易价格或协作意愿。

---

## 4. 渲染管线 (Rendering Pipeline)

### 4.1 摄像机 (Camera)
*   **Coordinate Transform**: `Screen_Pos = (World_Pos - Camera_Pos) * Zoom + Screen_Center`
*   **Culling (剔除)**: 仅渲染摄像机矩形范围内的 Tile 和 Entity。

### 4.2 渲染层级 (Z-Ordering)
必须严格控制绘制顺序，避免穿模。
1.  **Layer 0**: 地形 (Grass, Dirt)
2.  **Layer 1**: 地面装饰 (Flowers, Roads)
3.  **Layer 2**: 物品/掉落物
4.  **Layer 3**: 角色 & 建筑 (根据 Y 轴坐标排序，实现伪 3D 遮挡关系)
5.  **Layer 4**: 天气/光照遮罩 (Multiply Blend Mode)
6.  **Layer 5**: UI/Debug Overlay (上帝观察面板)

### 4.3 上帝观察面板 (God/Observer Panel) ✅
*   **功能**: ✅ 实时显示当前选中 Entity 的状态 (Action, Inventory, Skills)。
*   **Global Stats**: ✅ 显示 FPS, 游戏时间, 摄像机位置, 缩放级别。
*   **Zone Mode Indicator**: ✅ 显示当前区域设置模式 (OFF/STOCKPILE/FARM/RESIDENTIAL)。
*   **Inspector Panel**: ✅ 显示选中格子的信息 (位置, 区域类型, 实体详情)。
*   **目的**: 迅速观察村民基本情况，记录变化。

### 4.4 区域可视化 ✅ [新增]
*   **Zone Overlay**: ✅ 在地图上用半透明颜色显示所有区域
    *   仓库区域: 橙黄色覆盖层
    *   农场区域: 绿色覆盖层
    *   住宅区域: 紫色覆盖层
*   **实时更新**: ✅ 区域设置后立即在地图上显示

---

## 5. 环境与经济 (Environment & Economy)

### 5.1 资源生命周期 (Sustainable Economy)
*   **Tree**: `Sapling` -> (Time) -> `Tree` -> (Chop) -> `Log` + `Stump` -> (Decay) -> `FertileSpot`
*   **Crop**: `Seed` -> (Water + Sun) -> `Growing` -> `Ripe` -> (Harvest) -> `Food`
*   **Durability**: 物品 (如斧头) 有耐久度，使用消耗，归零损毁。这保证了对原材料 (木头/石头) 的持续需求，形成闭环。

### 5.2 时间系统与环境变化 (Time & Environment) ⏳ [Phase 4]
*   **季节系统 (Seasonal System)**:
    *   **季节周期**: 每90游戏天为一个季节 (Spring/Summer/Autumn/Winter)
    *   **季节效果**:
        *   **春季 (Spring)**: 作物生长速度 +20%, 树木生长加速, 温度适中
        *   **夏季 (Summer)**: 作物生长速度 +30%, 但需要更多水分, 温度高 (村民工作效率 -10% 在正午)
        *   **秋季 (Autumn)**: 收获季节, 作物成熟速度 +10%, 温度适中, 最佳工作季节
        *   **冬季 (Winter)**: 作物停止生长, 树木生长暂停, 温度低 (村民需要更多食物保暖, 工作效率 -15%)
    *   **日夜循环 (Day-Night Cycle)**:
        *   基于 `TimeManager.time_of_day` (0-24小时)
        *   **白天 (06:00-20:00)**: 正常视野, 正常工作效率
        *   **夜晚 (20:00-06:00)**: 视野范围 -30%, 工作效率 -20% (除非有光源)
        *   **黎明/黄昏 (05:00-07:00, 19:00-21:00)**: 过渡期, 渐变效果
    *   **环境可视化**:
        *   季节色调覆盖层 (Seasonal Tint Overlay)
        *   日夜光照遮罩 (Day-Night Lighting Mask)
        *   天气粒子效果 (可选: 雨、雪、雾)

### 5.3 交互设计 (Interaction) ✅
*   **Logging**: ✅ 从树木实体伐木 -> 生成Log物品实体 -> 村民自动搬运到Stockpile。
*   **Hauling**: ✅ 村民自动拾取地面物品 -> 搬运到最近的Stockpile区域。
*   **Inventory**: ✅ 村民有库存系统，可携带物品。
*   **Farming**: ⏳ (Phase 4) 耕地 -> 播种 -> 等待 -> 收获。
*   **Building**: ⏳ (Phase 5) 消耗木头/石头 -> 生成建筑实体 (如房屋、仓库)。

### 5.4 集中式配置示例 (data/balance.json)

**Tick 与游戏时间换算 (基于以下配置)**:
*   `tick_rate = 60`: 每秒 60 个 Tick
*   `day_length_seconds = 600`: 1 游戏天 = 600 秒 (10 分钟)
*   **换算结果**:
    *   1 游戏小时 = 600/24 = 25 秒 = 1500 Ticks
    *   1 游戏天 = 600 秒 = 36000 Ticks
    *   1 游戏分钟 = 25/60 ≈ 0.417 秒 = 25 Ticks

```json
{
  "global": {
    "tick_rate": 60,
    "pixels_per_unit": 32
  },
  "simulation": {
    "day_length_seconds": 600,
    "season_length_days": 90,
    "starting_season": "spring"
  },
  "time": {
    "day_night": {
      "day_start_hour": 6.0,
      "day_end_hour": 20.0,
      "night_vision_reduction": 0.3,
      "night_work_efficiency": 0.8
    },
    "seasons": {
      "spring": {
        "crop_growth_multiplier": 1.2,
        "tree_growth_multiplier": 1.1,
        "temperature": 15.0,
        "work_efficiency": 1.0
      },
      "summer": {
        "crop_growth_multiplier": 1.3,
        "tree_growth_multiplier": 1.0,
        "temperature": 25.0,
        "work_efficiency": 0.9,
        "midday_rest_hours": [12.0, 14.0]
      },
      "autumn": {
        "crop_growth_multiplier": 1.1,
        "tree_growth_multiplier": 1.0,
        "temperature": 15.0,
        "work_efficiency": 1.1
      },
      "winter": {
        "crop_growth_multiplier": 0.0,
        "tree_growth_multiplier": 0.0,
        "temperature": 0.0,
        "work_efficiency": 0.85,
        "food_consumption_multiplier": 1.2
      }
    }
  },
  "entities": {
    "villager": {
      "move_speed": 50.0,
      "max_health": 100,
      "sight_range": 10,
      "default_skills": {"logging": 0.1, "farming": 0.1},
      "chop_speed": 5.0,
      "needs": {
        "hunger_per_hour": 2.0,
        "tiredness_per_hour_working": 5.0,
        "tiredness_per_hour_resting": -10.0,
        "sleep_hours_per_day": 8.0
      },
      "daily_schedule": {
        "wake_up": 6.0,
        "breakfast": [6.0, 8.0],
        "work_morning": [8.0, 12.0],
        "lunch": [12.0, 13.0],
        "work_afternoon": [13.0, 18.0],
        "dinner": [18.0, 19.0],
        "leisure": [19.0, 22.0],
        "sleep": [22.0, 6.0]
      }
    },
    "tree_oak": {
      "hp": 20,
      "growth_days": 5,
      "drops": {"log": [3, 5], "sapling": [0, 2]}
    },
    "tools": {
      "axe_stone": {
        "durability": 50,
        "efficiency": 1.0
      }
    }
  }
}
```

---

## 6. 开发路线图 (Roadmap) - [调整]

### Phase 0: 创世纪 (Genesis)
*   **任务**: 搭建 Python + Pygame-ce 框架，实现 ECS 基类，显示一个可移动的方块。
*   **任务**: **实现 Headless Mode (无头模式)**: 通过命令行参数 `--headless` 启动，禁用 Pygame 窗口渲染，直接在控制台输出 Tick 和 Entity 状态。
*   **关键产出**: `python main.py --headless` 能跑通，控制台每秒输出 `[Tick: 100] Entities: 5, FPS: 60`，且能自动运行简单的测试逻辑 (如移动一步)。

### Phase 1: 世界与观察者 (The World)
*   **任务**: 实现 NumPy TileMap 渲染，摄像机移动/缩放。
*   **任务**: **实现上帝观察面板 (UI Overlay)**，显示 FPS, 鼠标位置, 选中实体详情 (含技能)。
*   **任务**: **集成 Logger 系统**，确保控制台能输出结构化日志。

### Phase 2: 傀儡与交互 (The Golem)
*   **任务**: 实现点击移动 (A* Pathfinding)。
*   **任务**: 实现 `ResourceComponent` (树) 和 `ActionSystem` (砍树)。
*   **任务**: **接入 `balance.json` 热重载**，并在此时测试修改砍树速度。
*   **关键产出**: 右键点击树木，角色走过去，播放动画，树木消失，日志记录 "Chopped tree"。

### Phase 3: 任务与区域 (The Steward) ✅ [已完成]
*   **任务**: ✅ 实现 `ZoneManager` (划区)。
    *   ✅ 区域标记与查询 (`mark_zone`, `get_nearest_zone_tile`)
    *   ✅ 区域类型: Stockpile, Farm, Residential
    *   ✅ 区域可视化 (半透明覆盖层)
    *   ✅ 区域设置模式 (键盘快捷键 S/F/R, 右键放置)
*   **任务**: ✅ 实现 GOAP 基础框架 (Idle -> Find Work -> Do Work)。
    *   ✅ `JobSystem`: 全局任务队列
    *   ✅ `AISystem`: 任务分配与执行
    *   ✅ 支持 `chop` 和 `haul` 任务类型
*   **任务**: ✅ **实现技能系统与自动任务分发 (Auto-Assignment)**。
    *   ✅ `SkillComponent`: 技能熟练度系统
    *   ✅ 技能影响动作速度
    *   ✅ 技能学习 (执行动作增加熟练度)
    *   ✅ 基于技能的任务分配
*   **任务**: ✅ 搬运逻辑 (Hauling)。
    *   ✅ 自动生成Haul任务 (地面物品)
    *   ✅ 拾取 -> 移动到Stockpile -> 放置
    *   ✅ `InventoryComponent`: 库存系统
    *   ✅ `ItemComponent`: 物品实体
*   **关键产出**: ✅ 村民自动砍树 -> 生成Log -> 自动搬运到Stockpile，无需玩家干预。

### Phase 4: 生存与配置 (The Survivor)
*   **任务**: 引入饥饿度与食物消耗。
*   **任务**: **实现自主生存循环 (Hunger -> Eat)**。
*   **任务**: **农业系统 (耕地、播种、生长、收获)**。
*   **任务**: **物品耐久系统**与工具消耗逻辑。
*   **任务**: **时间系统扩展 (季节与日夜)**。
    *   实现季节系统: 春夏秋冬 (Spring, Summer, Autumn, Winter)
    *   季节影响: 温度、作物生长速度、资源生成率
    *   日夜循环: 基于 `TimeManager.time_of_day` 实现光照变化
    *   日夜影响: 村民工作效率、视野范围、睡眠需求
    *   季节可视化: 地图色调随季节变化 (春季绿色、夏季明亮、秋季金黄、冬季雪白)
    *   **时间系统实现要点**:
        *   所有基于时间的逻辑应使用 `TimeManager.time_of_day` (游戏小时) 而非 Tick 数
        *   需求增长 (饥饿、疲劳) 应基于游戏时间: `hunger += hunger_per_hour * (delta_time / day_length_seconds) * 24.0`
        *   作息时间表检查: `if 6.0 <= time_of_day < 8.0: state = EATING`
        *   季节计算: `current_season = (day // season_length_days) % 4`
        *   确保时间缩放 (`time_scale`) 时所有时间相关行为保持一致
*   **任务**: **村民完整每日行为逻辑 (Daily Routine System)**。
    *   **作息时间表 (Schedule)**:
        *   06:00-08:00: 起床、洗漱、早餐 (Eat)
        *   08:00-12:00: 工作时段 (Work: Chop/Haul/Farm)
        *   12:00-13:00: 午餐休息 (Eat, Social)
        *   13:00-18:00: 工作时段 (Work)
        *   18:00-19:00: 晚餐 (Eat)
        *   19:00-22:00: 休闲时段 (Social, Craft, Idle)
        *   22:00-06:00: 睡眠 (Sleep in Residential Zone)
    *   **需求驱动行为 (Needs-Based Behavior)**:
        *   `HungerComponent`: 饥饿度 (0-100), 随时间增长, 进食降低
        *   `TirednessComponent`: 疲劳度 (0-100), 工作增加, 睡眠降低
        *   `MoodComponent`: 心情值 (0-100), 影响工作效率, 受食物/休息/社交影响
    *   **优先级系统 (Priority System)**:
        *   紧急需求 (Hunger > 80, Tiredness > 90) 打断工作
        *   正常需求按时间表执行
        *   空闲时自动寻找工作 (JobBoard)
    *   **季节适应性 (Seasonal Adaptation)**:
        *   冬季: 需要更多食物保暖, 工作时间缩短 (寒冷)
        *   夏季: 需要更多水分, 中午休息时间延长 (炎热)
        *   春季/秋季: 最佳工作季节, 效率提升
    *   **行为状态机 (Behavior State Machine)**:
        *   `State.SLEEPING` -> `State.WAKING` -> `State.EATING` -> `State.WORKING` -> `State.SOCIALIZING` -> `State.SLEEPING`
        *   状态转换基于时间、需求阈值、环境条件

### Phase 5: 建筑与社会 (The Builder & Social)
*   **任务**: 实现建筑系统 (蓝图 -> 搬运材料 -> 建造)。
*   **任务**: 社交系统 (记忆交换, 聊天气泡)。
*   **任务**: 完善经济闭环 (工具损坏 -> 制造新工具 -> 消耗资源)。

### Phase 6: 传承与轮回 (Legacy & Cycle) [新增]
*   **任务**: **恋爱与家庭系统**: 基于好感度 (`Relationship`) 触发恋爱 -> 结婚 -> 组建家庭 (`HomeZone` 共享)。
*   **任务**: **生命周期管理**: 
    *   引入 `AgeComponent`: 幼年 -> 成年 -> 老年。
    *   生: 夫妻有概率生下子代 (继承父母部分技能潜力)。
    *   老: 老年村民移动速度变慢，体力下降。
    *   病/死: 寿命耗尽或生病死亡，变为 `Corpse` (需埋葬，否则引发瘟疫)。
*   **关键产出**: 观察到一个家族延续了三代人，老一代的遗产被下一代继承。

---

## 7. 游戏操作指南

### 7.1 基本控制
*   **摄像机移动**: W/A/S/D 或 方向键
*   **缩放**: 鼠标滚轮
*   **暂停**: Space
*   **时间速度**: 1 (正常), 2 (2x), 3 (5x)
*   **选择**: 左键点击实体/格子
*   **移动/交互**: 右键点击 (选中实体时)

### 7.2 区域设置
*   **S键**: 进入仓库 (Stockpile) 放置模式
*   **F键**: 进入农场 (Farm) 放置模式
*   **R键**: 进入住宅 (Residential) 放置模式
*   **X键**: 退出区域放置模式
*   **放置**: 在区域模式下右键点击地图
*   **查看**: 所有区域会以半透明颜色显示在地图上

### 7.3 观察面板
*   **右上角 (God Panel)**: FPS, 时间, 摄像机位置, 缩放, **区域模式状态**
*   **右下角 (Inspector)**: 选中格子的详细信息 (位置, 区域类型, 实体状态)

### 7.4 Headless 模式
*   运行: `python main.py --headless`
*   用途: 自动化测试, 无GUI运行
*   输出: 控制台日志, 测试结果

---

## 8. 风险与应对
1.  **Python 性能瓶颈**: 
    *   *应对*: 核心算法 (寻路、视野) 必须向量化 (NumPy) 或使用 Cython/C 扩展。避免在 System 循环中做重 IO 或 字符串操作。
2.  **AI 逻辑死循环**:
    *   *应对*: 限制 GOAP 搜索深度；为所有 AI 增加 "发呆 (Idle)" 的默认状态作为 Fallback；**利用日志系统定位死锁点**。✅ 已实现: 区域检查防止重复生成Haul任务。
3.  **复杂度失控**:
    *   *应对*: 严格遵守 ECS 原则，Component 不写逻辑，System 不存状态。✅ 当前架构保持清晰。

---

## 9. 当前实现状态总结

### ✅ 已完成 (Phase 0-3)
- [x] ECS 架构基础
- [x] 地图渲染与摄像机
- [x] 寻路系统 (A*)
- [x] 资源系统 (树木, 砍伐)
- [x] 技能系统
- [x] 任务系统 (JobSystem)
- [x] AI系统 (AISystem)
- [x] 区域系统 (ZoneManager)
- [x] 物品与库存系统
- [x] 搬运系统 (Hauling)
- [x] 区域可视化
- [x] UI系统 (God Panel, Inspector, Zone Mode Indicator)
- [x] Headless 模式

### ⏳ 进行中 / 计划中
- [ ] Phase 4: 生存系统 (饥饿, 食物, 农业)
- [ ] Phase 5: 建筑系统, 社交系统
- [ ] Phase 6: 生命周期, 家庭系统
