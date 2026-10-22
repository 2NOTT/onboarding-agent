# 使用、导出与复现完整流程

## 1. 直接打开网站

[在线演示](https://2nott.github.io/onboarding-agent/) 托管于 GitHub Pages。它是单文件 HTML 的静态发布，不连接作者电脑，不调用外部模型或 Coze，不要求输入凭据。

所有人物、任务、制度、培训和联系人都是模拟数据。请使用示例问题体验，不要填写真实公司敏感资料。

## 2. 一次完整问答

1. 在“Agent 执行台”选择模拟员工 `E001`，输入或点击“我入职第一天需要做什么？”。
2. 点击“提交问题，开始执行”。本地 Planner 创建问题结构化、员工查询、任务查询、状态计算、任务建议、话术和审核等步骤。
3. 展开“输入 JSON / 输出 JSON”，查看数据如何传递；查看最终回复和审核结果。
4. 点击“导出本次流程 JSON”。文件中保留 `plan`、`steps`、`final_reply`、`risk_result` 等字段，能够查看本次完整过程。
5. 到“执行日志”打开该记录，再次查看或导出。切换页面不丢记录；换浏览器、清理站点数据后记录不会保留。

轨迹是程序调用记录，不是模型内部思维链。静态版按本地规则计算，页面更新不代表发起了真实 AI 请求。

## 3. 制度与负责人场景

分别体验“公司请假制度是什么？”“我应该联系谁办理工位和门禁？”“我的入职培训有哪些？”。比较不同模拟身份的适用任务、负责人、培训与完成状态。

制度返回版本与生效日期；当前以 active 状态和关键词筛选为主，未完整解决多个 active 版本的唯一最新选择与严格适用范围控制。

## 4. Skill 配置与测试

进入“Skill 管理”后，可以查看六类 Skill，打开详情、修改名称与 Prompt、调整模型参数并保存，再运行单独测试。静态版配置保存在浏览器中，Prompt 修改不会改变固定的本地规则算法；真实 Prompt 效果需要在后端接入模型后另外评测。

“导出能力配置”下载 `onboarding-capabilities.json`，结构包含：

```text
format: onboarding-capabilities/v1
mode: local-rule-demo
skills: 当前六类 Skill 配置，不含最近测试记录
tools: 当前七项 Tool 元数据
```

这是便于审阅和复用的配置快照。若用于后端，可分别把 `skills` 和 `tools` 字段包装成同名顶层对象，写入自己的 `backend/data/skills.json` 和 `tools.json`。不要把浏览器配置或仓库当作凭据存储位置。

## 5. Tool 启停与失败边界

“Tool 管理”可查看查询/计算能力与启用状态。可以禁用某个 Tool 后重新提问，观察计划与轨迹，再恢复启用。具体被跳过还是导致回复兜底取决于当前规则与依赖；启停是原型内的能力控制，不是企业身份授权。

Coze Tool 在静态版始终是本地模拟，不联网。后端适配器支持请求、挂起信息与续跑参数，但没有可导出的远端节点定义，也没有完成前端续跑用户流程。

## 6. 下载离线与源码

- 需要给面试官直接体验：发送在线链接。
- 需要脱网演示：下载 Release 附件 `onboarding-demo.html`，双击打开。
- 需要代码复现：GitHub “Code → Download ZIP”，或 `git clone` 后按 README 安装四项 Python 依赖。
- 需要看完整过程：先执行示例，再导出流程 JSON；不需要后端即可审阅。

静态页面与后端版是两套实现，保留了相同业务主题，不能用一版的演示结果代替另一版的外部集成验证。

## 7. 源码调用链

后端主入口为 `backend/main.py`，请求从 `backend/routers/agent.py` 进入 `executor.execute()`，再调用 `planner.make_plan()`；各步骤通过 `skill_registry`、`tool_registry` 和 `backend/tools/` 分发。`risk_control.finalize()` 处理最终审核，`logger.save_execution()` 持久化结果。

静态版对应函数位于 `docs/index.html`：`mockPlan`、`validatePlan`、`execute`、`renderTrace`。`downloadJson` 负责下载，配置与轨迹通过 localStorage 保存。

新下载的源码不包含作者历史执行日志和最近测试记录，后端首次运行时自行生成本地记录。
