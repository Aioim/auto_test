"""
测试数据库工具类（直接导入）

验证数据库连接和操作功能是否正常工作
"""
import os
import sys
import importlib.util

# 直接从文件路径导入db_helper模块
spec = importlib.util.spec_from_file_location(
    "db_helper", "E:/Code/auto_test/src/utils/data/db_helper.py"
)
db_helper_module = importlib.util.module_from_spec(spec)
sys.modules["db_helper"] = db_helper_module

# 替换logger导入，避免依赖其他模块
db_helper_module.logger = type('MockLogger', (), {
    'debug': lambda *args, **kwargs: None,
    'info': lambda *args, **kwargs: None,
    'warning': lambda *args, **kwargs: None,
    'error': lambda *args, **kwargs: None
})()

# 替换settings导入
db_helper_module.settings = type('MockSettings', (), {
    'locale': 'zh'
})()

spec.loader.exec_module(db_helper_module)

# 从模块中获取需要的对象
db_helper = db_helper_module.db_helper
execute_sql = db_helper_module.execute_sql
insert_data = db_helper_module.insert_data
update_data = db_helper_module.update_data
delete_data = db_helper_module.delete_data
get_session = db_helper_module.get_session


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
        import traceback
        traceback.print_exc()
        # 清理测试文件
        if os.path.exists('test.db'):
            os.remove('test.db')
        return False


def run_test():
    """
    运行测试
    """
    print("开始测试数据库工具类...")
    
    success = test_sqlite_connection()
    
    print(f"\n测试完成: {'通过' if success else '失败'}")
    
    return success


if __name__ == "__main__":
    success = run_test()
    sys.exit(0 if success else 1)