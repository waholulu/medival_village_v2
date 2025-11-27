# Project Medieval: Society - 技术设计与开发计划书 (v3.6)

**版本**: 3.6 (自治与职业系统增强版)
**核心理念**: 涌现式叙事 / 逻辑驱动 / 可观测性优先 (Observability First)
**主要变更**: 明确职业/技能熟练度系统，强化村民自主运行逻辑。

---

## 1. 技术栈与工程结构 (Tech Stack & Structure)

### 1.1 核心技术栈
*   **Language**: Python 3.10+ (利用 Type Hinting 和 Pattern Matching)
*   **Engine/Framework**: `pygame-ce` (Community Edition) - 性能优于原版 pygame。
*   **Math/Data**: `NumPy` - 用于高性能地图数据处理 (Terrain, Fog of War, Pathfinding weights)。
*   **UI**: `pygame-gui` 或 自研简单 IMGUI (Debug 用)。

### 1.2 推荐目录结构
```text
medival_village/
├── main.py                 # 入口文件
├── config/                 # 配置文件
│   └── balance.json        # 数值配置 (热重载)
├── assets/                 # 资源文件
│   ├── sprites/
│   └── fonts/
├── src/
│   ├── core/               # 核心引擎代码
│   │   ├── ecs.py          # EntityManager, Component, System 基类
│   │   ├── time_manager.py # 游戏循环与时间控制
│   │   └── event_bus.py    # 事件总线
│   ├── components/         # 所有 Component 定义
│   │   ├── data_components.py # 纯数据组件
│   │   ├── tags.py         # 标签组件 (如 IsPlayer, IsBuilding)
│   │   └── skill_component.py # [新增] 技能与熟练度
│   ├── systems/            # 所有 System 逻辑
│   │   ├── ai_system.py    # GOAP/行为树
│   │   ├── render_system.py# 渲染循环
│   │   ├── nature_system.py# 植物生长
│   │   └── economy_system.py # 价格与市场
│   ├── world/              # 地图与环境
│   │   ├── grid.py         # NumPy 地图数据封装
│   │   └── pathfinding.py  # A* / JPS 寻路
│   └── utils/              # 工具函数
│       ├── loader.py       # 资源加载
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
    *   Layers: 地形ID(0), 湿度(1), 移动消耗(2), 占用者ID(3)。
*   **Spatial Hash**: 
    *   用于查询 "半径 N 格内有哪些树?"。
    *   字典结构: `Dict[(chunk_x, chunk_y), List[EntityID]]`。

---

## 3. AI 与 行为逻辑 (The Brain)

### 3.1 职业与技能 (Profession & Skills) [新增]
村民不仅仅是通用的劳动力，他们有各自的专精。
*   **SkillComponent**:
    *   `skills: Dict[str, float]` (例如 `{"logging": 0.1, "farming": 0.8}`)。
    *   熟练度 (`0.0 - 1.0`) 影响动作速度和产出概率。
    *   **Learning**: 成功执行动作会微量增加对应技能熟练度。
*   **Auto-Assignment**:
    *   AI 会优先认领自己熟练度高的任务。
    *   如果没有熟练工，新手也会尝试去做 (效率低下)。

### 3.2 自主运行 (Autonomous Operation) [新增]
村民不需要玩家微操，他们基于自身需求和环境驱动。
*   **Self-Preservation Loop**:
    *   Hunger > 80? -> Find Food -> Eat.
    *   Tired? -> Find Bed -> Sleep.
*   **Work Loop**:
    *   Has Job? -> Execute Plan.
    *   Idle? -> Scan `JobBoard` (任务公告板) -> Claim Task based on Skill.
*   **Player Role**: 玩家是"市长"而非"上帝"，只负责划定区域 (`Zoning`) 和放置蓝图 (`Blueprint`)，不直接控制村民移动。

### 3.3 GOAP (Goal-Oriented Action Planning)
*   **State**: `{"has_wood": False, "near_stockpile": False}`
*   **Goal**: `{"in_stockpile": True, "inventory_empty": True}`
*   **Actions**:
    *   `ChopTree`: Pre: `has_axe`, Post: `has_wood`. Cost: `10 - skill_level * 5`.
    *   `MoveTo`: Pre: `None`, Post: `at_target`
    *   `StoreItem`: Pre: `has_wood`, `at_stockpile`, Post: `!has_wood`, `!at_stockpile`

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

### 4.3 上帝观察面板 (God/Observer Panel)
*   **功能**: 实时显示当前选中 Entity 的状态 (Hunger, Current Action, Inventory, **Skills**)。
*   **Global Stats**: 显示全图资源总量、总人口、平均幸福度。
*   **目的**: 迅速观察村民基本情况，记录变化。

---

## 5. 环境与经济 (Environment & Economy)

### 5.1 资源生命周期 (Sustainable Economy)
*   **Tree**: `Sapling` -> (Time) -> `Tree` -> (Chop) -> `Log` + `Stump` -> (Decay) -> `FertileSpot`
*   **Crop**: `Seed` -> (Water + Sun) -> `Growing` -> `Ripe` -> (Harvest) -> `Food`
*   **Durability**: 物品 (如斧头) 有耐久度，使用消耗，归零损毁。这保证了对原材料 (木头/石头) 的持续需求，形成闭环。

### 5.2 交互设计 (Interaction)
*   **Logging**: 从树木实体伐木 -> 获得木头。
*   **Farming**: 耕地 -> 播种 -> 等待 -> 收获。
*   **Building**: 消耗木头/石头 -> 生成建筑实体 (如房屋、仓库)。

### 5.3 集中式配置示例 (data/balance.json)
```json
{
  "global": {
    "tick_rate": 60,
    "pixels_per_unit": 32
  },
  "entities": {
    "villager": {
      "move_speed": 50.0,
      "max_health": 100,
      "sight_range": 10,
      "default_skills": {"logging": 0.1, "farming": 0.1}
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

### Phase 3: 任务与区域 (The Steward)
*   **任务**: 实现 `ZoneManager` (划区)。
*   **任务**: 实现 GOAP 基础框架 (Idle -> Find Work -> Do Work)。
*   **任务**: **实现技能系统与自动任务分发 (Auto-Assignment)**。
*   **任务**: 搬运逻辑 (Hauling)。

### Phase 4: 生存与配置 (The Survivor)
*   **任务**: 引入饥饿度与食物消耗。
*   **任务**: **实现自主生存循环 (Hunger -> Eat)**。
*   **任务**: **农业系统 (耕地、播种、生长、收获)**。
*   **任务**: **物品耐久系统**与工具消耗逻辑。

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

## 7. 风险与应对
1.  **Python 性能瓶颈**: 
    *   *应对*: 核心算法 (寻路、视野) 必须向量化 (NumPy) 或使用 Cython/C 扩展。避免在 System 循环中做重 IO 或 字符串操作。
2.  **AI 逻辑死循环**:
    *   *应对*: 限制 GOAP 搜索深度；为所有 AI 增加 "发呆 (Idle)" 的默认状态作为 Fallback；**利用日志系统定位死锁点**。
3.  **复杂度失控**:
    *   *应对*: 严格遵守 ECS 原则，Component 不写逻辑，System 不存状态。
