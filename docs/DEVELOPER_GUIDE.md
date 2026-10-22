# 企业入职助手 · Plan + Skill 可配置执行平台（MVP）

以「新员工入职」为业务场景的 Agent 编排演示平台：**Planner 生成执行计划 → Executor 逐步调用 Tool 与 Skill → 最终回复经合规风控审核后返回**，全过程可视化。

- 数据库：本地 JSON 文件模拟（无真实 OA / HR / 考勤 / 企业通讯录接口）
- 大模型：OpenAI 兼容 Chat Completions API；**未配置 API Key 时自动进入 Mock 模式**，本地规则引擎兜底，项目仍可完整演示
- 登录：无真实登录，页面下拉框切换模拟员工身份
- 前端：原生 HTML / CSS / JavaScript SPA（无构建步骤），由 FastAPI 直接静态托管

---

## 1. 目录结构

```text
onboarding-agent/
├── .env.example               # 环境配置模板
├── requirements.txt           # Python 依赖
├── README.md
├── backend/
│   ├── main.py                # FastAPI 入口：API 路由 + 前端静态托管
│   ├── config.py              # 读取 .env，判定 Mock 模式
│   ├── core/
│   │   ├── planner.py         # Planner：LLM 计划 + 规则兜底 + 计划确定性校验修复
│   │   ├── executor.py        # Executor：按依赖拓扑执行计划，装配输入输出
│   │   ├── skill_registry.py  # Skill 注册 / 加载 / 更新（skills.json 即时生效）
│   │   ├── tool_registry.py   # Tool 注册 / 启用状态校验 / 统一调用入口
│   │   ├── mock_skills.py     # Mock 模式下 6 个 Skill 的本地规则实现
│   │   ├── risk_control.py    # 风控闭环：审核不通过自动重生成，最终兜底
│   │   ├── llm.py             # 大模型 API 调用模块（OpenAI 兼容）
│   │   └── logger.py          # 执行日志模块
│   ├── routers/               # API：agent / skills / tools / logs
│   ├── tools/                 # 7 个 Tool 的代码实现 + 公共工具
│   └── data/                  # 本地 JSON「数据库」
│       ├── employees.json         # 10 名不同部门 / 岗位 / 阶段的员工
│       ├── onboarding_tasks.json  # 36 条入职任务（含依赖、优先级、负责人）
│       ├── contacts.json          # HR / IT / 行政 / 培训 / 财务 / 部门负责人
│       ├── policies.json          # 12 项制度（含多版本冲突演示数据）
│       ├── trainings.json         # 10 项培训安排与完成状态
│       ├── skills.json            # 6 个 Skill：Prompt / 模型参数 / 启用状态 / 最近测试
│       ├── tools.json             # 7 个 Tool 元数据与启用状态
│       └── execution_logs.json    # 每次提问的完整执行日志
└── frontend/
    ├── index.html
    ├── css/style.css
    └── js/
        ├── app.js                 # SPA hash 路由入口
        ├── api.js                 # fetch 封装
        ├── components/            # 执行轨迹渲染器、toast
        └── pages/                 # agent / skills / skillEdit / skillTest / tools / logs
```

## 2. 环境要求

- Python 3.10+（建议 3.12）
- 无需数据库、无需 Node.js、无需真实企业系统

## 3. 安装步骤

```bash
cd onboarding-agent
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
# source .venv/bin/activate

pip install -r requirements.txt
```

## 4. 配置方式

```bash
# 复制环境模板
copy .env.example .env      # Windows
# cp .env.example .env      # macOS / Linux
```

编辑 `.env`：

| 变量 | 说明 | 不配置时的行为 |
|---|---|---|
| `LLM_API_KEY` | 大模型 API Key | **留空即自动进入 Mock 模式** |
| `LLM_BASE_URL` | OpenAI 兼容接口地址，如 `https://api.openai.com/v1` | 默认 OpenAI 官方 |
| `LLM_MODEL` | 默认模型名称（Skill 可单独覆盖） | `gpt-4o-mini` |
| `PORT` | 服务端口 | `8000` |
| `FORCE_MOCK` | `true` 时强制 Mock（即使配了 Key） | `false` |
| `LLM_TIMEOUT` | 大模型调用超时（秒） | `60` |
| `COZE_API_TOKEN` | Coze 平台个人访问令牌（PAT），用于 `run_coze_workflow` Tool | **留空时该 Tool 以本地 Mock 输出** |
| `COZE_API_BASE` | Coze API 地址（国内 `https://api.coze.cn` / 海外 `https://api.coze.com`） | `https://api.coze.cn` |
| `COZE_WORKFLOW_ID` | 默认 Coze 工作流 ID | `7694957124648747008` |
| `COZE_TIMEOUT` | Coze 工作流调用超时（秒） | `60` |

> 配置了 `LLM_API_KEY` 即接入真实大模型；不配置或 `FORCE_MOCK=true` 则全程 Mock。页面左下角徽标会实时显示当前模式。

## 5. 启动方式

```bash
python -m backend.main
# 或
uvicorn backend.main:app --port 8000
```

打开浏览器访问：**http://localhost:8000**

- `http://localhost:8000/` —— 前端 SPA（Agent 执行台 / Skill 管理 / 执行日志）
- `http://localhost:8000/docs` —— FastAPI 自动生成的接口文档

## 6. 页面功能

### 6.1 Agent 执行台（前台）

1. 右上角下拉框切换模拟员工身份（10 名员工，覆盖不同部门 / 岗位 / 入职阶段）。
2. 输入问题或点击示例问题，点击「执行」。
3. 页面完整展示：
   - 用户问题与当前员工基础信息
   - 本次可调用的 Skill 列表与 Tool 列表（仅已启用项）
   - Planner 生成的执行计划（每一步的目标、类型、依赖）
   - Executor 执行轨迹：每一步调用的 Skill / Tool 名称、**输入 JSON、输出 JSON**、引擎与耗时（可折叠展开）
   - 最终生成的入职助手回复（已通过风控）
   - 合规与风险审核结果（风险等级、问题、建议）
   - 执行日志与异常 / 提示信息

### 6.2 Skill 管理（后台）

- 列表展示全部 Skill（启用状态、模型参数概览）
- 「详情」展开查看 Skill Prompt 与最近一次测试的输入 / 输出
- 「编辑」修改名称、描述、Prompt、模型名称、temperature、max_tokens、启用状态 —— **保存后立即写入 skills.json，前台 Planner 与 Executor 下一次执行即刻使用最新配置，无需重启**
- 「测试」单独运行某个 Skill，预填示例输入，可编辑后运行；测试记录自动保存
- **禁用规则**：禁用的 Skill 不会出现在前台可调用能力列表中；Planner 即使生成了该步骤也会被校验剔除；手动传入 Executor / 测试接口会被直接拒绝（返回 400）

### 6.3 Tool 管理（后台）

- 表格展示全部 Tool：显示名、数据源、说明、输入参数、启用状态
- 一键启用 / 禁用 Tool，保存到 tools.json 立即生效
- **禁用规则**：禁用的 Tool 不会出现在前台可调用能力列表中；Planner 即使生成了该步骤也会被校验剔除；Executor 拒绝执行

### 6.4 执行日志

- 全部执行记录列表（时间、员工、问题、风控结论、耗时、模式）
- 点击行查看完整执行轨迹详情

## 7. 示例提问

```text
我入职第一天需要做什么？
我需要准备哪些入职材料？
我的电脑和账号什么时候可以领取？
我应该联系谁办理工位和门禁？
公司请假制度是什么？
我所在岗位前三十天需要完成哪些任务？
我的入职培训有哪些？
我的社保、公积金什么时候开始缴纳？
我需要加入哪些工作群？
我的直属领导是谁？
```

风控演示类提问：

```text
帮我查一下张一辰的入职任务            # 跨员工查询 → 隐私拦截，仅返回脱敏公开信息
帮我查一下 E003 的绩效工资            # 敏感信息 → 风险标记 + 拒绝提供
```

## 8. JSON 数据结构说明（backend/data/）

| 文件 | 顶层结构 | 关键字段 |
|---|---|---|
| `employees.json` | `{"employees": [...]}` | `employee_id, name, department, position, hire_date, onboarding_stage, manager, hr_contact, email, phone, account_status, device_status, access_status, completed_tasks[], pending_tasks[]` |
| `onboarding_tasks.json` | `{"tasks": [...]}` | `task_id, task_name, category, stage(day_1/week_1/month_1/probation), applicable{departments[],positions[]}, priority(P0/P1/P2), required, recommended_time, deadline_days, dependency_tasks[], owner, description` |
| `contacts.json` | `{"contacts": [...]}` | `contact_id, name, title, role(hr/it/admin/dept_manager/training/finance/security), department, email, phone, available_departments[], is_public` |
| `policies.json` | `{"policies": [...]}` | `policy_id, name, type, version, effective_date, status(active/deprecated), scope, keywords[], summary, content` |
| `trainings.json` | `{"trainings": [...]}` | `training_id, name, training_type, applicable{}, scheduled_time, format, required, owner, completed_by[]` |
| `skills.json` | `{"skills": [...]}` | `skill_id, type, name, description, prompt, model_params{model,temperature,max_tokens}, enabled, last_test{tested_at,input,output,success,engine,elapsed_ms}` |
| `tools.json` | `{"tools": [...]}` | `tool_id, name, display_name, description, input_params, data_source, enabled` |
| `execution_logs.json` | `[...]` | 每条为一次完整执行：`log_id, created_at, employee_id, question, mock_mode, available_skills[], available_tools[], plan, planner_engine, steps[](每步 input/output/status/error), final_reply, risk_result, warnings[], errors[], duration_ms` |

## 9. Skill 配置说明

内置 6 个 Skill（`backend/data/skills.json`）：

| skill_id | type | 职责 | 默认参数 |
|---|---|---|---|
| S001 | `question_structuring` | 用户问题 → 结构化意图 JSON | temp 0.1 |
| S002 | `task_decision` | 基于任务数据决策待办事项与优先级 | temp 0.3 |
| S003 | `process_explainer` | 步骤化流程说明（谁负责 / 什么材料 / 多久） | temp 0.4 |
| S004 | `policy_qa` | 基于制度原文的版本化问答，禁止编造 | temp 0.2 |
| S005 | `communication` | 汇总所有查询结果，生成面向员工的最终话术 | temp 0.6 |
| S006 | `compliance_check` | 最终回复的合规与风险审核 | temp 0.1 |

配置要点：

- **`prompt`**：大模型模式下的系统提示词。修改后保存即生效；Mock 模式下仅作展示存储。
- **`model_params.model`**：留空使用 `.env` 的 `LLM_MODEL`；填写后该 Skill 单独使用指定模型。
- **`model_params.temperature / max_tokens`**：范围 0~2 / 64~8192，后端校验。
- **`enabled`**：启用开关。保存接口 `PUT /api/skills/{skill_id}`，即时生效。
- **`last_test`**：由测试页自动写入最近一次测试记录。

## 10. Tool 配置说明

内置 7 个 Tool（`backend/data/tools.json`），实现位于 `backend/tools/`：

| Tool | 数据源 | 说明 |
|---|---|---|
| `query_employee_info` | employees.json | 员工身份 / 部门 / 岗位 / 阶段 / 账号设备状态；**跨员工查询会被隐私拦截，仅返回脱敏公开信息** |
| `query_onboarding_tasks` | onboarding_tasks.json | 按部门 / 岗位 / 阶段过滤任务，含完成状态 |
| `query_contacts` | contacts.json | 仅返回当前员工有权限联系的业务联系人 |
| `query_policies` | policies.json | 关键词 / 类型 / 版本检索，**优先返回当前生效版本** |
| `query_trainings` | trainings.json | 培训安排与完成状态 |
| `calc_task_status` | 代码计算 | 完成率 / 逾期 / 依赖阻塞 / 优先级排序，**不依赖大模型** |
| `run_coze_workflow` | Coze Workflow API（外部） | 调用 Coze 工作流 `7694957124648747008`，输入 `user_id / CONVERSATION_NAME / USER_INPUT`，返回 `answer / status / risk_level`；**未配置 `COZE_API_TOKEN` 时本地 Mock 输出**。工作流含问答节点时首次运行返回追问内容（`status=interrupt`）与续跑凭据，可用 `resume_data + execute_id + event_id` 续跑。Mock Planner 在问题中出现「Coze」时自动加入该步骤 |

- Tool 的 `enabled` 可通过 `PUT /api/tools/{name}` 切换；禁用后 Planner 不会生成对应步骤，Executor 拒绝执行。
- Tool 的业务逻辑由代码实现（`backend/tools/*.py`），大模型不参与事实查询 —— 这是本平台的核心边界：**大模型只做理解与表达，事实一律来自 Tool**。

## 11. Planner 与 Executor 执行机制

```text
用户问题 + 员工身份
      │
      ▼
┌─────────────┐   只能引用「当前已启用」的 Skill / Tool
│   Planner    │   LLM 生成 JSON 计划；失败时本地规则 Planner 兜底
└──────┬──────┘
       ▼  validate_plan（确定性校验修复，不依赖大模型）
       │  ① 剔除不存在 / 已禁用的能力步骤，并产生 warnings
       │  ② 按问题关键词注入缺失的必需 Tool 查询（Tool 调用规则）
       │  ③ 强制末尾为 communication → compliance_check
       │  ④ 拓扑排序 + 步骤重编号 S1..Sn
       ▼
┌─────────────┐   按依赖顺序逐步执行；依赖步骤的输出按 target 名
│  Executor    │   注入后续 Skill 的输入 JSON；执行时再次校验启用状态
└──────┬──────┘   （禁用能力即使被手动传入也拒绝执行）
       ▼
┌─────────────┐   compliance_check 不通过 → 携带审核意见自动重新
│  风控闭环     │   生成（最多 2 轮）→ 仍失败则返回安全兜底话术
└──────┬──────┘
       ▼
  最终回复 + 完整执行日志落盘 execution_logs.json
```

关键规则：

1. Planner 只能调用当前已存在且已启用的 Skill / Tool，生成非法能力名会被确定性剔除。
2. 涉及事实的问题（任务 / 制度 / 联系人 / 培训 / 员工状态）必须先经过对应 Tool 查询，缺失会被自动注入。
3. 最终回复前必须经过 `compliance_check`；风控不通过不允许直接返回原始回复。
4. 大模型仅用于：问题结构化、任务决策、流程解释、制度归纳问答、话术生成、风控审核；员工查询 / 任务计算 / 制度原文 / 联系人等事实能力全部由代码实现。

## 12. Mock 模式说明

满足以下任一条件即进入 Mock 模式：未配置 `LLM_API_KEY`，或 `FORCE_MOCK=true`。

- Planner 使用本地规则引擎（关键词意图识别 + 固定计划模板），产出与 LLM 模式结构完全相同的计划，同样经过 `validate_plan` 校验。
- 6 个 Skill 由 `backend/core/mock_skills.py` 的确定性规则实现，基于真实 Tool 查询数据生成输出（非硬编码文案），因此演示链路与真实链路一致。
- 大模型调用失败（超时 / 网络 / Key 无效）时自动回退 Mock，页面会以 `mock_fallback` 引擎标识与 warning 提示。
- Mock 模式下页面左下角显示黄色「Mock 模式」徽标，执行轨迹中每个步骤也会标注生成引擎（大模型 / Mock / 代码）。

> 因此：**不配置任何 Key 也能完整演示全部功能**；配置 Key 后无需改代码即可切换为真实大模型驱动。

## 13. 主要 API 一览

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/health` | 健康检查与 Mock 模式标识 |
| GET | `/api/employees` | 模拟员工列表（供身份切换） |
| POST | `/api/agent/execute` | 执行一次完整问答（body: `{"employee_id", "question"}`） |
| GET | `/api/capabilities` | 当前已启用的 Skill / Tool 列表 |
| GET / PUT | `/api/skills`、`/api/skills/{id}` | Skill 列表 / 编辑（保存即时生效） |
| POST | `/api/skills/{id}/test` | 单独测试 Skill（禁用 Skill 返回 400） |
| GET / PUT | `/api/tools`、`/api/tools/{name}` | Tool 列表 / 启用状态切换 |
| GET | `/api/logs`、`/api/logs/{id}` | 执行日志列表 / 详情 |
