# 多平台接入指南（官方姿势 · 稳定版）

Hy Memory 服务：REST `127.0.0.1:19527` + MCP `127.0.0.1:19528/mcp`（HTTP）+ stdio 启动器（任一宿主可拉起）。
所有平台共用 `user_id=user_1` 同一记忆库，`agent_id` 区分来源。

## 稳定性保障（已配置）

| 机制 | 说明 |
|---|---|
| 开机自启 | 启动文件夹 `hy-memory-autostart.vbs`，登录即触发 `keepalive.pyw`（拉起 embedding + 服务） |
| 控制台自启 | 启动文件夹 `hy-memory-console.vbs`，等服务 healthz 就绪（最多等 3 分钟）后自动用默认浏览器打开 `http://127.0.0.1:19527/`（无窗口） |
| 保活任务 | 计划任务 `HyMemoryKeepalive` 每 5 分钟自检：11434（embedding）与 19527（服务）谁挂拉谁（幂等，全程无窗口） |
| embedding 后端 | llama.cpp **Vulkan 构建**（`D:\llama-cpp-vulkan\llama-server.exe`）跑 `D:\models\embeddinggemma-300M-Q8_0.gguf`，`-ngl 99` 全量跑在 Intel 集显上，占 11434，OpenAI 兼容 `/v1/embeddings`（2026-10-28 起替代 Ollama；用户要求必须 GPU 不允许 CPU）；日志在 `D:\models\llama-server.log` |
| 手动启动 | `D:\项目\hy-memory\keepalive.bat`（幂等）或 `start_memory.bat`，两者等价于跑一遍 `keepalive.pyw` |

## 各平台接入（官方姿势）

### Codex —— config.toml（官方文档：learn.chatgpt.com/docs/config-file/config-reference）
已配置 `[mcp_servers.hy-memory] url`（HTTP 型，官方支持；goofish-post-mcp 同款已验证）。
自动召回：`~/.codex/AGENTS.md` 已写入"会话开始先检索"规则（Codex 每次会话自动读取）。

### Qoder —— mcp.json stdio 型（官方 docs.qoder.com：MCP 页面支持 SSE/stdio）
已配置 `~/.qoder/mcp.json`：
```json
"hy-memory": { "command": "D:\\项目\\hy-memory\\.venv\\Scripts\\python.exe",
               "args": ["D:\\项目\\hy-memory\\plugins\\mcp\\hy_memory_mcp.py", "--stdio"],
               "env": { "PYTHONIOENCODING": "utf-8" }, "disabled": false }
```
GUI 等价路径：设置 → MCP → 添加 → 类型选 stdio/SSE。`~/.qoder/AGENTS.md` 已写自动召回规则。

### WorkBuddy —— mcp.json http 型（已连通验证）
`~/.workbuddy/mcp.json` 的 `"hy-memory": {"type":"http","url":"http://127.0.0.1:19528/mcp"}`。

### 豆包 —— 自定义连接器（官方文档：doubao.com/work/docs → 在豆包工作中使用插件）
官方路径：豆包客户端左侧「技能 · 连接器 · 伙伴」→ 右上「+ 新建」→「新建自定义连接器」→ 手动添加，填写：
- 命令：`D:\项目\hy-memory\.venv\Scripts\python.exe`
- 参数：`D:\项目\hy-memory\plugins\mcp\hy_memory_mcp.py --stdio`
- 环境：`PYTHONIOENCODING=utf-8`

用户技能（备用，已装）：`agent_mode\workspace\.user_skills\hy-memory\SKILL.md`。

### ZCode —— 用户技能
`C:\Users\a1866\.agents\skills\hy-memory\SKILL.md`（按语义自动触发，教 agent 走 REST 读写）。

## 新平台通用三步

1. 支持 MCP → 优先 stdio（`plugins/mcp/hy_memory_mcp.py --stdio`，100% 兼容），其次 HTTP `http://127.0.0.1:19528/mcp`
2. 只支持 HTTP → REST：`POST /api/v1/add`（写）/ `POST /api/v1/search`（读），UTF-8 JSON，`user_id=user_1`
3. 在该工具的常驻指令位（AGENTS.md / Rules / 连接器描述）写自动召回规则：实质请求前先 search；用户说"记住"时 add

## 其他设备（手机/别的电脑）

`.env` 加 `HY_MEMORY_SERVER_HOST=0.0.0.0` + 防火墙放行 19527-19528 → 局域网用 `http://<IP>:19527`。
跨公网走 Tailscale。**API 无鉴权，仅限可信网络，勿暴露公网。**
