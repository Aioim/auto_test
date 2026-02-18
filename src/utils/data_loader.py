from pathlib import Path
from typing import Any, Dict, List
import yaml
from logger import logger




def load_yaml_file( file_path: Path) -> Dict[str, List[Dict[str, Any]]]:
    """加载 YAML，返回 {group_name: [case1, case2, ...]}
    - 若值是 dict → 自动转为 [dict]
    - 若值是 list → 保持原样
    - 其他类型 → 跳过并告警（避免无效数据）
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if data is None:
            return {}
        if not isinstance(data, dict):
            raise ValueError("YAML 根必须是字典（组名作为键）")

        result = {}
        for group_name, value in data.items():
            cases = []
            if isinstance(value, dict):
                # 单个用例：自动包装为列表
                cases = [value]
                logger.debug(f"将单个用例组 '{group_name}' 包装为列表")
            elif isinstance(value, list):
                # 多个用例：直接使用
                cases = value
            else:
                # 非 dict/list 类型（如字符串、数字等）→ 跳过
                logger.warning(f"跳过无效组 '{group_name}'（类型: {type(value).__name__}）in {file_path}")
                continue

            # 验证每个用例是否为 dict
            validated_cases = []
            for i, case in enumerate(cases):
                if isinstance(case, dict):
                    validated_cases.append(case)
                else:
                    logger.warning(f"跳过非字典用例 in {file_path}:{group_name}[{i}]（类型: {type(case).__name__}）")
            result[group_name] = validated_cases

        return result
    except Exception as e:
        logger.exception(f"加载 YAML 文件失败 {file_path}: {e}")
        raise


if __name__=='__main__':
    from config import settings

    res=load_yaml_file(settings.project_root/'test_data/login_page.yaml')
    print(res['login_page_case'])
    print(res['llm_model'])
    print(res['llm_model'])
