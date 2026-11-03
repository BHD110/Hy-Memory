# -*- coding: utf-8 -*-
"""分析今天的 pipeline 日志：谁在调用、查了多少、写了多少。"""
import json
import os
from collections import Counter, defaultdict

HOME = os.path.expanduser("~")
LOG = os.path.join(HOME, ".hy_memory", "logs", "pipeline", "default", "2026-10-23.log")

if not os.path.exists(LOG):
    print("今天还没有 pipeline 日志文件")
    raise SystemExit

entries = []
with open(LOG, encoding="utf-8", errors="replace") as f:
    for ln in f:
        try:
            entries.append(json.loads(ln))
        except Exception:
            continue

# 按 request_id 聚合
reqs = defaultdict(lambda: {"steps": set(), "agent": "", "user": "", "ts": "", "query": ""})
for e in entries:
    rid = e.get("request_id")
    if not rid:
        continue
    r = reqs[rid]
    r["steps"].add(e.get("step"))
    r["agent"] = e.get("agent_id") or r["agent"]
    r["user"] = e.get("user_id") or r["user"]
    if not r["ts"]:
        r["ts"] = str(e.get("timestamp", ""))[11:19]
    if e.get("step") == "READ_REQUEST" and not r["query"]:
        try:
            p = json.loads(e.get("parsed") or "{}")
            r["query"] = str(p.get("query", ""))[:40]
        except Exception:
            pass

READ_MARKS = {"READ_REQUEST", "READ_EMBED_QUERY", "READ_RECALL_VEC"}
WRITE_MARKS = {"S1_EMBED", "EXTRACT", "RECONCILE", "S1_L1_UPSERT"}

reads, writes = [], []
for rid, r in reqs.items():
    if r["steps"] & READ_MARKS:
        reads.append((rid, r))
    if r["steps"] & WRITE_MARKS:
        writes.append((rid, r))

print(f"今日请求总数: {len(reqs)}   检索: {len(reads)}   写入: {len(writes)}")
print()
print("== 检索按来源 ==")
print(dict(Counter(r["agent"] or "?" for _, r in reads)))
print("== 写入按来源 ==")
print(dict(Counter(r["agent"] or "?" for _, r in writes)))
print()
print("== 最近的检索（时间 来源 查询词）==")
for rid, r in sorted(reads, key=lambda x: x[1]["ts"])[-12:]:
    print(f"  {r['ts']}  [{r['agent'] or '?'}]  {r['query']}")
print()
print("== 今天的写入（时间 来源）==")
for rid, r in sorted(writes, key=lambda x: x[1]["ts"])[-12:]:
    print(f"  {r['ts']}  [{r['agent'] or '?'}]")
