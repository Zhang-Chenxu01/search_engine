# 南开大学新闻通知垂直搜索引擎

基于 Elasticsearch 的面向南开大学公开新闻、通知、公告、讲座、就业、招生等网页资源的垂直搜索引擎。

## 功能特性

- 网页抓取与内容解析
- 全文检索与中文分词
- 网页快照
- 查询日志与个性化排序

## 技术栈

| 层级 | 技术 |
|------|------|
| 爬虫 | Python 3.13, Scrapy, BeautifulSoup4, lxml, readability-lxml |
| 文档解析 | PyMuPDF, python-docx, openpyxl |
| 数据库 | MySQL 8.0, SQLAlchemy 2.x, Alembic |
| 搜索引擎 | Elasticsearch 8.x, IK Analyzer |
| 后端 API | FastAPI, Uvicorn |
| 前端 | React, TypeScript, Vite, Ant Design |

## 快速开始

### 环境要求

- Docker Desktop（含 `docker compose` V2）
- Python 3.13+
- Node.js 18+ / npm 10+
- MySQL 8.0 客户端（可选，用于直连调试）

### 1. 启动基础设施（MySQL + Elasticsearch）

```bash
cd docker
docker compose up -d        # V2 命令（不是 docker-compose）
```

> 如果 `docker.elastic.co` 不可达，先用国内镜像拉取再打标签：
> ```bash
> docker pull docker.m.daocloud.io/library/mysql:8.0
> docker tag docker.m.daocloud.io/library/mysql:8.0 mysql:8.0
> docker pull docker.m.daocloud.io/library/elasticsearch:8.12.0
> docker tag docker.m.daocloud.io/library/elasticsearch:8.12.0 docker.elastic.co/elasticsearch/elasticsearch:8.12.0
> ```

### 2. 安装 IK 分词插件

```bash
curl -sL -o analysis-ik-8.12.0.zip "https://get.infini.cloud/elasticsearch/analysis-ik/8.12.0"
docker cp analysis-ik-8.12.0.zip search-engine-es:/tmp/
docker exec search-engine-es bin/elasticsearch-plugin install -b file:///tmp/analysis-ik-8.12.0.zip
docker restart search-engine-es
```

### 3. 配置环境变量

```bash
cp backend/.env.example backend/.env
# 按 docker-compose.yml 中的密码编辑 backend/.env：
#   MYSQL_PASSWORD=root_secret_pwd
#   MYSQL_PORT=3307             （如果本机已有 MySQL 占 3306）
```

### 4. 安装 Python 依赖 + 数据库迁移

```bash
cd backend
pip install -r requirements.txt
python -m alembic upgrade head
```

### 5. 创建 Elasticsearch 索引

```bash
cd backend
python -m indexer.create_indices --force
```

### 6. 运行爬虫抓取网页

```bash
cd backend/crawler
python -m scrapy crawl news
# 输出：data/jsonl/news_YYYYMMDD_HHMMSS.jsonl
```

### 7. 导入数据到 MySQL + Elasticsearch

```bash
cd backend
python -m indexer.import_pages --input data/jsonl/news_YYYYMMDD_HHMMSS.jsonl
```

### 8. 启动后端 API

```bash
cd backend
uvicorn app.main:app --reload --port 8000
# API 文档：http://127.0.0.1:8000/docs
```

### 9. 启动前端

```bash
cd frontend
npm install
npm run dev
# http://localhost:3000
```

---

## 项目结构

```
search_engine/
├── backend/                 # FastAPI 服务
│   ├── app/
│   │   ├── api/             # 路由（auth, search, snapshot, recommend）
│   │   ├── core/            # 配置 / 日志 / 安全
│   │   ├── db/              # 数据库会话
│   │   ├── models/          # SQLAlchemy 模型（6 表）
│   │   ├── schemas/         # Pydantic 数据模型
│   │   ├── search/          # ES 客户端 / 查询构建器
│   │   └── services/        # 业务逻辑（搜索 / 认证 / 快照 / 推荐 / 个性化）
│   ├── alembic/             # 数据库迁移
│   ├── crawler/             # Scrapy 爬虫（可独立运行）
│   ├── indexer/             # ES 索引导入
│   └── parser/              # 文档解析器
├── frontend/                # React + TypeScript + Vite + Ant Design
│   ├── src/
│   │   ├── components/      # MainLayout
│   │   ├── pages/           # 8 个页面
│   │   ├── services/        # Axios API 客户端
│   │   └── types/           # TypeScript 类型定义
│   └── vite.config.ts
├── data/                    # 数据存储（gitignore 内容，只保留 .gitkeep）
│   ├── snapshots/           # HTML 快照
│   ├── attachments/         # 下载的附件
│   └── jsonl/               # 爬虫 JSONL 输出
├── docker/                  # Docker Compose 编排
├── docs/                    # 系统设计 / 开发计划
├── .gitignore
├── CLAUDE.md
└── README.md
```

## API 端点一览

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| POST | `/api/auth/register` | 用户注册 |
| POST | `/api/auth/login` | 用户登录 |
| GET | `/api/auth/me` | 当前用户信息 |
| GET | `/api/search/pages` | 全文搜索（multi_match） |
| GET | `/api/search/phrase` | 精确短语搜索 |
| GET | `/api/search/wildcard` | 通配符搜索 |
| GET | `/api/search/documents` | 文档搜索 |
| GET | `/api/snapshots/by-page/{id}` | 按页 ID 获取快照 |
| GET | `/api/snapshots/raw` | 按路径获取快照 |
| GET | `/api/recommend/suggest` | 查询建议 |
| GET | `/api/recommend/related` | 相关内容推荐 |
| GET | `/api/recommend/hot` | 热门查询 |
