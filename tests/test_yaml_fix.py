# tests/test_yaml_fix.py
import pytest

# 测试单字典组的情况
@pytest.mark.yaml_data(file="login_cases.yaml", group="valid_login")
def test_single_case(username, password, expected):
    assert (password == "secure123") == (expected == 200)

# 测试多字典组的情况
@pytest.mark.yaml_data(file="login_cases.yaml", group="invalid_cases")
def test_multiple_cases(username, password, expected):
    assert (password == "secure123") == (expected == 200)
