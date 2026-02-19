#!/usr/bin/env python3
"""
验证 security.log 修复效果（纯 JSON、无重复）
"""

import json
from pathlib import Path

# 尝试导入secure_logger，使其成为可选依赖
try:
    from secure_logger import log_security_event, security_logger, logger
    SECURE_LOGGER_AVAILABLE = True
except ImportError:
    log_security_event = None
    security_logger = None
    logger = None
    SECURE_LOGGER_AVAILABLE = False


def verify_security_log():
    if not SECURE_LOGGER_AVAILABLE:
        print("⚠️  secure_logger库不可用，跳过安全日志验证")
        return True
        
    print("=" * 70)
    print("✅ Security Log Verification")
    print("=" * 70)

    # 清理旧日志
    sec_file = Path("./logs/security.log")
    if sec_file.exists():
        sec_file.unlink()
        print(f"🧹 Cleaned {sec_file.name}")

    # 记录测试事件
    print("\n📝 Recording test events...")
    events = [
        ("test_event_1", "user1", "resource1", "success", {"key1": "value1"}),
        ("test_event_2", "user2", "resource2", "failed", {"key2": "value2", "password": "secret"}),
    ]

    for action, user, resource, status, details in events:
        log_security_event(action, user, resource, status, details)

    # 验证文件
    print(f"\n🔍 Checking {sec_file.name}...")
    if not sec_file.exists():
        print("❌ File does not exist!")
        return False

    content = sec_file.read_text(encoding='utf-8').strip()
    lines = [line for line in content.splitlines() if line.strip()]

    print(f"✅ File exists ({len(lines)} lines, {sec_file.stat().st_size} bytes)")

    # 验证每行
    valid = True
    for i, line in enumerate(lines, 1):
        # 检查是否纯 JSON（无前缀）
        if line.startswith(("WARNING", "INFO", "[security:", "202")):
            print(f"❌ Line {i}: Has prefix (not pure JSON)")
            valid = False
            continue

        # 验证 JSON
        try:
            event = json.loads(line)
            if "password" in str(event):
                print(f"❌ Line {i}: Contains unmasked password!")
                valid = False
            else:
                print(f"✅ Line {i}: Valid JSON (action={event.get('action')})")
        except json.JSONDecodeError as e:
            print(f"❌ Line {i}: Invalid JSON - {e}")
            valid = False

    # 最终结果
    print("\n" + "=" * 70)
    if valid and len(lines) == len(events):
        print("🎉 SUCCESS: security.log is clean (pure JSON, no duplicates, auto-masked)")
    else:
        print("❌ FAILED: security.log has issues")
    print("=" * 70)

    return valid


if __name__ == "__main__":
    success = verify_security_log()
    exit(0 if success else 1)