"""Compatibility headers for OpenCode Go's OpenAI-compatible gateway."""

from uuid import uuid4
from urllib.parse import urlsplit

_SESSION_ID = f"hy-memory-{uuid4()}"


def opencode_session_header(base_url: str | None) -> dict[str, str]:
    """Return the routing header required by OpenCode Go, when applicable."""

    if urlsplit(base_url or "").hostname != "opencode.ai":
        return {}
    return {"x-opencode-session": _SESSION_ID}
