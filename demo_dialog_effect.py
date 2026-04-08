from config import settings

# 直接访问配置属性
print(settings.base_url)
print(settings.browser.headless)
print(settings.timeouts.page_load)