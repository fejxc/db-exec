#!/bin/bash

# SQL执行API Docker启动脚本

echo "🚀 SQL执行API Docker启动脚本"
echo "================================"

# 检查Docker是否安装
if ! command -v docker &> /dev/null; then
    echo "❌ Docker未安装，请先安装Docker"
    echo "   Ubuntu/Debian: sudo apt install docker.io docker-compose"
    echo "   CentOS/RHEL: sudo yum install docker docker-compose"
    echo "   或使用官方安装脚本: curl -fsSL https://get.docker.com | sh"
    exit 1
fi

# 检查Docker Compose是否安装
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "❌ Docker Compose未安装，请先安装Docker Compose"
    echo "   Ubuntu/Debian: sudo apt install docker-compose"
    echo "   或使用: pip install docker-compose"
    exit 1
fi

# 创建日志目录
mkdir -p logs

# 显示菜单
echo "请选择启动方式："
echo "1) 标准启动（使用官方镜像）"
echo "2) 国内镜像加速（推荐国内用户）"
echo "3) 仅启动API服务（不包含数据库）"
echo "4) 重新构建并启动"
echo "5) 查看日志"
echo "6) 停止服务"
echo "7) 网络问题修复模式"

read -p "请输入选项 [1-7]: " choice

case $choice in
    1)
        echo "📦 使用标准镜像启动..."
        docker-compose up -d
        ;;
    2)
        echo "📦 使用国内镜像加速启动..."
        if [ -f "docker-compose-cn.yml" ]; then
            docker-compose -f docker-compose-cn.yml up -d
        else
            echo "❌ 国内镜像配置文件不存在，使用标准配置"
            docker-compose up -d
        fi
        ;;
    3)
        echo "📦 仅启动API服务..."
        docker-compose up -d sql-api
        ;;
    4)
        echo "🔨 重新构建并启动..."
        docker-compose down
        docker-compose build --no-cache
        docker-compose up -d
        ;;
    5)
        echo "📋 查看日志..."
        docker-compose logs -f
        exit 0
        ;;
    6)
        echo "🛑 停止服务..."
        docker-compose down
        exit 0
        ;;
    7)
        echo "🔧 网络问题修复模式..."
        echo "正在使用国内镜像源重新构建..."
        docker-compose down
        docker-compose -f docker-compose-cn.yml build --no-cache
        docker-compose -f docker-compose-cn.yml up -d
        ;;
    *)
        echo "❌ 无效选项，使用标准启动"
        docker-compose up -d
        ;;
esac

# 等待服务启动
echo "⏳ 等待服务启动..."
sleep 15

# 检查服务状态
if docker-compose ps | grep -q "Up"; then
    echo ""
    echo "✅ 服务启动成功！"
    echo "================================"
    echo "🌐 访问地址："
    echo "   API文档: http://localhost:3001/docs"
    echo "   健康检查: http://localhost:3001/health"
    echo "   连接池状态: http://localhost:3001/pools"
    echo ""
    echo "🗄️  数据库连接信息："
    echo "   MySQL: host=localhost, port=3306, user=testuser, password=testpass123, database=testdb"
    echo "   PostgreSQL: host=localhost, port=5432, user=testuser, password=testpass123, database=testdb"
    echo ""
    echo "📊 常用命令："
    echo "   查看日志: docker-compose logs -f sql-api"
    echo "   重启服务: docker-compose restart sql-api"
    echo "   停止服务: docker-compose down"
    echo "   查看状态: docker-compose ps"
else
    echo ""
    echo "❌ 服务启动失败，请查看日志："
    docker-compose logs sql-api
    echo ""
    echo "💡 故障排查建议："
    echo "   1. 检查端口是否被占用: netstat -tlnp | grep :3001"
    echo "   2. 检查Docker服务: systemctl status docker"
    echo "   3. 清理容器: docker-compose down && docker system prune -f"
    echo "   4. 重新构建: ./start.sh 然后选择选项4"
fi