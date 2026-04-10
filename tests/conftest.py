"""
全局 pytest 配置文件
适用于所有测试类型（API + E2E）
提供：
- 命令行选项（--env）
- 环境标记跳过逻辑
- 公共 YAML 数据驱动钩子
- 全局路径常量
"""
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pytest

from config import PROJECT_ROOT, settings
from data.yaml_cases_loader import InvalidYamlFormatError, load_yaml_file
from logger import logger

# ==================== 常量 ====================
TEST_DATA_DIR = Path(getattr(settings, "test_data_dir", PROJECT_ROOT / "test_data/test_cases/"))


# ==================== 命令行选项 ====================
def pytest_addoption(parser):
    parser.addoption(
        "--env",
        action="store",
        default=os.getenv("ENV", "beta"),
        choices=["alpha", "beta", "prod"],
        help="指定测试环境：alpha, beta, prod"
    )


def pytest_collection_modifyitems(config, items):
    """根据环境标记跳过测试"""
    current_env = config.getoption("--env")
    for item in items:
        env_marker = item.get_closest_marker("env")
        if env_marker:
            allowed_envs = env_marker.args
            if not allowed_envs:
                continue
            if len(allowed_envs) == 1 and isinstance(allowed_envs[0], (list, tuple)):
                allowed_envs = allowed_envs[0]
            if current_env not in allowed_envs:
                reason = f"测试仅允许在环境 {allowed_envs} 中运行，当前环境为 {current_env}"
                item.add_marker(pytest.mark.skip(reason=reason))


# ==================== YAML 数据驱动公共钩子 ====================
@lru_cache(maxsize=128)
def _cached_load_yaml(file_path_str: str) -> Dict[str, List[Dict[str, Any]]]:
    file_path = Path(file_path_str)
    if not file_path.exists():
        raise FileNotFoundError(f"YAML文件不存在: {file_path}")
    return load_yaml_file(file_path)


def _extract_yaml_param_names(metafunc, first_case: Dict[str, Any]) -> List[str]:
    yaml_fields = set(first_case.keys()) if first_case else set()
    param_names = [p for p in metafunc.fixturenames if p in yaml_fields]
    if not param_names and yaml_fields:
        all_params = set(metafunc.fixturenames)
        _raise_usage_error(
            metafunc,
            f"测试函数参数与YAML字段无匹配\n"
            f"  YAML字段: {sorted(yaml_fields)}\n"
            f"  测试参数: {sorted(all_params)}\n"
            f"  要求: 测试函数参数名必须与YAML字段名完全一致"
        )
    unused_fields = yaml_fields - set(param_names)
    if unused_fields:
        logger.warning(f"[YAML数据] 以下YAML字段未被测试函数使用: {sorted(unused_fields)}")
    return param_names


def _mark_test_skip_due_to_no_cases(metafunc, reason: str = "No valid YAML test cases found") -> None:
    """标记测试为跳过，并创建一个虚拟参数化以避免 pytest 因缺少参数而失败"""
    metafunc.definition.add_marker(pytest.mark.skip(reason=reason))
    if "request" in metafunc.fixturenames:
        metafunc.parametrize("request", [pytest.param(None)], indirect=True)


def pytest_generate_tests(metafunc):
    """公共 YAML 数据驱动参数化钩子（所有测试类型共用）"""
    marker = metafunc.definition.get_closest_marker("yaml_data")
    if marker is None:
        return

    try:
        file_name = marker.kwargs["file"]
        group_name = marker.kwargs["group"]
    except KeyError as e:
        _raise_usage_error(
            metafunc,
            f"@pytest.mark.yaml_data 缺少必需参数 {e}\n"
            f"  正确用法: @pytest.mark.yaml_data(file='xxx.yaml', group='yyy')"
        )
        return

    if "params" in marker.kwargs:
        _raise_usage_error(
            metafunc,
            f"@pytest.mark.yaml_data 不再支持 'params' 参数\n"
            f"  要求: 测试函数参数名必须与YAML字段名完全一致"
        )
        return

    abs_file_path = TEST_DATA_DIR / file_name
    logger.debug(f"Loading YAML file: {abs_file_path}")

    if not abs_file_path.exists():
        logger.warning(f"YAML数据文件不存在，跳过测试: {abs_file_path}")
        _mark_test_skip_due_to_no_cases(metafunc, f"YAML file {file_name} not found")
        return

    try:
        res = _cached_load_yaml(str(abs_file_path))
    except InvalidYamlFormatError as e:
        _raise_usage_error(metafunc, f"YAML数据格式验证失败:\n{e}")
        return
    except Exception as e:
        logger.warning(f"加载YAML数据异常: {type(e).__name__}: {e}")
        _mark_test_skip_due_to_no_cases(metafunc, f"YAML loading error: {e}")
        return

    if group_name not in res:
        available = list(res.keys())
        logger.warning(f"YAML中不存在用例组 '{group_name}'，可用组: {available}")
        _mark_test_skip_due_to_no_cases(metafunc, f"Group '{group_name}' not found")
        return

    cases = res[group_name]
    if isinstance(cases, dict):
        cases = [cases]
    if not cases:
        logger.warning(f"用例组 '{group_name}' 为空")
        _mark_test_skip_due_to_no_cases(metafunc, f"Group '{group_name}' has no cases")
        return

    param_names = _extract_yaml_param_names(metafunc, cases[0])
    if not param_names:
        logger.warning("无法提取有效参数名")
        _mark_test_skip_due_to_no_cases(metafunc, "No matching parameter names")
        return

    param_values: List[Tuple[Any, ...]] = []
    param_ids: List[str] = []
    used_ids = set()

    for idx, case in enumerate(cases):
        if not isinstance(case, dict):
            continue

        missing = [p for p in param_names if p not in case]
        if missing:
            logger.warning(f"[YAML数据] 用例 {idx} 缺少字段 {missing}，已跳过")
            continue

        case_id = (
            str(case.get("id", "")) or
            str(case.get("name", "")) or
            str(case.get("desc", "")) or
            f"{group_name}_{idx}"
        )
        case_id = re.sub(r'[^a-zA-Z0-9_]', '_', case_id)
        case_id = re.sub(r'_+', '_', case_id).strip('_')
        if not case_id or not case_id[0].isalpha():
            case_id = f"{group_name}_{idx}"
        if case_id in used_ids:
            suffix = 2
            while f"{case_id}_{suffix}" in used_ids:
                suffix += 1
            case_id = f"{case_id}_{suffix}"
        used_ids.add(case_id)
        if len(case_id) > 100:
            case_id = case_id[:97] + "..."

        values = tuple(case[p] for p in param_names)
        param_values.append(values)
        param_ids.append(case_id)

    if not param_values:
        logger.warning(f"用例组 '{group_name}' 无有效用例")
        _mark_test_skip_due_to_no_cases(metafunc, "No valid cases after filtering")
        return

    metafunc.parametrize(
        ",".join(param_names),
        param_values,
        ids=param_ids,
        scope="function"
    )


def _raise_usage_error(metafunc, message: str) -> None:
    raise pytest.UsageError(
        f"[YAML数据错误] in {metafunc.definition.nodeid}\n{message}"
    )