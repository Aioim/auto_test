# tests/test_login.py
import pytest

# ✅ 正确：参数名与YAML字段名完全一致
@pytest.mark.yaml_data(file="login_cases.yaml", group="valid_login")
def test_valid_login(username, password, expected):
    assert mock_login(username, password) == expected

# ✅ 正确：多用例自动展开
@pytest.mark.yaml_data(file="login_cases.yaml", group="invalid_cases")
def test_invalid_login(username, password, expected):
    print(username)
    assert mock_login(username, password) == expected

# ❌ 错误：参数名不匹配（会触发 UsageError）
# @pytest.mark.yaml_data(file="login_cases.yaml", group="valid_login")
# def test_wrong_param(url):  # YAML中无"url"字段
#     pass

# 普通测试（无标记）
def test_static():
    assert 1 + 1 == 2

# --- 模拟函数 ---     b
def mock_login(username, password):
    return 200 if password == "secure123" else 401