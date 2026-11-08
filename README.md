# KEKG 知识图谱学习系统

基于 **Flask + Vue3 + MySQL + Neo4j** 的在线学习平台，以知识图谱为核心，覆盖刷题练习、考试测评、班级教学与学习路径推荐等完整学习闭环。

## 技术栈

| 层次 | 技术 |
|------|------|
| 前端 | Vue 3、Vue Router、Axios、ECharts、Vite |
| 后端 | Python Flask、JWT 认证、PyMySQL |
| 图数据库 | Neo4j 5.15（知识图谱存储与路径计算） |
| 关系数据库 | MySQL（业务数据） |
| 测试 | pytest |

## 核心功能

- **知识图谱**：多学科知识点图谱（机器学习、深度学习、Python、DevOps、NLP、LLM 等），支持图谱可视化、知识点检索、前置关系导航
- **刷题练习**：题库管理、难度/题型筛选、答题判题、错题本、刷题历史、AI 组题练习
- **考试测评**：教师布置考试/作业、学生在线作答、自动判分、成绩分析、多轮重做限制
- **班级教学**：班级管理（加入码）、学生管理、教师教学工作台（待批改、草稿考试、最近布置）
- **学习路径**：基于答题掌握度自动评估薄弱点，推荐个性化学习路径（Neo4j 最短路径）
- **统计看板**：全局数据统计、学习热力图、知识点掌握度、难度分布
- **AI 能力**：AI 自动出题、AI 对话练习、AI 编程题解
- **多角色权限**：学生（个人学习）/ 教师（班级教学管理）/ 开发者（系统运维）三类个人界面与功能权限

## 项目结构

```
KEKG/
├── backend/            # Python Flask 后端
│   ├── app/
│   │   ├── routes/     # 接口路由（auth/class/exam/graph/practice/question…）
│   │   ├── services/   # 业务逻辑（学习路径、任务调度、LLM 服务等）
│   │   ├── repositories/  # 数据访问（SQLRepo：MySQL；GraphRepo：Neo4j）
│   │   ├── utils/      # 认证、分页、限流、Excel/Markdown 导出等
│   │   └── config.py   # 配置（从 .env 读取）
│   ├── data/           # 学科图谱种子数据
│   ├── scripts/        # 图谱清洗 / 教材导入工具
│   ├── tests/          # 单元 / 集成 / E2E 测试
│   └── run.py          # 后端启动入口
├── frontend/           # Vue3 前端
│   └── src/
│       ├── views/      # 页面视图（30+）
│       ├── components/ # 通用组件
│       ├── stores/     # 认证状态
│       ├── router/     # 路由
│       └── api/        # axios 封装
└── .gitignore          # 忽略敏感配置与依赖产物
```

## 快速启动

### 环境要求

- Python 3.10+
- Node.js 18+
- MySQL（本地 3306，库名 `kekg_db`）
- Neo4j 5.15（本地 7687）

### 1. 后端

```bash
cd backend
pip install -r requirements.txt
# 复制环境变量模板并按实际环境修改（SECRET_KEY / MySQL / Neo4j 必填）
# cp .env.example .env
python run.py            # http://127.0.0.1:5000
```

### 2. 前端

```bash
cd frontend
npm install
npm run dev              # http://localhost:3000（/api/v1 代理到 5000）
```

## 演示环境还原（MySQL + Neo4j）

本项目的数据分为两部分，需要分别还原：

| 数据 | 落库位置 | 来源文件 |
|------|---------|---------|
| 业务数据（题库、试卷、班级、元数据镜像表等） | MySQL `kekg_db` | `database/seed_demo.sql` |
| 知识图谱（知识点节点、关系、赛道） | Neo4j | `backend/data/graph_*.json` |

### 步骤 1：导入 MySQL 业务数据

> **警告**：`seed_demo.sql` 开头包含 `CREATE DATABASE kekg_db` 和 39 条 `DROP TABLE`，导入会**清空并重建 `kekg_db` 中的数据表**。请勿对已有正式数据的库执行。

```bash
mysql -u root -p < database/seed_demo.sql
```

导入完成后核对行数（可选）：

```sql
USE kekg_db;
SELECT COUNT(*) FROM question_bank;          -- 885
SELECT COUNT(*) FROM question_kp_map;        -- 7952
SELECT COUNT(*) FROM knowledge_points_meta;  -- 6706
SELECT COUNT(*) FROM relationship_meta;      -- 9574
```

### 步骤 2：配置 `.env` 并设置 `SKIP_SQL_META=1`

```bash
cd backend
cp .env.example .env
```

编辑 `.env`，至少填写 `SECRET_KEY`、`MYSQL_PASSWORD`、`NEO4J_PASSWORD`，并确认：

```ini
SKIP_SQL_META=1
```

**为什么必须设为 1**：`seed_demo.sql` 已经把 `knowledge_points_meta` / `relationship_meta` 灌好了。导入图谱时若仍同步写 MySQL（`SKIP_SQL_META=0`），这两张表会出现重复记录，统计数字翻倍。

| 场景 | `SKIP_SQL_META` |
|------|----------------|
| 演示环境（先导入 seed_demo.sql，再导入图谱） | `1` |
| 从零构建（Neo4j 与 MySQL 都没有数据） | `0`（默认） |
| 生产环境（需要 Neo4j / MySQL 双写一致） | `0` |

### 步骤 3：启动 Neo4j 并导入图谱

确认 Neo4j 5.15 已启动（默认 `bolt://localhost:7687`），然后：

```bash
cd backend
python data/seed_data.py     # 读取 data/graph_*.json，导入全部赛道
```

种子文件共 8 个（`python公共部分.json`、`graph_data_analysis.json`、`graph_ml.json`、`graph_dl.json`、`graph_llm.json`、`graph_nlp.json`、`graph_crawler.json`、`graph_devops.json`），按知识点名称去重后约 **6706 个节点 / 9574 条关系** 落入 Neo4j。

> Neo4j 为空时，图谱可视化、学习路径推荐等依赖图谱的功能不可用，但题库、考试、班级等功能不受影响。

### 步骤 4：启动服务并验证

```bash
cd backend && python run.py     # 后端 :5000
cd frontend && npm run dev      # 前端 :3000
```

浏览器访问 `http://localhost:3000`。演示库里预置了两个账号：

| 账号 | 角色 |
|------|------|
| `admin` | 教师 / 管理员 |
| `student` | 学生 |

> 账号密码、邀请码与班级加入码见 `database/seed_demo.sql` 头部注释（**演示环境专用**，请勿用于生产）。也可以自行修改 `users` 表或通过 `.env` 的 `ADMIN_DEFAULT_PASSWORD` / `DEFAULT_INVITE_CODE` 生成新的凭证。

健康检查：`GET http://127.0.0.1:5000/api/v1/health`。

## 角色说明

| 角色 | 定位 | 界面重点 |
|------|------|---------|
| 学生（user） | 普通学习账号 | 刷题、考试、学习路径、个人数据 |
| 教师（admin） | 教学管理者 | 班级管理、布置考试、教学工作台 |
| 开发者（is_dev） | 系统维护者 | 系统概览、用户/日志/配置管理 |
