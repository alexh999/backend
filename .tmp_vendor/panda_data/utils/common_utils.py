import os


def _endpoint(base_path: str, path: str) -> str:
    return f"{base_path.rstrip('/')}/{path.lstrip('/')}"

# 添加公共方法
def build_endpoint(base_path: str, path: str) -> str:
    """
    构建完整的API端点URL

    Args:
        base_path (str): 路径
        path (str): API路径

    Returns:
        :param path:
        :param base_path:
        str: 完整的端点URL
    """
    return _endpoint(base_path, path)



def find_project_root(current_path: str, markers: list = None) -> str:
    """
    查找项目根目录

    Args:
        current_path: 当前路径
        markers: 标识项目根目录的文件或文件夹列表

    Returns:
        项目根目录路径
    """
    if markers is None:
        markers = ["pyproject.toml", "setup.py", "requirements.txt", ".git", "README.md"]

    current_dir = os.path.abspath(current_path)

    # 向上查找直到找到项目的标志文件或到达根目录
    while current_dir != os.path.dirname(current_dir):  # 防止无限循环
        for marker in markers:
            if os.path.exists(os.path.join(current_dir, marker)):
                return current_dir
        current_dir = os.path.dirname(current_dir)

    # 如果没找到标志文件，则返回默认的项目根目录
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
