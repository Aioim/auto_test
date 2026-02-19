"""
log_monitor.py - 实时日志监控器（密码泄露检测）

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
from pathlib import Path
from threading import Thread, Event
from datetime import datetime, timezone
from typing import Dict

IS_WINDOWS = platform.system() == "Windows"

class RealtimeLogMonitor:
    """实时日志文件扫描（检测脱敏失败）"""

    PASSWORD_PATTERNS = [
        re.compile(r'(?i)(password|pwd|pass)[=:]\s*["\']?([a-zA-Z0-9!@#$%^&*()_+\-]{8,})', re.UNICODE),
        re.compile(r'(?i)(token|secret)[=:]\s*["\']?([a-zA-Z0-9\-_\.]{30,})', re.UNICODE),
        re.compile(r'(?i)bearer\s+([a-zA-Z0-9\-_\.]{30,})', re.IGNORECASE),
        re.compile(r'(?i)(api[_-]?key)[=:]\s*["\']?([a-zA-Z0-9\-_]{20,})', re.UNICODE),
    ]

    SAFE_PATTERNS = [
        'password=******', 'pwd=******', 'token=******', 'secret=******',
        'authorization: bearer ******', 'credit_card=******'
    ]

    def __init__(self, log_dir: Path, check_interval: float = 1.0):
        self.log_dir = log_dir.resolve()
        self.check_interval = check_interval
        self.running = Event()
        self.running.set()
        self.thread = None
        self.file_positions: Dict[Path, int] = {}

        if not self.log_dir.exists():
            raise ValueError(f"Log directory not found: {self.log_dir}")
        if not self.log_dir.is_dir():
            raise ValueError(f"Not a directory: {self.log_dir}")

    def start(self):
        """启动监控线程"""
        if self.thread and self.thread.is_alive():
            print("Monitor already running", file=sys.stderr)
            return

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
        """停止监控"""
        if not self.running.is_set():
            return

        print("\n🛑 Stopping monitor...", end='', flush=True)
        self.running.clear()

        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=timeout)
            if self.thread.is_alive():
                print("⚠️  (forced)", end='', flush=True)

        print("✅", flush=True)

    def _monitor_loop(self):
        """主监控循环"""
        print(f"🔍 Monitoring logs for password leaks (checking every {self.check_interval}s)...\n")

        while self.running.is_set():
            try:
                self._scan_log_files()

                # 使用短循环避免阻塞
                for _ in range(int(self.check_interval / 0.1)):
                    if not self.running.is_set():
                        return
                    time.sleep(0.1)

            except Exception as e:
                if self.running.is_set():
                    print(f"⚠️  Monitor error: {e}", file=sys.stderr)
                    time.sleep(min(1.0, self.check_interval))

    def _scan_log_files(self):
        try:
            for log_file in self.log_dir.glob("*.log"):
                if not log_file.is_file() or "log_monitor" in log_file.name.lower():
                    continue
                self._scan_file(log_file)
        except Exception as e:
            print(f"⚠️  Scan error: {e}", file=sys.stderr)

    def _scan_file(self, log_file: Path):
        last_pos = self.file_positions.get(log_file, 0)
        try:
            curr_size = log_file.stat().st_size
        except FileNotFoundError:
            self.file_positions.pop(log_file, None)
            return

        if curr_size <= last_pos:
            self.file_positions[log_file] = curr_size
            return

        try:
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                f.seek(last_pos)
                new_content = f.read(1024 * 1024)  # 限制单次读取1MB
                self.file_positions[log_file] = f.tell()
        except Exception as e:
            print(f"⚠️  Read error {log_file.name}: {e}", file=sys.stderr)
            return

        if new_content:
            self._scan_content(new_content, log_file)

    def _scan_content(self, content: str, source_file: Path):
        lines = content.splitlines()
        for lineno, line in enumerate(lines, 1):
            if any(safe in line.lower() for safe in self.SAFE_PATTERNS):
                continue

            for pattern in self.PASSWORD_PATTERNS:
                match = pattern.search(line)
                if match:
                    password_preview = (match.group(2)[:4] + "...") if len(match.group(2)) > 4 else "****"
                    self._handle_password_leak(line, source_file, lineno, password_preview)
                    break

    def _handle_password_leak(self, line: str, source_file: Path, lineno: int, password_preview: str):
        timestamp = datetime.now(timezone.utc).isoformat()

        # 高亮控制台告警
        print("\n" + "🚨" * 5, file=sys.stderr)
        print(f"🚨 CRITICAL: PASSWORD LEAK DETECTED IN LOGS 🚨", file=sys.stderr)
        print("🚨" * 5, file=sys.stderr)
        print(f"   Time     : {timestamp}", file=sys.stderr)
        print(f"   File     : {source_file.name}", file=sys.stderr)
        print(f"   Line     : {lineno}", file=sys.stderr)
        print(f"   Preview  : ...{password_preview}...", file=sys.stderr)
        print(f"   Raw Line : {line[:120]}", file=sys.stderr)
        print("🚨" * 5 + "\n", file=sys.stderr)

        # 写入应急文件
        emergency_file = self.log_dir / "EMERGENCY_PASSWORD_LEAK.log"
        try:
            with open(emergency_file, 'a', encoding='utf-8') as f:
                f.write(
                    f"[{timestamp}] CRITICAL: Password leak detected!\n"
                    f"  Source: {source_file.name}:{lineno}\n"
                    f"  Preview: ...{password_preview}...\n"
                    f"  Line: {line[:200]}\n"
                    f"  Action: Rotate credentials IMMEDIATELY!\n"
                    f"{'='*80}\n\n"
                )
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

    # 注册信号处理器
    def signal_handler(sig, frame):
        print("\n\n🛑 Received stop signal...", file=sys.stderr)
        monitor.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    if not IS_WINDOWS:
        signal.signal(signal.SIGTERM, signal_handler)

    import atexit
    atexit.register(lambda: monitor.stop(timeout=1.0) if monitor.running.is_set() else None)

    try:
        monitor.start()

        if IS_WINDOWS:
            while monitor.running.is_set() and monitor.thread.is_alive():
                time.sleep(0.1)
        else:
            while monitor.running.is_set() and monitor.thread.is_alive():
                signal.pause()

    except KeyboardInterrupt:
        monitor.stop(timeout=1.0)
    except SystemExit:
        raise
    except Exception as e:
        print(f"\n❌ Fatal error: {e}", file=sys.stderr)
        monitor.stop(timeout=1.0)
        sys.exit(1)

if __name__ == "__main__":
    main()