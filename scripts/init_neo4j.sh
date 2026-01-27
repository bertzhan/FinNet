#!/bin/bash

# Neo4j 初始化脚本
# 用于创建知识图谱的初始索引和约束

echo "=========================================="
echo "Neo4j 初始化"
echo "=========================================="
echo ""

# 检查 Neo4j 服务是否运行
echo "检查 Neo4j 服务状态..."
if ! docker ps | grep -q finnet-neo4j; then
    echo "错误: Neo4j 服务未运行"
    echo "请先运行: docker-compose up -d neo4j"
    exit 1
fi

echo "✓ Neo4j 服务正在运行"
echo "等待服务完全启动..."
sleep 15

# 自动检测网络名称（Docker Compose 创建的网络）
NETWORK_NAME=$(docker inspect finnet-neo4j --format='{{range $net, $v := .NetworkSettings.Networks}}{{$net}}{{end}}' 2>/dev/null | head -n1)

if [ -z "$NETWORK_NAME" ]; then
    # 如果无法自动检测，尝试常见的网络名称
    NETWORK_NAME="finnet_finnet-network"
    echo "⚠ 无法自动检测网络名称，使用默认值: $NETWORK_NAME"
else
    echo "✓ 检测到网络: $NETWORK_NAME"
fi

# 检查 Neo4j 是否就绪
echo "检查 Neo4j 服务就绪状态..."
NEO4J_READY=false
for i in {1..30}; do
    # 尝试连接 Neo4j
    HTTP_CODE=$(docker run --rm --network "$NETWORK_NAME" curlimages/curl:latest \
        -s -o /dev/null -w "%{http_code}" \
        http://finnet-neo4j:7474 2>/dev/null)
    
    if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "301" ] || [ "$HTTP_CODE" = "302" ]; then
        NEO4J_READY=true
        echo "✓ Neo4j 服务已就绪"
        break
    fi
    
    echo "等待 Neo4j 服务启动... ($i/30)"
    sleep 2
done

if [ "$NEO4J_READY" = false ]; then
    echo ""
    echo "✗ Neo4j 服务未就绪（等待了 60 秒）"
    echo ""
    echo "请检查服务日志:"
    echo "  docker-compose logs neo4j"
    echo ""
    exit 1
fi

echo ""
echo "正在初始化 Neo4j 数据库..."
echo ""

# 从环境变量或默认值获取认证信息
NEO4J_USER=${NEO4J_USER:-neo4j}
NEO4J_PASSWORD=${NEO4J_PASSWORD:-finnet123456}

# 创建初始化 Cypher 脚本
INIT_CYPHER=$(cat <<'EOF'
// 创建约束和索引

// 公司节点约束和索引
CREATE CONSTRAINT company_id IF NOT EXISTS FOR (c:Company) REQUIRE c.id IS UNIQUE;
CREATE INDEX company_code IF NOT EXISTS FOR (c:Company) ON (c.code);
CREATE INDEX company_name IF NOT EXISTS FOR (c:Company) ON (c.name);
CREATE INDEX company_market IF NOT EXISTS FOR (c:Company) ON (c.market);

// 人物节点约束和索引
CREATE CONSTRAINT person_id IF NOT EXISTS FOR (p:Person) REQUIRE p.id IS UNIQUE;
CREATE INDEX person_name IF NOT EXISTS FOR (p:Person) ON (p.name);

// 高管节点索引
CREATE INDEX executive_company IF NOT EXISTS FOR (e:Executive) ON (e.company_id);
CREATE INDEX executive_position IF NOT EXISTS FOR (e:Executive) ON (e.position);

// 股东节点索引
CREATE INDEX shareholder_company IF NOT EXISTS FOR (s:Shareholder) ON (s.company_id);
CREATE INDEX shareholder_type IF NOT EXISTS FOR (s:Shareholder) ON (s.type);

// 行业节点索引
CREATE INDEX industry_code IF NOT EXISTS FOR (i:Industry) ON (i.code);

// 财务指标节点索引
CREATE INDEX financial_metric_company IF NOT EXISTS FOR (f:FinancialMetric) ON (f.company_id);
CREATE INDEX financial_metric_period IF NOT EXISTS FOR (f:FinancialMetric) ON (f.report_period);

// 事件节点索引
CREATE INDEX event_type IF NOT EXISTS FOR (e:Event) ON (e.type);
CREATE INDEX event_date IF NOT EXISTS FOR (e:Event) ON (e.date);

RETURN 'Neo4j 初始化完成' AS message;
EOF
)

# 使用 cypher-shell 执行初始化脚本
echo "执行初始化 Cypher 脚本..."
docker exec -i finnet-neo4j cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" <<< "$INIT_CYPHER"

if [ $? -eq 0 ]; then
    echo ""
    echo "✓ Neo4j 初始化成功"
else
    echo ""
    echo "⚠ 初始化过程中可能出现错误，请检查输出"
fi

# 验证初始化结果
echo ""
echo "验证索引和约束..."
docker exec -i finnet-neo4j cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" <<< "SHOW CONSTRAINTS;" > /dev/null 2>&1
docker exec -i finnet-neo4j cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" <<< "SHOW INDEXES;" > /dev/null 2>&1

if [ $? -eq 0 ]; then
    echo "✓ 可以正常查询索引和约束"
else
    echo "⚠ 查询索引和约束时出现问题"
fi

echo ""
echo "=========================================="
echo "Neo4j 初始化完成"
echo "=========================================="
echo ""
echo "连接信息:"
echo "  - HTTP端口: http://localhost:7474"
echo "  - Bolt端口: localhost:7687"
echo "  - 用户名: $NEO4J_USER"
echo "  - 密码: $NEO4J_PASSWORD"
echo ""
echo "使用 cypher-shell 连接:"
echo "  docker exec -it finnet-neo4j cypher-shell -u $NEO4J_USER -p $NEO4J_PASSWORD"
echo ""
echo "或使用 Python 客户端连接:"
echo "  pip install neo4j"
echo "  from neo4j import GraphDatabase"
echo "  driver = GraphDatabase.driver('bolt://localhost:7687', auth=('$NEO4J_USER', '$NEO4J_PASSWORD'))"
echo ""
