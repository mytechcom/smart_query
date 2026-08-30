"""pytest 全局配置：把项目根目录加入 sys.path，确保测试能导入 config / database 等包。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
