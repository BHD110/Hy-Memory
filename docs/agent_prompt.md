# Hy Memory Agent 提示词包（官方口径）

来源：本仓库 `plugins/openclaw/`（官方 OpenClaw 插件的自动召回模板与工具描述）与
`memhub/packages/host-bridge/src/recall-injection.ts`（官方宿主注入实现）。
以下文本可直接贴进任意 agent 的常驻指令位（AGENTS.md / Rules / 系统提示 / 连接器描述）。

---

## A. 行为指令（贴给 agent 的规则，中文版）

```markdown
## 长期记忆（Hy Memory，跨工具共享）

你拥有跨会话的长期记忆（工具前缀 hy-memory：memory_add / memory_search /
memory_update / memory_delete / memory_list / memory_profile）。数据只存本机。

- 回答任何关于用户的问题（偏好、历史、正在进行的工作）之前，先 memory_search。
- 每次会话开始处理第一个实质请求前，先 memory_search 与当前任务相关的用户背景；
  分数低（<0.3）的条目不相关，忽略。
- 用户说「记住……」时用 memory_add，把信息提炼成自包含的事实再传 text；
  只有需要系统从原始对话抽取事实时才传 messages。不要用 memory_update 存新事实。
- 用户要删除记忆时：先 memory_search 找到 memory_id，查看内容后判断——
  去掉目标内容后剩余部分仍是完整记忆就用 memory_update 只留剩余文本；
  否则才 memory_delete 整条删除。
- 记忆服务不可用时如实说明，不要编造记忆。
```

## B. 行为指令（英文版，与官方工具描述同语言）

```markdown
## Long-term Memory (Hy Memory, shared across tools)

You have persistent cross-session memory (tools prefixed hy-memory: memory_add /
memory_search / memory_update / memory_delete / memory_list / memory_profile).
Data is stored locally only.

- Before answering any question about the user (preferences, history, ongoing
  work), call memory_search first.
- At the start of a session, search for user context relevant to the first
  substantive request; ignore low-score (<0.3) items.
- When the user says "remember ...", call memory_add with 'text' containing the
  distilled, self-contained fact. Pass raw 'messages' only when you want LLM
  extraction. Never use memory_update to store brand-new facts.
- For delete requests: memory_search first, inspect content; if removing the
  target still leaves a complete memory, use memory_update with the remaining
  text; otherwise memory_delete.
- If the memory service is unavailable, say so honestly; never invent memories.
```

## C. 注入模板（hook 类集成用，官方原文）

自动召回命中后，把以下块注入上下文（官方 `plugins/openclaw/index.ts` 同款格式）：

```
<relevant-memories>
The following are stored memories for user "user_1". Use them to personalize
your response. Ignore items not relevant to the current request:
- [1] 2026-10-21 15:30  记忆内容…
- [2] 2026-10-20 09:12  记忆内容…
</relevant-memories>
```

规则（官方实现同款）：
- prompt < 5 字符不检索；跳过心跳/诊断类系统提示
- 相似度低于阈值（官方默认 0.3~0.4）不注入
- 检索失败必须静默，绝不阻塞主对话
- 捕获对话时先剥掉 `<relevant-memories>` 块，防止记忆嵌套

## D. MCP 工具描述（已内置于 hy-memory MCP server，随 tools/list 下发）

`memory_add` / `memory_search` / `memory_update` / `memory_delete` 的描述已按
官方 `plugins/openclaw/tools/*.ts` 的口径重写（text vs messages 取舍、删除策略、
"先 search 拿 id"）。宿主只要连上 MCP 即自动获得，无需额外配置。
