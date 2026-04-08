#!/usr/bin/env python3
"""
验证 security.log 修复效果（纯 JSON、无重复、敏感信息掩码）
"""

import json
import sys
import time
from pathlib import Path
from utils.logger import log_security_event
from config import PROJECT_ROOT

def verify_security_log():
    # 使用脚本所在目录作为基准，避免 CWD 问题
    sec_file = PROJECT_ROOT / "logs" / "security.log"
    
    print("=" * 70)
    print("✅ Security Log Verification")
    print("=" * 70)
    print(f"📂 Target File: {sec_file.resolve()}")

    # 1. 清理旧日志
    if sec_file.exists():
        try:
            sec_file.unlink()
            print(f"🧹 Cleaned existing {sec_file.name}")
        except PermissionError:
            print("❌ Permission denied when cleaning log file")
            return False

    # 确保 logs 目录存在 (防止 log_security_event 报错)
    sec_file.parent.mkdir(parents=True, exist_ok=True)

    # 2. 记录测试事件
    print("\n📝 Recording test events...")
    # 定义一个明显的敏感值用于验证掩码
    sensitive_value = "SUPER_SECRET_PASSWORD_123"
    
    events = [
        ("test_event_1", "user1", "resource1", "success", {"key1": "value1"}),
        ("test_event_2", "user2", "resource2", "failed", {"password": sensitive_value, "token": "abc"}),
    ]

    for action, user, resource, status, details in events:
        log_security_event(action, user, resource, status, details)

    # 3. 强制刷新日志缓冲 (关键步骤)
    # 如果 utils.logger 提供了 flush 方法，请在这里调用
    # 例如：flush_security_handlers() 
    # 如果没有，短暂休眠给文件系统一点时间写入
    time.sleep(0.5) 

    # 4. 验证文件
    print(f"\n🔍 Checking {sec_file.name}...")
    if not sec_file.exists():
        print("❌ File does not exist after logging!")
        return False

    try:
        content = sec_file.read_text(encoding='utf-8').strip()
    except Exception as e:
        print(f"❌ Failed to read file: {e}")
        return False

    lines = [line for line in content.splitlines() if line.strip()]
    print(f"✅ File exists ({len(lines)} lines, {sec_file.stat().st_size} bytes)")

    if len(lines) != len(events):
        print(f"❌ Line count mismatch: Expected {len(events)}, Got {len(lines)}")
        # 不直接返回，继续检查内容以便调试
        # return False 

    # 5. 验证每行内容
    valid = True
    for i, line in enumerate(lines, 1):
        # 检查是否纯 JSON (排除常见的日志前缀)
        # 更稳健的方法是尝试直接解析，如果失败再检查前缀
        if line.startswith(("WARNING", "INFO", "ERROR", "DEBUG", "[", "202")):
            # 排除掉 JSON 本身以 [ 或 { 开头的情况，这里主要抓日志级别前缀
            if not line.startswith("{"):
                print(f"❌ Line {i}: Has log prefix (not pure JSON): {line[:50]}...")
                valid = False
                continue

        # 验证 JSON 格式
        try:
            event = json.loads(line)
        except json.JSONDecodeError as e:
            print(f"❌ Line {i}: Invalid JSON - {e}")
            valid = False
            continue

        # 验证敏感信息掩码 (修复逻辑错误)
        # 检查原始敏感值是否出现在日志中，而不是检查键名
        if sensitive_value in line:
            print(f"❌ Line {i}: Contains unmasked sensitive value!")
            valid = False
        elif "password" in event and event["password"] == sensitive_value:
            # 双重确认：解析后的字典里值也是明文
            print(f"❌ Line {i}: Password field contains original value!")
            valid = False
        else:
            # 如果存在 password 键，确认它被掩码了 (可选)
            if "password" in event:
                val = event["password"]
                if val != "***" and val != "******" and len(val) > 0: 
                    # 根据实际掩码策略调整，这里假设掩码后不是原值即可
                    pass 
            print(f"✅ Line {i}: Valid JSON (action={event.get('action')})")

    # 6. 最终结果
    print("\n" + "=" * 70)
    # 只有当格式验证通过 且 行数匹配 且 无敏感泄露时才算成功
    if valid and len(lines) == len(events):
        print("🎉 SUCCESS: security.log is clean (pure JSON, no duplicates, auto-masked)")
        return True
    else:
        print("❌ FAILED: security.log has issues")
        return False

if __name__ == "__main__":
    success = verify_security_log()
    sys.exit(0 if success else 1)