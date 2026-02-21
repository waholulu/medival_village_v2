# Tests package for Medieval Village v2
import os
import sys

# 统一设置项目根目录到 sys.path，所有测试模块共享
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
