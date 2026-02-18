"""
环境变量加载器
负责从系统环境和.env文件加载配置
"""
import os
from typing import Any, Dict
from dotenv import load_dotenv
from ._path import PROJECT_ROOT


class EnvLoader:
    """环境变量加载器"""

    def __init__(self):
        self._loaded = False

    def load(self) -> Dict[str, Any]:
        """加载环境变量配置"""
        if not self._loaded:
            # 1. 从系统环境变量加载
            self._load_system_env()

            # 2. 从.env文件加载 (如果存在)
            env_path = os.getenv("ENV_FILE", PROJECT_ROOT/'.env')
            if os.path.exists(env_path):
                load_dotenv(env_path, override=True)

            self._loaded = True

        return self._env_to_config()

    @staticmethod
    def _load_system_env():
        """加载系统环境变量并进行环境自适应优化"""
        import platform
        import psutil

        # 1. 检测CI/CD环境
        ci_env_vars = {
            "GITHUB_ACTIONS": "github_actions",
            "GITLAB_CI": "gitlab_ci",
            "JENKINS_HOME": "jenkins",
            "TRAVIS": "travis_ci",
            "CIRCLECI": "circleci",
            "BITBUCKET_PIPELINES": "bitbucket",
            "TEAMCITY_VERSION": "teamcity",
            "AZURE_PIPELINES": "azure_pipelines",
            "CI": "generic_ci"  # 通用CI标记
        }

        detected_ci = None
        for var, name in ci_env_vars.items():
            if os.getenv(var):
                detected_ci = name
                break

        if detected_ci:
            # CI环境优化
            os.environ.setdefault("CI_ENVIRONMENT", detected_ci)
            os.environ.setdefault("BROWSER_HEADLESS", "true")  # 强制无头模式
            os.environ.setdefault("VIDEO_RECORDING", "failed")  # 仅录制失败视频
            os.environ.setdefault("PRESERVE_CONTEXT_ON_FAILURE", "false")  # 避免资源泄漏
            os.environ.setdefault("ENABLE_NETWORK_TRACING", "false")  # 减少磁盘I/O

            # 根据CI类型特殊优化
            if detected_ci == "github_actions":
                # GitHub Actions 优化
                os.environ.setdefault("ALLURE_RESULTS_DIR", "/github/workspace/reports/allure-results")
            elif detected_ci == "gitlab_ci":
                # GitLab CI 优化
                os.environ.setdefault("ALLURE_RESULTS_DIR", "${CI_PROJECT_DIR}/reports/allure-results")
                os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "${CI_PROJECT_DIR}/.cache/ms-playwright")

        # 2. 检测容器环境
        is_container = False

        # 检查容器标记文件
        container_markers = [
            "/.dockerenv",
            "/run/.containerenv",
            "/proc/1/cgroup"
        ]

        for marker in container_markers:
            if os.path.exists(marker):
                is_container = True
                break

        # 检查环境变量
        container_vars = ["DOCKER_CONTAINER", "KUBERNETES_SERVICE_HOST", "CONTAINERIZED"]
        if not is_container:
            is_container = any(os.getenv(var) for var in container_vars)

        if is_container:
            os.environ.setdefault("CONTAINER_ENVIRONMENT", "true")
            os.environ.setdefault("BROWSER_HEADLESS", "true")  # 容器必须无头
            os.environ.setdefault("ENABLE_JS", "true")

            # 容器资源限制优化
            try:
                # 检测容器内存限制
                mem_limit = psutil.virtual_memory().total
                if mem_limit < 2 * 1024 * 1024 * 1024:  # < 2GB
                    os.environ.setdefault("RESOURCE_CLEANUP_TIMEOUT", "3")
                    os.environ.setdefault("MAX_MEMORY_MB", "1500")
            except Exception:
                pass  # 忽略资源检测失败

        # 3. 检测操作系统和架构
        system_info = {
            "platform": platform.system().lower(),
            "machine": platform.machine().lower(),
            "python_version": platform.python_version(),
            "processor": platform.processor()
        }

        # Windows 特定优化
        if system_info["platform"] == "windows":
            os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", os.path.join(
                os.environ.get("LOCALAPPDATA", "C:\\Users\\Default\\AppData\\Local"),
                "ms-playwright"
            ))

            # Windows 路径规范化
            for key in ["BASE_URL", "API_BASE_URL"]:
                if value := os.getenv(key):
                    os.environ[key] = value.replace("\\", "/")

        # macOS 特定优化
        elif system_info["platform"] == "darwin":
            os.environ.setdefault("BROWSER_TYPE", "webkit")  # WebKit 在 macOS 上更稳定

        # Linux 特定优化
        elif system_info["platform"] == "linux":
            # 检测是否为 ARM 架构（树莓派等）
            if "arm" in system_info["machine"] or "aarch64" in system_info["machine"]:
                os.environ.setdefault("BROWSER_TYPE", "chromium")  # ARM 上 Firefox 支持有限

        # 4. 调试模式检测
        debug_vars = ["DEBUG", "PYTEST_DEBUG", "TEST_DEBUG"]
        is_debug = any(os.getenv(var, "").lower() in ["true", "1", "yes"] for var in debug_vars)

        if is_debug:
            os.environ.setdefault("LOG_LEVEL", "debug")
            os.environ.setdefault("BROWSER_HEADLESS", "false")  # 调试时显示浏览器
            os.environ.setdefault("VIDEO_RECORDING", "always")  # 始终录制视频
            os.environ.setdefault("PRESERVE_CONTEXT_ON_FAILURE", "true")  # 保留失败上下文

        # 5. 代理和网络配置
        # 检测系统代理设置
        proxy_vars = ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"]
        for proxy_var in proxy_vars:
            if proxy_url := os.getenv(proxy_var):
                # 标准化代理URL
                if not proxy_url.startswith(("http://", "https://", "socks://")):
                    proxy_url = f"http://{proxy_url}"
                os.environ[proxy_var] = proxy_url
                break

        # 6. 企业环境特定配置
        # 检测企业CA证书
        ca_paths = [
            os.getenv("REQUESTS_CA_BUNDLE"),
            os.getenv("SSL_CERT_FILE"),
            "/etc/ssl/certs/ca-certificates.crt",  # Debian/Ubuntu
            "/etc/pki/tls/certs/ca-bundle.crt",  # RHEL/CentOS
            "/etc/ssl/certs/ca-certificates.crt"  # Alpine
        ]

        for ca_path in ca_paths:
            if ca_path and os.path.exists(ca_path):
                os.environ.setdefault("CUSTOM_CA_BUNDLE", ca_path)
                break

        # 7. 性能优化（基于CPU核心数）
        try:
            cpu_count = psutil.cpu_count(logical=False) or psutil.cpu_count()
            if cpu_count:
                # 设置并行工作进程数建议值
                worker_count = min(cpu_count, 4)  # 最多4个worker
                os.environ.setdefault("WORKER_COUNT", str(worker_count))
        except Exception:
            pass  # 忽略CPU检测失败

        # 8. 安全加固
        # 检测是否在受限环境
        restricted_vars = ["NO_INTERNET", "AIRGAPPED", "OFFLINE_MODE"]
        is_restricted = any(os.getenv(var) for var in restricted_vars)

        if is_restricted:
            os.environ.setdefault("ENABLE_NETWORK_TRACING", "false")
            os.environ.setdefault("VIDEO_RECORDING", "off")  # 节省磁盘空间

        # 9. 诊断信息（仅在debug模式）
        if is_debug or os.getenv("CONFIG_DEBUG", "").lower() in ["true", "1"]:
            diag_info = {
                "ci_environment": detected_ci,
                "container_environment": is_container,
                "platform": system_info["platform"],
                "machine": system_info["machine"],
                "debug_mode": is_debug,
                "restricted_environment": is_restricted
            }

            print("\n" + "=" * 60)
            print("🔧 环境检测诊断")
            print("-" * 60)
            for key, value in diag_info.items():
                print(f"  {key:25s}: {value}")
            print("=" * 60 + "\n")

    @staticmethod
    def _env_to_config() -> Dict[str, Any]:
        """转换环境变量为配置字典"""
        config = {}

        # 核心配置
        if env := os.getenv("ENV"):
            config["env"] = env.lower()
        if version := os.getenv("FRONTEND_VERSION"):
            config["frontend_version"] = version

        # URL配置
        if base_url := os.getenv("BASE_URL"):
            config["base_url"] = base_url
        if api_url := os.getenv("API_BASE_URL"):
            config["api_base_url"] = api_url

        # 凭证 (不验证值，由模型验证)
        for key in ["ADMIN_USERNAME", "ADMIN_PASSWORD", "API_SECRET_KEY"]:
            if value := os.getenv(key):
                # 转换为snake_case
                config_key = key.lower()
                config[config_key] = value

        # 浏览器配置
        browser_config = {}
        if headless := os.getenv("BROWSER_HEADLESS"):
            browser_config["headless"] = headless.lower() == "true"
        if browser_type := os.getenv("BROWSER_TYPE"):
            browser_config["type"] = browser_type.lower()
        if width := os.getenv("VIEWPORT_WIDTH"):
            browser_config.setdefault("viewport", {})["width"] = int(width)
        if height := os.getenv("VIEWPORT_HEIGHT"):
            browser_config.setdefault("viewport", {})["height"] = int(height)
        if browser_config:
            config["browser"] = browser_config

        # 超时配置
        timeouts = {}
        for key in ["PAGE_LOAD_TIMEOUT", "ELEMENT_WAIT_TIMEOUT", "API_TIMEOUT"]:
            if value := os.getenv(key):
                timeout_key = key.replace("_TIMEOUT", "").lower()
                timeouts[timeout_key] = int(value)
        if timeouts:
            config["timeouts"] = timeouts

        # Allure配置
        allure_config = {}
        if results_dir := os.getenv("ALLURE_RESULTS_DIR"):
            allure_config["results_dir"] = results_dir
        if auto_clean := os.getenv("AUTO_CLEAN_RESULTS"):
            allure_config["auto_clean"] = auto_clean.lower() == "true"
        if allure_config:
            config["allure"] = allure_config

        # Playwright目录配置（兼容顶级和嵌套结构）
        playwright_dirs = {}
        for key in ["PLAYWRIGHT_VIDEO_DIR", "PLAYWRIGHT_SCREENSHOT_DIR", "PLAYWRIGHT_TRACE_DIR"]:
            if value := os.getenv(key):
                # 转换为snake_case并移除前缀
                clean_key = key.lower().replace("playwright_", "")
                playwright_dirs[clean_key] = value
        if playwright_dirs:
            config["playwright"] = playwright_dirs

        # 高级选项
        if log_level := os.getenv("LOG_LEVEL"):
            config["log_level"] = log_level.lower()
        if preserve := os.getenv("PRESERVE_CONTEXT_ON_FAILURE"):
            config["preserve_context_on_failure"] = preserve.lower() == "true"
        if video := os.getenv("VIDEO_RECORDING"):
            config["video_recording"] = video.lower()
        if tracing := os.getenv("ENABLE_NETWORK_TRACING"):
            config["enable_network_tracing"] = tracing.lower() == "true"

        return config


# ======================
# 命令行验证 (自包含)
# ======================
if __name__ == '__main__':
    loader = EnvLoader()
    print(loader.load())
