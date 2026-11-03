# -*- coding: utf-8 -*-
"""
HY Memory 本地控制台（内嵌静态资源，完整版）。

视觉与功能对标 MemHub 桌面版（memhub/apps/web R6 shell）：
  · 记忆空间四模式：工作台（图谱）/ 记忆库 / 问答 / 历史检索
  · 应用（来源管理）：各宿主工具的记忆量、最近写入、跳转
  · 设置：模型配置、连通性探测、帮助与诊断
数据全部来自本进程 REST API（/api/v1/*），无外部依赖。
"""

INDEX_HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MemHub · Hy Memory</title>
<style>
:root {
  color-scheme: light;
  --bg: #e9edf2; --card: #fff; --panel: #f4f6f9; --hover: #edf1f5;
  --tx: #262a2e; --tx2: #5a6169; --tx3: #5d6873;
  --bd: #d3d9e0; --bd2: #bfccd8;
  --ac: #4e6478; --ac-strong: #3b4e5e; --ac-bg: rgba(78,100,120,.07);
  --dg: #96453e; --dg-bg: #f8eeec; --dg-bd: #d3a9a4;
  --wn: #816020; --wn-bg: #f7f1e6; --wn-bd: #c7b188;
  --ok: #2f6b57; --ok-bg: #edf4f0; --ok-bd: #a3bdaf;
  --idle: #aab1b8;
  --nd-memory: #4e6478; --nd-schema: #7d93a6; --nd-topic: #a88140; --nd-source: #2f6b57;
  --r-ctl: 9px; --r-card: 14px;
  --ease: cubic-bezier(.32,.72,0,1);
  --shadow-pop: 0 2px 10px rgba(38,42,46,.04);
  --shadow-modal: 0 24px 64px rgba(38,42,46,.14);
}
* { box-sizing: border-box; }
html, body { height: 100%; }
body {
  margin: 0; font-family: -apple-system, BlinkMacSystemFont, "PingFang SC",
    "Microsoft YaHei UI", "Noto Sans SC", sans-serif;
  font-size: 14px; line-height: 1.65; color: var(--tx);
  background: linear-gradient(125deg, #ecf2f6, #e7edf2 54%, #edf1f4) fixed;
}
.shell { display: grid; grid-template-columns: 78px minmax(0,1fr); grid-template-rows: 58px minmax(0,1fr) 44px; height: 100dvh; }
/* ── 标题栏 / 图标栏 / 底栏（R6 shell）── */
.titlebar { grid-column: 1/-1; display: flex; align-items: center; gap: 10px; height: 58px; padding: 0 24px;
  border-bottom: 1px solid rgb(255 255 255 / 75%); background: rgb(255 255 255 / 19%);
  backdrop-filter: blur(40px); color: #384a57; user-select: none; }
.brand-mark { display: flex; align-items: center; justify-content: center; width: 30px; height: 30px;
  border-radius: 9px; background: linear-gradient(135deg, #5d7488, #3b4e5e); color: #fff; font-weight: 700; font-size: 13px; }
.titlebar .title { font-weight: 600; }
.titlebar .sub { color: var(--tx3); font-size: 12px; }
.pill { margin-left: auto; display: inline-flex; align-items: center; gap: 6px; padding: 3px 10px;
  border-radius: 999px; font-size: 12px; border: 1px solid var(--bd); background: rgb(255 255 255 / 65%); }
.pill .dot { width: 7px; height: 7px; border-radius: 50%; background: var(--idle); }
.pill.ok { color: var(--ok); background: var(--ok-bg); border-color: var(--ok-bd); } .pill.ok .dot { background: var(--ok); }
.pill.bad { color: var(--dg); background: var(--dg-bg); border-color: var(--dg-bd); } .pill.bad .dot { background: var(--dg); }
.rail { grid-column: 1; grid-row: 2; display: flex; flex-direction: column; gap: 12px; padding: 20px 9px 16px;
  background: rgb(239 245 248 / 38%); border-right: 1px solid rgb(255 255 255 / 70%); backdrop-filter: blur(20px) saturate(110%); }
.rail-spacer { flex: 1; }
.rail-btn { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 6px;
  width: 60px; min-height: 64px; padding: 10px 2px; border: 1px solid transparent; border-radius: 8px;
  background: transparent; color: var(--tx2); font-size: 11px; font-weight: 500; cursor: pointer;
  transition: background .12s var(--ease), color .12s var(--ease); }
.rail-btn svg { width: 20px; height: 20px; }
.rail-btn:hover { color: var(--tx); background: rgb(255 255 255 / 76%); }
.rail-btn.active { color: var(--tx); background: #e7edf2; box-shadow: inset 0 0 0 1px #c2ced8; }
.footer { grid-column: 1/-1; grid-row: 3; display: flex; align-items: center; gap: 14px; padding: 0 32px;
  font-size: 12px; color: var(--tx3); background: rgb(255 255 255 / 15%); border-top: 1px solid rgb(255 255 255 / 60%); }
.footer .lock { display: inline-flex; align-items: center; gap: 5px; color: var(--tx2); }
/* ── 内容区 ── */
.content { grid-column: 2; grid-row: 2; overflow-y: auto; overscroll-behavior: contain; scrollbar-width: thin; padding: 24px 36px 22px; }
.view { display: none; }
.view.on { display: block; animation: enter .22s cubic-bezier(.16,1,.3,1); }
@keyframes enter { from { opacity: 0; transform: translateY(6px); } }
.page-head { margin-bottom: 16px; display: flex; align-items: flex-end; gap: 14px; flex-wrap: wrap; }
.page-head .grow { flex: 1; min-width: 240px; }
.eyebrow { margin: 0; color: var(--tx2); font-size: 12px; font-weight: 600; }
.page-head h1 { margin: 2px 0 0; font-size: 21px; font-weight: 650; letter-spacing: .2px; }
.page-head .desc { margin: 3px 0 0; color: var(--tx2); font-size: 13px; }
/* ── 记忆空间模式页签 ── */
.space-head { display: flex; align-items: center; gap: 14px; margin-bottom: 14px; flex-wrap: wrap; }
.space-head .who { display: flex; align-items: center; gap: 8px; }
.space-head .who input { width: 170px; min-height: 34px; }
.mode-tabs { display: inline-flex; gap: 4px; padding: 4px; border: 1px solid var(--bd); border-radius: 11px;
  background: rgb(255 255 255 / 72%); margin-left: auto; }
.mode-tabs button { display: inline-flex; align-items: center; gap: 6px; min-height: 32px; padding: 5px 13px;
  border: 0; border-radius: 8px; background: transparent; color: var(--tx2); font-size: 13px; font-weight: 500; cursor: pointer; }
.mode-tabs button svg { width: 15px; height: 15px; }
.mode-tabs button:hover { color: var(--tx); background: var(--hover); }
.mode-tabs button[aria-selected="true"] { color: #fff; background: var(--ac); }
.mode-panel { display: none; }
.mode-panel.on { display: block; animation: enter .22s cubic-bezier(.16,1,.3,1); }
/* ── 通用卡片/控件 ── */
.card { border: 1px solid rgb(255 255 255 / 80%); border-radius: var(--r-card); background: var(--card);
  box-shadow: var(--shadow-pop); padding: 16px 18px; }
.card + .card { margin-top: 13px; }
.card h2 { margin: 0 0 4px; font-size: 15px; font-weight: 600; }
.card .hint { margin: 0 0 12px; color: var(--tx2); font-size: 12.5px; }
.row { display: flex; gap: 10px; flex-wrap: wrap; align-items: flex-end; }
.field { display: flex; flex-direction: column; gap: 4px; }
.field label { font-size: 12px; font-weight: 600; color: var(--tx2); }
input, textarea, select { font: inherit; width: 100%; min-height: 38px; padding: 8px 10px;
  border: 1px solid var(--bd); border-radius: 6px; color: var(--tx); background: var(--card); }
textarea { min-height: 84px; resize: vertical; line-height: 1.55; }
input:focus-visible, textarea:focus-visible, select:focus-visible, button:focus-visible { outline: 2px solid var(--ac); outline-offset: 2px; }
button { min-height: 36px; padding: 8px 16px; border: .5px solid var(--ac); border-radius: var(--r-ctl);
  color: #fff; background: var(--ac); font-size: 13px; font-weight: 500; cursor: pointer;
  transition: background .12s var(--ease), transform .12s var(--ease); display: inline-flex; align-items: center; gap: 6px; justify-content: center; }
button:hover:not(:disabled) { background: var(--ac-strong); border-color: var(--ac-strong); }
button:active:not(:disabled) { transform: translateY(1px); }
button:disabled { border-color: var(--bd2); color: var(--tx3); background: var(--panel); cursor: not-allowed; }
button.secondary { border-color: var(--bd2); color: var(--tx); background: var(--card); }
button.secondary:hover:not(:disabled) { background: var(--hover); }
button.quiet { border-color: transparent; color: var(--tx2); background: transparent; }
button.quiet:hover:not(:disabled) { color: var(--tx); background: var(--hover); }
button.danger { border-color: var(--dg-bd); color: var(--dg); background: var(--dg-bg); }
button.danger:hover:not(:disabled) { background: #f1ded9; border-color: var(--dg); }
button.small { min-height: 28px; padding: 3px 10px; font-size: 12px; }
.spin { display: inline-block; animation: spin .9s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
/* ── 概览统计 ── */
.stat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 13px; margin-bottom: 13px; }
.stat .k { color: var(--tx2); font-size: 12px; font-weight: 600; }
.stat .v { font-size: 21px; font-weight: 650; margin-top: 2px; font-variant-numeric: tabular-nums; }
.stat .s { color: var(--tx3); font-size: 12px; margin-top: 1px; }
/* ── 记忆条目 ── */
.mem { border: 1px solid var(--bd); border-radius: 10px; padding: 11px 14px; background: var(--card); }
.mem + .mem { margin-top: 9px; }
.mem .top { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.tag { font-size: 11px; font-weight: 600; padding: 1px 8px; border-radius: 999px; border: 1px solid var(--bd); color: var(--tx2); background: var(--panel); }
.tag.layer { color: var(--ac); background: var(--ac-bg); border-color: rgba(78,100,120,.42); }
.tag.src { color: var(--nd-source); background: var(--ok-bg); border-color: var(--ok-bd); }
.tag.st-active { color: var(--ok); background: var(--ok-bg); border-color: var(--ok-bd); }
.tag.st-superseded { color: var(--wn); background: var(--wn-bg); border-color: var(--wn-bd); }
.mem .meta { margin-left: auto; color: var(--tx3); font-size: 11.5px; display: flex; gap: 8px; align-items: center; }
.mem .body { margin-top: 5px; white-space: pre-wrap; word-break: break-word; }
.mem .mid { color: var(--tx3); font-size: 11px; font-family: ui-monospace, Consolas, monospace; margin-top: 5px; }
.score { font-variant-numeric: tabular-nums; color: var(--ac); font-weight: 600; font-size: 12px; }
.scorebar { height: 3px; border-radius: 2px; background: var(--panel); margin-top: 7px; overflow: hidden; }
.scorebar i { display: block; height: 100%; background: linear-gradient(90deg, #7d93a6, var(--ac)); }
mark { background: #f3e3c2; border-radius: 3px; padding: 0 2px; }
.empty { border: 1px dashed var(--bd2); border-radius: var(--r-card); padding: 38px 20px; text-align: center;
  color: var(--tx2); background: rgb(255 255 255 / 55%); }
.empty b { display: block; color: var(--tx); font-size: 15px; margin-bottom: 4px; }
.toast { position: fixed; left: 50%; bottom: 62px; transform: translateX(-50%) translateY(20px); max-width: 560px;
  padding: 10px 18px; border-radius: 12px; background: #323a41; color: #f2f5f7; font-size: 13px;
  box-shadow: var(--shadow-modal); opacity: 0; pointer-events: none; transition: all .18s var(--ease); z-index: 60; }
.toast.show { opacity: 1; transform: translateX(-50%) translateY(0); }
.toast.err { background: #6e332d; }
details.json { margin-top: 8px; }
details.json summary { cursor: pointer; color: var(--tx2); font-size: 12px; }
details.json pre { margin: 6px 0 0; padding: 10px 12px; border-radius: 8px; background: var(--panel);
  border: 1px solid var(--bd); font-size: 11.5px; line-height: 1.5; overflow: auto;
  font-family: ui-monospace, Consolas, monospace; white-space: pre-wrap; word-break: break-all; }
/* ── 工作台图谱 ── */
.map-wrap { position: relative; border: 1px solid rgb(255 255 255 / 80%); border-radius: var(--r-card);
  background: var(--panel); box-shadow: var(--shadow-pop); overflow: hidden; }
.map-toolbar { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; padding: 12px 16px;
  border-bottom: 1px solid var(--bd); background: rgb(255 255 255 / 55%); }
.map-toolbar .search { flex: 1; min-width: 180px; max-width: 320px; }
.map-toolbar .search input { min-height: 32px; }
.seg { display: inline-flex; gap: 3px; padding: 3px; border: 1px solid var(--bd); border-radius: 9px; background: rgb(255 255 255 / 70%); }
.seg button { min-height: 27px; padding: 2px 11px; font-size: 12px; border: 0; border-radius: 7px; background: transparent; color: var(--tx2); }
.seg button[aria-pressed="true"] { background: var(--ac); color: #fff; }
.map-groups { display: flex; gap: 6px; flex-wrap: wrap; padding: 9px 16px; border-bottom: 1px solid var(--bd); }
.map-groups button { min-height: 26px; padding: 1px 11px; font-size: 12px; border-radius: 999px;
  border: 1px solid var(--bd); background: var(--card); color: var(--tx2); }
.map-groups button.selected { border-color: var(--ac); background: var(--ac-bg); color: var(--ac); }
.map-canvas { display: block; width: 100%; height: 520px; cursor: grab; }
.map-legend { display: flex; gap: 14px; flex-wrap: wrap; padding: 8px 16px; border-top: 1px solid var(--bd);
  font-size: 11.5px; color: var(--tx2); background: rgb(255 255 255 / 45%); }
.map-legend i { display: inline-block; width: 9px; height: 9px; border-radius: 50%; margin-right: 4px; vertical-align: -1px; }
.map-tip { position: absolute; pointer-events: none; max-width: 280px; padding: 7px 10px; border-radius: 9px;
  background: #323a41; color: #f2f5f7; font-size: 12px; line-height: 1.5; display: none; z-index: 5;
  box-shadow: var(--shadow-pop); }
.inspector { position: absolute; top: 57px; right: 14px; bottom: 34px; width: 316px; overflow-y: auto;
  border: 1px solid var(--bd2); border-radius: 12px; background: var(--card); box-shadow: var(--shadow-modal);
  padding: 14px 16px; display: none; z-index: 6; }
.inspector.on { display: block; animation: enter .18s cubic-bezier(.16,1,.3,1); }
.inspector h3 { margin: 0 0 2px; font-size: 13px; }
.inspector .close { position: absolute; top: 8px; right: 8px; }
/* ── 问答 ── */
.answer { margin-top: 13px; padding: 14px 16px; border: 1px solid var(--ok-bd); border-radius: 12px;
  background: var(--ok-bg); white-space: pre-wrap; }
.answer .model { display: block; margin-top: 8px; color: var(--tx3); font-size: 11.5px; }
.cites { margin-top: 10px; }
.cite { border: 1px solid var(--bd); border-radius: 10px; padding: 9px 12px; background: var(--card); margin-top: 7px; font-size: 13px; }
.cite .n { display: inline-flex; width: 19px; height: 19px; align-items: center; justify-content: center;
  border-radius: 50%; background: var(--ac); color: #fff; font-size: 11px; font-weight: 700; margin-right: 7px; }
/* ── 应用卡片 ── */
.src-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 13px; }
.src-card .head { display: flex; align-items: center; gap: 10px; }
.src-ico { display: flex; align-items: center; justify-content: center; width: 36px; height: 36px;
  border-radius: 10px; color: #fff; font-weight: 700; font-size: 15px; }
.src-card .name { font-weight: 600; }
.src-card .how { color: var(--tx3); font-size: 11.5px; }
.src-card .nums { display: flex; gap: 16px; margin: 10px 0 4px; }
.src-card .nums b { font-size: 17px; font-variant-numeric: tabular-nums; }
.src-card .nums span { display: block; color: var(--tx3); font-size: 11px; }
/* ── 设置 ── */
.kv { display: grid; grid-template-columns: auto 1fr; gap: 4px 18px; font-size: 13px; margin: 4px 0 2px; }
.kv dt { color: var(--tx2); }
.kv dd { margin: 0; word-break: break-all; font-family: ui-monospace, Consolas, monospace; font-size: 12px; }
.probe-line { display: flex; align-items: center; gap: 8px; margin-top: 8px; font-size: 12.5px; }
.notice { display: none; margin: 0 0 13px; padding: 9px 14px; border: 1px solid var(--wn-bd); border-radius: 10px;
  background: var(--wn-bg); color: var(--wn); font-size: 12.5px; }
.notice.show { display: block; }
@media (max-width: 900px) { .content { padding: 16px 14px; } .shell { grid-template-columns: 64px minmax(0,1fr); }
  .mode-tabs { margin-left: 0; } .map-canvas { height: 420px; } .inspector { width: 260px; } }
</style>
</head>
<body>
<div class="shell">
  <header class="titlebar">
    <span class="brand-mark">M</span>
    <span class="title">MemHub</span>
    <span class="sub">hy-memory runtime</span>
    <span class="pill" id="status-pill"><span class="dot"></span><span id="status-text">连接中…</span></span>
  </header>

  <nav class="rail" aria-label="主要导航">
    <button class="rail-btn" data-view="memory" title="记忆">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 1.66 3.58 3 8 3s8-1.34 8-3V5"/><path d="M4 12c0 1.66 3.58 3 8 3s8-1.34 8-3"/></svg>
      <span>记忆</span>
    </button>
    <button class="rail-btn" data-view="sources" title="应用">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/></svg>
      <span>应用</span>
    </button>
    <div class="rail-spacer"></div>
    <button class="rail-btn" data-view="settings" title="设置">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09a1.65 1.65 0 0 0 1.51-1 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33h.01a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51h.01a1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82v.01a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
      <span>设置</span>
    </button>
  </nav>

  <main class="content">
    <div class="notice" id="env-notice">
      记忆整理需要模型服务。当前未配置或不可达 —— 在 <code>D:\项目\hy-memory\.env</code> 检查
      <code>MEMORY_LLM_API_KEY</code> 与 Embedder 配置后重启服务。
    </div>

    <!-- ═════════ 记忆空间 ═════════ -->
    <section class="view" id="view-memory">
      <div class="space-head">
        <div class="who">
          <div class="field"><label for="uid">user_id</label><input id="uid" placeholder="user_1"></div>
        </div>
        <div class="mode-tabs" role="tablist" aria-label="记忆空间模式" id="mode-tabs">
          <button role="tab" data-mode="map" aria-selected="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="16" y="16" width="6" height="6" rx="1"/><rect x="2" y="16" width="6" height="6" rx="1"/><rect x="9" y="2" width="6" height="6" rx="1"/><path d="M5 16v-3a1 1 0 0 1 1-1h12a1 1 0 0 1 1 1v3"/><path d="M12 12V8"/></svg>
            工作台</button>
          <button role="tab" data-mode="library" aria-selected="false">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>
            记忆库</button>
          <button role="tab" data-mode="ask" aria-selected="false">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/></svg>
            问答</button>
          <button role="tab" data-mode="history" aria-selected="false">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/><line x1="8" y1="11" x2="14" y2="11"/></svg>
            历史检索</button>
        </div>
      </div>

      <!-- ── 工作台（图谱）── -->
      <div class="mode-panel on" id="panel-map" role="tabpanel">
        <div class="map-wrap">
          <div class="map-toolbar">
            <div class="seg" id="axis-seg" role="group" aria-label="分组维度">
              <button data-axis="agent" aria-pressed="true">按来源</button>
              <button data-axis="layer" aria-pressed="false">按层级</button>
              <button data-axis="status" aria-pressed="false">按状态</button>
            </div>
            <div class="field search"><label for="map-q" class="sr" style="position:absolute;left:-9999px">过滤</label>
              <input id="map-q" placeholder="过滤记忆…"></div>
            <button class="secondary small" id="map-reload">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M21 12a9 9 0 1 1-2.64-6.36"/><polyline points="21 3 21 9 15 9"/></svg>
              刷新</button>
            <span style="color:var(--tx3);font-size:12px" id="map-count"></span>
          </div>
          <div class="map-groups" id="map-groups"></div>
          <canvas class="map-canvas" id="map-canvas"></canvas>
          <div class="map-tip" id="map-tip"></div>
          <aside class="inspector" id="map-inspector" aria-label="记忆详情"></aside>
          <div class="map-legend" id="map-legend"></div>
        </div>
      </div>

      <!-- ── 记忆库 ── -->
      <div class="mode-panel" id="panel-library" role="tabpanel">
        <div class="card">
          <div class="row">
            <div class="field" style="flex:1;min-width:200px"><label for="lib-q">过滤（内容 / 标签）</label><input id="lib-q" placeholder="输入关键词…"></div>
            <div class="field" style="width:150px"><label for="lib-agent">来源</label><select id="lib-agent"><option value="">全部</option></select></div>
            <div class="field" style="width:130px"><label for="lib-layer">层级</label><select id="lib-layer"><option value="">全部</option></select></div>
            <div class="field" style="width:130px"><label for="lib-status">状态</label><select id="lib-status"><option value="">全部</option></select></div>
            <button class="danger" id="btn-del-all">清空该用户…</button>
          </div>
        </div>
        <div id="library-body" style="margin-top:13px"></div>
        <div class="row" style="margin-top:12px;justify-content:center">
          <button class="secondary" id="lib-more" style="display:none">加载更多</button>
        </div>
      </div>

      <!-- ── 问答 ── -->
      <div class="mode-panel" id="panel-ask" role="tabpanel">
        <div class="card">
          <div class="field">
            <label for="ask-q">问你的记忆</label>
            <textarea id="ask-q" style="min-height:70px" placeholder="例如：我最近在忙哪些项目？我的开发环境有什么偏好？"></textarea>
          </div>
          <div class="row" style="margin-top:10px">
            <button id="btn-ask">提问</button>
            <span style="color:var(--tx3);font-size:12px" id="ask-meta"></span>
          </div>
          <div id="ask-result"></div>
        </div>
      </div>

      <!-- ── 历史检索 ── -->
      <div class="mode-panel" id="panel-history" role="tabpanel">
        <div class="card">
          <div class="field">
            <label for="his-q">全文检索（子串匹配，扫描全部记忆原文）</label>
            <input id="his-q" placeholder="输入要找的原文片段，如某个项目名、命令、路径…">
          </div>
          <p class="hint" style="margin-top:8px" id="his-meta"></p>
        </div>
        <div id="history-body" style="margin-top:13px"></div>
      </div>
    </section>

    <!-- ═════════ 应用 ═════════ -->
    <section class="view" id="view-sources">
      <div class="page-head">
        <div class="grow">
          <p class="eyebrow">应用</p>
          <h1>接入记忆的宿主工具</h1>
          <p class="desc">仅处理已授权范围 —— 各工具通过本机 MCP / REST 读写同一份记忆库。</p>
        </div>
      </div>
      <div class="stat-grid" id="src-stats"></div>
      <div class="src-grid" id="src-grid"></div>
      <div class="card" style="margin-top:13px">
        <h2>接入方式</h2>
        <p class="hint">以下宿主已配置自动召回；未列出的工具按 <code>docs/multi_platform.md</code> 三步接入。</p>
        <div id="how-list"></div>
      </div>
    </section>

    <!-- ═════════ 设置 ═════════ -->
    <section class="view" id="view-settings">
      <div class="page-head">
        <div class="grow">
          <p class="eyebrow">设置</p>
          <h1 id="settings-title">设置</h1>
          <p class="desc" id="settings-desc">模型与运行时配置（只读展示，改动请编辑 .env 后重启）。</p>
        </div>
        <button class="secondary" id="btn-back-settings" style="display:none">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/></svg>
          返回设置</button>
      </div>

      <div id="settings-main">
        <div class="card">
          <h2>记忆模型</h2>
          <p class="hint">写入抽取（LLM）与向量化（Embedding）两组服务。</p>
          <div class="stat-grid" style="margin-bottom:8px">
            <div class="card stat" id="cfg-llm"></div>
            <div class="card stat" id="cfg-emb"></div>
            <div class="card stat" id="cfg-run"></div>
          </div>
          <div class="row">
            <button id="btn-probe">测试连接</button>
            <button class="secondary" id="btn-diag">帮助与诊断</button>
          </div>
          <div id="probe-out"></div>
        </div>
        <div class="card">
          <h2>快捷入口</h2>
          <p class="hint">控制台与本机端点。</p>
          <div class="kv">
            <dt>REST API</dt><dd>http://127.0.0.1:19527/api/v1/*</dd>
            <dt>MCP 端点</dt><dd>http://127.0.0.1:19528/mcp</dd>
            <dt>数据目录</dt><dd id="cfg-datadir">~/.hy_memory</dd>
            <dt>启动脚本</dt><dd>D:\项目\hy-memory\start_memory.bat</dd>
          </div>
        </div>
      </div>

      <div id="settings-health" style="display:none">
        <div class="card">
          <h2>运行状况</h2>
          <div class="stat-grid" id="health-stats"></div>
        </div>
        <div class="card">
          <h2>指标（最近 60 分钟）</h2>
          <div id="health-metrics"></div>
        </div>
        <div class="card">
          <h2>原始状态</h2>
          <details class="json"><summary>healthz / health / info / metrics 原始 JSON</summary><pre id="health-raw">…</pre></details>
        </div>
      </div>
    </section>
  </main>

  <footer class="footer">
    <span class="lock">
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
      记忆保存在本机
    </span>
    <span>·</span>
    <span id="footer-info">hy-memory runtime</span>
    <span style="margin-left:auto">仅本机监听 · 使用云模型整理时相关内容会发送给对应服务</span>
  </footer>
</div>
<div class="toast" id="toast"></div>

<script>
"use strict";
/* ═════════════ 基础 ═════════════ */
const $ = (id) => document.getElementById(id);
const state = {
  user: localStorage.getItem("hy_uid") || "user_1",
  view: "memory", mode: "map",
  mems: [],            // 全量记忆缓存（list 拉取）
  axis: "agent", groupKey: "", mapQ: "",
  libShown: 80,
};
const AGENT_NAMES = {
  codex: "Codex", zcode: "ZCode", doubao: "豆包", qoder: "Qoder",
  workbuddy: "WorkBuddy", claude: "Claude Code", openclaw: "OpenClaw",
  default_agent: "默认助手", unknown: "未知来源",
};
const LAYER_NAMES = {
  l0_basic_info: "基础信息", l1_raw: "原始对话", l2_fact: "事实",
  l3_summary: "会话摘要", l4_identity: "身份", l5_knowledge: "知识",
  l6_schema: "心智图式", l7_intention: "前瞻意图",
};
const HOW = [
  ["Codex", "MCP（~/.codex/config.toml）+ AGENTS.md 自动召回", "#4e6478"],
  ["Qoder", "MCP（~/.qoder/mcp.json）+ AGENTS.md 规则", "#7d93a6"],
  ["WorkBuddy", "MCP（~/.workbuddy/mcp.json）", "#a88140"],
  ["豆包", "用户技能（agent_mode .user_skills）", "#2f6b57"],
  ["ZCode", "用户技能（~/.agents/skills）", "#5d7488"],
  ["Claude Code", "UserPromptSubmit hook 每条消息自动注入", "#96453e"],
];
const PALETTE = ["#4e6478","#7d93a6","#a88140","#2f6b57","#8a6d9b","#b0713f","#5d7488","#96453e"];

async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json; charset=utf-8" },
    ...opts, body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  let data = null; try { data = await res.json(); } catch {}
  if (!res.ok) {
    const msg = data && (data.error?.message || data.error) || res.statusText;
    throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
  }
  return data;
}
let toastTimer;
function toast(msg, err = false) {
  const el = $("toast"); el.textContent = msg;
  el.className = "toast show" + (err ? " err" : "");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (el.className = "toast"), err ? 6000 : 2600);
}
function esc(s) { return String(s ?? "").replace(/[&<>"']/g, c => ({ "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;" }[c])); }
function escRe(s) { return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); }
function hi(text, q) { if (!q) return esc(text); return esc(text).replace(new RegExp(escRe(esc(q)), "gi"), m => `<mark>${m}</mark>`); }
const fmtTime = (ts) => { if (!ts) return ""; const n = Number(ts); if (!n) return "";
  const d = n > 1e12 ? new Date(n) : new Date(n * 1000);
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")} ${String(d.getHours()).padStart(2,"0")}:${String(d.getMinutes()).padStart(2,"0")}`; };
const agentName = (a) => AGENT_NAMES[a] || a || "未知来源";
const layerName = (l) => LAYER_NAMES[l] || l || "";
function busy(btn, on, label) {
  if (on) { btn.dataset.t = btn.innerHTML; btn.disabled = true; btn.innerHTML = label + ' <span class="spin">◌</span>'; }
  else { btn.disabled = false; btn.innerHTML = btn.dataset.t || label; }
}

/* ═════════════ 导航 ═════════════ */
function goto(view) {
  state.view = view;
  document.querySelectorAll(".rail-btn").forEach(b => b.classList.toggle("active", b.dataset.view === view));
  document.querySelectorAll(".view").forEach(v => v.classList.toggle("on", v.id === "view-" + view));
  if (view === "sources") loadSources();
  if (view === "settings") loadSettings();
  if (view === "memory") ensureMems();
}
document.querySelectorAll(".rail-btn").forEach(b => b.addEventListener("click", () => goto(b.dataset.view)));

/* 模式页签（含左右键切换，同桌面版 tablist 行为） */
function setMode(mode) {
  state.mode = mode;
  document.querySelectorAll("#mode-tabs [role=tab]").forEach(t => t.setAttribute("aria-selected", t.dataset.mode === mode));
  document.querySelectorAll(".mode-panel").forEach(p => p.classList.toggle("on", p.id === "panel-" + mode));
  if (mode === "map") drawMap();
  if (mode === "library") renderLibrary();
}
document.querySelectorAll("#mode-tabs [role=tab]").forEach(t => t.addEventListener("click", () => setMode(t.dataset.mode)));
$("mode-tabs").addEventListener("keydown", (e) => {
  const order = ["map","library","ask","history"];
  const cur = order.indexOf(state.mode); if (cur < 0) return;
  let next = null;
  if (e.key === "ArrowRight") next = order[(cur + 1) % order.length];
  if (e.key === "ArrowLeft") next = order[(cur - 1 + order.length) % order.length];
  if (e.key === "Home") next = order[0];
  if (e.key === "End") next = order[order.length - 1];
  if (!next) return;
  e.preventDefault(); setMode(next);
  document.querySelector(`#mode-tabs [data-mode="${next}"]`).focus();
});
$("uid").addEventListener("change", async (e) => {
  state.user = e.target.value.trim() || "user_1";
  localStorage.setItem("hy_uid", state.user);
  state.mems = []; state.groupKey = "";
  await ensureMems(true);
});

/* ═════════════ 记忆数据 ═════════════ */
async function ensureMems(force = false) {
  if (state.mems.length && !force) { drawMap(); renderLibrary(); return; }
  try {
    const r = await api("/api/v1/list", { method: "POST", body: { user_id: state.user, limit: 2000 } });
    state.mems = (r?.vdb?.memories || []).slice();
    fillSelects();
    drawMap(); renderLibrary();
  } catch (e) {
    toast("加载记忆失败：" + e.message, true);
    state.mems = [];
  }
}
function fillSelects() {
  const agents = [...new Set(state.mems.map(m => m.agent_id).filter(Boolean))].sort();
  const layers = [...new Set(state.mems.map(m => m.layer).filter(Boolean))].sort();
  const sa = $("lib-agent"), sl = $("lib-layer");
  sa.innerHTML = '<option value="">全部来源</option>' + agents.map(a => `<option value="${esc(a)}">${esc(agentName(a))}</option>`).join("");
  sl.innerHTML = '<option value="">全部层级</option>' + layers.map(l => `<option value="${esc(l)}">${esc(layerName(l))}</option>`).join("");
}
function memCard(m, q = "") {
  const id = m.memory_id || m.node_id || m.id || "";
  const score = typeof m.score === "number" ? m.score : null;
  const tags = (m.tags || []).slice(0, 6).map(t => `<span class="tag">${hi(t, q)}</span>`).join("");
  return `<div class="mem">
    <div class="top">
      ${m.layer ? `<span class="tag layer">${esc(layerName(m.layer))}</span>` : ""}
      ${m.agent_id ? `<span class="tag src">${esc(agentName(m.agent_id))}</span>` : ""}
      ${m.status && m.status !== "active" ? `<span class="tag st-${esc(m.status)}">${esc(m.status)}</span>` : ""}
      ${score !== null ? `<span class="score">${score.toFixed(3)}</span>` : ""}
      ${tags}
      <span class="meta">${esc(fmtTime(m.gmt_created || m.memory_at))}
        <button class="quiet small" data-edit="${esc(id)}" title="编辑内容">✎</button>
        <button class="quiet small" data-del="${esc(id)}" title="删除">✕</button>
      </span>
    </div>
    <div class="body">${hi(m.content || "", q)}</div>
    ${score !== null ? `<div class="scorebar"><i style="width:${Math.max(4, Math.min(100, score * 100))}%"></i></div>` : ""}
    ${id ? `<div class="mid">${esc(id)}</div>` : ""}
  </div>`;
}
document.body.addEventListener("click", async (ev) => {
  const t = ev.target;
  const del = t?.dataset?.del;
  if (del) {
    if (!confirm("删除这条记忆？不可恢复。")) return;
    try { await api("/api/v1/memories/" + encodeURIComponent(del), { method: "DELETE" });
      toast("已删除"); await ensureMems(true); } catch (e) { toast("删除失败：" + e.message, true); }
    return;
  }
  const edit = t?.dataset?.edit;
  if (edit) {
    const m = state.mems.find(x => (x.memory_id || x.node_id) === edit);
    const next = prompt("编辑记忆内容：", m?.content || "");
    if (next === null || !next.trim() || next === m?.content) return;
    try { await api("/api/v1/memories/" + encodeURIComponent(edit), { method: "PUT", body: { content: next } });
      toast("已更新"); await ensureMems(true); } catch (e) { toast("更新失败：" + e.message, true); }
  }
});

/* ═════════════ 工作台（图谱）═════════════ */
const canvas = $("map-canvas"), tip = $("map-tip");
let nodes = [];  // {x,y,r,fill,label,mem,hub,group}
function mapData() {
  const q = state.mapQ.trim().toLowerCase();
  let items = state.mems;
  if (q) items = items.filter(m => (m.content || "").toLowerCase().includes(q) || (m.tags || []).some(t => String(t).toLowerCase().includes(q)));
  const keyOf = (m) => state.axis === "agent" ? (m.agent_id || "unknown")
    : state.axis === "layer" ? (m.layer || "unknown") : (m.status || "unknown");
  const nameOf = (k) => state.axis === "agent" ? agentName(k)
    : state.axis === "layer" ? layerName(k) : k;
  const groups = {};
  for (const m of items) { const k = keyOf(m); (groups[k] = groups[k] || []).push(m); }
  return { items, groups, nameOf };
}
function drawMap() {
  const wrap = canvas.parentElement;
  const W = wrap.clientWidth, H = canvas.clientHeight || 520;
  const dpr = window.devicePixelRatio || 1;
  canvas.width = W * dpr; canvas.height = H * dpr;
  canvas.style.width = W + "px";
  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, W, H);
  nodes = [];

  const { items, groups, nameOf } = mapData();
  const keys = Object.keys(groups).sort((a, b) => groups[b].length - groups[a].length).slice(0, 12);
  const shown = keys.reduce((n, k) => n + groups[k].length, 0);
  $("map-count").textContent = items.length ? `${shown} 条记忆 · ${keys.length} 组` : "";

  // 组分片
  const chips = [`<button class="${!state.groupKey ? "selected" : ""}" data-g="">全部 (${items.length})</button>`]
    .concat(keys.map((k, i) => `<button class="${state.groupKey === k ? "selected" : ""}" data-g="${esc(k)}">${esc(nameOf(k))} (${groups[k].length})</button>`));
  $("map-groups").innerHTML = chips.join("");
  $("map-legend").innerHTML = keys.map((k, i) =>
    `<span><i style="background:${PALETTE[i % PALETTE.length]}"></i>${esc(nameOf(k))} · ${groups[k].length}</span>`).join("");

  const cx = W / 2, cy = H / 2;
  const R = Math.min(W, H) * (keys.length > 1 ? 0.34 : 0);
  const t0 = performance.now();
  const draw = () => {
    ctx.clearRect(0, 0, W, H);
    const spin = (performance.now() - t0) / 100000;
    keys.forEach((k, gi) => {
      const members = groups[k].slice().sort((a, b) => (b.gmt_created||0) - (a.gmt_created||0)).slice(0, 60);
      const ang = keys.length > 1 ? (gi / keys.length) * Math.PI * 2 - Math.PI / 2 + spin : 0;
      const hx = cx + Math.cos(ang) * R, hy = cy + Math.sin(ang) * R;
      const fill = PALETTE[gi % PALETTE.length];
      // 轨道 + 成员
      const orbit = 26 + Math.min(64, members.length) * 1.15;
      members.forEach((m, i) => {
        const a2 = (i / Math.max(6, members.length)) * Math.PI * 2 + spin * 3 + gi;
        const rr = orbit + (i % 3) * 11;
        const x = hx + Math.cos(a2) * rr, y = hy + Math.sin(a2) * rr;
        ctx.strokeStyle = "rgba(78,100,120,.13)"; ctx.lineWidth = .7;
        ctx.beginPath(); ctx.moveTo(hx, hy); ctx.lineTo(x, y); ctx.stroke();
        ctx.fillStyle = fill; ctx.globalAlpha = m.status && m.status !== "active" ? .45 : .9;
        ctx.beginPath(); ctx.arc(x, y, 4.2, 0, 7); ctx.fill(); ctx.globalAlpha = 1;
        nodes.push({ x, y, r: 6, fill, label: (m.content || "").slice(0, 60), mem: m, group: k });
      });
      // 组中心
      const hubR = Math.max(15, Math.min(26, 13 + Math.sqrt(members.length) * 2.2));
      ctx.fillStyle = fill; ctx.beginPath(); ctx.arc(hx, hy, hubR, 0, 7); ctx.fill();
      ctx.strokeStyle = "rgba(255,255,255,.85)"; ctx.lineWidth = 2; ctx.stroke();
      nodes.push({ x: hx, y: hy, r: hubR, fill, label: `${nameOf(k)} · ${groups[k].length}`, hub: true, group: k, groupKey: k });
      ctx.fillStyle = "#fff"; ctx.font = "600 10.5px system-ui"; ctx.textAlign = "center"; ctx.textBaseline = "middle";
      ctx.fillText(String(groups[k].length), hx, hy);
      ctx.fillStyle = "rgba(38,42,46,.75)"; ctx.font = "600 11.5px system-ui";
      ctx.fillText(nameOf(k), hx, hy + hubR + 13);
    });
  };
  draw();
  canvas._redraw = draw;
}
window.addEventListener("resize", () => { if (state.view === "memory" && state.mode === "map") drawMap(); });
$("axis-seg").addEventListener("click", (e) => {
  const b = e.target.closest("button[data-axis]"); if (!b) return;
  state.axis = b.dataset.axis; state.groupKey = "";
  document.querySelectorAll("#axis-seg button").forEach(x => x.setAttribute("aria-pressed", x === b ? "true" : "false"));
  drawMap();
});
$("map-groups").addEventListener("click", (e) => {
  const b = e.target.closest("button[data-g]"); if (!b) return;
  state.groupKey = b.dataset.g;
  drawMap();
  if (b.dataset.g) { const n = nodes.find(n => n.hub && n.groupKey === b.dataset.g); if (n) openInspector(n); }
});
$("map-q").addEventListener("input", (e) => { state.mapQ = e.target.value; clearTimeout(window._mq); window._mq = setTimeout(drawMap, 250); });
$("map-reload").addEventListener("click", async () => { await ensureMems(true); toast("已刷新"); });

function nodeAt(mx, my) {
  let best = null, bd = 1e9;
  for (const n of nodes) { const d = (n.x - mx) ** 2 + (n.y - my) ** 2; if (d < bd && d < (n.r + 6) ** 2) { bd = d; best = n; } }
  return best;
}
canvas.addEventListener("mousemove", (e) => {
  const r = canvas.getBoundingClientRect();
  const n = nodeAt(e.clientX - r.left, e.clientY - r.top);
  if (n) {
    canvas.style.cursor = "pointer";
    tip.style.display = "block";
    tip.style.left = Math.min(e.clientX - r.left + 14, r.width - 290) + "px";
    tip.style.top = (e.clientY - r.top + 10) + "px";
    tip.textContent = n.label;
  } else { canvas.style.cursor = "grab"; tip.style.display = "none"; }
});
canvas.addEventListener("mouseleave", () => (tip.style.display = "none"));
canvas.addEventListener("click", (e) => {
  const r = canvas.getBoundingClientRect();
  const n = nodeAt(e.clientX - r.left, e.clientY - r.top);
  if (n) openInspector(n);
});
function openInspector(n) {
  const box = $("map-inspector");
  if (n.hub) {
    const members = state.mems.filter(m => (state.axis === "agent" ? (m.agent_id || "unknown")
      : state.axis === "layer" ? (m.layer || "unknown") : (m.status || "unknown")) === n.groupKey)
      .sort((a, b) => (b.gmt_created||0) - (a.gmt_created||0)).slice(0, 8);
    box.innerHTML = `<button class="quiet small close" onclick="document.getElementById('map-inspector').classList.remove('on')">✕</button>
      <h3>${esc(n.label)}</h3>
      <p class="hint">该组最近写入：</p>
      ${members.map(m => `<div class="cite" style="font-size:12.5px">${esc((m.content||"").slice(0,120))}<div style="color:var(--tx3);font-size:11px;margin-top:3px">${esc(fmtTime(m.gmt_created))}</div></div>`).join("") || "<p class='hint'>（空）</p>"}`;
  } else {
    const m = n.mem;
    const related = state.mems.filter(x => x.agent_id === m.agent_id && x.memory_id !== m.memory_id)
      .sort((a, b) => (b.gmt_created||0) - (a.gmt_created||0)).slice(0, 4);
    box.innerHTML = `<button class="quiet small close" onclick="document.getElementById('map-inspector').classList.remove('on')">✕</button>
      <h3>记忆详情</h3>
      <div class="top" style="display:flex;gap:6px;flex-wrap:wrap;margin:6px 0">
        ${m.layer ? `<span class="tag layer">${esc(layerName(m.layer))}</span>` : ""}
        ${m.agent_id ? `<span class="tag src">${esc(agentName(m.agent_id))}</span>` : ""}
        ${(m.tags||[]).slice(0,5).map(t => `<span class="tag">${esc(t)}</span>`).join("")}
      </div>
      <div class="body" style="white-space:pre-wrap;font-size:13px">${esc(m.content || "")}</div>
      <div class="mid" style="margin-top:8px">${esc(m.memory_id || "")}<br>${esc(fmtTime(m.gmt_created || m.memory_at))}</div>
      <div class="row" style="margin-top:10px">
        <button class="danger small" data-del="${esc(m.memory_id || "")}">删除</button>
      </div>
      <p class="hint" style="margin:12px 0 6px">同来源的其他记忆：</p>
      ${related.map(x => `<div class="cite" style="font-size:12.5px">${esc((x.content||"").slice(0,100))}</div>`).join("") || "<p class='hint'>（无）</p>"}`;
  }
  box.classList.add("on");
}

/* ═════════════ 记忆库 ═════════════ */
function renderLibrary() {
  const q = $("lib-q").value.trim().toLowerCase();
  const ag = $("lib-agent").value, ly = $("lib-layer").value, st = $("lib-status").value;
  let items = state.mems.filter(m =>
    (!ag || m.agent_id === ag) && (!ly || m.layer === ly) && (!st || m.status === st) &&
    (!q || (m.content || "").toLowerCase().includes(q) || (m.tags || []).some(t => String(t).toLowerCase().includes(q))));
  const total = items.length;
  items = items.slice(0, state.libShown);
  $("library-body").innerHTML = total
    ? items.map(m => memCard(m, q)).join("")
    : `<div class="empty"><b>没有匹配的记忆</b>调整过滤条件，或去工作台看全景。</div>`;
  $("lib-more").style.display = total > state.libShown ? "" : "none";
}
["lib-q","lib-agent","lib-layer","lib-status"].forEach(id =>
  $(id).addEventListener("input", () => { state.libShown = 80; renderLibrary(); }));
$("lib-more").addEventListener("click", () => { state.libShown += 120; renderLibrary(); });
$("btn-del-all").addEventListener("click", async () => {
  if (!confirm(`确定清空 ${state.user} 的全部记忆？不可恢复！`)) return;
  try { const r = await api("/api/v1/delete_all", { method: "POST", body: { user_id: state.user } });
    toast("已清空" + (r?.deleted != null ? `（${r.deleted} 条）` : "")); await ensureMems(true); }
  catch (e) { toast("清空失败：" + e.message, true); }
});

/* ═════════════ 问答 ═════════════ */
$("btn-ask").addEventListener("click", async () => {
  const q = $("ask-q").value.trim();
  if (!q) { toast("请输入问题", true); return; }
  const btn = $("btn-ask"); busy(btn, true, "思考中");
  $("ask-meta").textContent = ""; $("ask-result").innerHTML = "";
  const t0 = performance.now();
  try {
    const r = await api("/api/v1/ask", { method: "POST", body: { query: q, user_id: state.user } });
    const secs = ((performance.now() - t0) / 1000).toFixed(1);
    $("ask-meta").textContent = `${secs}s · ${r.model || ""} · 引用 ${r.citations?.length || 0} 条`;
    $("ask-result").innerHTML = `
      <div class="answer">${esc(r.answer || "（模型没有返回内容）")}<span class="model">依据下方引用的记忆回答；记忆里没有的信息不会编造。</span></div>
      ${r.citations?.length ? `<div class="cites">${r.citations.map((c, i) => `
        <div class="cite"><span class="n">${i + 1}</span>${esc(c.content || "")}
        <span class="score" style="margin-left:6px">${c.score?.toFixed(3) ?? ""}</span>
        ${c.agent_id ? `<span class="tag src" style="margin-left:6px">${esc(agentName(c.agent_id))}</span>` : ""}</div>`).join("")}</div>` : ""}`;
  } catch (e) {
    $("ask-result").innerHTML = `<div class="empty" style="margin-top:12px"><b>问答失败</b>${esc(e.message)}</div>`;
    if (/api key|401|403|connection|timed? ?out/i.test(e.message)) $("env-notice").classList.add("show");
  } finally { busy(btn, false, "提问"); }
});

/* ═════════════ 历史检索 ═════════════ */
$("his-q").addEventListener("input", async (e) => {
  const q = e.target.value.trim();
  clearTimeout(window._hq);
  window._hq = setTimeout(async () => {
    if (!q) { $("history-body").innerHTML = ""; $("his-meta").textContent = ""; return; }
    if (!state.mems.length) await ensureMems(true);
    const ql = q.toLowerCase();
    const hits = state.mems.filter(m => (m.content || "").toLowerCase().includes(ql));
    $("his-meta").textContent = `在 ${state.mems.length} 条记忆中找到 ${hits.length} 条包含「${q}」`;
    $("history-body").innerHTML = hits.length
      ? hits.map(m => memCard(m, q)).join("")
      : `<div class="empty"><b>没有找到</b>换一个片段试试；记忆是抽取后的事实，原对话不一定逐字保留。</div>`;
  }, 220);
});

/* ═════════════ 应用 ═════════════ */
async function loadSources() {
  try {
    const [stats, health, metrics] = await Promise.all([
      api("/api/v1/stats?user_id=" + encodeURIComponent(state.user)).catch(() => null),
      api("/healthz").catch(() => null),
      api("/api/v1/metrics?minutes=60").catch(() => null),
    ]);
    const up = metrics ? Math.round(metrics.uptime_seconds / 60) : null;
    $("src-stats").innerHTML = `
      <div class="card stat"><div class="k">记忆总数</div><div class="v">${stats?.total ?? "—"}</div><div class="s">user_id = ${esc(state.user)}</div></div>
      <div class="card stat"><div class="k">写入来源</div><div class="v">${stats ? Object.keys(stats.by_agent || {}).length : "—"}</div><div class="s">个宿主工具</div></div>
      <div class="card stat"><div class="k">服务运行</div><div class="v">${up != null ? up + " 分钟" : "—"}</div><div class="s">${health?.status === "ok" ? "健康检查通过" : "状态未知"}</div></div>
      <div class="card stat"><div class="k">最近写入</div><div class="v" style="font-size:15px">${stats?.last_write ? esc(fmtTime(stats.last_write)) : "—"}</div><div class="s">任意来源</div></div>`;
    const byAgent = stats?.by_agent || {};
    const rows = Object.entries(byAgent).sort((a, b) => b[1] - a[1]);
    const lastOf = (ag) => {
      const m = state.mems.filter(x => x.agent_id === ag).sort((a, b) => (b.gmt_created||0)-(a.gmt_created||0))[0];
      return m ? fmtTime(m.gmt_created || m.memory_at) : "";
    };
    if (!state.mems.length) { try { await ensureMems(true); } catch {} }
    $("src-grid").innerHTML = rows.length ? rows.map(([ag, n], i) => `
      <div class="card src-card">
        <div class="head">
          <span class="src-ico" style="background:${PALETTE[i % PALETTE.length]}">${esc(agentName(ag).slice(0,1))}</span>
          <div><div class="name">${esc(agentName(ag))}</div><div class="how">${esc(ag)}</div></div>
        </div>
        <div class="nums">
          <div><b>${n}</b><span>条记忆</span></div>
          <div><b style="font-size:12px;font-weight:500;line-height:2.1">${esc(lastOf(ag) || "—")}</b><span>最近写入</span></div>
        </div>
        <button class="secondary small" data-src-view="${esc(ag)}">查看记忆</button>
      </div>`).join("")
      : `<div class="empty"><b>还没有任何来源写入</b>从任一接入工具说「记住……」即可产生记忆。</div>`;
    $("how-list").innerHTML = HOW.map(([n, how, c]) => `
      <div style="display:flex;align-items:center;gap:10px;padding:7px 0;border-bottom:1px solid var(--panel)">
        <i style="width:9px;height:9px;border-radius:50%;background:${c};display:inline-block"></i>
        <b style="width:110px">${esc(n)}</b><span style="color:var(--tx2);font-size:12.5px">${esc(how)}</span>
        <span class="tag" style="margin-left:auto">${byAgent[(Object.keys(AGENT_NAMES).find(k => AGENT_NAMES[k] === n) || "")] != null ? "已产生记忆" : "已配置"}</span>
      </div>`).join("");
  } catch (e) { toast("加载应用页失败：" + e.message, true); }
}
document.body.addEventListener("click", (e) => {
  const ag = e.target?.dataset?.srcView;
  if (ag) { goto("memory"); setMode("library"); $("lib-agent").value = ag; renderLibrary(); }
});

/* ═════════════ 设置 / 诊断 ═════════════ */
async function loadSettings() {
  try {
    const cfg = await api("/api/v1/config");
    $("cfg-llm").innerHTML = `<div class="k">整理模型（LLM）</div><div class="v" style="font-size:15px">${esc(cfg.llm?.model || "未配置")}</div><div class="s">${esc(cfg.llm?.base_url || "")} ${cfg.llm?.key_set ? "· key 已配置" : "· 无 key"}</div>`;
    $("cfg-emb").innerHTML = `<div class="k">向量化（Embedding）</div><div class="v" style="font-size:15px">${esc(cfg.embedder?.model || "未配置")}</div><div class="s">${esc(cfg.embedder?.base_url || "")} · ${cfg.embedder?.dims || "?"} 维</div>`;
    $("cfg-run").innerHTML = `<div class="k">运行模式</div><div class="v" style="font-size:15px">${esc(cfg.mode || "pro")}</div><div class="s">向量库 ${esc(cfg.vector_store || "chroma")}</div>`;
    $("cfg-datadir").textContent = cfg.data_dir || "~/.hy_memory";
  } catch (e) { toast("读取配置失败：" + e.message, true); }
}
$("btn-probe").addEventListener("click", async () => {
  const btn = $("btn-probe"); busy(btn, true, "测试中");
  try {
    const cfg = await api("/api/v1/config?probe=1");
    const p = cfg.probes || {};
    const line = (name, r) => `<div class="probe-line">
      <span class="pill ${r?.ok ? "ok" : "bad"}" style="margin:0"><span class="dot"></span>${r?.ok ? "正常" : "失败"}</span>
      <b>${name}</b><span style="color:var(--tx3)">${r?.ok ? (r.dims ? r.dims + " 维" : "调用成功") : esc(r?.error || "")}</span></div>`;
    $("probe-out").innerHTML = line("Embedding", p.embedder) + line("LLM", p.llm);
  } catch (e) { $("probe-out").innerHTML = `<div class="probe-line"><span class="pill bad" style="margin:0"><span class="dot"></span>失败</span><b>探测</b><span style="color:var(--tx3)">${esc(e.message)}</span></div>`; }
  finally { busy(btn, false, "测试连接"); }
});
$("btn-diag").addEventListener("click", async () => {
  $("settings-main").style.display = "none";
  $("settings-health").style.display = "";
  $("btn-back-settings").style.display = "";
  $("settings-title").textContent = "帮助与诊断";
  $("settings-desc").textContent = "运行状况、指标与原始状态。";
  try {
    const [hz, hv, info, met] = await Promise.all([
      api("/healthz"), api("/health"), api("/info"), api("/api/v1/metrics?minutes=60"),
    ]);
    const up = met.uptime_seconds ? (met.uptime_seconds > 5400 ? (met.uptime_seconds/3600).toFixed(1) + " 小时" : Math.round(met.uptime_seconds/60) + " 分钟") : "—";
    $("health-stats").innerHTML = `
      <div class="card stat"><div class="k">healthz</div><div class="v" style="color:var(--ok)">${esc(hz.status)}</div><div class="s">静态健康检查</div></div>
      <div class="card stat"><div class="k">事件循环</div><div class="v" style="color:${hv.status === "ok" ? "var(--ok)" : "var(--dg)"}">${esc(hv.status || "?")}</div><div class="s">活性探测</div></div>
      <div class="card stat"><div class="k">版本</div><div class="v" style="font-size:16px">${esc(info.version || "")}</div><div class="s">${esc(info.status || "")}</div></div>
      <div class="card stat"><div class="k">已运行</div><div class="v">${up}</div><div class="s">本轮进程</div></div>`;
    const req = met.requests || {}, tp = met.throughput || {};
    $("health-metrics").innerHTML = `
      <div class="kv">
        <dt>窗口内请求</dt><dd>${req.total ?? 0}（完成 ${req.completed ?? 0} / 失败 ${req.failed ?? 0}）</dd>
        <dt>Sys1 吞吐（60s）</dt><dd>${tp.sys1_completed_last_60s ?? 0}</dd>
        <dt>Sys2 吞吐（60s）</dt><dd>${tp.sys2_completed_last_60s ?? 0}</dd>
        <dt>统计起点</dt><dd>${esc(met.since || "")}</dd>
      </div>`;
    $("health-raw").textContent = JSON.stringify({ healthz: hz, health: hv, info, metrics: met }, null, 2);
  } catch (e) { $("health-stats").innerHTML = `<div class="empty"><b>诊断加载失败</b>${esc(e.message)}</div>`; }
});
$("btn-back-settings").addEventListener("click", () => {
  $("settings-health").style.display = "none";
  $("settings-main").style.display = "";
  $("btn-back-settings").style.display = "none";
  $("settings-title").textContent = "设置";
  $("settings-desc").textContent = "模型与运行时配置（只读展示，改动请编辑 .env 后重启）。";
});

/* ═════════════ 启动 ═════════════ */
(async function init() {
  $("uid").value = state.user;
  try {
    const [h, info] = await Promise.all([api("/healthz"), api("/info")]);
    const ok = h?.status === "ok";
    $("status-pill").className = "pill " + (ok ? "ok" : "bad");
    $("status-text").textContent = ok ? "运行中 · " + (info.version || "") : "异常";
    $("footer-info").textContent = `hy-memory ${info.version || ""} runtime`;
  } catch {
    $("status-pill").className = "pill bad";
    $("status-text").textContent = "服务未连接";
  }
  goto("memory");
  setMode("map");
})();
</script>
</body>
</html>
"""
