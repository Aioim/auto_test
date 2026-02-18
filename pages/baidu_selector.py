from utils.selector_helper import Selector

search_input = Selector(
    css="#chat-textarea",
    description="百度搜索输入框"
)

# 搜索按钮
search_button = Selector(
    role="button",
    role_name="百度一下",
    description="百度搜索按钮"
)

# 搜索结果列表项
search_results = Selector(
    css="#content_left .result-op",
    description="搜索结果列表项"
)

# 第一个搜索结果的标题
first_result_title = Selector(
    css="#content_left .result-op .title a",
    description="第一个搜索结果标题"
)

# 搜索建议下拉框
search_suggestions = Selector(
    css="#sugWrapper .sug-list",
    description="搜索建议下拉框"
)

# 百度Logo
baidu_logo = Selector(
    css="#s_lg_img",
    role="img",
    description="百度Logo"
)