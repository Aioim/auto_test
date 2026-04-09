"""
数据库操作辅助类

提供通用的数据库连接和操作方法，支持MySQL、PostgreSQL、SQLite等常见数据库。
"""
from __future__ import annotations
from typing import Optional, Dict, Any, List, Tuple, Union
from contextlib import contextmanager
try:
    import pymysql
except ImportError:
    pymysql = None

try:
    import psycopg2
except ImportError:
    psycopg2 = None

try:
    import sqlite3
except ImportError:
    sqlite3 = None
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError
from logger import logger
from config import settings


class DatabaseHelper:
    """
    数据库操作辅助类
    
    提供数据库连接、查询、执行等通用方法
    """
    
    # 数据库类型映射
    DB_TYPES = {
        'mysql': 'mysql+pymysql',
        'postgresql': 'postgresql+psycopg2',
        'sqlite': 'sqlite'
    }
    
    def __init__(self):
        """
        初始化数据库辅助类
        """
        self._connections: Dict[str, Any] = {}
        self._engines: Dict[str, Any] = {}
        self._sessions: Dict[str, Any] = {}
    
    def get_connection_string(self, db_type: str, host: Optional[str] = None, port: Optional[int] = None,
                             database: Optional[str] = None, user: Optional[str] = None,
                             password: Optional[str] = None, **kwargs) -> str:
        """
        生成数据库连接字符串
        
        Args:
            db_type: 数据库类型 (mysql, postgresql, sqlite)
            host: 数据库主机
            port: 数据库端口
            database: 数据库名称
            user: 数据库用户
            password: 数据库密码
            **kwargs: 其他连接参数
            
        Returns:
            str: 数据库连接字符串
        """
        # 参数验证
        if not db_type:
            raise ValueError("Database type is required")
        
        if db_type not in self.DB_TYPES:
            raise ValueError(f"Unsupported database type: {db_type}")
        
        # 验证必要参数
        if db_type != 'sqlite':
            if not host:
                raise ValueError("Host is required for non-SQLite databases")
            if not database:
                raise ValueError("Database name is required for non-SQLite databases")
        
        if db_type == 'sqlite':
            # SQLite 连接字符串
            db_path = database or ':memory:'
            return f"{self.DB_TYPES[db_type]}:///{db_path}"
        else:
            # MySQL 和 PostgreSQL 连接字符串
            connection_parts = []
            
            # 添加用户和密码
            if user:
                connection_parts.append(user)
                if password:
                    connection_parts.append(f":{password}")
                connection_parts.append("@")
            
            # 添加主机和端口
            if host:
                connection_parts.append(host)
                if port:
                    connection_parts.append(f":{port}")
            
            # 添加数据库
            if database:
                connection_parts.append(f"/{database}")
            
            # 添加其他参数
            if kwargs:
                # 添加连接超时参数
                if 'connect_timeout' not in kwargs:
                    kwargs['connect_timeout'] = 30
                params = '&'.join([f"{k}={v}" for k, v in kwargs.items()])
                connection_parts.append(f"?{params}")
            else:
                # 默认添加连接超时参数
                connection_parts.append("?connect_timeout=30")
            
            return f"{self.DB_TYPES[db_type]}://{''.join(connection_parts)}"
    
    def get_engine(self, db_type: str, host: Optional[str] = None, port: Optional[int] = None,
                  database: Optional[str] = None, user: Optional[str] = None,
                  password: Optional[str] = None, **kwargs) -> Any:
        """
        获取数据库引擎
        
        Args:
            db_type: 数据库类型 (mysql, postgresql, sqlite)
            host: 数据库主机
            port: 数据库端口
            database: 数据库名称
            user: 数据库用户
            password: 数据库密码
            **kwargs: 其他连接参数
            
        Returns:
            Any: SQLAlchemy 引擎对象
        """
        # 生成连接字符串
        conn_str = self.get_connection_string(
            db_type, host, port, database, user, password, **kwargs
        )
        
        # 检查是否已经存在该连接的引擎
        key = f"{db_type}_{host or 'localhost'}_{port or 'default'}_{database or 'default'}"
        if key not in self._engines:
            # 创建新的引擎
            logger.debug(f"Creating new database engine for: {key}")
            self._engines[key] = create_engine(
                conn_str,
                pool_pre_ping=True,
                pool_size=10,
                max_overflow=20
            )
        
        return self._engines[key]
    
    @contextmanager
    def get_session(self, db_type: str, host: Optional[str] = None, port: Optional[int] = None,
                   database: Optional[str] = None, user: Optional[str] = None,
                   password: Optional[str] = None, **kwargs) -> Session:
        """
        获取数据库会话（上下文管理器）
        
        Args:
            db_type: 数据库类型 (mysql, postgresql, sqlite)
            host: 数据库主机
            port: 数据库端口
            database: 数据库名称
            user: 数据库用户
            password: 数据库密码
            **kwargs: 其他连接参数
            
        Yields:
            Session: SQLAlchemy 会话对象
        """
        engine = self.get_engine(
            db_type, host, port, database, user, password, **kwargs
        )
        
        # 创建会话工厂
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        session = SessionLocal()
        
        try:
            yield session
            session.commit()
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            session.close()
    
    def execute_sql(self, db_type: str, sql: str, params: Optional[Dict[str, Any]] = None,
                   host: Optional[str] = None, port: Optional[int] = None,
                   database: Optional[str] = None, user: Optional[str] = None,
                   password: Optional[str] = None, **kwargs) -> List[Dict[str, Any]]:
        """
        执行SQL语句
        
        Args:
            db_type: 数据库类型 (mysql, postgresql, sqlite)
            sql: SQL语句
            params: SQL参数
            host: 数据库主机
            port: 数据库端口
            database: 数据库名称
            user: 数据库用户
            password: 数据库密码
            **kwargs: 其他连接参数
            
        Returns:
            List[Dict[str, Any]]: 查询结果
        """
        with self.get_session(
            db_type, host, port, database, user, password, **kwargs
        ) as session:
            try:
                result = session.execute(text(sql), params or {})
                
                # 处理结果
                if result.returns_rows:
                    # 查询语句，返回结果集
                    columns = result.keys()
                    return [dict(zip(columns, row)) for row in result]
                else:
                    # 非查询语句，返回空列表
                    return []
            except SQLAlchemyError as e:
                logger.error(f"SQL execution error: {e}")
                raise
    
    def insert_data(self, db_type: str, table: str, data: Dict[str, Any],
                   host: Optional[str] = None, port: Optional[int] = None,
                   database: Optional[str] = None, user: Optional[str] = None,
                   password: Optional[str] = None, **kwargs) -> int:
        """
        插入数据
        
        Args:
            db_type: 数据库类型 (mysql, postgresql, sqlite)
            table: 表名
            data: 要插入的数据
            host: 数据库主机
            port: 数据库端口
            database: 数据库名称
            user: 数据库用户
            password: 数据库密码
            **kwargs: 其他连接参数
            
        Returns:
            int: 影响的行数
        """
        # 生成插入语句
        columns = ', '.join(data.keys())
        placeholders = ', '.join([f':{k}' for k in data.keys()])
        sql = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
        
        with self.get_session(
            db_type, host, port, database, user, password, **kwargs
        ) as session:
            try:
                result = session.execute(text(sql), data)
                return result.rowcount
            except SQLAlchemyError as e:
                logger.error(f"Insert data error: {e}")
                raise
    
    def update_data(self, db_type: str, table: str, data: Dict[str, Any],
                   condition: str, condition_params: Optional[Dict[str, Any]] = None,
                   host: Optional[str] = None, port: Optional[int] = None,
                   database: Optional[str] = None, user: Optional[str] = None,
                   password: Optional[str] = None, **kwargs) -> int:
        """
        更新数据
        
        Args:
            db_type: 数据库类型 (mysql, postgresql, sqlite)
            table: 表名
            data: 要更新的数据
            condition: 更新条件
            condition_params: 条件参数
            host: 数据库主机
            port: 数据库端口
            database: 数据库名称
            user: 数据库用户
            password: 数据库密码
            **kwargs: 其他连接参数
            
        Returns:
            int: 影响的行数
        """
        # 生成更新语句
        set_clause = ', '.join([f"{k} = :{k}" for k in data.keys()])
        sql = f"UPDATE {table} SET {set_clause} WHERE {condition}"
        
        # 合并参数
        params = {**data, **(condition_params or {})}
        
        with self.get_session(
            db_type, host, port, database, user, password, **kwargs
        ) as session:
            try:
                result = session.execute(text(sql), params)
                return result.rowcount
            except SQLAlchemyError as e:
                logger.error(f"Update data error: {e}")
                raise
    
    def delete_data(self, db_type: str, table: str, condition: str,
                   condition_params: Optional[Dict[str, Any]] = None,
                   host: Optional[str] = None, port: Optional[int] = None,
                   database: Optional[str] = None, user: Optional[str] = None,
                   password: Optional[str] = None, **kwargs) -> int:
        """
        删除数据
        
        Args:
            db_type: 数据库类型 (mysql, postgresql, sqlite)
            table: 表名
            condition: 删除条件
            condition_params: 条件参数
            host: 数据库主机
            port: 数据库端口
            database: 数据库名称
            user: 数据库用户
            password: 数据库密码
            **kwargs: 其他连接参数
            
        Returns:
            int: 影响的行数
        """
        # 生成删除语句
        sql = f"DELETE FROM {table} WHERE {condition}"
        
        with self.get_session(
            db_type, host, port, database, user, password, **kwargs
        ) as session:
            try:
                result = session.execute(text(sql), condition_params or {})
                return result.rowcount
            except SQLAlchemyError as e:
                logger.error(f"Delete data error: {e}")
                raise
    
    def batch_insert_data(self, db_type: str, table: str, data_list: List[Dict[str, Any]],
                        host: Optional[str] = None, port: Optional[int] = None,
                        database: Optional[str] = None, user: Optional[str] = None,
                        password: Optional[str] = None, **kwargs) -> int:
        """
        批量插入数据
        
        Args:
            db_type: 数据库类型 (mysql, postgresql, sqlite)
            table: 表名
            data_list: 要插入的数据列表
            host: 数据库主机
            port: 数据库端口
            database: 数据库名称
            user: 数据库用户
            password: 数据库密码
            **kwargs: 其他连接参数
            
        Returns:
            int: 影响的行数
        """
        if not data_list:
            return 0
        
        # 获取所有字段名
        columns = list(data_list[0].keys())
        columns_str = ', '.join(columns)
        
        # 生成占位符
        placeholders = []
        params = {}
        
        for i, data in enumerate(data_list):
            row_placeholders = []
            for j, col in enumerate(columns):
                param_name = f"{col}_{i}"
                row_placeholders.append(f":{param_name}")
                params[param_name] = data[col]
            placeholders.append(f"({', '.join(row_placeholders)})")
        
        # 生成批量插入语句
        placeholders_str = ', '.join(placeholders)
        sql = f"INSERT INTO {table} ({columns_str}) VALUES {placeholders_str}"
        
        with self.get_session(
            db_type, host, port, database, user, password, **kwargs
        ) as session:
            try:
                result = session.execute(text(sql), params)
                return result.rowcount
            except SQLAlchemyError as e:
                logger.error(f"Batch insert data error: {e}")
                raise
    
    def get_connection(self, db_type: str, host: Optional[str] = None, port: Optional[int] = None,
                      database: Optional[str] = None, user: Optional[str] = None,
                      password: Optional[str] = None, **kwargs) -> Any:
        """
        获取数据库原始连接
        
        Args:
            db_type: 数据库类型 (mysql, postgresql, sqlite)
            host: 数据库主机
            port: 数据库端口
            database: 数据库名称
            user: 数据库用户
            password: 数据库密码
            **kwargs: 其他连接参数
            
        Returns:
            Any: 数据库连接对象
        """
        # 生成连接键
        key = f"{db_type}_{host or 'localhost'}_{port or 'default'}_{database or 'default'}"
        
        if key not in self._connections:
            # 创建新的连接
            logger.debug(f"Creating new database connection for: {key}")
            
            if db_type == 'mysql':
                # MySQL 连接
                if pymysql is None:
                    raise ImportError("pymysql is not installed. Please install it with 'pip install pymysql'")
                self._connections[key] = pymysql.connect(
                    host=host,
                    port=port or 3306,
                    user=user,
                    password=password,
                    database=database,
                    **kwargs
                )
            elif db_type == 'postgresql':
                # PostgreSQL 连接
                if psycopg2 is None:
                    raise ImportError("psycopg2 is not installed. Please install it with 'pip install psycopg2-binary'")
                self._connections[key] = psycopg2.connect(
                    host=host,
                    port=port or 5432,
                    user=user,
                    password=password,
                    database=database,
                    **kwargs
                )
            elif db_type == 'sqlite':
                # SQLite 连接
                if sqlite3 is None:
                    raise ImportError("sqlite3 is not available in this Python installation")
                db_path = database or ':memory:'
                self._connections[key] = sqlite3.connect(db_path, **kwargs)
            else:
                raise ValueError(f"Unsupported database type: {db_type}")
        
        return self._connections[key]
    
    def close_connections(self):
        """
        关闭所有数据库连接
        """
        for key, conn in self._connections.items():
            try:
                conn.close()
                logger.debug(f"Closed database connection: {key}")
            except Exception as e:
                logger.warning(f"Error closing connection {key}: {e}")
        
        # 清空连接字典
        self._connections.clear()
    
    def close_engines(self):
        """
        关闭所有数据库引擎
        """
        for key, engine in self._engines.items():
            try:
                engine.dispose()
                logger.debug(f"Disposed database engine: {key}")
            except Exception as e:
                logger.warning(f"Error disposing engine {key}: {e}")
        
        # 清空引擎字典
        self._engines.clear()
    
    def close_all(self):
        """
        关闭所有数据库连接和引擎
        """
        self.close_connections()
        self.close_engines()


# 创建全局数据库辅助实例
db_helper = DatabaseHelper()


# 便捷函数
def get_db_helper() -> DatabaseHelper:
    """
    获取数据库辅助实例
    
    Returns:
        DatabaseHelper: 数据库辅助实例
    """
    return db_helper


def execute_sql(db_type: str, sql: str, params: Optional[Dict[str, Any]] = None,
               host: Optional[str] = None, port: Optional[int] = None,
               database: Optional[str] = None, user: Optional[str] = None,
               password: Optional[str] = None, **kwargs) -> List[Dict[str, Any]]:
    """
    执行SQL语句的便捷函数
    
    Args:
        db_type: 数据库类型 (mysql, postgresql, sqlite)
        sql: SQL语句
        params: SQL参数
        host: 数据库主机
        port: 数据库端口
        database: 数据库名称
        user: 数据库用户
        password: 数据库密码
        **kwargs: 其他连接参数
        
    Returns:
        List[Dict[str, Any]]: 查询结果
    """
    return db_helper.execute_sql(
        db_type, sql, params, host, port, database, user, password, **kwargs
    )


def insert_data(db_type: str, table: str, data: Dict[str, Any],
               host: Optional[str] = None, port: Optional[int] = None,
               database: Optional[str] = None, user: Optional[str] = None,
               password: Optional[str] = None, **kwargs) -> int:
    """
    插入数据的便捷函数
    
    Args:
        db_type: 数据库类型 (mysql, postgresql, sqlite)
        table: 表名
        data: 要插入的数据
        host: 数据库主机
        port: 数据库端口
        database: 数据库名称
        user: 数据库用户
        password: 数据库密码
        **kwargs: 其他连接参数
        
    Returns:
        int: 影响的行数
    """
    return db_helper.insert_data(
        db_type, table, data, host, port, database, user, password, **kwargs
    )


def update_data(db_type: str, table: str, data: Dict[str, Any],
               condition: str, condition_params: Optional[Dict[str, Any]] = None,
               host: Optional[str] = None, port: Optional[int] = None,
               database: Optional[str] = None, user: Optional[str] = None,
               password: Optional[str] = None, **kwargs) -> int:
    """
    更新数据的便捷函数
    
    Args:
        db_type: 数据库类型 (mysql, postgresql, sqlite)
        table: 表名
        data: 要更新的数据
        condition: 更新条件
        condition_params: 条件参数
        host: 数据库主机
        port: 数据库端口
        database: 数据库名称
        user: 数据库用户
        password: 数据库密码
        **kwargs: 其他连接参数
        
    Returns:
        int: 影响的行数
    """
    return db_helper.update_data(
        db_type, table, data, condition, condition_params, host, port, database, user, password, **kwargs
    )


def delete_data(db_type: str, table: str, condition: str,
               condition_params: Optional[Dict[str, Any]] = None,
               host: Optional[str] = None, port: Optional[int] = None,
               database: Optional[str] = None, user: Optional[str] = None,
               password: Optional[str] = None, **kwargs) -> int:
    """
    删除数据的便捷函数
    
    Args:
        db_type: 数据库类型 (mysql, postgresql, sqlite)
        table: 表名
        condition: 删除条件
        condition_params: 条件参数
        host: 数据库主机
        port: 数据库端口
        database: 数据库名称
        user: 数据库用户
        password: 数据库密码
        **kwargs: 其他连接参数
        
    Returns:
        int: 影响的行数
    """
    return db_helper.delete_data(
        db_type, table, condition, condition_params, host, port, database, user, password, **kwargs
    )


def get_session(db_type: str, host: Optional[str] = None, port: Optional[int] = None,
               database: Optional[str] = None, user: Optional[str] = None,
               password: Optional[str] = None, **kwargs) -> Session:
    """
    获取数据库会话的便捷函数
    
    Args:
        db_type: 数据库类型 (mysql, postgresql, sqlite)
        host: 数据库主机
        port: 数据库端口
        database: 数据库名称
        user: 数据库用户
        password: 数据库密码
        **kwargs: 其他连接参数
        
    Returns:
        Session: SQLAlchemy 会话对象
    """
    return db_helper.get_session(
        db_type, host, port, database, user, password, **kwargs
    )


def batch_insert_data(db_type: str, table: str, data_list: List[Dict[str, Any]],
                     host: Optional[str] = None, port: Optional[int] = None,
                     database: Optional[str] = None, user: Optional[str] = None,
                     password: Optional[str] = None, **kwargs) -> int:
    """
    批量插入数据的便捷函数
    
    Args:
        db_type: 数据库类型 (mysql, postgresql, sqlite)
        table: 表名
        data_list: 要插入的数据列表
        host: 数据库主机
        port: 数据库端口
        database: 数据库名称
        user: 数据库用户
        password: 数据库密码
        **kwargs: 其他连接参数
        
    Returns:
        int: 影响的行数
    """
    return db_helper.batch_insert_data(
        db_type, table, data_list, host, port, database, user, password, **kwargs
    )