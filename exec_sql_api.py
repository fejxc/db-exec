from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List, Union, Set
import asyncio
import traceback
import aiomysql
import asyncpg
import logging
import time
import os
from concurrent.futures import ThreadPoolExecutor
from cors_config import CORSConfig

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 定义连接池字典
mysql_pools: Dict[str, aiomysql.Pool] = {}
pg_pools: Dict[str, asyncpg.Pool] = {}
thread_pool = ThreadPoolExecutor(max_workers=20)


# 使用 lifespan 替代 on_event
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时执行的代码
    logger.info("应用启动，初始化资源...")

    yield  # 这里是应用运行期间

    # 关闭时执行的代码
    logger.info("应用关闭，清理资源...")

    # 关闭所有MySQL连接池
    for key, pool in mysql_pools.items():
        logger.info(f"关闭MySQL连接池: {key}")
        pool.close()
        await pool.wait_closed()

    # 关闭所有PostgreSQL连接池
    for key, pool in pg_pools.items():
        logger.info(f"关闭PostgreSQL连接池: {key}")
        await pool.close()

    # 关闭线程池
    thread_pool.shutdown()
    logger.info("所有资源已清理完毕")


# 创建FastAPI应用并使用lifespan
app = FastAPI(
    title="SQL执行服务",
    description="支持MySQL和PostgreSQL的SQL执行API",
    lifespan=lifespan
)

# 配置CORS中间件
cors_config = CORSConfig.get_cors_config()
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_config["allow_origins"],
    allow_credentials=cors_config["allow_credentials"],
    allow_methods=cors_config["allow_methods"],
    allow_headers=cors_config["allow_headers"],
    expose_headers=cors_config["expose_headers"]
)


# 定义输入模型
class ConnectionInfo(BaseModel):
    db_type: str = Field(default="mysql", description="数据库类型：mysql或postgresql")
    host: str = Field(default="localhost", description="数据库主机地址")
    user: str = Field(..., description="数据库用户名")
    password: str = Field(..., description="数据库密码")
    database: str = Field(..., description="数据库名称")
    port: int = Field(None, description="数据库端口，默认MySQL为3306，PostgreSQL为5432")
    charset: str = Field(default="utf8mb4", description="字符集")
    min_size: int = Field(default=5, description="连接池最小连接数")
    max_size: int = Field(default=20, description="连接池最大连接数")


class SQLRequest(BaseModel):
    sql: str = Field(..., description="要执行的SQL语句")
    connection_info: ConnectionInfo
    async_mode: bool = Field(default=True, description="是否异步执行")


# 定义统一的响应模型
class SQLResponse(BaseModel):
    success: bool = Field(description="操作是否成功")
    result: Optional[Any] = Field(None, description="查询结果或受影响的行数")
    error: Optional[Dict[str, Any]] = Field(None, description="错误信息")
    execution_time: Optional[float] = Field(None, description="执行时间(秒)")


# 自定义异常处理器
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    response = {
        "success": False,
        "result": None,
        "error": exc.detail if isinstance(exc.detail, dict) else {"message": str(exc.detail)},
        "execution_time": None
    }
    return JSONResponse(status_code=exc.status_code, content=response)


# 全局异常处理器
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    error_info = {
        "message": str(exc),
        "type": type(exc).__name__,
        "traceback": traceback.format_exc()
    }
    response = {
        "success": False,
        "result": None,
        "error": error_info,
        "execution_time": None
    }
    return JSONResponse(status_code=500, content=response)


# 生成连接池键名
def get_pool_key(connection_info: Dict[str, Any]) -> str:
    """生成唯一的连接池键名"""
    return f"{connection_info['db_type']}_{connection_info['host']}_{connection_info['port']}_{connection_info['database']}_{connection_info['user']}"


# 获取MySQL连接池
async def get_mysql_pool(connection_info: Dict[str, Any]) -> aiomysql.Pool:
    """获取或创建MySQL连接池"""
    pool_key = get_pool_key(connection_info)

    if pool_key not in mysql_pools:
        host = connection_info.get("host")
        user = connection_info.get("user")
        password = connection_info.get("password")
        database = connection_info.get("database")
        port = connection_info.get("port", 3306)
        charset = connection_info.get("charset", "utf8mb4")
        min_size = connection_info.get("min_size", 5)
        max_size = connection_info.get("max_size", 20)

        logger.info(f"Creating new MySQL pool for {pool_key}")
        pool = await aiomysql.create_pool(
            host=host,
            port=port,
            user=user,
            password=password,
            db=database,
            charset=charset,
            minsize=min_size,
            maxsize=max_size,
            autocommit=False
        )
        mysql_pools[pool_key] = pool

    return mysql_pools[pool_key]


# 获取PostgreSQL连接池
async def get_pg_pool(connection_info: Dict[str, Any]) -> asyncpg.Pool:
    """获取或创建PostgreSQL连接池"""
    pool_key = get_pool_key(connection_info)

    if pool_key not in pg_pools:
        host = connection_info.get("host")
        user = connection_info.get("user")
        password = connection_info.get("password")
        database = connection_info.get("database")
        port = connection_info.get("port", 5432)
        min_size = connection_info.get("min_size", 5)
        max_size = connection_info.get("max_size", 20)

        logger.info(f"Creating new PostgreSQL pool for {pool_key}")
        pool = await asyncpg.create_pool(
            user=user,
            password=password,
            database=database,
            host=host,
            port=port,
            min_size=min_size,
            max_size=max_size,
            command_timeout=60
        )
        pg_pools[pool_key] = pool

    return pg_pools[pool_key]


# 异步执行SQL
async def execute_sql_async(sql: str, connection_info: Dict[str, Any]) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
    """异步执行SQL语句并返回结果"""
    start_time = time.time()
    db_type = connection_info.get("db_type", "mysql").lower()

    try:
        if db_type == "mysql":
            return await execute_mysql_async(sql, connection_info)
        elif db_type in ("postgresql", "postgres"):
            return await execute_pg_async(sql, connection_info)
        else:
            raise ValueError(f"不支持的数据库类型: {db_type}")
    except Exception as e:
        error_details = {
            "type": type(e).__name__,
            "message": str(e),
            "sql": sql,
            "execution_time": time.time() - start_time
        }
        if "connection" in str(e).lower() or "timeout" in str(e).lower():
            error_details["category"] = "连接错误"
            error_details["suggestion"] = "请检查数据库连接参数是否正确，数据库服务是否可用"
        elif "syntax" in str(e).lower() or "parse" in str(e).lower():
            error_details["category"] = "SQL语法错误"
            error_details["suggestion"] = "请检查SQL语句的语法是否正确"
        elif "integrity" in str(e).lower() or "constraint" in str(e).lower():
            error_details["category"] = "数据完整性错误"
            error_details["suggestion"] = "操作违反了数据库完整性约束"
        else:
            error_details["category"] = "其他数据库错误"
            error_details["suggestion"] = "请检查SQL语句和数据库状态"
        raise HTTPException(status_code=500, detail=error_details)

# MySQL异步执行
async def execute_mysql_async(sql: str, connection_info: Dict[str, Any]) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
    pool = await get_mysql_pool(connection_info)
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cursor:
            await cursor.execute(sql)
            if sql.strip().lower().startswith(("select", "with", "show")):
                rows = await cursor.fetchall()
                # 检查是否为单行且所有值都是 None
                if rows and len(rows) == 1 and all(value is None for value in rows[0].values()):
                    return []
                result = [dict(row) for row in rows]
                return result
            else:
                await conn.commit()
                return {"affected_rows": cursor.rowcount}



from decimal import Decimal, ROUND_HALF_UP

async def execute_pg_async(sql: str, connection_info: Dict[str, Any]) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
    """异步执行PostgreSQL SQL语句，并保留数值结果为两位小数"""
    pool = await get_pg_pool(connection_info)
    async with pool.acquire() as conn:
        if sql.strip().lower().startswith(("select", "with", "show")):
            rows = await conn.fetch(sql)
            # 如果没有查询到任何行，返回空列表
            if not rows:
                return []
            # 检查是否为单行且所有值都是 None
            if rows and len(rows) == 1 and all(value is None for value in rows[0].values()):
                return []
            # 处理查询结果
            result = []
            for row in rows:
                processed_row = {}
                for key, value in row.items():
                    if isinstance(value, Decimal):
                        # 处理Decimal类型，保留两位小数并转为浮点数
                        rounded = value.quantize(Decimal('0.00'), rounding=ROUND_HALF_UP)
                        processed_row[key] = float(rounded)
                    elif isinstance(value, float):
                        # 处理float，四舍五入到两位小数
                        processed_row[key] = round(value, 2)
                    else:
                        processed_row[key] = value
                result.append(processed_row)
            return result
        else:
            result = await conn.execute(sql)
            if result:
                command, _, count = result.partition(' ')
                try:
                    affected_rows = int(count) if count else 0
                except ValueError:
                    affected_rows = 0
                result = {"affected_rows": affected_rows, "command": command}
            else:
                result = {"affected_rows": 0}
            return result

# 同步代码包装函数（用于非异步执行）
def execute_sql_sync(sql: str, connection_info: Dict[str, Any]) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
    """在线程池中执行同步SQL"""
    import pymysql
    import psycopg2
    from psycopg2.extras import RealDictCursor

    db_type = connection_info.get("db_type", "mysql").lower()
    host = connection_info.get("host", "localhost")
    user = connection_info.get("user")
    password = connection_info.get("password")
    database = connection_info.get("database")
    port = connection_info.get("port")

    # 如果port为None，设置默认值
    if port is None:
        port = 3306 if db_type == "mysql" else 5432

    charset = connection_info.get("charset", "utf8mb4")
    conn = None

    try:
        # 建立数据库连接
        if db_type == "mysql":
            conn = pymysql.connect(
                host=host,
                user=user,
                password=password,
                database=database,
                port=port,
                charset=charset,
                cursorclass=pymysql.cursors.DictCursor
            )
        elif db_type in ("postgresql", "postgres"):
            conn = psycopg2.connect(
                host=host,
                user=user,
                password=password,
                dbname=database,
                port=port,
                cursor_factory=RealDictCursor
            )
        else:
            raise ValueError(f"不支持的数据库类型: {db_type}")

        with conn.cursor() as cursor:
            cursor.execute(sql)

            if sql.strip().lower().startswith(("select", "with", "show")):
                result = cursor.fetchall()
                # 统一转换为标准字典格式
                result = [dict(row) for row in result]
            else:
                conn.commit()
                result = {"affected_rows": cursor.rowcount}

        return result

    except Exception as e:
        if conn:
            conn.rollback()
        raise e

    finally:
        if conn:
            conn.close()


# 接口实现
@app.post("/execute_sql", summary="执行SQL语句", response_model=SQLResponse)
async def execute_sql_api(request: SQLRequest, background_tasks: BackgroundTasks):
    """
    执行SQL语句并返回结果

    - **sql**: 要执行的SQL语句
    - **connection_info**: 数据库连接信息
    - **async_mode**: 是否异步执行(默认为true)

    返回统一格式的响应：
    - success: 操作是否成功
    - result: 查询结果或受影响的行数
    - error: 错误信息
    - execution_time: 执行时间(秒)
    """
    start_time = time.time()
    sql = request.sql.replace("```sql", "").replace("```", "").strip()

    if not sql:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "result": None,
                "error": {
                    "type": "BadRequest",
                    "message": "SQL语句不能为空",
                    "suggestion": "请提供有效的SQL语句"
                },
                "execution_time": time.time() - start_time
            }
        )

    try:
        # 根据异步模式选择不同的执行方式
        if request.async_mode:
            # 异步执行
            result = await execute_sql_async(sql, request.connection_info.dict())
        else:
            # 在线程池中同步执行
            result = await asyncio.to_thread(
                execute_sql_sync,
                sql,
                request.connection_info.dict()
            )

        # 计算执行时间
        execution_time = time.time() - start_time

        # 成功响应使用统一格式
        return {
            "success": True,
            "result": result,
            "error": None,
            "execution_time": execution_time
        }
    except HTTPException as e:
        # HTTPException已在异常处理器中处理
        e.detail["execution_time"] = time.time() - start_time
        raise e
    except Exception as e:
        # 未预期的异常
        execution_time = time.time() - start_time
        error_info = {
            "type": type(e).__name__,
            "message": str(e),
            "suggestion": "请联系管理员或检查服务器日志",
            "execution_time": execution_time
        }
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "result": None,
                "error": error_info,
                "execution_time": execution_time
            }
        )


# CORS测试端点
@app.get("/cors-test")
async def cors_test():
    """测试CORS配置是否生效"""
    cors_config = CORSConfig.get_cors_config()
    return {
        "success": True,
        "result": {
            "message": "CORS配置已启用",
            "cors_enabled": True,
            "allow_origins": cors_config["allow_origins"],
            "allow_methods": cors_config["allow_methods"],
            "allow_headers": cors_config["allow_headers"],
            "allow_credentials": cors_config["allow_credentials"],
            "expose_headers": cors_config["expose_headers"],
            "config_source": "环境变量" if os.getenv("CORS_ORIGINS") or os.getenv("CORS_MODE") else "默认配置"
        },
        "error": None,
        "execution_time": 0
    }


# 健康检查端点
@app.get("/health")
async def health_check():
    return {
        "success": True,
        "result": {
            "status": "healthy",
            "service": "sql-execution-api",
            "mysql_pools": len(mysql_pools),
            "pg_pools": len(pg_pools)
        },
        "error": None,
        "execution_time": 0
    }


# 监控端点 - 查看连接池状态
@app.get("/pools")
async def pool_status():
    mysql_status = {k: {"min_size": v.minsize, "max_size": v.maxsize, "size": v.size, "freesize": v.freesize}
                    for k, v in mysql_pools.items()}

    pg_status = {
        k: {"min_size": v.get_min_size(), "max_size": v.get_max_size(), "size": v.get_size(), "idle": v.get_idle_size()}
        for k, v in pg_pools.items()}

    return {
        "success": True,
        "result": {
            "mysql_pools": mysql_status,
            "pg_pools": pg_status
        },
        "error": None
    }


# 正确运行应用程序
if __name__ == "__main__":
    import sys
    import uvicorn

    # 使用更高性能的uvloop
    try:
        import uvloop

        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    except ImportError:
        logger.warning("uvloop not installed. Using default event loop.")

    # 将文件名作为模块路径
    module_name = __file__.replace('.py', '').split('/')[-1]

    # 启动服务器(修改为使用import-string方式)
    uvicorn.run(
        f"{module_name}:app",  # 使用 module:app 格式
        host="0.0.0.0",
        port=3001,
        workers=4,  # 根据CPU核心数调整
        reload=True  # 启用热重载
    )
