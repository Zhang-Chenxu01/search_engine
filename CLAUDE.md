# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

基于 Elasticsearch 的南开大学新闻通知垂直搜索引擎。面向南开大学公开新闻、通知、公告、讲座、就业、招生等网页资源，构建支持网页抓取、文本索引、搜索查询、文档查询、网页快照、查询日志、个性化排序和推荐的 Web 搜索系统。

## 技术栈

| 层级 | 技术 |
|------|------|
| 爬虫 | Python 3.13, Scrapy, BeautifulSoup4, lxml, readability-lxml |
| 文档解析 | PyMuPDF, python-docx, openpyxl |
| 数据库 | MySQL 8.0, SQLAlchemy 2.x, Alembic |
| 搜索引擎 | Elasticsearch 8.x, IK Analyzer |
| 后端 API | FastAPI, Uvicorn |
| 前端 | React, TypeScript, Vite, Ant Design |

## 目录结构

```
search_engine/
├── crawler/                 # Scrapy 爬虫模块
│   ├── scrapy.cfg
│   └── crawler/
│       ├── spiders/         # 各站点爬虫
│       ├── items.py         # 数据模型
│       ├── pipelines.py     # 数据持久化管道
│       ├── middlewares.py   # 中间件
│       └── settings.py      # 爬虫配置
├── backend/                 # FastAPI 服务
│   ├── app/
│   │   ├── main.py          # 应用入口
│   │   ├── config.py        # 配置管理
│   │   ├── models/          # SQLAlchemy 模型
│   │   ├── schemas/         # Pydantic 数据模型
│   │   ├── routers/         # 按模块拆分的路由
│   │   ├── services/        # 业务逻辑层（含 ES 查询）
│   │   └── dependencies/    # 依赖注入
│   └── alembic/             # 数据库迁移
├── frontend/                # React + TypeScript + Vite
│   ├── src/
│   │   ├── pages/
│   │   ├── components/
│   │   ├── services/        # API 调用层
│   │   └── types/           # TypeScript 类型定义
│   └── vite.config.ts
├── docker-compose.yml       # MySQL + ES 基础设施
├── .env.example             # 环境变量模板
└── README.md
```

## 开发命令参考

```bash
# 启动 MySQL 和 Elasticsearch
docker-compose up -d

# 爬虫
cd crawler && scrapy crawl <spider_name>

# 后端
cd backend && uvicorn app.main:app --reload --port 8000

# 数据库迁移
cd backend && alembic upgrade head
cd backend && alembic revision --autogenerate -m "描述"

# 前端
cd frontend && npm run dev
```

## 开发原则

1. **不要一次性生成过大的代码**，逐步迭代，每个文件保持职责单一。
2. **所有模块都要有清晰目录结构**，新增代码放在对应目录中。
3. **后端代码使用类型注解**，函数签名、方法返回值必须标注类型。
4. **数据库访问通过 SQLAlchemy**，禁止手写 SQL 字符串拼接。
5. **FastAPI 路由按模块拆分**（如 `routers/search.py`、`routers/documents.py`、`routers/logs.py`），在 `main.py` 中统一注册。
6. **Elasticsearch 查询逻辑放在独立 service 层**，路由层不直接操作 ES 客户端。
7. **Scrapy 爬虫与 FastAPI 服务解耦**，爬虫可独立运行，通过数据库或消息队列与后端通信。
8. **React 前端使用 TypeScript**，所有组件 props 定义接口类型。
9. **不要把 API Key、数据库密码等敏感信息写死在代码中**，一律从环境变量读取。
10. **所有配置从 `.env` 或环境变量读取**，提供一个 `.env.example` 作为模板（不含真实值）。
11. **爬虫遵循礼貌抓取原则**：
    - 遵守 `robots.txt`
    - 设置 `DOWNLOAD_DELAY`（建议 1–3 秒）
    - 限制 `CONCURRENT_REQUESTS`（建议 8–16）
    - 设置合理的 `User-Agent`，标明爬虫身份
12. **优先实现最小闭环**：爬取网页 → 解析 → 存 MySQL → 建 ES 索引 → FastAPI 查询 → React 展示。每个环节跑通后再扩展功能。
13. **每次修改代码后，在回复中简要说明**：修改了哪些文件、实现了什么功能、下一步应该做什么。

## 关键约束

- 所有 Python 依赖写入 `requirements.txt` 或 `pyproject.toml`，前端依赖写入 `package.json`。
- Elasticsearch 索引映射需支持 IK Analyzer 中文分词（`ik_max_word` 用于索引，`ik_smart` 用于搜索）。
- 数据库表设计需包含 `created_at` 和 `updated_at` 时间戳字段。
- API 返回格式统一为 `{"code": 0, "data": ..., "message": "ok"}`，分页列表额外包含 `total`、`page`、`page_size`。
- 前端路由使用 React Router，页面级组件做代码分割（`React.lazy`）。
- 项目使用 git 进行版本控制，`.env`、`__pycache__`、`node_modules`、ES 数据目录加入 `.gitignore`。
