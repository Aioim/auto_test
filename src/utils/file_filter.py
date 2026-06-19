import os
import fnmatch
from typing import List, Iterator, Tuple, Optional


class FileFilter:
    def __init__(self, project_root: str, custom_ignore_patterns: Optional[List[str]] = None):
        self.project_root = os.path.abspath(project_root)
        self.ignore_patterns = self._get_default_ignore_patterns()

        if custom_ignore_patterns:
            self.ignore_patterns.extend(custom_ignore_patterns)

        gitignore_path = os.path.join(self.project_root, ".gitignore")
        if os.path.exists(gitignore_path):
            self.ignore_patterns.extend(self._parse_gitignore(gitignore_path))

    def _get_default_ignore_patterns(self) -> List[str]:
        return [
            "venv/",
            ".venv/",
            "env/",
            ".env/",
            "virtualenv/",
            "__pycache__/",
            "*.pyc",
            "*.pyo",
            "*.pyd",
            ".git/",
            ".hg/",
            ".svn/",
            ".vscode/",
            ".idea/",
            "*.swp",
            "*.swo",
            "build/",
            "dist/",
            "*.egg-info/",
            "*.egg",
            ".DS_Store",
            "Thumbs.db",
            "*.log",
            "*.sqlite",
            "*.db",
            ".env",
            ".env.local",
            ".env.*.local",
            "tests/",
            "test_*.py",
            "*_test.py",
        ]

    def _parse_gitignore(self, gitignore_path: str) -> List[str]:
        patterns = []
        try:
            with open(gitignore_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        patterns.append(line)
        except Exception:
            pass
        return patterns

    def should_ignore(self, file_path: str) -> bool:
        if not (file_path.endswith('.py') or
                os.path.basename(file_path) in ['requirements.txt', 'pyproject.toml', 'Pipfile', 'uv.lock'] or
                file_path.endswith(('.yaml', '.yml', '.toml'))):
            return True

        for pattern in self.ignore_patterns:
            if pattern.endswith('/'):
                if file_path.startswith(pattern) or fnmatch.fnmatch(file_path, pattern + '*'):
                    return True
            else:
                if fnmatch.fnmatch(file_path, pattern):
                    return True

        return False

    def walk_filtered(self) -> Iterator[Tuple[str, str, str]]:
        for root, dirs, files in os.walk(self.project_root):
            dirs[:] = [d for d in dirs if not self._should_ignore_dir(d)]

            rel_root = os.path.relpath(root, self.project_root)
            if rel_root == '.':
                rel_root = ''

            for file in files:
                rel_file_path = os.path.join(rel_root, file) if rel_root else file
                if not self.should_ignore(rel_file_path):
                    full_path = os.path.join(root, file)
                    yield root, file, full_path

    def _should_ignore_dir(self, dir_name: str) -> bool:
        for pattern in self.ignore_patterns:
            if pattern.endswith('/'):
                dir_pattern = pattern[:-1]
                if fnmatch.fnmatch(dir_name, dir_pattern):
                    return True
        return False

    def get_python_files(self) -> List[str]:
        python_files = []
        for _, _, full_path in self.walk_filtered():
            if full_path.endswith('.py'):
                python_files.append(os.path.abspath(full_path))
        return python_files

    def get_dependency_files(self) -> List[str]:
        dep_files = []
        for _, _, full_path in self.walk_filtered():
            filename = os.path.basename(full_path)
            if filename in ['requirements.txt', 'pyproject.toml', 'Pipfile']:
                dep_files.append(os.path.abspath(full_path))
        return dep_files