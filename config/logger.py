"""统一日志配置：控制台 + 文件双输出。

用法：
    from config.logger import logger
    logger.info("...")
    logger.error("...", exc_info=True)

日志文件默认写到 logs/smart_query.log（UTF-8），便于排查问题。
"""
import logging
import os

# 项目根目录 = config/ 的上一级
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(ROOT, "logs")
LOG_FILE = os.path.join(LOG_DIR, "smart_query.log")

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


def _setup_file_handler(logger: logging.Logger, filename: str) -> None:
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    fh = logging.FileHandler(filename, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(fh)


def get_logger(name: str = "smart_query") -> logging.Logger:
    """获取（或创建）一个已配置好控制台 + 文件输出的 logger。"""
    logger = logging.getLogger(name)
    if logger.handlers:  # 已初始化过，避免重复添加 handler
        return logger
    logger.setLevel(logging.DEBUG)

    # 控制台输出
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(console)

    # 文件输出（保留 DEBUG 级别，方便排障）
    try:
        _setup_file_handler(logger, LOG_FILE)
    except OSError as e:
        console.warning(f"日志文件创建失败，仅控制台输出：{e}")

    logger.propagate = False
    return logger


logger = get_logger()
