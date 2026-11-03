# -*- coding: utf-8 -*-
"""
HY Memory SDK - pytest 配置

共享的 fixtures 和配置。
"""

import os
import sys
from pathlib import Path

import pytest


# Windows 的 CRT 默认只给进程 512 个 fd。整个测试套件会创建大量 sqlite / chroma
# 连接，句柄配额耗尽后所有新开文件的操作都会报 "Too many open files"（Linux 上
# 默认 1024+ 所以没暴露）。CRT 上限最高可提到 8192，进程级、幂等、无副作用。
# Python 3.12 与 faiss 的 fopen 走的都是 ucrtbase.dll 的 fd 表。
if sys.platform == "win32":
    try:
        import ctypes
        for _crt in ("ucrtbase", "msvcrt"):
            try:
                ctypes.CDLL(_crt)._setmaxstdio(8192)
            except Exception:
                pass
    except Exception:
        pass


# 加载 .env 文件（如果存在，向上逐级查找）
def _load_env():
    cur = Path(__file__).resolve().parent
    for _ in range(5):
        candidate = cur / ".env"
        if candidate.exists():
            with open(candidate, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, _, v = line.partition("=")
                    k, v = k.strip(), v.strip()
                    if k and k not in os.environ:
                        os.environ[k] = v
            return
        cur = cur.parent


_load_env()


def pytest_configure(config):
    """pytest 配置钩子"""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )


@pytest.fixture(scope="session")
def test_uid():
    """测试用 uid"""
    return "test_user"


@pytest.fixture(scope="session")
def test_agent_id():
    """测试用 agent_id"""
    return "test_scene"


@pytest.fixture
def sample_text_content():
    """示例文本内容"""
    return "用户喜欢在周末去爬山，特别喜欢北京香山"


@pytest.fixture
def sample_qa_pair():
    """示例 QA 对"""
    from hy_memory.models import QAPair
    return QAPair(
        question="你最喜欢的食物是什么？",
        answer="我最喜欢吃火锅，尤其是四川麻辣火锅"
    )


@pytest.fixture
def sample_dialogue():
    """示例对话"""
    return [
        {"role": "user", "content": "你好！"},
        {"role": "assistant", "content": "你好！有什么可以帮助你的吗？"},
        {"role": "user", "content": "我想了解一下天气"},
        {"role": "assistant", "content": "今天北京天气晴朗，气温 15-25 度"}
    ]
