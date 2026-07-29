"""
配置模块，用于加载和管理配置信息
支持从配置文件和环境变量导入，环境变量优先级更高
"""
import os
import yaml
import logging
from pathlib import Path

# 获取logger
try:
    from panda_data.logger.config import logger
except ImportError:
    # 如果无法导入logger，创建一个基本的logger
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("config")

# 初始化配置变量config = None

def load_config():
    """加载配置文件，并从环境变量更新配置"""
    global config

    config = {}

    # 日志配置 Logging
    config["LOG_LEVEL"] = os.getenv("LOG_LEVEL", "DEBUG")
    config["log_file"] = os.getenv("LOG_FILE", "logs/panda_data.log")
    config["log_rotation"] = os.getenv("LOG_ROTATION", "1 MB")
    config["LOG_PATH"] = os.getenv("LOG_PATH", "~/log")

    # HTTP service integration
    config["DEFAULT_USERNAME"] = os.getenv("DEFAULT_USERNAME", "")
    config["DEFAULT_PASSWORD"] = os.getenv("DEFAULT_PASSWORD", "")

    config["HTTP_SERVICE_BASE_URL"] = os.getenv("HTTP_SERVICE_BASE_URL")
    config["HTTP_TIMEOUT"] = os.getenv("HTTP_TIMEOUT", "300")
    config["HTTP_MAX_RETRIES"] = os.getenv("HTTP_MAX_RETRIES", "3")
    config["HTTP_VERIFY_SSL"] = os.getenv("HTTP_VERIFY_SSL", "true")
    config["HTTP_PROXY_TYPE"] = os.getenv("HTTP_PROXY_TYPE")  # "http" or "https"
    config["HTTP_PROXY_HOST"] = os.getenv("HTTP_PROXY_HOST")
    config["HTTP_PROXY_PORT"] = os.getenv("HTTP_PROXY_PORT")
    config["HTTP_PROXY_USERNAME"] = os.getenv("HTTP_PROXY_USERNAME")
    config["HTTP_PROXY_PASSWORD"] = os.getenv("HTTP_PROXY_PASSWORD")
    config["HTTP_USE_GZIP"] = os.getenv("HTTP_USE_GZIP", "false")
    config["HTTP_DATA_FIELD"] = os.getenv("HTTP_DATA_FIELD", "data")
    config["HTTP_ABNORMAL_ENDPOINT"] = os.getenv("HTTP_ABNORMAL_ENDPOINT", "/abnormal")

    # Auth / token 持久化配置
    config["AUTH_TOKEN_DEFAULT_TTL"] = int(os.getenv("PANDA_AUTH_TOKEN_TTL", "14400"))
    config["AUTH_PROACTIVE_REFRESH_THRESHOLD"] = int(os.getenv("PANDA_AUTH_REFRESH_THRESHOLD", "1800"))

    # Legacy HTTP service config (for backward compatibility)
    config["JAVA_SERVICE_BASE_URL"] = os.getenv("JAVA_SERVICE_BASE_URL", "http://pandadata.pandaaiquant.com")
    config["JAVA_SERVICE_TIMEOUT"] = os.getenv("JAVA_SERVICE_TIMEOUT", "15")
    config["JAVA_SERVICE_MAX_RETRIES"] = os.getenv("JAVA_SERVICE_MAX_RETRIES", "3")
    config["JAVA_SERVICE_VERIFY_SSL"] = os.getenv("JAVA_SERVICE_VERIFY_SSL", "true")
    config["JAVA_SERVICE_DATA_FIELD"] = os.getenv("JAVA_SERVICE_DATA_FIELD", "data")
    config["JAVA_SERVICE_ABNORMAL_ENDPOINT"] = os.getenv("JAVA_SERVICE_ABNORMAL_ENDPOINT", "/abnormal")

    # 用户登录 endpoint/path（仍被 init_token / auth_manager 使用）
    config["JAVA_SERVICE_USER_ENDPOINT"] = os.getenv("JAVA_SERVICE_USER_ENDPOINT", "/dataUser")
    config["JAVA_SERVICE_USER_PATH_LOGIN"] = os.getenv("JAVA_SERVICE_USER_PATH_LOGIN", "/login")
    config["JAVA_SERVICE_TICK_USER_ENDPOINT"] = os.getenv("JAVA_SERVICE_TICK_USER_ENDPOINT", "/tickUser")
    config["JAVA_SERVICE_TICK_USER_PATH_LOGIN"] = os.getenv("JAVA_SERVICE_TICK_USER_PATH_LOGIN", "/login")

    # WebSocket 实时行情
    config["WS_LIVE_MARKET_URL"] = os.getenv("WS_LIVE_MARKET_URL", "ws://127.0.0.1:8180/pandaDataTick/ws/tick")

    return config


def get_config():
    """
    获取配置对象，如果配置未加载则先加载配置

    Returns:
        dict: 配置信息字典
    """
    global config
    if config is None:
        config = load_config()
    return config


# 初始加载配置
try:
    config = load_config()
    # logger.info(f"初始化配置成功: {config}")  # 已禁用初始化配置日志
except Exception as e:
    logger.error(f"初始化配置失败: {str(e)}")
    # 不在初始化时抛出异常，留到实际使用时再处理
