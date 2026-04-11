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

            # 智能过滤响应内容
            safe_response = self._filter_response_content(response)
            logger.debug(f"Response body (filtered): {safe_response}")

            # Allure 附加信息
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
        """根据响应 Content-Type 智能过滤敏感信息"""
        content_type = response.headers.get("Content-Type", "").lower()
        try:
            if "application/json" in content_type:
                json_data = response.json()
                filtered = self._filter_sensitive_info(json_data)
                return json.dumps(filtered, ensure_ascii=False, indent=2)
            else:
                raw_text = response.text[:1000]
                return self._mask_sensitive_strings(raw_text)
        except Exception:
            raw_text = response.text[:500]
            return self._mask_sensitive_strings(raw_text)

    @staticmethod
    def _mask_sensitive_strings(text: str) -> str:
        """对纯文本字符串进行敏感关键词掩码"""
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
        if isinstance(expected, list):
            assert response.status_code in expected, \
                f"Expected status in {expected}, got {response.status_code}"
        else:
            assert response.status_code == expected, \
                f"Expected status {expected}, got {response.status_code}"
        return self

    @allure.step("验证响应 JSON Schema")
    def assert_schema(self, response: requests.Response, schema: Dict):
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
        data = response.json()
        actual = self._get_nested_field(data, field)
        assert actual == expected, f"Field {field}: expected {expected}, got {actual}"
        return self

    @allure.step("验证响应字段存在")
    def assert_field_exists(self, response: requests.Response, field: str):
        data = response.json()
        actual = self._get_nested_field(data, field)
        assert actual is not None, f"Field {field} not found in response"
        return self

    @allure.step("验证响应字段包含")
    def assert_field_contains(self, response: requests.Response, field: str, expected: Any):
        data = response.json()
        actual = self._get_nested_field(data, field)
        assert expected in str(actual), f"Field {field} does not contain {expected}"
        return self

    @allure.step("验证响应时间")
    def assert_response_time(self, response: requests.Response, max_time: float):
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
        """设置自定义 Authorization 头"""
        self.session.headers.update({"Authorization": header_value})
        return self

    def set_header(self, key: str, value: str):
        self.session.headers.update({key: value})
        return self

    def remove_header(self, key: str):
        if key in self.session.headers:
            del self.session.headers[key]
        return self

    def close(self):
        self.session.close()
        logger.info("API Client session closed")

    def _filter_sensitive_info(self, data: Any) -> Any:
        """递归过滤敏感信息"""
        sensitive_keys = {"password", "token", "secret", "key", "auth", "authorization"}

        if isinstance(data, dict):
            return {
                k: "***" if k.lower() in sensitive_keys else self._filter_sensitive_info(v)
                for k, v in data.items()
            }
        elif isinstance(data, list):
            return [self._filter_sensitive_info(item) for item in data]
        elif isinstance(data, str):
            return data
        else:
            return data

    @staticmethod
    def _get_nested_field(data: Dict, field: str) -> Any:
        """获取嵌套字段值"""
        keys = field.split(".")
        result = data
        for key in keys:
            if isinstance(result, dict) and key in result:
                result = result[key]
            else:
                return None
        return result
