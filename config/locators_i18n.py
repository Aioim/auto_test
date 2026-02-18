"""
示例的本地化映射。把页面中依赖可见文本作为定位（如 label、role name、link text）时，
用 key 去映射不同语言的实际文本。你可以把它改成 JSON/YAML 并通过 Settings 指定路径。
结构示例：
{
  "zh": {
    "login.username": "用户名",
    "login.password": "密码",
    "login.submit": "登录"
  },
  "en": {
    "login.username": "Username",
    "login.password": "Password",
    "login.submit": "Sign in"
  }
}
"""
LOCATORS_I18N = {
    "zh": {
        "login.username": "用户名",
        "login.password": "密码",
        "login.submit": "登录",
        "dashboard.title": "控制台"
    },
    "en": {
        "login.username": "Username",
        "login.password": "Password",
        "login.submit": "Sign in",
        "dashboard.title": "Dashboard"
    }
}

def get_text(key: str, locale: str = "zh") -> str:
    return LOCATORS_I18N.get(locale, {}).get(key, "")