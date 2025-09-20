# SQL执行API服务

基于FastAPI的SQL执行服务，支持MySQL和PostgreSQL数据库。

## 快速开始

### 1. 使用Docker Compose启动

```bash
# 克隆项目后，直接运行启动脚本
./start.sh

# 或者手动启动
docker-compose up -d
```

### 2. 访问服务

- **API文档**: http://localhost:3001/docs
- **健康检查**: http://localhost:3001/health
- **连接池状态**: http://localhost:3001/pools

### 3. 测试API

#### 执行SQL查询

```bash
curl -X POST "http://localhost:3001/execute_sql" \
  -H "Content-Type: application/json" \
  -d '{
    "sql": "SELECT * FROM users LIMIT 10",
    "connection_info": {
      "db_type": "mysql",
      "host": "localhost",
      "user": "testuser",
      "password": "testpass123",
      "database": "testdb",
      "port": 3306
    },
    "async_mode": true
  }'
```

#### PostgreSQL查询

```bash
curl -X POST "http://localhost:3001/execute_sql" \
  -H "Content-Type: application/json" \
  -d '{
    "sql": "SELECT version()",
    "connection_info": {
      "db_type": "postgresql",
      "host": "localhost",
      "user": "testuser",
      "password": "testpass123",
      "database": "testdb",
      "port": 5432
    },
    "async_mode": true
  }'
```

## 服务管理

```bash
# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f sql-api

# 停止服务
docker-compose down

# 重启服务
docker-compose restart sql-api

# 查看服务状态
docker-compose ps
```

## 配置说明

### 环境变量

复制 `.env.example` 为 `.env` 并修改配置：

```bash
cp .env.example .env
```

### 端口映射

- **API服务**: 3001 (主机) -> 3001 (容器)
- **MySQL**: 3306 (主机) -> 3306 (容器)
- **PostgreSQL**: 5432 (主机) -> 5432 (容器)

### 数据持久化

- MySQL数据: `mysql_data` volume
- PostgreSQL数据: `postgres_data` volume
- 应用日志: `./logs` 目录

## API端点

### 1. 执行SQL语句

**POST** `/execute_sql`

**请求体**:
```json
{
  "sql": "SELECT * FROM users",
  "connection_info": {
    "db_type": "mysql",
    "host": "localhost",
    "user": "username",
    "password": "password",
    "database": "dbname",
    "port": 3306
  },
  "async_mode": true
}
```

### 2. 健康检查

**GET** `/health`

### 3. 连接池状态

**GET** `/pools`

### 4. CORS测试

**GET** `/cors-test`

## CORS支持

API已启用CORS支持，允许所有来源的跨域请求。在生产环境中，建议配置具体的域名：

```python
# 当前配置（开发环境）
allow_origins=["*"]  # 允许所有来源

# 生产环境建议配置
allow_origins=["https://your-domain.com", "https://app.your-domain.com"]
```

### 测试CORS配置

```bash
# 测试CORS配置
curl http://localhost:3001/cors-test

# 测试跨域预检请求
curl -X OPTIONS http://localhost:3001/execute_sql \
  -H "Origin: http://example.com" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: content-type"
```

## 开发模式

如需本地开发，可以直接运行Python文件：

```bash
# 安装依赖
pip install -r requirements.txt

# 启动服务
python exec_sql_api.py
```

## 注意事项

1. **安全性**: 生产环境中请修改默认的数据库密码
2. **性能**: 连接池参数可以在请求中配置
3. **日志**: 查看 `logs` 目录获取详细日志信息
4. **网络**: 确保Docker网络配置正确，避免端口冲突