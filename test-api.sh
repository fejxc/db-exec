#!/bin/bash

# SQL执行API测试脚本

echo "🧪 测试SQL执行API服务..."

# 检查服务是否运行
if ! curl -s http://localhost:3001/health > /dev/null; then
    echo "❌ API服务未运行，请先启动服务"
    echo "   运行: ./start.sh"
    exit 1
fi

echo "✅ API服务运行正常"

# 测试CORS配置
echo "🔍 测试CORS配置..."
cors_response=$(curl -s http://localhost:3001/cors-test)
echo "CORS测试响应: $cors_response"

# 测试跨域请求（模拟浏览器预检请求）
echo "🔍 测试跨域预检请求..."
curl -X OPTIONS http://localhost:3001/execute_sql \
  -H "Origin: http://example.com" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: content-type" \
  -v 2>&1 | grep -E "(Access-Control-Allow-|HTTP/1.1)"

# 测试健康检查
echo "🔍 测试健康检查端点..."
response=$(curl -s http://localhost:3001/health)
echo "响应: $response"

# 测试MySQL连接
echo ""
echo "🗄️ 测试MySQL连接..."
curl -X POST "http://localhost:3001/execute_sql" \
  -H "Content-Type: application/json" \
  -d '{
    "sql": "SELECT 1 as test_value",
    "connection_info": {
      "db_type": "mysql",
      "host": "mysql",
      "user": "testuser",
      "password": "testpass123",
      "database": "testdb",
      "port": 3306
    },
    "async_mode": true
  }' | jq .

# 测试PostgreSQL连接
echo ""
echo "🗄️ 测试PostgreSQL连接..."
curl -X POST "http://localhost:3001/execute_sql" \
  -H "Content-Type: application/json" \
  -d '{
    "sql": "SELECT 1 as test_value",
    "connection_info": {
      "db_type": "postgresql",
      "host": "postgres",
      "user": "testuser",
      "password": "testpass123",
      "database": "testdb",
      "port": 5432
    },
    "async_mode": true
  }' | jq .

# 检查jq是否安装
if ! command -v jq &> /dev/null; then
    echo ""
    echo "💡 建议安装jq来格式化JSON输出:"
    echo "   Ubuntu/Debian: sudo apt install jq"
    echo "   CentOS/RHEL: sudo yum install jq"
    echo "   macOS: brew install jq"
fi

echo ""
echo "✅ 测试完成！"
echo "📖 查看API文档: http://localhost:3001/docs"