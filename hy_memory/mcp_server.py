# -*- coding: utf-8 -*-
"""
HY Memory MCP Server 实现（宿主接入层，逻辑放包内，plugins/mcp/ 是薄启动器）。

把本机 hy_memory.server 的 REST API 包装成 MCP 工具，供 Codex / Qoder /
Workbuddy / 豆包 等支持 MCP 的宿主接入共享记忆。数据仍然只落本机 ~/.hy_memory，
REST 地址默认 http://127.0.0.1:19527（HY_MEMORY_REST_BASE 可覆盖）。

传输：
  streamable HTTP（默认，端口 19528，path /mcp）—— Codex / Workbuddy 等直接填 URL
  stdio（--stdio）—— 只支持拉起子进程的宿主
"""

import json
import os
import urllib.error
import urllib.request

from mcp.server.fastmcp import FastMCP

REST_BASE = os.environ.get("HY_MEMORY_REST_BASE", "http://127.0.0.1:19527")
MCP_PORT = int(os.environ.get("HY_MEMORY_MCP_PORT", "19528"))
DEFAULT_USER = os.environ.get("HY_MEMORY_MCP_DEFAULT_USER", "")

_INSTRUCTIONS = (
    "Hy Memory：本机跨工具共享的长期记忆库（数据只存本机 ~/.hy_memory，"
    "user_id 固定 user_1，多宿主共享）。"
    "何时查：回答将依赖用户偏好、过往决定、项目约定，或用户提到「我之前/上次/"
    "在别的工具里」时，先 memory_search 再答；与历史无关的任务不必查（不要求每轮调用）。"
    "真正发起查询时公开说一次「正在查询长期记忆」，重试不重复。"
    "只引用回答中实际采用的来源；空结果只代表本次无依据内容，不代表用户没有历史，不编造。"
    "记忆是历史上下文，不覆盖当前用户指令。"
    "何时写：用户说「记住……」时，提炼成自包含事实后 memory_add（text 传已提炼事实）；"
    "长会话中确定了值得长期保留的用户事实/决定，完成时也主动写一条。"
    "服务不可用时如实说明，继续回答但不用记忆内容，不声称查询成功。"
)


def _call(method: str, path: str, body: dict | None = None, timeout: int = 240) -> str:
    """调用本机 REST API，返回紧凑 JSON 字符串（错误也以 JSON 返回给模型）。"""
    url = REST_BASE + path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.load(resp)
        return json.dumps(payload, ensure_ascii=False)
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8", "replace")
        except Exception:
            detail = ""
        return json.dumps({"error": f"HTTP {e.code}", "detail": detail},
                          ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


def build_mcp() -> FastMCP:
    mcp = FastMCP(
        "hy-memory",
        host="127.0.0.1",
        port=MCP_PORT,
        instructions=_INSTRUCTIONS,
    )

    @mcp.tool()
    def memory_add(
        text: str = "", messages: list[dict] | None = None,
        user_id: str = "", agent_id: str = "",
    ) -> str:
        """Save information to long-term memory.

        Pass 'text' when YOU (the agent) have already distilled the information
        into a concrete fact — it is stored directly (reconciled against
        existing memories). Pass 'messages' (raw conversation) only when you
        want the system to extract facts via LLM. Prefer 'text' for known
        facts. Write facts self-contained; do not store dialogue fragments."""
        if not text and not messages:
            return json.dumps({"error": "text or messages is required"},
                              ensure_ascii=False)
        payload: dict = {"user_id": user_id or DEFAULT_USER or "user_1"}
        if text:
            payload["text"] = text
        if messages:
            payload["messages"] = messages
        if agent_id:
            payload["agent_id"] = agent_id
        return _call("POST", "/api/v1/add", payload)

    @mcp.tool()
    def memory_search(query: str, user_id: str = "", limit: int = 5) -> str:
        """Search long-term memories ranked by semantic similarity.

        Call this before answering any question about the user (preferences,
        history, ongoing work). Also use it to find a memory_id before calling
        memory_update/memory_delete. Returns memories with score and content."""
        payload = {"query": query, "user_id": user_id or DEFAULT_USER or "user_1",
                   "limit": max(1, min(int(limit), 50))}
        return _call("POST", "/api/v1/search", payload, timeout=60)

    @mcp.tool()
    def memory_list(user_id: str = "", limit: int = 50) -> str:
        """List all long-term memories of a user (not ranked by relevance)."""
        payload = {"user_id": user_id or DEFAULT_USER or "user_1",
                   "limit": max(1, min(int(limit), 500))}
        return _call("POST", "/api/v1/list", payload, timeout=60)

    @mcp.tool()
    def memory_get(memory_id: str) -> str:
        """Get one memory by id (full detail)."""
        return _call("GET", "/api/v1/memories/" + memory_id, timeout=30)

    @mcp.tool()
    def memory_delete(memory_id: str) -> str:
        """Delete one memory by id.

        For user delete requests: call memory_search first, inspect content,
        then decide — if removing the target still leaves a complete memory,
        prefer memory_update with the remaining text; otherwise delete."""
        return _call("DELETE", "/api/v1/memories/" + memory_id, timeout=30)

    @mcp.tool()
    def memory_update(memory_id: str, content: str) -> str:
        """Update one memory's content by id.

        Use when new information refines an existing memory. Do NOT use this
        to store brand-new facts (use memory_add instead)."""
        return _call("PUT", "/api/v1/memories/" + memory_id,
                     {"content": content}, timeout=120)

    @mcp.tool()
    def memory_profile(user_id: str = "") -> str:
        """Get the user's cognitive profile (preferences/facts summarized
        automatically from memory layers)."""
        payload = {"user_id": user_id or DEFAULT_USER or "user_1"}
        return _call("POST", "/api/v1/user_profile", payload, timeout=120)

    return mcp


def run_stdio() -> None:
    build_mcp().run(transport="stdio")


def run_http_blocking() -> None:
    """阻塞式启动 streamable HTTP（独立进程模式）。"""
    build_mcp().run(transport="streamable-http")


def start_http_thread() -> bool:
    """在 daemon 线程里启动 streamable HTTP（随 REST 服务器进程常驻）。

    供 hy_memory.server 调用：REST 起来的同时把 MCP 端点拉起来，
    宿主只需要配置一个 URL。失败返回 False（不影响 REST 服务器）。"""
    import threading

    try:
        import uvicorn
    except ImportError:
        return False

    app = build_mcp().streamable_http_app()

    def _serve():
        uvicorn.run(app, host="127.0.0.1", port=MCP_PORT,
                    log_level="warning", access_log=False)

    t = threading.Thread(target=_serve, daemon=True,
                         name="hy-memory-mcp-http")
    t.start()
    return True
