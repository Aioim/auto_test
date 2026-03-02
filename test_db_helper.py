"""
测试数据库工具类

验证数据库连接和操作功能是否正常工作
"""
import os
import sys
# 直接导入db_helper模块，避免依赖其他模块
from src.utils.data.db_helper import (
    db_helper,
    execute_sql,
    insert_data,
    update_data,
    delete_data,
    get_session
)


def test_sqlite_connection():
    """
    测试 SQLite 数据库连接
    """
    print("\n=== 测试 SQLite 数据库连接 ===")
    
    try:
        # 创建测试表
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS test_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            age INTEGER
        )
        """
        execute_sql('sqlite', create_table_sql, database='test.db')
        print("✓ 成功创建测试表")
        
        # 插入测试数据
        data = {
            'name': '测试用户',
            'email': 'test@example.com',
            'age': 25
        }
        rows_affected = insert_data('sqlite', 'test_users', data, database='test.db')
        print(f"✓ 成功插入 {rows_affected} 条数据")
        
        # 查询测试数据
        select_sql = "SELECT * FROM test_users"
        results = execute_sql('sqlite', select_sql, database='test.db')
        print(f"✓ 查询到 {len(results)} 条数据")
        for row in results:
            print(f"  - {row}")
        
        # 更新测试数据
        update_data_sql = {
            'name': '更新后的用户',
            'age': 30
        }
        rows_affected = update_data('sqlite', 'test_users', update_data_sql, 'id = :id', {'id': 1}, database='test.db')
        print(f"✓ 成功更新 {rows_affected} 条数据")
        
        # 再次查询验证更新
        results = execute_sql('sqlite', select_sql, database='test.db')
        print(f"✓ 更新后查询到 {len(results)} 条数据")
        for row in results:
            print(f"  - {row}")
        
        # 删除测试数据
        rows_affected = delete_data('sqlite', 'test_users', 'id = :id', {'id': 1}, database='test.db')
        print(f"✓ 成功删除 {rows_affected} 条数据")
        
        # 再次查询验证删除
        results = execute_sql('sqlite', select_sql, database='test.db')
        print(f"✓ 删除后查询到 {len(results)} 条数据")
        
        # 清理测试文件
        if os.path.exists('test.db'):
            os.remove('test.db')
            print("✓ 成功清理测试文件")
        
        return True
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        # 清理测试文件
        if os.path.exists('test.db'):
            os.remove('test.db')
        return False


def test_get_session():
    """
    测试获取数据库会话
    """
    print("\n=== 测试获取数据库会话 ===")
    
    try:
        # 使用上下文管理器获取会话
        with get_session('sqlite', database='test_session.db') as session:
            # 创建测试表
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS test_session_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL
            )
            """
            session.execute(create_table_sql)
            session.commit()
            print("✓ 成功创建测试表")
            
            # 插入测试数据
            insert_sql = "INSERT INTO test_session_users (name) VALUES (:name)"
            session.execute(insert_sql, {'name': '会话测试用户'})
            session.commit()
            print("✓ 成功插入测试数据")
            
            # 查询测试数据
            select_sql = "SELECT * FROM test_session_users"
            result = session.execute(select_sql)
            rows = result.fetchall()
            print(f"✓ 查询到 {len(rows)} 条数据")
            for row in rows:
                print(f"  - {row}")
        
        # 清理测试文件
        if os.path.exists('test_session.db'):
            os.remove('test_session.db')
            print("✓ 成功清理测试文件")
        
        return True
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        # 清理测试文件
        if os.path.exists('test_session.db'):
            os.remove('test_session.db')
        return False


def test_connection_pool():
    """
    测试数据库连接池
    """
    print("\n=== 测试数据库连接池 ===")
    
    try:
        # 多次执行查询，验证连接池是否正常工作
        for i in range(5):
            results = execute_sql('sqlite', 'SELECT 1 as test', database='test_pool.db')
            print(f"✓ 连接池测试 {i+1}/5 成功")
        
        # 清理测试文件
        if os.path.exists('test_pool.db'):
            os.remove('test_pool.db')
            print("✓ 成功清理测试文件")
        
        return True
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        # 清理测试文件
        if os.path.exists('test_pool.db'):
            os.remove('test_pool.db')
        return False


def test_close_connections():
    """
    测试关闭数据库连接
    """
    print("\n=== 测试关闭数据库连接 ===")
    
    try:
        # 执行一些操作，建立连接
        execute_sql('sqlite', 'CREATE TABLE IF NOT EXISTS test_close (id INTEGER PRIMARY KEY)', database='test_close.db')
        print("✓ 成功建立连接")
        
        # 关闭所有连接
        db_helper.close_all()
        print("✓ 成功关闭所有连接")
        
        # 清理测试文件
        if os.path.exists('test_close.db'):
            os.remove('test_close.db')
            print("✓ 成功清理测试文件")
        
        return True
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        # 清理测试文件
        if os.path.exists('test_close.db'):
            os.remove('test_close.db')
        return False


def run_all_tests():
    """
    运行所有测试
    """
    print("开始测试数据库工具类...")
    
    tests = [
        test_sqlite_connection,
        test_get_session,
        test_connection_pool,
        test_close_connections
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        if test():
            passed += 1
        else:
            failed += 1
    
    print(f"\n测试完成: {passed} 个通过, {failed} 个失败")
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)