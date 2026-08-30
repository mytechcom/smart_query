"""database 包：连接层、建表、Mock 数据。

为保证 `python database/init_db.py` 这类「直接运行子目录脚本」的方式，
也能正确导入项目根目录下的 config / database 等包，在此做一次 sys.path 引导（幂等）。
"""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
