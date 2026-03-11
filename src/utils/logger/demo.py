"""Logger模块使用示例"""

import sys
import os
import time

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from src.utils.logger import (
    logger, api_logger, perf_logger, security_logger,
    log_exception, log_security_event, log_step, log_duration, log_performance,
    mask_sensitive_data, request_logger, cleanup,
    setup_logger
)

print("Logger module usage demo...")
print("=" * 70)

# 等待延迟初始化完成
time.sleep(0.5)

# 确保logger对象已初始化
def get_valid_logger():
    """获取有效的logger对象"""
    global logger
    if logger is None:
        print("⚠️  logger not initialized, creating temporary logger...")
        return setup_logger("demo", log_level="DEBUG", log_to_console=True)
    return logger

# 示例1: 基本日志记录
def demo_basic_logging():
    """演示基本日志记录"""
    print("\n1. Basic logging demo:")
    print("-" * 50)
    
    # 获取有效的logger对象
    demo_logger = get_valid_logger()
    
    # 不同级别的日志
    demo_logger.debug("This is a debug message")
    demo_logger.info("This is an info message")
    demo_logger.warning("This is a warning message")
    demo_logger.error("❌ Database connection timeout")
    demo_logger.critical("🚨 System failure!")
    
    # 带上下文的日志
    user_id = 123
    action = "login"
    demo_logger.info(f"User {user_id} performed {action}")

# 示例2: API日志记录
def demo_api_logging():
    """演示API日志记录"""
    print("\n2. API logging demo:")
    print("-" * 50)
    
    if request_logger:
        # 记录API请求
        request_id = request_logger.log_request(
            "POST", 
            "/api/login", 
            params={"username": "test", "password": "secret123"}
        )
        print(f"✓ Request logged with ID: {request_id}")
        
        # 模拟处理时间
        time.sleep(0.1)
        
        # 记录API响应
        request_logger.log_response(
            request_id, 
            200, 
            method="POST", 
            url="/api/login", 
            duration_ms=123.45
        )
        print("✓ Response logged")
    else:
        print("⚠️  request_logger not initialized")
        # 使用基本logger记录
        demo_logger = get_valid_logger()
        demo_logger.info("API logging demo: request_logger not available")

# 示例3: 性能日志记录
def demo_performance_logging():
    """演示性能日志记录"""
    print("\n3. Performance logging demo:")
    print("-" * 50)
    
    demo_logger = get_valid_logger()
    
    # 检查装饰器是否可用
    if log_performance and log_duration:
        # 使用装饰器记录函数性能
        @log_performance()
        def slow_function():
            """慢函数示例"""
            time.sleep(0.15)
            return "Done"
        
        # 使用上下文管理器记录代码块性能
        with log_duration("database_operation"):
            print("Performing database operation...")
            time.sleep(0.08)
        
        # 调用带性能日志的函数
        result = slow_function()
        print(f"✓ Performance logged, result: {result}")
    else:
        print("⚠️  Performance decorators not initialized")
        # 使用基本logger记录
        start_time = time.time()
        print("Performing database operation...")
        time.sleep(0.08)
        duration = (time.time() - start_time) * 1000
        demo_logger.info(f"Database operation took {duration:.2f}ms")
        
        start_time = time.time()
        time.sleep(0.15)
        duration = (time.time() - start_time) * 1000
        result = "Done"
        demo_logger.info(f"Slow function took {duration:.2f}ms, result: {result}")
        print(f"✓ Performance measured manually, result: {result}")

# 示例4: 安全事件日志记录
def demo_security_logging():
    """演示安全事件日志记录"""
    print("\n4. Security logging demo:")
    print("-" * 50)
    
    demo_logger = get_valid_logger()
    
    if log_security_event:
        # 记录登录事件
        success = log_security_event(
            "login",
            user="admin",
            resource="/api/login",
            status="success",
            details={"ip": "192.168.1.100", "user_agent": "Mozilla/5.0"}
        )
        print(f"✓ Login event logged: {success}")
        
        # 记录权限变更事件
        success = log_security_event(
            "permission_change",
            user="admin",
            resource="/api/users/123",
            status="success",
            details={"action": "grant_admin", "target_user": "user1"}
        )
        print(f"✓ Permission change event logged: {success}")
    else:
        print("⚠️  log_security_event not initialized")
        demo_logger.info("Security logging demo: log_security_event not available")

# 示例5: 异常日志记录
def demo_exception_logging():
    """演示异常日志记录"""
    print("\n5. Exception logging demo:")
    print("-" * 50)
    
    demo_logger = get_valid_logger()
    
    try:
        # 故意引发异常
        result = 10 / 0
    except Exception:
        if log_exception:
            # 记录异常
            log_exception(context="division_by_zero")
            print("✓ Exception logged")
        else:
            print("⚠️  log_exception not initialized")
            demo_logger.error("Exception logging demo: log_exception not available")
            import traceback
            traceback.print_exc()

# 示例6: 敏感数据脱敏
def demo_data_masking():
    """演示敏感数据脱敏"""
    print("\n6. Sensitive data masking demo:")
    print("-" * 50)
    
    demo_logger = get_valid_logger()
    
    # 测试数据
    test_data = [
        "Password: mysecret123",
        "Token: abcdef123456",
        "Email: user@example.com",
        "Phone: 13812345678",
        "Credit Card: 1234567890123456"
    ]
    
    if mask_sensitive_data:
        for data in test_data:
            masked = mask_sensitive_data(data)
            print(f"Original: {data}")
            print(f"Masked:   {masked}")
        print("✓ Data masking demonstrated")
    else:
        print("⚠️  mask_sensitive_data not initialized")
        # 手动实现简单的脱敏
        for data in test_data:
            if "Password:" in data or "Token:" in data:
                masked = data.split(":")[0] + ": ******"
            elif "Email:" in data:
                parts = data.split(": ")[1].split("@")
                masked = f"Email: ***@{parts[1]}"
            else:
                masked = data
            print(f"Original: {data}")
            print(f"Masked:   {masked}")
        demo_logger.info("Data masking demo: using manual masking")

# 示例7: 自定义日志器
def demo_custom_logger():
    """演示自定义日志器"""
    print("\n7. Custom logger demo:")
    print("-" * 50)
    
    try:
        # 创建自定义日志器
        custom_logger = setup_logger(
            "my_app",
            log_level="DEBUG",
            log_to_console=True,
            separate_log_file="my_app.log"
        )
        
        custom_logger.info("Custom logger initialized")
        custom_logger.debug("Debug message from custom logger")
        print("✓ Custom logger created and used")
    except Exception as e:
        print(f"⚠️  Custom logger creation failed: {e}")
        demo_logger = get_valid_logger()
        demo_logger.error(f"Custom logger demo failed: {e}")

# 示例8: 配置信息
def demo_config():
    """演示配置信息"""
    print("\n8. Configuration demo:")
    print("-" * 50)
    
    demo_logger = get_valid_logger()
    
    try:
        print(f"Log directory: {LogConfig.LOG_DIR}")
        print(f"Log level: {LogConfig.LOG_LEVEL}")
        print(f"Environment: {LogConfig.ENV}")
        print(f"Backup count: {LogConfig.BACKUP_COUNT}")
        print(f"Max log size: {LogConfig.MAX_BYTES / 1024 / 1024:.1f}MB")
        print("✓ Configuration displayed")
    except Exception as e:
        print(f"⚠️  Configuration access failed: {e}")
        demo_logger.error(f"Configuration demo failed: {e}")

# 示例9: 步骤日志
def demo_step_logging():
    """演示步骤日志"""
    print("\n9. Step logging demo:")
    print("-" * 50)
    
    demo_logger = get_valid_logger()
    
    if log_step:
        @log_step("Process data")
        def process_data():
            """处理数据"""
            print("Processing data...")
            time.sleep(0.05)
            return "Data processed"
        
        result = process_data()
        print(f"✓ Step logged, result: {result}")
    else:
        print("⚠️  log_step not initialized")
        # 手动记录步骤
        demo_logger.info("▶️ Step: Process data")
        print("Processing data...")
        time.sleep(0.05)
        result = "Data processed"
        demo_logger.info(f"✅ Completed: Process data")
        print(f"✓ Step recorded manually, result: {result}")

# 运行所有示例
if __name__ == "__main__":
    print(f"Starting logger demo at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        demo_basic_logging()
        demo_api_logging()
        demo_performance_logging()
        demo_security_logging()
        demo_exception_logging()
        demo_data_masking()
        demo_custom_logger()
        demo_config()
        demo_step_logging()
        
        print("\n" + "=" * 70)
        print("✅ All demos completed successfully!")
        print("Check the logs directory for generated log files:")
        print("- test_run.log: Main log file")
        print("- api.log: API request/response logs")
        print("- performance.log: Performance metrics")
        print("- security.log: Security events")
        print("- error_*.log: Error logs")
        print("- my_app.log: Custom logger logs")
        print("=" * 70)
        
    except Exception as e:
        print(f"❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 清理资源
        cleanup()
        print("\nDemo finished.")
