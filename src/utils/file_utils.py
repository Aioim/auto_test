"""
文件操作相关工具函数：哈希计算、路径判断、模式匹配（支持 .gitignore 规则）等。
"""

import hashlib
from pathlib import Path
from typing import List, Optional, Union
from logger import logger

import pathspec


def compute_file_hash(file_path: Path, algorithm: str = "sha256") -> Optional[str]:
    """
    计算文件的哈希值。

    Args:
        file_path: 文件路径。
        algorithm: 哈希算法，默认为 sha256。

    Returns:
        十六进制哈希字符串，若文件不存在或读取失败则返回 None。
    """
    try:
        hasher = hashlib.new(algorithm)
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    except FileNotFoundError:
        logger.warning(f"File not found for hashing: {file_path}")
        return None
    except Exception as e:
        logger.error(f"Error computing hash for {file_path}: {e}")
        return None


def is_path_under(path: Path, parent: Path) -> bool:
    """
    判断 path 是否位于 parent 目录下（包括子目录）。

    Args:
        path: 待检查的路径。
        parent: 父目录路径。

    Returns:
        True 表示 path 是 parent 的子路径。
    """
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def parse_gitignore(gitignore_path: Path) -> List[str]:
    """
    解析 .gitignore 文件，返回模式行列表（原始字符串）。

    处理规则：
        - 忽略空行和以 '#' 开头的注释行
        - 移除行尾空格和回车
        - 保留原始模式（不自动添加通配符）

    Args:
        gitignore_path: .gitignore 文件路径。

    Returns:
        模式字符串列表。
    """
    if not gitignore_path.exists():
        return []

    patterns = []
    try:
        with open(gitignore_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.rstrip("\n\r")
                # 跳过空行和注释
                if not line or line.startswith("#"):
                    continue
                patterns.append(line)
    except Exception as e:
        logger.warning(f"Failed to parse .gitignore at {gitignore_path}: {e}")

    return patterns


def load_ignore_spec(project_root: Path, extra_patterns: Optional[List[str]] = None) -> pathspec.PathSpec:
    """
    加载项目的忽略规则规范，合并 .gitignore 与额外追加的模式。

    Args:
        project_root: 项目根目录，其中应包含 .gitignore 文件（可选）。
        extra_patterns: 额外追加的忽略模式列表（支持 gitwildmatch 语法）。

    Returns:
        pathspec.PathSpec 对象，用于匹配路径。
    """
    patterns = []
    gitignore_path = project_root / ".gitignore"
    if gitignore_path.exists():
        patterns.extend(parse_gitignore(gitignore_path))
    if extra_patterns:
        patterns.extend(extra_patterns)
    return pathspec.PathSpec.from_lines("gitwildmatch", patterns)


def matches_ignore_pattern(rel_path: str, spec: Union[pathspec.PathSpec, List[str]]) -> bool:
    """
    判断相对路径是否匹配忽略规则。

    支持两种调用方式：
        1. 传入已构建的 pathspec.PathSpec 对象（推荐，避免重复解析）。
        2. 传入模式字符串列表（内部会临时构建 PathSpec，仅适用于少量调用）。

    Args:
        rel_path: 相对于项目根目录的文件路径字符串。
        spec: pathspec.PathSpec 对象或模式字符串列表。

    Returns:
        True 表示应被忽略。
    """
    if isinstance(spec, list):
        if not spec:
            return False
        spec = pathspec.PathSpec.from_lines("gitwildmatch", spec)
    return spec.match_file(rel_path)


def find_files(
        root: Path,
        patterns: List[str],
        ignore_spec: Optional[pathspec.PathSpec] = None,
) -> List[Path]:
    """
    在根目录下递归查找匹配模式的文件，并应用忽略规则。

    Args:
        root: 搜索根目录。
        patterns: 文件匹配模式列表（如 ["*.py", "*.java"]）。
        ignore_spec: 预加载的 pathspec.PathSpec 对象，用于忽略规则匹配。

    Returns:
        符合条件的文件路径列表。
    """
    files: List[Path] = []
    for pattern in patterns:
        for path in root.rglob(pattern):
            if not path.is_file():
                continue
            rel_path = str(path.relative_to(root))
            if ignore_spec and matches_ignore_pattern(rel_path, ignore_spec):
                continue
            files.append(path)
    return files
