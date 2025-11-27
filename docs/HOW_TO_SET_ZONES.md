# 如何设置区域 (Zone)

## 方法 1: 程序化设置 (在代码中)

```python
from src.world.grid import ZONE_STOCKPILE, ZONE_FARM, ZONE_RESIDENTIAL
from src.world.zone_manager import ZoneManager

# 假设你已经有了 zone_manager 和 grid
# 设置单个格子为仓库区域
zone_manager.mark_zone(x=20, y=10, zone_type=ZONE_STOCKPILE)

# 设置农场区域
zone_manager.mark_zone(x=30, y=15, zone_type=ZONE_FARM)

# 设置住宅区域
zone_manager.mark_zone(x=5, y=5, zone_type=ZONE_RESIDENTIAL)

# 清除区域 (设置为 ZONE_NONE)
from src.world.grid import ZONE_NONE
zone_manager.mark_zone(x=20, y=10, zone_type=ZONE_NONE)
```

## 方法 2: 通过玩家输入设置 (游戏中)

### 键盘快捷键:
- **S** - 切换仓库 (Stockpile) 放置模式
- **F** - 切换农场 (Farm) 放置模式  
- **R** - 切换住宅 (Residential) 放置模式
- **X** - 取消区域放置模式

### 操作步骤:
1. 按 **S** (或 F/R) 进入区域放置模式
2. 在目标位置**右键点击**放置区域
3. 按 **X** 退出放置模式

### 示例流程:
```
1. 按 S → 进入 Stockpile 模式
2. 右键点击 (20, 10) → 在该位置放置仓库区域
3. 按 X → 退出放置模式
```

## 可用的区域类型

定义在 `src/world/grid.py`:
- `ZONE_NONE = 0` - 无区域
- `ZONE_STOCKPILE = 1` - 仓库区域 (村民会将物品搬运到这里)
- `ZONE_FARM = 2` - 农场区域 (未来用于农业)
- `ZONE_RESIDENTIAL = 3` - 住宅区域 (未来用于居住)

## 查询区域

```python
# 获取某个格子的区域类型
zone_type = grid.get_zone(x, y)

# 查找最近的仓库区域
from src.world.grid import ZONE_STOCKPILE
nearest_stockpile = zone_manager.get_nearest_zone_tile((x, y), ZONE_STOCKPILE)
if nearest_stockpile:
    sx, sy = nearest_stockpile
    print(f"最近的仓库在: ({sx}, {sy})")
```

## 在 main.py 中的示例

查看 `main.py` 第 130-135 行，可以看到程序化设置的例子:
```python
# Setup Phase 3 Test Scenario
stockpile_pos = (20, 10)
zone_manager.mark_zone(stockpile_pos[0], stockpile_pos[1], ZONE_STOCKPILE)
Logger.info(f"Marked Stockpile at {stockpile_pos}")
```

