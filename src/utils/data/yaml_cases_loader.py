from pathlib import Path
import yaml
from typing import Any, Dict, List


class InvalidYamlFormatError(ValueError):
    """YAML 格式验证失败异常"""
    pass


def load_yaml_file(file_path: Path) -> Dict[str, List[Dict[str, Any]]]:
    """
    加载并严格验证 YAML 测试数据（单一职责：仅处理文件加载与验证）

    :param file_path: YAML 文件的完整绝对路径
    :return: 统一结构 {group_name: [case_dict1, case_dict2, ...]}
    :raises FileNotFoundError: 文件不存在或非文件
    :raises InvalidYamlFormatError: 格式验证失败
    """
    if not file_path.exists():
        raise FileNotFoundError(f"YAML 文件不存在: {file_path}")

    if not file_path.is_file():
        raise FileNotFoundError(f"路径不是文件: {file_path}")

    # 安全性：限制文件大小（防 DoS）
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    if file_path.stat().st_size > MAX_FILE_SIZE:
        raise InvalidYamlFormatError(f"YAML 文件过大 (>10MB): {file_path}")

    # 读取并解析 YAML
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            raw_data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise InvalidYamlFormatError(f"YAML 语法错误 in {file_path}:\n{e}")
    except UnicodeDecodeError as e:
        raise InvalidYamlFormatError(f"YAML 文件编码错误（需 UTF-8）in {file_path}:\n{e}")

    if raw_data is None:
        return {}

    if not isinstance(raw_data, dict):
        raise InvalidYamlFormatError(
            f"YAML 根必须是字典，当前类型: {type(raw_data).__name__}\n"
            f"文件: {file_path}"
        )

    # 严格验证并标准化
    normalized_data: Dict[str, List[Dict[str, Any]]] = {}

    for group_name, value in raw_data.items():
        _validate_group_value(group_name, value, file_path)
        normalized_data[group_name] = [value] if isinstance(value, dict) else value

    return normalized_data


def _validate_group_value(group_name: str, value: Any, file_path: Path) -> None:
    """验证单个测试组的值格式"""
    if isinstance(value, dict):
        if not value:
            _raise_format_error(
                group_name=group_name,
                message=(
                    f"组 '{group_name}' 的值不能为空字典。\n"
                    "  ❌ 禁止格式:\n"
                    f"      {group_name}: {{}}\n"
                    "  ✅ 正确格式:\n"
                    f"      {group_name}:\n"
                    "        field: value"
                ),
                file_path=file_path
            )
        return

    if isinstance(value, list):
        if not value:
            _raise_format_error(
                group_name=group_name,
                message=(
                    f"组 '{group_name}' 的值不能为空列表。\n"
                    "  ❌ 禁止格式:\n"
                    f"      {group_name}: []\n"
                    "  ✅ 正确格式:\n"
                    f"      {group_name}:\n"
                    "        - field1: value1\n"
                    "          field2: value2"
                ),
                file_path=file_path
            )

        for idx, item in enumerate(value):
            if not isinstance(item, dict):
                _raise_format_error(
                    group_name=group_name,
                    message=(
                        f"组 '{group_name}' 的第 {idx + 1} 个元素必须是字典，"
                        f"当前类型: {type(item).__name__}，值: {repr(item)}\n"
                        "  ❌ 禁止格式:\n"
                        f"      {group_name}:\n"
                        f"        - {repr(item)}\n"
                        "  ✅ 正确格式:\n"
                        f"      {group_name}:\n"
                        "        - field1: value1\n"
                        "          field2: value2"
                    ),
                    file_path=file_path
                )
            if not item:
                _raise_format_error(
                    group_name=group_name,
                    message=f"组 '{group_name}' 的第 {idx + 1} 个元素不能为空字典。",
                    file_path=file_path
                )
        return

    # 标量值（字符串/数字/布尔等）→ 严格禁止
    _raise_format_error(
        group_name=group_name,
        message=(
            f"组 '{group_name}' 的值必须是字典或字典列表，"
            f"当前类型: {type(value).__name__}，值: {repr(value)}\n"
            "  ❌ 禁止格式:\n"
            f"      {group_name}: {repr(value)}\n"
            "  ✅ 正确格式（单用例）:\n"
            f"      {group_name}:\n"
            "        field1: value1\n"
            "        field2: value2\n"
            "  ✅ 正确格式（多用例）:\n"
            f"      {group_name}:\n"
            "        - field1: value1\n"
            "          field2: value2\n"
            "        - field1: value3\n"
            "          field2: value4"
        ),
        file_path=file_path
    )


def _raise_format_error(group_name: str, message: str, file_path: Path) -> None:
    """统一抛出格式错误异常"""
    raise InvalidYamlFormatError(
        f"YAML 格式验证失败 in {file_path}\n"
        f"组: '{group_name}'\n"
        f"{message}"
    )


if __name__ == '__main__':
    from config import settings

    path = settings.project_root / 'test_data/login_page.yaml'
    print(load_yaml_file(path))
