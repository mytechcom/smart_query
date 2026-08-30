# 智能问数系统 (Smart Query System)

## 项目简介
用户输入自然语言（如"统计今天各个品类的销售额"），系统自动：
1. **识别意图** —— 判断适合用柱状图、折线图、饼图还是表格展示
2. **生成 SQL** —— 结合数据库表结构，调用 LLM 将自然语言转为 SQL 查询
3. **执行查询** —— 安全校验后执行 SQL，获取结果
4. **可视化展示** —— 按识别的图表类型渲染结果

## 技术栈
| 层级 | 技术 |
|------|------|
| LLM | DeepSeek / OpenAI（OpenAI 兼容接口） |
| 后端 | FastAPI |
| 前端 | Streamlit |
| 可视化 | PyECharts |
| NL2SQL | OpenAI SDK + Prompt 工程（LLM 失败自动规则兜底） |
| **数据库** | **MySQL 8.0（默认）** / SQLite（本地免服务模式，可选） |
| 部署 | Docker / Docker Compose（内置 MySQL 服务） |

## 项目结构
```
smart_query/
├── config/              # 配置层（DB / API Key / 常量 / logger，支持 mysql|sqlite）
├── llm/                 # LLM 客户端封装（延迟导入 + 健壮 JSON 解析）
├── intent/              # 意图识别（LLM + 关键词规则兜底）
├── database/            # connection 连接层 + 建表（MySQL DDL）+ Mock 数据
├── nl2sql/              # 核心引擎：表结构注入 → SQL 生成 → 校验 → 执行 → 规则兜底
├── visualization/       # PyECharts 柱状/折线/饼 + 表格
├── api/                 # FastAPI 后端服务
├── web/                 # Streamlit 前端界面
├── tests/               # 单元测试
├── scripts/             # verify.py 一键验证
├── docs/                # 技术文档、API 文档、部署手册
├── requirements.txt
├── .env.example
├── Dockerfile
└── docker-compose.yml   # 内置 MySQL 8 服务
```

## 快速开始（MySQL）

### 1. 安装依赖
```bash
pip install -r requirements.txt
# 如果安装比较慢，可以使用下面的命令进行加速
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 2. 配置数据库与 API Key
```bash
cp .env.example .env
```
编辑 `.env`：
```env
DB_TYPE=mysql
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your-password
DB_NAME=ecommerce

DEEPSEEK_API_KEY=sk-your-api-key-here
```

### 3. 初始化数据库（自动建库 + 建表 + Mock 数据）
```bash
python database/init_db.py
```
> 若 `ecommerce` 库不存在会自动创建，无需手动建库。

### 4. 启动服务
```bash
# 终端1：后端 API
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

# 终端2：前端界面
streamlit run web/app.py --server.port 8501
```

### 5. 打开浏览器
访问 http://localhost:8501 ，输入问题即可体验。

## Docker 一键启动（含 MySQL 8）
```bash
docker-compose up -d
```
Compose 内置 MySQL 8 服务 + 健康检查，API 启动前自动完成建表与 Mock 数据。
> 注意：容器网络内 `DB_HOST` 会自动设为服务名 `mysql`，无需修改 `.env`。

## 本地免 MySQL 体验（可选）
如果没有 MySQL 服务，可切换到 SQLite 模式离线跑通：
```bash
# .env 中设置
DB_TYPE=sqlite

python scripts/verify.py    # 一键验证全链路（建表/意图/SQL校验/统计查询/图表）
```

## 日志与排障
系统核心链路（意图识别 / NL2SQL / SQL 执行 / API）已接入统一日志：

| 位置 | 内容 |
|------|------|
| `logs/smart_query.log` | 全链路日志（UTF-8，含 DEBUG），默认自动生成 |
| 后端控制台 | INFO 级别运行日志 |
| 前端页面「🔍 调试信息」折叠栏 | 当前查询的意图 / SQL / 生成方式（LLM 或规则模板） |

常见问题排查：
- **页面提示"无法连接后端 API"**：确认已启动 `uvicorn api.main:app --port 8000`
- **查询失败但 SQL 生成正常**：查看 `logs/smart_query.log` 中「SQL 执行失败」的具体错误（如表结构 / MySQL 函数兼容性）
- **一直走规则模板（method=rule）**：查看日志中「LLM 调用失败」，多为 `.env` 中 `DEEPSEEK_API_KEY` 缺失或网络异常
- **查询速度慢**：LLM 单次调用耗时数秒属正常，可观察日志中的「LLM 调用耗时」确认

## 示例
> **输入**：统计今天各个品类的销售额
> **意图**：柱状图（bar）
> **SQL**：`SELECT c.name, SUM(oi.quantity*oi.price) FROM categories c JOIN products p ON p.category_id=c.id JOIN order_items oi ON oi.product_id=p.id WHERE DATE(o.created_at)=CURDATE() GROUP BY c.name`
> **输出**：柱状图 📊

## 推送到 GitHub
```bash
git init
git add .
git commit -m "feat: 智能问数系统（MySQL）"
git remote add origin https://github.com/你的用户名/smart-query.git
git push -u origin main
```
> `.env` 已被 `.gitignore` 忽略，**数据库密码与 API Key 不会泄露**。
