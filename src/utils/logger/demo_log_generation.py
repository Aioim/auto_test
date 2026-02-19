"""日志生成演示 - 生成各种类型的日志文件"""

import sys
import os
import time
import random

# Add src directory to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from utils.logger import (
    logger, api_logger, perf_logger, security_logger,
    log_exception, log_security_event, log_step, log_duration, log_performance,
    mask_sensitive_data, request_logger, cleanup,
    setup_logger, LogConfig
)

print("Log generation demo - generating various log files...")
print("=" * 80)

# 确保logs目录存在
def ensure_log_dir():
    """确保日志目录存在"""
    log_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "logs")
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
        print(f"Created log directory: {log_dir}")
    return log_dir

# 等待延迟初始化完成
def wait_for_initialization():
    """等待延迟初始化完成"""
    print("\nWaiting for logger initialization...")
    time.sleep(0.5)
    print("Initialization complete!")

# 生成主日志
def generate_main_logs():
    """生成主日志文件 (test_run.log)"""
    print("\n1. Generating main logs (test_run.log):")
    print("-" * 60)
    
    # 获取或创建主日志器
    main_logger = logger if logger else setup_logger("automation", log_to_file=True)
    
    # 生成不同级别的日志
    main_logger.debug("Debug message: This is a detailed debug message")
    main_logger.info("Info message: Application started successfully")
    main_logger.warning("Warning message: Disk usage is high")
    main_logger.error("Error message: Database connection failed")
    main_logger.critical("Critical message: System failure detected")
    
    # 生成带上下文的日志
    for i in range(3):
        user_id = random.randint(100, 999)
        action = random.choice(["login", "logout", "update_profile", "delete_account"])
        main_logger.info(f"User {user_id} performed {action}")
        time.sleep(0.1)
    
    print("✓ Main logs generated")

# 生成API日志
def generate_api_logs():
    """生成API日志文件 (api.log)"""
    print("\n2. Generating API logs (api.log):")
    print("-" * 60)
    
    # 创建API日志器
    api_logger_instance = setup_logger(
        "api", 
        log_level="DEBUG", 
        log_to_console=False, 
        separate_log_file="api.log"
    )
    
    # 生成API请求和响应日志
    endpoints = ["/api/login", "/api/users", "/api/products", "/api/orders", "/api/payments"]
    methods = ["GET", "POST", "PUT", "DELETE"]
    
    for i in range(5):
        method = random.choice(methods)
        endpoint = random.choice(endpoints)
        status_code = random.choice([200, 201, 400, 401, 404, 500])
        duration = random.uniform(10, 200)
        
        # 生成请求日志
        api_logger_instance.info(f"{method} {endpoint} (params: id={i}, token=******)")
        
        # 模拟处理时间
        time.sleep(0.05)
        
        # 生成响应日志
        status_marker = "✅" if 200 <= status_code < 300 else "❌"
        api_logger_instance.info(f"{status_marker} {method} {endpoint} {status_code} ({duration:.1f}ms)")
    
    print("✓ API logs generated")

# 生成性能日志
def generate_performance_logs():
    """生成性能日志文件 (performance.log)"""
    print("\n3. Generating performance logs (performance.log):")
    print("-" * 60)
    
    # 创建性能日志器
    perf_logger_instance = setup_logger(
        "performance", 
        log_level="DEBUG", 
        log_to_console=False, 
        separate_log_file="performance.log"
    )
    
    # 生成性能指标日志
    operations = ["database_query", "external_api_call", "cache_hit", "file_io", "cpu_intensive"]
    
    for i in range(10):
        operation = random.choice(operations)
        duration = random.uniform(1, 300)
        
        # 生成性能日志
        if duration > 100:
            perf_logger_instance.info(f"{operation} {duration:.2f}ms ⚠️ SLOW")
        else:
            perf_logger_instance.info(f"{operation} {duration:.2f}ms")
        
        time.sleep(0.02)
    
    print("✓ Performance logs generated")

# 生成安全日志
def generate_security_logs():
    """生成安全日志文件 (security.log)"""
    print("\n4. Generating security logs (security.log):")
    print("-" * 60)
    
    # 创建安全日志器
    security_logger_instance = setup_logger(
        "security", 
        log_level="INFO", 
        log_to_console=False, 
        separate_log_file="security.log"
    )
    
    # 生成安全事件日志
    actions = ["user_login", "user_logout", "permission_change", "data_access", "failed_authentication"]
    users = ["admin", "user123", "support_agent", "anonymous"]
    statuses = ["success", "failed", "denied", "compliant"]
    
    for i in range(8):
        action = random.choice(actions)
        user = random.choice(users)
        status = random.choice(statuses)
        ip = f"{random.randint(1, 255)}.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(0, 255)}"
        
        # 生成安全事件日志
        event = {
            "action": action,
            "user": user,
            "status": status,
            "ip": ip,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "details": {"resource": "/api/secure", "method": "POST"}
        }
        security_logger_instance.info(str(event).replace("'", '"'))
        
        time.sleep(0.05)
    
    print("✓ Security logs generated")

# 生成错误日志
def generate_error_logs():
    """生成错误日志文件 (error_*.log)"""
    print("\n5. Generating error logs (error_*.log):")
    print("-" * 60)
    
    # 创建错误日志器（会自动使用错误日志文件）
    error_logger = setup_logger("error_logger", log_to_file=True)
    
    # 生成错误日志
    errors = [
        "Database connection timeout",
        "API request failed with 500 error",
        "Invalid input parameters",
        "File not found",
        "Permission denied"
    ]
    
    for i in range(5):
        error_message = random.choice(errors)
        
        # 生成错误日志
        error_logger.error(f"❌ {error_message}")
        
        # 生成异常日志
        try:
            if random.random() > 0.5:
                raise ValueError(f"Test exception: {error_message}")
        except Exception:
            if log_exception:
                log_exception(context=f"test_error_{i}")
            else:
                error_logger.error(f"Exception: {error_message}")
        
        time.sleep(0.1)
    
    print("✓ Error logs generated")

# 生成自定义日志
def generate_custom_logs():
    """生成自定义日志文件 (custom_app.log)"""
    print("\n6. Generating custom logs (custom_app.log):")
    print("-" * 60)
    
    # 创建自定义日志器
    custom_logger = setup_logger(
        "custom_app", 
        log_level="DEBUG", 
        log_to_console=False, 
        separate_log_file="custom_app.log"
    )
    
    # 生成自定义日志
    activities = ["user_registered", "order_placed", "payment_processed", "email_sent", "notification_delivered"]
    
    for i in range(10):
        activity = random.choice(activities)
        user_id = random.randint(1000, 9999)
        
        # 生成不同级别的日志
        if random.random() > 0.7:
            custom_logger.debug(f"DEBUG: {activity} for user {user_id}")
        elif random.random() > 0.5:
            custom_logger.info(f"INFO: {activity} for user {user_id}")
        elif random.random() > 0.3:
            custom_logger.warning(f"WARNING: {activity} for user {user_id} requires attention")
        else:
            custom_logger.error(f"ERROR: Failed to process {activity} for user {user_id}")
        
        time.sleep(0.02)
    
    print("✓ Custom logs generated")

# 验证日志文件生成
def verify_log_files():
    """验证日志文件是否生成"""
    print("\n7. Verifying log files generation:")
    print("-" * 60)
    
    log_dir = ensure_log_dir()
    # Use today's date for error log file name
    today_date = time.strftime("%Y%m%d")
    expected_logs = [
        "test_run.log",
        "api.log",
        "performance.log",
        "security.log",
        f"error_{today_date}.log",
        "custom_app.log"
    ]
    
    generated_files = []
    missing_files = []
    
    for log_file in expected_logs:
        file_path = os.path.join(log_dir, log_file)
        if os.path.exists(file_path):
            file_size = os.path.getsize(file_path)
            generated_files.append((log_file, file_size))
            print(f"✓ {log_file} - {file_size} bytes")
        else:
            missing_files.append(log_file)
            print(f"✗ {log_file} - NOT FOUND")
    
    print(f"\nSummary:")
    print(f"Generated: {len(generated_files)} files")
    print(f"Missing: {len(missing_files)} files")
    
    if missing_files:
        print(f"Missing files: {', '.join(missing_files)}")
    else:
        print("✅ All expected log files were generated!")
    
    return len(missing_files) == 0

# 主函数
def main():
    """主函数"""
    try:
        # 确保日志目录存在
        ensure_log_dir()
        
        # 等待初始化
        wait_for_initialization()
        
        # 生成各种日志
        generate_main_logs()
        generate_api_logs()
        generate_performance_logs()
        generate_security_logs()
        generate_error_logs()
        generate_custom_logs()
        
        # 验证日志文件
        all_generated = verify_log_files()
        
        print("\n" + "=" * 80)
        if all_generated:
            print("✅ Log generation demo completed successfully!")
            print("All log files have been generated in the 'logs' directory.")
        else:
            print("⚠️  Log generation demo completed with some missing files.")
        print("=" * 80)
        
    except Exception as e:
        print(f"❌ Error during log generation: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 清理资源
        cleanup()
        print("\nResources cleaned up.")

if __name__ == "__main__":
    main()
