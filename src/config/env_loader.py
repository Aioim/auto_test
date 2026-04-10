"""环境变量自适应加载器 - 负责检测运行环境并设置默认环境变量"""
import os
import platform
import logging
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from config.path import PROJECT_ROOT

logger = logging.getLogger(__name__)


class EnvLoader:
    """环境变量加载器 - 自动优化 CI/容器/操作系统环境"""

    def __init__(self, enable_auto_optimize: bool = True):
        self.enable_auto_optimize = enable_auto_optimize
        self._loaded = False
        self._detected_ci: Optional[str] = None
        self._is_container: bool = False
        self._system_info: dict = {}

    def load(self) -> None:
        """加载并优化环境变量（不返回配置字典，只设置 os.environ）"""
        if self._loaded:
            return

        # 1. 从 .env 文件加载（如果存在）
        env_file = os.getenv("ENV_FILE", str(PROJECT_ROOT / ".env"))
        if os.path.exists(env_file):
            load_dotenv(env_file, override=True)
            logger.debug(f"Loaded .env file from {env_file}")

        # 2. 自动优化（可禁用）
        if self.enable_auto_optimize:
            self._detect_ci_environment()
            self._detect_container_environment()
            self._detect_os_and_optimize()
            self._detect_debug_mode()
            self._normalize_proxy_settings()
            self._detect_ca_certificates()
            self._optimize_by_cpu_cores()
            self._apply_restricted_mode()
            self._log_diagnostics_if_debug()

        self._loaded = True

    # ---------- 环境检测与优化方法 ----------
    def _detect_ci_environment(self) -> None:
        """检测 CI/CD 环境并设置优化变量"""
        ci_env_vars = {
            "GITHUB_ACTIONS": "github_actions",
            "GITLAB_CI": "gitlab_ci",
            "JENKINS_HOME": "jenkins",
            "TRAVIS": "travis_ci",
            "CIRCLECI": "circleci",
            "BITBUCKET_PIPELINES": "bitbucket",
            "TEAMCITY_VERSION": "teamcity",
            "AZURE_PIPELINES": "azure_pipelines",
            "CI": "generic_ci",
        }

        for var, name in ci_env_vars.items():
            if os.getenv(var):
                self._detected_ci = name
                break

        if self._detected_ci:
            os.environ.setdefault("CI_ENVIRONMENT", self._detected_ci)
            os.environ.setdefault("BROWSER_HEADLESS", "true")
            os.environ.setdefault("VIDEO_RECORDING", "failed")
            os.environ.setdefault("PRESERVE_CONTEXT_ON_FAILURE", "false")
            os.environ.setdefault("ENABLE_NETWORK_TRACING", "false")

            # CI 特定路径优化
            if self._detected_ci == "github_actions":
                os.environ.setdefault("ALLURE_RESULTS_DIR", "/github/workspace/reports/allure-results")
            elif self._detected_ci == "gitlab_ci":
                os.environ.setdefault("ALLURE_RESULTS_DIR", "${CI_PROJECT_DIR}/reports/allure-results")
                os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "${CI_PROJECT_DIR}/.cache/ms-playwright")

    def _detect_container_environment(self) -> None:
        """检测容器环境并设置优化变量"""
        # 环境变量检测
        container_vars = ["DOCKER_CONTAINER", "KUBERNETES_SERVICE_HOST", "CONTAINERIZED"]
        if any(os.getenv(var) for var in container_vars):
            self._is_container = True
        else:
            # 文件标记检测（仅非 Windows）
            if platform.system().lower() != "windows":
                container_markers = ["/.dockerenv", "/run/.containerenv"]
                for marker in container_markers:
                    try:
                        if os.path.exists(marker):
                            self._is_container = True
                            break
                    except Exception:
                        pass

        if self._is_container:
            os.environ.setdefault("CONTAINER_ENVIRONMENT", "true")
            os.environ.setdefault("BROWSER_HEADLESS", "true")
            os.environ.setdefault("ENABLE_JS", "true")

            # 内存限制优化
            try:
                import psutil
                mem_limit = psutil.virtual_memory().total
                if mem_limit < 2 * 1024 * 1024 * 1024:  # < 2GB
                    os.environ.setdefault("RESOURCE_CLEANUP_TIMEOUT", "3")
                    os.environ.setdefault("MAX_MEMORY_MB", "1500")
            except ImportError:
                pass  # psutil 可选，跳过

    def _detect_os_and_optimize(self) -> None:
        """检测操作系统并设置优化变量"""
        system = platform.system().lower()
        machine = platform.machine().lower()
        self._system_info = {
            "platform": system,
            "machine": machine,
            "python_version": platform.python_version(),
            "processor": platform.processor(),
        }

        if system == "windows":
            default_browsers_path = os.path.join(
                os.environ.get("LOCALAPPDATA", "C:\\Users\\Default\\AppData\\Local"),
                "ms-playwright"
            )
            os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", default_browsers_path)

            # 规范化 Windows 路径中的斜杠
            for key in ["BASE_URL", "API_BASE_URL"]:
                if value := os.getenv(key):
                    os.environ[key] = value.replace("\\", "/")

        elif system == "darwin":
            os.environ.setdefault("BROWSER_TYPE", "webkit")

        elif system == "linux":
            if "arm" in machine or "aarch64" in machine:
                os.environ.setdefault("BROWSER_TYPE", "chromium")

    @staticmethod
    def _detect_debug_mode() -> None:
        """检测调试模式并设置相关变量"""
        debug_vars = ["DEBUG", "PYTEST_DEBUG", "TEST_DEBUG"]
        is_debug = any(os.getenv(var, "").lower() in ("true", "1", "yes") for var in debug_vars)

        if is_debug:
            os.environ.setdefault("LOG_LEVEL", "debug")
            os.environ.setdefault("BROWSER_HEADLESS", "false")
            os.environ.setdefault("VIDEO_RECORDING", "always")
            os.environ.setdefault("PRESERVE_CONTEXT_ON_FAILURE", "true")

    @staticmethod
    def _normalize_proxy_settings() -> None:
        """标准化代理设置"""
        for proxy_var in ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"]:
            if proxy_url := os.getenv(proxy_var):
                if not proxy_url.startswith(("http://", "https://", "socks://")):
                    proxy_url = f"http://{proxy_url}"
                os.environ[proxy_var] = proxy_url
                break  # 只处理第一个找到的代理

    @staticmethod
    def _detect_ca_certificates() -> None:
        """检测企业 CA 证书"""
        ca_paths = [
            os.getenv("REQUESTS_CA_BUNDLE"),
            os.getenv("SSL_CERT_FILE"),
        ]
        if platform.system().lower() != "windows":
            ca_paths.extend([
                "/etc/ssl/certs/ca-certificates.crt",
                "/etc/pki/tls/certs/ca-bundle.crt",
            ])

        for ca_path in ca_paths:
            if ca_path and os.path.exists(ca_path):
                os.environ.setdefault("CUSTOM_CA_BUNDLE", ca_path)
                break

    @staticmethod
    def _optimize_by_cpu_cores() -> None:
        """根据 CPU 核心数优化并行度"""
        try:
            import psutil
            cpu_count = psutil.cpu_count(logical=False) or psutil.cpu_count()
            if cpu_count:
                worker_count = min(cpu_count, 4)
                os.environ.setdefault("WORKER_COUNT", str(worker_count))
        except ImportError:
            pass

    @staticmethod
    def _apply_restricted_mode() -> None:
        """应用受限环境（无网络/离线）优化"""
        restricted_vars = ["NO_INTERNET", "AIRGAPPED", "OFFLINE_MODE"]
        if any(os.getenv(var) for var in restricted_vars):
            os.environ.setdefault("ENABLE_NETWORK_TRACING", "false")
            os.environ.setdefault("VIDEO_RECORDING", "off")

    def _log_diagnostics_if_debug(self) -> None:
        """调试模式下输出诊断信息（使用 logging）"""
        debug_flag = os.getenv("CONFIG_DEBUG", "").lower() in ("true", "1")
        if not debug_flag:
            return

        diag_info = {
            "ci_environment": self._detected_ci,
            "container_environment": self._is_container,
            "platform": self._system_info.get("platform"),
            "machine": self._system_info.get("machine"),
            "debug_mode": bool(os.getenv("DEBUG")),
            "restricted_environment": bool(os.getenv("AIRGAPPED")),
        }
        logger.info("Environment diagnostics:\n" +
                    "\n".join(f"  {k:20}: {v}" for k, v in diag_info.items()))


if __name__ == "__main__":
    env_loader = EnvLoader()
    env_loader.load()
