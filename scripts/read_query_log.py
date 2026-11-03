# -*- coding: utf-8 -*-
"""提取最近一次 search 请求的完整 pipeline 链路（按 step 字段）。"""
import json
import os
from collections import Counter

LOG = os.path.join(os.path.expanduser("~"), ".hy_memory",
                   "logs", "pipeline", "default", "2026-10-21.log")

entries = []
with open(LOG, encoding="utf-8", errors="replace") as f:
    for ln in f:
        try:
            entries.append(json.loads(ln))
        except Exception:
            continue

steps = Counter(e.get("step") for e in entries)
print("步骤分布:", dict(steps))

# trigger=search 或 step 含 READ 的请求里取最近的
cand = [e for e in entries
        if "search" in str(e.get("parsed", ""))[:30].lower()
        or str(e.get("step", "")).upper().startswith(("READ", "SEARCH", "RETRIEVE"))]
if not cand:
    cand = [e for e in entries if e.get("step") == "DEDUP"]

rid = cand[-1].get("request_id")
steps_of = [e for e in entries if e.get("request_id") == rid]
print(f"\n最近查询 request_id={rid}  步骤 {len(steps_of)} 条：")

for e in steps_of:
    parsed = e.get("parsed") or ""
    try:
        p = json.loads(parsed) if isinstance(parsed, str) and parsed.strip() else {}
    except Exception:
        p = {"raw": str(parsed)[:120]}
    keep = {}
    for k, v in p.items():
        s = json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v
        if len(s) <= 160:
            keep[k] = s
        else:
            keep[k] = s[:160] + "…"
    print(f"\n[{e.get('step')}] {e.get('timestamp','')[11:19]}")
    for k, v in keep.items():
        print(f"  {k}: {v}")
