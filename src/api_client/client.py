"""
API 测试客户端
"""
import json
import re
import time
from typing import Optional, Dict, Any, List, Union
import allure
import backoff
import requests
from jsonschema import ValidationError, validate
from loguru import logger
from requests.exceptions import ConnectionError, RequestException, Timeout


class APIClient:
    """API 客户端，支持重试、日志、Allure报告、断言链、上下文管理器"""

    def __init__(self, base_url: str, headers: Dict = None, timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.default_timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(headers or {
            "Content-Type": "application/json",
            "Accept": "application/json"
        })
        logger.info(f"API Client initialized: {self.base_url} (timeout={timeout}s)")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    @backoff.on_exception(
        backoff.expo,
        (RequestException, Timeout, ConnectionError),
        max_tries=3,
        max_time=60,
        on_backoff=lambda details: logger.warning(
            f"请求失败，{details['wait']:.1f}秒后重试 ({details['tries']}/3)"
        ),
        on_giveup=lambda details: logger.error(f"请求最终失败，已尝试 {details['tries']} 次")
    )
    @allure.step("API 请求: {method} {endpoint}")
    def request(
            self,
            method: str,
            endpoint: str,
            headers: Dict = None,
            params: Dict = None,
            json_data: Dict = None,
            data: Any = None,
            files: Dict = None,
            timeout: Optional[int] = None,
            **kwargs
    ) -> requests.Response:
        """发送 HTTP 请求"""
        return self._request_impl(
            method, endpoint, headers, params, json_data, data, files,
            timeout if timeout is not None else self.default_timeout,
            **kwargs
        )

    def _request_impl(
            self,
            method: str,
            endpoint: str,
            headers: Dict = None,
            params: Dict = None,
            json_data: Dict = None,
            data: Any = None,
            files: Dict = None,
            timeout: int = 30,
            **kwargs
    ) -> requests.Response:
        """请求实现"""
        url = f"{self.base_url}{endpoint}"

        # 过滤敏感信息
        safe_params = self._filter_sensitive_info(params or {})
        safe_json = self._filter_sensitive_info(json_data or {})

        logger.info(f"{method} {url}")
        if safe_json:
            logger.debug(f"Request body: {safe_json}")
        if safe_params:
            logger.debug(f"Request params: {safe_params}")

        start_time = time.time()
        try:
            response = self.session.request(
                method=method.upper(),
                url=url,
                headers=headers,
                params=params,
                json=json_data,
                data=data,
                files=files,
                timeout=timeout,
                **kwargs
            )
            response_time = time.time() - start_time
            logger.info(f"Response status: {response.status_code} (耗时: {response_time:.2f}s)")

            # 智能过滤响应内容：JSON 则结构化过滤，否则纯文本过滤
            safe_response = self._filter_response_content(response)

            logger.debug(f"Response body (filtered): {safe_response}")

            # Allure 附加请求信息
            allure.attach(
                f"{method} {url}\nParams: {safe_params}\nHeaders: {headers or {} }",
                name="Request",
                attachment_type=allure.attachment_type.TEXT
            )
            allure.attach(
                safe_response,
                name="Response",
                attachment_type=allure.attachment_type.TEXT
            )
            allure.attach(
                f"Response time: {response_time:.2f}s",
                name="Performance",
                attachment_type=allure.attachment_type.TEXT
            )

            return response

        except RequestException as e:
            response_time = time.time() - start_time
            logger.error(f"Request failed: {e} (耗时: {response_time:.2f}s)")
            allure.attach(
                f"Request failed: {e}",
                name="Error",
                attachment_type=allure.attachment_type.TEXT
            )
            raise

    def _filter_response_content(self, response: requests.Response) -> str:
        """根据响应 Content-Type 智能过滤敏感信息，返回字符串表示"""
        content_type = response.headers.get("Content-Type", "").lower()
        try:
            if "application/json" in content_type:
                json_data = response.json()
                filtered = self._filter_sensitive_info(json_data)
                return json.dumps(filtered, ensure_ascii=False, indent=2)
            else:
                # 非 JSON 响应，截取前 1000 字符过滤敏感词
                raw_text = response.text[:1000]
                return self._mask_sensitive_strings(raw_text)
        except Exception:
            # 回退：截取原始文本
            raw_text = response.text[:500]
            return self._mask_sensitive_strings(raw_text)

    def _mask_sensitive_strings(self, text: str) -> str:
        """对纯文本字符串进行敏感关键词掩码，保留上下文"""
        sensitive_keys = ["password", "token", "secret", "key", "auth", "authorization"]
        pattern = r'(?i)("?(?:%s)"?\s*[:=]\s*"?)([^"\s&]+)' % "|".join(sensitive_keys)
        return re.sub(pattern, r'\1***', text)

    def get(self, endpoint: str, **kwargs) -> requests.Response:
        return self.request("GET", endpoint, **kwargs)

    def post(self, endpoint: str, **kwargs) -> requests.Response:
        return self.request("POST", endpoint, **kwargs)

    def put(self, endpoint: str, **kwargs) -> requests.Response:
        return self.request("PUT", endpoint, **kwargs)

    def patch(self, endpoint: str, **kwargs) -> requests.Response:
        return self.request("PATCH", endpoint, **kwargs)

    def delete(self, endpoint: str, **kwargs) -> requests.Response:
        return self.request("DELETE", endpoint, **kwargs)

    @allure.step("验证响应状态码")
    def assert_status(self, response: requests.Response, expected: Union[int, List[int]]):
        """断言状态码"""
        if isinstance(expected, list):
            assert response.status_code in expected, \
                f"Expected status in {expected}, got {response.status_code}"
        else:
            assert response.status_code == expected, \
                f"Expected status {expected}, got {response.status_code}"
        return self

    @allure.step("验证响应 JSON Schema")
    def assert_schema(self, response: requests.Response, schema: Dict):
        """断言 JSON Schema"""
        try:
            validate(instance=response.json(), schema=schema)
            logger.info("Schema validation passed")
        except ValidationError as e:
            logger.error(f"Schema validation failed: {e.message}")
            allure.attach(
                f"Schema validation failed: {e.message}",
                name="Schema Error",
                attachment_type=allure.attachment_type.TEXT
            )
            raise
        return self

    @allure.step("验证响应字段")
    def assert_field(self, response: requests.Response, field: str, expected: Any):
        """断言响应字段值"""
        data = response.json()
        actual = self._get_nested_field(data, field)
        assert actual == expected, f"Field {field}: expected {expected}, got {actual}"
        return self

    @allure.step("验证响应字段存在")
    def assert_field_exists(self, response: requests.Response, field: str):
        """断言响应字段存在"""
        data = response.json()
        actual = self._get_nested_field(data, field)
        assert actual is not None, f"Field {field} not found in response"
        return self

    @allure.step("验证响应字段包含")
    def assert_field_contains(self, response: requests.Response, field: str, expected: Any):
        """断言响应字段包含指定值"""
        data = response.json()
        actual = self._get_nested_field(data, field)
        assert expected in str(actual), f"Field {field} does not contain {expected}"
        return self

    @allure.step("验证响应时间")
    def assert_response_time(self, response: requests.Response, max_time: float):
        """断言响应时间（使用 elapsed 时间）"""
        response_time = response.elapsed.total_seconds()
        assert response_time <= max_time, \
            f"Response time {response_time:.2f}s exceeds maximum {max_time}s"
        logger.info(f"Response time {response_time:.2f}s within limit {max_time}s")
        return self

    def set_auth_token(self, token: str):
        """设置 Bearer Token 认证头"""
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        return self

    def set_auth_header(self, header_value: str):
        """设置自定义 Authorization 头（适用于非 Bearer 场景）"""
        self.session.headers.update({"Authorization": header_value})
        return self

    def set_header(self, key: str, value: str):
        """设置请求头"""
        self.session.headers.update({key: value})
        return self

    def remove_header(self, key: str):
        """移除请求头"""
        if key in self.session.headers:
            del self.session.headers[key]
        return self

    def close(self):
        """关闭会话"""
        self.session.close()
        logger.info("API Client session closed")

    def _filter_sensitive_info(self, data: Any) -> Any:
        """递归过滤敏感信息（字典、列表、字符串）"""
        sensitive_keys = {"password", "token", "secret", "key", "auth", "authorization"}

        if isinstance(data, dict):
            return {
                k: "***" if k.lower() in sensitive_keys else self._filter_sensitive_info(v)
                for k, v in data.items()
            }
        elif isinstance(data, list):
            return [self._filter_sensitive_info(item) for item in data]
        elif isinstance(data, str):
            # 对字符串内容不再做全替换，保留上下文（已在 _mask_sensitive_strings 中处理）
            return data
        else:
            return data

    def _get_nested_field(self, data: Dict, field: str) -> Any:
        """获取嵌套字段值"""
        keys = field.split(".")
        result = data
        for key in keys:
            if isinstance(result, dict) and key in result:
                result = result[key]
            else:
                return None
        return result


# ============================================================================
# 使用示例
# ============================================================================

if __name__ == "__main__":
    print("✅ API Client 模块加载成功")
    print("📌 使用方法: APIClient(base_url='https://api.example.com')")
    print("📌 支持的方法: get, post, put, patch, delete")
    print("📌 断言方法: assert_status, assert_field, assert_schema, assert_response_time")
    print("\n=== 使用示例 ===")
    print("""
# 基本使用示例
from src.utils.api_client import APIClient

# 创建 API 客户端（可使用上下文管理器）
with APIClient(base_url="https://jsonplaceholder.typicode.com") as client:
    # 发送 GET 请求
    response = client.get("/todos/1")
    client.assert_status(response, 200)
    client.assert_field(response, "userId", 1)
    client.assert_response_time(response, 2.0)

    # 发送 POST 请求
    new_data = {"title": "测试任务", "completed": False, "userId": 1}
    response = client.post("/todos", json_data=new_data)
    client.assert_status(response, 201)
    client.assert_field(response, "title", "测试任务")
""")
