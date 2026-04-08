#!/usr/bin/env python3
"""
log_monitor.py - 实时日志监控器（密码泄露检测）

改进版本（含异常类型输出、行号精确跟踪）：
- 逐行读取日志，避免跨块截断导致的漏报
- 使用 inode 跟踪文件轮转，防止数据丢失
- 排除自身告警文件，消除无限循环
- 紧急文件设置 600 权限，防止二次泄露（仅限 Linux/Unix）
- 安全模式改用正则精确匹配
- 信号处理改为轮询方式，确保优雅退出
- 优化睡眠机制，支持可中断等待
- 新增统计功能：扫描文件数、处理行数、泄露次数，停止时输出报告
- 泄露告警时输出文件路径、行号及具体异常类型（密码/Token/Bearer/API Key）
- 白名单排除常见误报（UUID、长数字串等）
- 紧急文件不再记录敏感内容，只保存元数据

运行方式:
  $ python log_monitor.py --log-dir ./logs

生产环境建议:
  $ nohup python log_monitor.py --log-dir /var/log/myapp > /var/log/log_monitor.log 2>&1 &
"""

import re
import time
import sys
import signal
import argparse
import platform
import os
import threading
from pathlib import Path
from threading import Thread, Event, RLock
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple, List

IS_WINDOWS = platform.system() == "Windows"


class RealtimeLogMonitor:
    """实时日志文件扫描（检测脱敏失败）"""

    # 敏感模式及其对应的异常类型描述（更严格的上下文）
    SENSITIVE_PATTERNS = [
        # (pattern, type_name)
        (re.compile(r'\b(password|pwd|pass)[=:]\s*["\']?([^\s"\'\n]{8,})', re.IGNORECASE),
         "PASSWORD LEAK"),
        (re.compile(r'\b(token|secret)[=:]\s*["\']?([a-zA-Z0-9\-_\.+/]{30,})', re.IGNORECASE),
         "TOKEN/SECRET LEAK"),
        (re.compile(r'\bbearer\s+([a-zA-Z0-9\-_\.+/]{30,})', re.IGNORECASE),
         "BEARER TOKEN LEAK"),
        (re.compile(r'\b(api[_\-]?key)[=:]\s*["\']?([a-zA-Z0-9\-_+/]{20,})', re.IGNORECASE),
         "API KEY LEAK"),
    ]

    # 安全模式改为正则表达式，精确匹配脱敏后的字段（至少6个星号）
    SAFE_PATTERNS = [
        re.compile(r'password=\*{6,}', re.IGNORECASE),
        re.compile(r'pwd=\*{6,}', re.IGNORECASE),
        re.compile(r'token=\*{6,}', re.IGNORECASE),
        re.compile(r'secret=\*{6,}', re.IGNORECASE),
        re.compile(r'authorization:\s*bearer\s+\*{6,}', re.IGNORECASE),
        re.compile(r'credit_card=\*{6,}', re.IGNORECASE),
    ]

    # 白名单模式：匹配这些模式的值认为是安全的（如 UUID、长数字串）
    DEFAULT_WHITELIST_PATTERNS = [
        re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.IGNORECASE),  # UUID
        re.compile(r'^\d{15,19}$'),  # 长数字串（信用卡号等）
        re.compile(r'^[a-f0-9]{32,64}$', re.IGNORECASE),  # MD5/SHA-1/SHA-256 十六进制哈希
    ]

    def __init__(self, log_dir: Path, check_interval: float = 1.0):
        self.log_dir = log_dir.resolve()
        self.check_interval = check_interval
        self.running = Event()
        self.running.set()
        self.thread: Optional[Thread] = None
        self.file_positions: Dict[Path, int] = {}
        self.file_inodes: Dict[Path, int] = {}          # 跟踪 inode 用于检测文件轮转
        self.file_line_numbers: Dict[Path, int] = {}    # 跟踪每个文件已处理的行数（绝对行号）
        self.lock = RLock()  # 保护上述三个字典

        # 加载额外白名单（环境变量）
        self.whitelist_patterns = list(self.DEFAULT_WHITELIST_PATTERNS)
        extra_whitelist = os.environ.get("LOG_MONITOR_WHITELIST_PATTERNS")
        if extra_whitelist:
            for pattern_str in extra_whitelist.split(";"):
                try:
                    self.whitelist_patterns.append(re.compile(pattern_str))
                except re.error as e:
                    print(f"⚠️  Invalid whitelist pattern '{pattern_str}': {e}", file=sys.stderr)

        # 统计信息
        self.stats = {
            'start_time': None,      # 监控开始时间
            'files_scanned': 0,      # 累计扫描的不同文件数量（去重）
            'lines_scanned': 0,      # 累计处理的行数
            'leaks_found': 0,        # 发现的泄露次数
        }
        self.stats_lock = threading.Lock()

        if not self.log_dir.exists():
            raise ValueError(f"Log directory not found: {self.log_dir}")
        if not self.log_dir.is_dir():
            raise ValueError(f"Not a directory: {self.log_dir}")

    def start(self):
        """启动监控线程"""
        if self.thread and self.thread.is_alive():
            print("Monitor already running", file=sys.stderr)
            return

        with self.stats_lock:
            self.stats['start_time'] = datetime.now()
            self.stats['files_scanned'] = 0
            self.stats['lines_scanned'] = 0
            self.stats['leaks_found'] = 0

        self.running.set()
        self.thread = Thread(
            target=self._monitor_loop,
            daemon=False,
            name="LogMonitor"
        )
        self.thread.start()
        print(f"✅ Realtime log monitor started (watching {self.log_dir})")
        print(f"   Press Ctrl+C to stop gracefully\n")

    def stop(self, timeout: float = 2.0):
        """停止监控，并打印最终统计报告"""
        if not self.running.is_set():
            return

        print("\n🛑 Stopping monitor...", end='', flush=True)
        self.running.clear()

        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=timeout)
            if self.thread.is_alive():
                print("⚠️  (forced)", end='', flush=True)

        print("✅", flush=True)

        # 打印最终统计结果
        self._print_summary()

    def _print_summary(self):
        """输出监控结束时的统计报告"""
        with self.stats_lock:
            end_time = datetime.now()
            start_time = self.stats['start_time']
            duration = (end_time - start_time).total_seconds() if start_time else 0
            files = self.stats['files_scanned']
            lines = self.stats['lines_scanned']
            leaks = self.stats['leaks_found']

        print("\n" + "=" * 60)
        print("📊 MONITORING SUMMARY")
        print("=" * 60)
        print(f"   Duration          : {duration:.2f} seconds")
        print(f"   Log files scanned : {files}")
        print(f"   Lines processed   : {lines:,}")
        print(f"   Password leaks    : {leaks}")
        if leaks > 0:
            print("\n⚠️  WARNING: Password leaks detected! Check EMERGENCY_PASSWORD_LEAK.log")
        else:
            print("\n✅ No password leaks detected.")
        print("=" * 60)

    def _monitor_loop(self):
        """主监控循环 - 使用 Event.wait() 实现可中断睡眠"""
        print(f"🔍 Monitoring logs for password leaks (checking every {self.check_interval}s)...\n")

        while self.running.is_set():
            try:
                self._scan_log_files()
                # 使用 Event.wait 代替 sleep，可以被 running.clear() 立即唤醒
                self.running.wait(timeout=self.check_interval)
            except Exception as e:
                if self.running.is_set():
                    print(f"⚠️  Monitor error: {e}", file=sys.stderr)
                    self.running.wait(timeout=min(1.0, self.check_interval))

    def _scan_log_files(self):
        """扫描所有 .log 文件，更新统计"""
        try:
            for log_file in self.log_dir.glob("*.log"):
                if not log_file.is_file():
                    continue
                if "log_monitor" in log_file.name.lower() or log_file.name == "EMERGENCY_PASSWORD_LEAK.log":
                    continue
                # 记录扫描到的文件（去重）
                with self.lock:
                    if log_file not in self.file_positions:
                        with self.stats_lock:
                            self.stats['files_scanned'] += 1
                self._scan_file(log_file)
        except Exception as e:
            print(f"⚠️  Scan error: {e}", file=sys.stderr)

    def _scan_file(self, log_file: Path):
        """扫描单个文件，支持文件轮转检测（基于 inode），并跟踪行号"""
        # 获取当前文件状态
        try:
            stat = log_file.stat()
            curr_size = stat.st_size
            curr_inode = stat.st_ino
        except FileNotFoundError:
            # 文件被删除，清理跟踪信息
            with self.lock:
                self.file_positions.pop(log_file, None)
                self.file_inodes.pop(log_file, None)
                self.file_line_numbers.pop(log_file, None)
            return

        with self.lock:
            last_inode = self.file_inodes.get(log_file)
            last_pos = self.file_positions.get(log_file, 0)
            current_line = self.file_line_numbers.get(log_file, 0)

        # 检测文件轮转（inode 变化）
        if last_inode != curr_inode:
            # 文件已被轮转（重新创建），从头开始读取
            with self.lock:
                self.file_positions[log_file] = 0
                self.file_inodes[log_file] = curr_inode
                self.file_line_numbers[log_file] = 0
            last_pos = 0
            current_line = 0
        # 检测文件截断（例如被 truncate 清空）
        elif curr_size < last_pos:
            # 文件被截断，重置到开头
            with self.lock:
                self.file_positions[log_file] = 0
                self.file_line_numbers[log_file] = 0
            last_pos = 0
            current_line = 0

        # 文件未增长，仅更新位置（避免重复读取）
        if curr_size <= last_pos:
            with self.lock:
                self.file_positions[log_file] = curr_size
            return

        # 逐行读取新增内容，并记录绝对行号
        try:
            line_count = 0
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                f.seek(last_pos)
                # 使用 enumerate 从 current_line+1 开始编号
                for i, line in enumerate(f, start=current_line + 1):
                    line_count += 1
                    self._scan_content(line, log_file, lineno=i, leak_type=None)
                # 更新文件位置和行号
                new_pos = f.tell()
                new_line = current_line + line_count
                with self.lock:
                    self.file_positions[log_file] = new_pos
                    self.file_line_numbers[log_file] = new_line
            # 更新统计行数
            with self.stats_lock:
                self.stats['lines_scanned'] += line_count
        except Exception as e:
            print(f"⚠️  Read error {log_file.name}: {e}", file=sys.stderr)

    def _is_whitelisted(self, value: str) -> bool:
        """检查敏感值是否匹配白名单模式（如 UUID）"""
        for pattern in self.whitelist_patterns:
            if pattern.fullmatch(value):
                return True
        return False

    def _scan_content(self, line: str, source_file: Path, lineno: int, leak_type: Optional[str] = None):
        """
        扫描单行内容，检测敏感信息。
        如果匹配到敏感模式，会调用 _handle_password_leak 并传入具体的异常类型。
        """
        # 检查是否为安全模式（脱敏后的行）
        if any(safe.search(line) for safe in self.SAFE_PATTERNS):
            return

        for pattern, leak_category in self.SENSITIVE_PATTERNS:
            match = pattern.search(line)
            if match:
                # 提取匹配的敏感值（第二个捕获组）
                sensitive_value = match.group(2) if match.lastindex >= 2 else match.group(1)
                # 白名单过滤：如果敏感值匹配已知安全模式，则忽略
                if self._is_whitelisted(sensitive_value):
                    return
                self._handle_password_leak(line, source_file, lineno, leak_category)
                break  # 一行只报告第一次匹配

    def _handle_password_leak(self, line: str, source_file: Path, lineno: int, leak_type: str):
        """处理密码泄露事件：控制台告警 + 写入紧急文件（权限 600），并更新统计"""
        # 更新泄露计数
        with self.stats_lock:
            self.stats['leaks_found'] += 1

        timestamp = datetime.now(timezone.utc).isoformat()

        # 控制台告警（stderr），不输出敏感值预览，只输出类型和位置

        print(f"CRITICAL: {leak_type} DETECTED IN LOGS 🚨", file=sys.stderr)
        print(f"Time    : {timestamp}", file=sys.stderr)
        print(f"File    : {source_file}", file=sys.stderr)   # 完整路径
        if lineno > 0:
            print(f"Line    : {lineno}", file=sys.stderr)
        print(f"Type    : {leak_type}", file=sys.stderr)
        print("Action  : Rotate credentials IMMEDIATELY!", file=sys.stderr)
        print("\n", file=sys.stderr)


        # 写入应急文件（权限 0o600，仅所有者可读写）—— 不保存敏感内容
        emergency_file = self.log_dir / "EMERGENCY_PASSWORD_LEAK.log"
        try:
            # 尝试设置权限（Windows 下可能无效，但不会报错）
            flags = os.O_CREAT | os.O_WRONLY | os.O_APPEND
            mode = 0o600
            fd = os.open(emergency_file, flags, mode)
            with os.fdopen(fd, 'a', encoding='utf-8') as f:
                f.write(
                    f"[{timestamp}] CRITICAL: {leak_type} detected!\n"
                    f"  Source: {source_file}:{lineno if lineno > 0 else 'unknown'}\n"
                    f"  Type: {leak_type}\n"
                    f"  Action: Rotate credentials IMMEDIATELY!\n"
                    f"{'='*80}\n\n"
                )
            # 确保权限（再次尝试，Windows 会忽略）
            if not IS_WINDOWS:
                os.chmod(emergency_file, 0o600)
        except Exception as e:
            print(f"⚠️  Emergency file write failed: {e}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="Realtime Log Monitor for Password Leaks")
    parser.add_argument("--log-dir", default="./logs", help="Log directory to monitor (default: ./logs)")
    parser.add_argument("--interval", type=float, default=1.0, help="Check interval in seconds (default: 1.0)")
    args = parser.parse_args()

    log_dir = Path(args.log_dir)
    if not log_dir.exists():
        print(f"❌ Error: Log directory not found: {log_dir}", file=sys.stderr)
        sys.exit(1)

    monitor = RealtimeLogMonitor(log_dir=log_dir, check_interval=args.interval)

    # 全局退出标志（用于信号处理）
    exit_flag = False

    def signal_handler(sig, frame):
        nonlocal exit_flag
        if not exit_flag:
            print("\n\n🛑 Received stop signal...", file=sys.stderr)
            exit_flag = True

    signal.signal(signal.SIGINT, signal_handler)
    if not IS_WINDOWS:
        signal.signal(signal.SIGTERM, signal_handler)

    import atexit
    def cleanup():
        if monitor.running.is_set():
            monitor.stop(timeout=1.0)
    atexit.register(cleanup)

    try:
        monitor.start()

        # 主线程等待监控线程结束，同时定期检查 exit_flag
        while not exit_flag and monitor.thread and monitor.thread.is_alive():
            monitor.thread.join(timeout=0.2)  # 可中断等待

        # 如果 exit_flag 被设置，主动停止监控
        if exit_flag:
            monitor.stop(timeout=1.0)

    except KeyboardInterrupt:
        monitor.stop(timeout=1.0)
    except SystemExit:
        raise
    except Exception as e:
        print(f"\n❌ Fatal error: {e}", file=sys.stderr)
        monitor.stop(timeout=1.0)
        sys.exit(1)

    print("\n👋 Monitor stopped. Exiting.")


if __name__ == "__main__":
    main()