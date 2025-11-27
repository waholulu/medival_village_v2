# Project Medieval: Society - 技术设计与开发计划书 (v3.4)

**版本**: 3.4 (技术落地细化版)
**核心理念**: 涌现式叙事 / 逻辑驱动 / 可观测性优先 (Observability First)
**主要变更**: 增加工程目录结构、渲染管线设计、提前调试工具开发计划。

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
│   │   └── tags.py         # 标签组件 (如 IsPlayer, IsBuilding)
│   ├── systems/            # 所有 System 逻辑
│   │   ├── ai_system.py    # GOAP/行为树
│   │   ├── render_system.py# 渲染循环
│   │   └── nature_system.py# 植物生长
│   ├── world/              # 地图与环境
│   │   ├── grid.py         # NumPy 地图数据封装
│   │   └── pathfinding.py  # A* / JPS 寻路
│   └── utils/              # 工具函数
│       └── loader.py       # 资源加载
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

### 2.3 地图与空间 (Spatial Management)
*   **NumPy Grid**: 
    *   Shape: `(Width, Height, Layers)`
    *   Layers: 地形ID(0), 湿度(1), 移动消耗(2), 占用者ID(3)。
*   **Spatial Hash**: 
    *   用于查询 "半径 N 格内有哪些树?"。
    *   字典结构: `Dict[(chunk_x, chunk_y), List[EntityID]]`。

---

## 3. AI 与 行为逻辑 (The Brain)

### 3.1 GOAP (Goal-Oriented Action Planning)
不直接编写 "如何做"，而是定义 "目标" 和 "动作"。
*   **State**: `{"has_wood": False, "near_stockpile": False}`
*   **Goal**: `{"in_stockpile": True, "inventory_empty": True}`
*   **Actions**:
    *   `ChopTree`: Pre: `has_axe`, Post: `has_wood`
    *   `MoveTo`: Pre: `None`, Post: `at_target`
    *   `StoreItem`: Pre: `has_wood`, `at_stockpile`, Post: `!has_wood`, `!at_stockpile`

### 3.2 传感器 (Sensors)
AI 不直接读取全图数据，而是通过 Sensor 组件获取感知。
*   `VisionSensor`: 扫描周围 Entity。
*   `MemoryStream`: 记录最近感知到的资源位置 ("我在 (10,15) 看到过浆果")。

---

## 4. 渲染管线 (Rendering Pipeline) - [新增]

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
6.  **Layer 5**: UI/Debug Overlay

---

## 5. 环境与经济 (Environment & Economy)

### 5.1 资源生命周期
*   **Tree**: `Sapling` -> (Time) -> `Tree` -> (Chop) -> `Log` + `Stump` -> (Decay) -> `FertileSpot`
*   **Crop**: `Seed` -> (Water + Sun) -> `Growing` -> `Ripe` -> (Harvest) -> `Food`

### 5.2 集中式配置示例 (data/balance.json)
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
      "sight_range": 10
    },
    "tree_oak": {
      "hp": 20,
      "growth_days": 5,
      "drops": {"log": [3, 5], "sapling": [0, 2]}
    }
  }
}
```

---

## 6. 开发路线图 (Roadmap) - [调整]

### Phase 0: 创世纪 (Genesis)
*   **任务**: 搭建 Python + Pygame-ce 框架，实现 ECS 基类，显示一个可移动的方块。
*   **关键产出**: `main.py` 能跑通，黑底白块。

### Phase 1: 世界与观察者 (The World)
*   **任务**: 实现 NumPy TileMap 渲染，摄像机移动/缩放。
*   **任务**: **实现 Debug Info 面板 (FPS, 实体数量, 鼠标位置 Grid 坐标)** <- *提前到这里*。

### Phase 2: 傀儡与交互 (The Golem)
*   **任务**: 实现点击移动 (A* Pathfinding)。
*   **任务**: 实现 `ResourceComponent` (树) 和 `ActionSystem` (砍树)。
*   **关键产出**: 右键点击树木，角色走过去，播放动画，树木消失。

### Phase 3: 任务与区域 (The Steward)
*   **任务**: 实现 `ZoneManager` (划区)。
*   **任务**: 实现 GOAP 基础框架 (Idle -> Find Work -> Do Work)。
*   **任务**: 搬运逻辑 (Hauling)。

### Phase 4: 生存与配置 (The Survivor)
*   **任务**: 接入 `balance.json` 热重载。
*   **任务**: 引入饥饿度与食物消耗。
*   **任务**: 农业系统 (耕地、播种、生长)。

---

## 7. 风险与应对
1.  **Python 性能瓶颈**: 
    *   *应对*: 核心算法 (寻路、视野) 必须向量化 (NumPy) 或使用 Cython/C 扩展。避免在 System 循环中做重 IO 或 字符串操作。
2.  **AI 逻辑死循环**:
    *   *应对*: 限制 GOAP 搜索深度；为所有 AI 增加 "发呆 (Idle)" 的默认状态作为 Fallback。
3.  **复杂度失控**:
    *   *应对*: 严格遵守 ECS 原则，Component 不写逻辑，System 不存状态。
