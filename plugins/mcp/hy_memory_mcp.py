# -*- coding: utf-8 -*-
"""
HY Memory MCP Server 启动器（薄壳，实现在 hy_memory.mcp_server）。

用法：
  python hy_memory_mcp.py            # streamable HTTP，http://127.0.0.1:19528/mcp
  python hy_memory_mcp.py --stdio    # stdio（宿主按 command/args 拉起）

需要 hy_memory 已安装（pip install hy-memory 或本仓库 pip install -e .），
且本机 hy_memory.server（REST，默认 19527）在运行。
"""

import argparse
import os
import sys


def main() -> None:
    parser = argparse.ArgumentParser(description="HY Memory MCP server")
    parser.add_argument("--stdio", action="store_true",
                        help="stdio 传输（默认 streamable HTTP）")
    args = parser.parse_args()

    # 允许直接从仓库源码运行（未安装时把仓库根目录加进 sys.path）
    try:
        from hy_memory.mcp_server import run_http_blocking, run_stdio
    except ImportError:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from hy_memory.mcp_server import run_http_blocking, run_stdio

    if args.stdio:
        run_stdio()
    else:
        run_http_blocking()


if __name__ == "__main__":
    main()
