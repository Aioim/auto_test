"""
通用工具函数模块。
"""
from .allure_attachment import attach_json, attach_jpg, attach_png, attach_image, attach_xml, attach_file, attach_text

from .file_utils import (
    compute_file_hash,
    is_path_under,
    matches_ignore_pattern,
    find_files,
)


__all__ = [
    # file_utils
    "compute_file_hash",
    "is_path_under",
    "matches_ignore_pattern",
    "find_files",
    # allure_attachment
    'attach_json',
    'attach_file',
    'attach_image',
    'attach_jpg',
    'attach_png',
    'attach_text',
    'attach_xml',

]
