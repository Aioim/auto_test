#!/usr/bin/env python
"""
登录状态缓存生成脚本

支持两种模式：
1. 单账号模式：通过 --username 和 --password 直接指定账号
2. 多账号模式：从 .env 文件中读取多组账号（按环境区分）

环境变量文件命名规则：
    - .env                # 默认文件（当 --env 未提供时尝试加载）
    - .env.<env>          # 例如 .env.beta, .env.alpha, .env.prod

多账号环境变量命名规范（以 beta 环境为例）：
    BETA_USER_1=user1
    BETA_PASS_1=pass1
    BETA_USER_2=user2
    BETA_PASS_2=pass2
    BETA_ADMIN_USER=admin
    BETA_ADMIN_PASS=admin123
    BETA_MANAGER_USER=mgr
    BETA_MANAGER_PASS=mgr456
    BETA_EMPLOYEE_USER=emp
    BETA_EMPLOYEE_PASS=emp123

也可以使用简化的单账号变量（与多账号并存）：
    BETA_USERNAME=user
    BETA_PASSWORD=pass

使用示例：
    # 单账号
    python generate_login_state.py --username admin --password 123 --env beta

    # 多账号（使用 .env.beta 中的所有账号）
    python generate_login_state.py --env beta

    # 多账号（使用默认 .env 中的所有账号）
    python generate_login_state.py
"""

import argparse
import sys
from pathlib import Path

# 添加项目根目录到 sys.path（保持原有导入结构）
sys.path.insert(0, str(Path(__file__).parent.parent))

from playwright.sync_api import sync_playwright
from config import settings
from pages.components.login_page import login_page
from logger import logger
from auth.cache_utils import (
    load_env_by_name,
    get_all_accounts_from_env,
    save_storage_state,
    wait_for_login_success,
    get_storage_state_path,
)


def generate_single(username: str, password: str, env: str) -> bool:
    """
    为单个账号生成登录缓存

    Args:
        username: 用户名
        password: 密码
        env: 环境标识

    Returns:
        成功返回 True，失败返回 False
    """
    print(f"👉 正在为用户 '{username}' (环境: {env}) 生成登录缓存...")
    with sync_playwright() as p:
        browser_type = getattr(playwright, settings.browser.type, p.chromium)
        browser = browser_type.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        try:
            # 执行登录
            login_page(page, username, password)
            # 等待登录成功（使用统一的等待机制）
            wait_for_login_success(page)
            # 保存缓存
            save_storage_state(page, username, env)
            cache_path = get_storage_state_path(username, env)
            print(f"✅ 登录缓存已保存至: {cache_path}")
            return True
        except Exception as e:
            print(f"❌ 登录失败: {e}")
            return False
        finally:
            browser.close()


def run_multi_accounts(env_name: str):
    """
    多账号模式：加载环境变量，为所有找到的账号生成登录缓存
    """
    load_env_by_name(env_name)
    accounts = get_all_accounts_from_env(env_name)

    if not accounts:
        print("❌ 未从环境变量中找到任何有效的账号配置")
        print("请检查 .env 文件是否定义了类似 BETA_USER_1 / BETA_PASS_1 或 BETA_USERNAME / BETA_PASSWORD 的变量")
        sys.exit(1)

    print(f"📋 共发现 {len(accounts)} 个账号需要处理\n")
    success_count = 0
    fail_count = 0

    for acc in accounts:
        username = acc["username"]
        password = acc["password"]
        if generate_single(username, password, env_name):
            success_count += 1
        else:
            fail_count += 1
        print()  # 输出空行分隔

    print(f"📊 汇总：成功 {success_count} 个，失败 {fail_count} 个")
    if fail_count > 0:
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="生成登录状态缓存文件")
    parser.add_argument("--username", help="用户名（单账号模式）")
    parser.add_argument("--password", help="密码（单账号模式）")
    parser.add_argument("--env", default="beta", help="环境标识，用于加载对应的 .env.<env> 文件，默认 beta")
    args = parser.parse_args()

    # 单账号模式：优先使用命令行提供的用户名密码
    if args.username and args.password:
        # 仍然需要加载环境文件，以便 settings 等依赖可能用到
        load_env_by_name(args.env)
        success = generate_single(args.username, args.password, args.env)
        sys.exit(0 if success else 1)

    # 多账号模式：从 .env 文件读取所有账号
    run_multi_accounts(args.env)


if __name__ == "__main__":
    main()