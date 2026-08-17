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

- **知识图谱**：多学科知识点图谱（高等数学、机器学习、深度学习、Python、DevOps、NLP、LLM 等），支持图谱可视化、知识点检索、前置关系导航
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
# 复制并配置环境变量（MySQL/Neo4j 账号密码、SECRET_KEY）
# cp .env.example .env   （若存在示例则复制，否则按 .env 模板创建）
python run.py            # http://127.0.0.1:5000
```

### 2. 前端

```bash
cd frontend
npm install
npm run dev              # http://localhost:3000（/api/v1 代理到 5000）
```

### 3. 初始化数据（可选）

```bash
cd backend
python data/seed_data.py   # 导入学科图谱种子数据
```

## 角色说明

| 角色 | 定位 | 界面重点 |
|------|------|---------|
| 学生（user） | 普通学习账号 | 刷题、考试、学习路径、个人数据 |
| 教师（admin） | 教学管理者 | 班级管理、布置考试、教学工作台 |
| 开发者（is_dev） | 系统维护者 | 系统概览、用户/日志/配置管理 |

## 安全说明

- 所有密钥与数据库凭据存放于 `backend/.env`（已被 .gitignore 排除，不入库）
- 用户密码以哈希存储，JWT 登录鉴权
- 启动时强校验 `SECRET_KEY` 强度，防止弱密钥伪造令牌
