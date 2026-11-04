/** Register `capture` on the hosts whose one-click install can own a hook file.
 *
 * The command is the packaged core binary. It reads the hook's JSON on stdin
 * and writes visible text into Evidence. Stdout stays empty, so the host does
 * not treat the capture as another instruction.
 *
 * WorkBuddy's command lives in its plugin tree. Hermes and OpenClaw deliver
 * the turn through a single memory-provider slot; those are not written here,
 * because taking the slot replaces whatever plugin is already there.
 */

import path from "node:path";

import type { RecallHostLayout, RecallRuntime } from "./recall-installer.js";
import { sameShellCommand, shellWords } from "./shell-words.js";

/** A place on the host that may still hold something of ours, which nothing
 * here can settle: a person has to look. */
export interface RemovalFinding {
  path: string;
  where: string;
}

export interface CaptureFile {
  path: string;
  before: string | null;
  after: string;
  /** The exact command string written into the host file, used to remove it. */
  command: string;
  kind: "merge" | "owned";
}

const COMMAND_HOSTS: Record<string, readonly string[]> = {
  cursor: ["beforeSubmitPrompt", "afterAgentResponse"],
  "claude-code": ["UserPromptSubmit", "Stop", "SubagentStop"],
  codex: ["UserPromptSubmit", "Stop"],
  qoder: ["UserPromptSubmit", "Stop", "SessionStart"],
  zcode: ["UserPromptSubmit", "Stop", "SessionStart"],
};

/** Hosts whose hook file is a JSON config shared with their MCP entry, and
 * whose hook command is an owned runner rather than a shell one-liner. */
export function isCliHookHost(hostId: string): boolean {
  return hostId === "qoder" || hostId === "zcode";
}

export function cliHookRunnerName(hostId: string): string {
  return `${hostId}-hook.cjs`;
}

export function resolveCaptureCommand(runtime: RecallRuntime): string {
  if (runtime.captureCommand !== undefined && runtime.captureCommand !== "") {
    return runtime.captureCommand;
  }
  const installRoot = path.resolve(path.dirname(runtime.mcpEntryPath), "..");
  const executable =
    process.platform === "win32" ? "one-memory.exe" : "one-memory";
  return path.join(installRoot, "core", executable);
}

export function quoteCaptureCommand(command: string): string {
  return `'${command.replaceAll("'", `'\\''`)}'`;
}

/** Run a hook without letting its failure become the host's error.
 *
 * Cursor and WorkBuddy treat a non-zero hook as a failed send and show the
 * program's own text. The installed core can reject `capture` and `boundary`,
 * and the MCP launcher is not a CLI at all. Either one used to stop the turn.
 * A capture stays silent. A boundary that cannot answer prints nothing: a host
 * that finds no `hookSpecificOutput` reads raw stdout as context, so even
 * `{"continue": true}` would reach the model as text.
 */
export function failOpenHookCommand(
  binary: string,
  args: string,
  mode: "silent" | "context",
  dataDir?: string,
): string {
  const quoted = quoteCaptureCommand(binary);
  const prefix =
    dataDir !== undefined && dataDir !== ""
      ? `ONE_MEMORY_DATA_DIR=${quoteCaptureCommand(dataDir)} `
      : "";
  const invocation = `${prefix}${quoted} ${args}`;
  const script =
    mode === "silent"
      ? `${invocation} >/dev/null 2>&1; exit 0`
      : `out=$(${invocation} 2>/dev/null); status=$?; if [ "$status" -eq 0 ] && [ -n "$out" ]; then printf '%s\\n' "$out"; fi; exit 0`;
  return `sh -c ${quoteCaptureCommand(script)}`;
}

export async function planCaptureFiles(
  layout: RecallHostLayout,
  runtime: RecallRuntime,
  readFile: (target: string) => Promise<string | null>,
): Promise<CaptureFile[]> {
  if (isCliHookHost(layout.hostId)) {
    return planCliHooks(layout, runtime, readFile);
  }
  const sourceId = layout.hostId;
  const command = captureCommandFor(layout, runtime);
  const filePath = captureFilePath(layout);
  if (filePath !== null && sourceId in COMMAND_HOSTS) {
    const before = await readFile(filePath);
    return [
      {
        path: filePath,
        before,
        after: mergeCommandHooks(
          before,
          sourceId,
          command,
          COMMAND_HOSTS[sourceId],
        ),
        command,
        kind: "merge",
      },
    ];
  }
  if (filePath !== null && sourceId === "pi") {
    const command = resolveCaptureCommand(runtime);
    return [
      {
        path: filePath,
        before: await readFile(filePath),
        after: piExtension(command, runtime.dataDir),
        command,
        kind: "owned",
      },
    ];
  }
  if (filePath !== null && sourceId === "opencode") {
    const command = resolveCaptureCommand(runtime);
    return [
      {
        path: filePath,
        before: await readFile(filePath),
        after: openCodePlugin(command, runtime.dataDir),
        command,
        kind: "owned",
      },
    ];
  }
  return [];
}

export function captureFilePath(layout: RecallHostLayout): string | null {
  const root = layout.containmentRoot;
  if (layout.hostId === "claude-code") return path.join(root, "settings.json");
  if (layout.hostId === "qoder") return path.join(root, "settings.json");
  if (layout.hostId === "zcode") return path.join(root, "cli", "config.json");
  if (layout.hostId in COMMAND_HOSTS) return path.join(root, "hooks.json");
  if (layout.hostId === "pi")
    return path.join(root, "extensions", "one-memory-capture.js");
  if (layout.hostId === "opencode")
    return path.join(root, "plugin", "one-memory-capture.js");
  return null;
}

/** The hook command an install from this runtime writes for this host. */
export function captureCommandFor(
  layout: RecallHostLayout,
  runtime: RecallRuntime,
): string {
  if (layout.hostId === "qoder" || layout.hostId === "zcode")
    return hookCommandIdentity(cliHook(layout, runtime));
  return failOpenHookCommand(
    resolveCaptureCommand(runtime),
    `capture ${layout.hostId}`,
    "silent",
    runtime.dataDir,
  );
}

export const UNPARSEABLE_HOOKS = "不是合法的 JSON，无法确认其中的采集命令";
export const UNREADABLE = "无法读取";

/** What a host's capture file says about us, read the way the host reads it.
 * `ours` when it runs `expected` however spelled. A command that names our
 * capture but is not `expected`, or a file that cannot be read, is a finding:
 * it is neither proof of absence nor something safe to remove. */
export async function inspectCapture(
  layout: RecallHostLayout,
  expected: string,
  readFile: (target: string) => Promise<string | null>,
): Promise<{ ours: boolean; findings: RemovalFinding[] }> {
  const filePath = captureFilePath(layout);
  if (filePath === null) return { ours: false, findings: [] };
  let raw: string | null;
  try {
    raw = await readFile(filePath);
  } catch {
    return { ours: false, findings: [{ path: filePath, where: UNREADABLE }] };
  }
  if (raw === null) return { ours: false, findings: [] };
  if (!(layout.hostId in COMMAND_HOSTS)) return { ours: true, findings: [] };
  let document: unknown;
  try {
    document = JSON.parse(raw);
  } catch {
    return {
      ours: false,
      findings: [{ path: filePath, where: UNPARSEABLE_HOOKS }],
    };
  }
  let ours = false;
  const findings: RemovalFinding[] = [];
  for (const { where, command } of hookCommands(document)) {
    if (sameHookCommand(command, expected)) ours = true;
    else if (namesCapture(command, layout.hostId))
      findings.push({ path: filePath, where });
  }
  if (isCliHookHost(layout.hostId) && ours) {
    const hooks = (document as { hooks?: Record<string, unknown> }).hooks ?? {};
    for (const event of COMMAND_HOSTS[layout.hostId]!) {
      const pair = eventArrayPairs(hooks).find(
        ([name]) => name === event || name === `events.${event}`,
      );
      if (
        !pair ||
        !hookCommands({ hooks: { [event]: pair[1] } }).some(({ command }) =>
          sameHookCommand(command, expected),
        )
      ) {
        findings.push({
          path: filePath,
          where: `hooks.${event}: MemHub hook missing or changed`,
        });
      }
    }
  }
  return { ours, findings };
}

/** Commands still naming our capture in a hook file uninstall has already
 * stripped of the recorded one. */
export function captureLeftovers(
  raw: string,
  hostId: string,
  filePath: string,
): RemovalFinding[] {
  return hookCommands(JSON.parse(raw) as unknown)
    .filter(({ command }) => namesCapture(command, hostId))
    .map(({ where }) => ({ path: filePath, where }));
}

export function namesCapture(command: string, hostId: string): boolean {
  if (command.startsWith(HOOK_IDENTITY_PREFIX)) {
    try {
      const entry = JSON.parse(command.slice(HOOK_IDENTITY_PREFIX.length));
      return Array.isArray(entry.args) && entry.args.includes("capture") && entry.args.includes(hostId);
    } catch { return false; }
  }
  const words = shellWords(command);
  if (words === null)
    return command.includes("capture") && command.includes(hostId);
  return words.some(
    (word, index) => word === "capture" && words[index + 1] === hostId,
  );
}

function hookCommands(
  document: unknown,
): Array<{ where: string; command: string }> {
  if (!document || typeof document !== "object") return [];
  const hooks = (document as { hooks?: unknown }).hooks;
  if (!hooks || typeof hooks !== "object") return [];
  const commands: Array<{ where: string; command: string }> = [];
  const visit = (entry: unknown, where: string): void => {
    if (!entry || typeof entry !== "object") return;
    const record = entry as Record<string, unknown>;
    if (typeof record.command === "string")
        commands.push({ where: `${where}.command`, command: hookCommandIdentity(record) });
    if (Array.isArray(record.hooks))
      for (const [index, hook] of record.hooks.entries())
        visit(hook, `${where}.hooks[${index}]`);
  };
  for (const [event, entries] of eventArrayPairs(
    hooks as Record<string, unknown>,
  ))
    for (const [index, entry] of entries.entries())
      visit(entry, `hooks.${event}[${index}]`);
  return commands;
}

/** Event arrays in either host shape: direct (`hooks.SessionStart`) or
 * nested under `hooks.events` (ZCode). */
function eventArrayPairs(
  hooks: Record<string, unknown>,
): Array<[string, unknown[]]> {
  const events = hooks.events;
  const container =
    events && typeof events === "object" && !Array.isArray(events)
      ? (events as Record<string, unknown>)
      : hooks;
  const pairs: Array<[string, unknown[]]> = [];
  for (const [event, entries] of Object.entries(container))
    if (Array.isArray(entries))
      pairs.push([container === hooks ? event : `events.${event}`, entries]);
  return pairs;
}

/** True when stripping our command left no hook entries. */
export function strippedCaptureIsEmpty(raw: string): boolean {
  const parsed: unknown = JSON.parse(raw);
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    return false;
  }
  const hooks = (parsed as { hooks?: unknown }).hooks;
  if (hooks === undefined) return true;
  if (typeof hooks !== "object" || hooks === null || Array.isArray(hooks)) {
    return false;
  }
  return eventArrayPairs(hooks as Record<string, unknown>).length === 0;
}

export function stripCaptureCommand(raw: string, command: string): string {
  const parsed: unknown = JSON.parse(raw);
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    return raw;
  }
  const document = parsed as Record<string, unknown>;
  const hooks = document.hooks;
  if (!hooks || typeof hooks !== "object" || Array.isArray(hooks)) return raw;
  const record = hooks as Record<string, unknown>;
  const events = record.events;
  const container =
    events && typeof events === "object" && !Array.isArray(events)
      ? (events as Record<string, unknown>)
      : record;
  for (const [event, entries] of Object.entries(container)) {
    if (!Array.isArray(entries)) continue;
    const kept = entries.flatMap((entry) => stripEntry(entry, command));
    if (kept.length === 0) delete container[event];
    else container[event] = kept;
  }
  if (container !== record && Object.keys(container).length === 0)
    delete record.events;
  if (Object.keys(record).length === 0) delete document.hooks;
  return `${JSON.stringify(document, null, 2)}\n`;
}

function stripEntry(entry: unknown, command: string): unknown[] {
  if (!entry || typeof entry !== "object") return [entry];
  const record = entry as Record<string, unknown>;
  if (
    typeof record.command === "string" &&
    sameHookCommand(hookCommandIdentity(record), command)
  )
    return [];
  if (!Array.isArray(record.hooks)) return [entry];
  const hooks = record.hooks.filter(
    (hook) =>
      !hook ||
      typeof hook !== "object" ||
      !isCommand(hookCommandIdentity(hook as Record<string, unknown>), command),
  );
  if (hooks.length === 0) return [];
  return [{ ...record, hooks }];
}

function isCommand(value: unknown, command: string): boolean {
  return typeof value === "string" && sameHookCommand(value, command);
}

const HOOK_IDENTITY_PREFIX = "memhub-hook-v1:";

function hookCommandIdentity(entry: Record<string, unknown>): string {
  if (!Array.isArray(entry.args)) return typeof entry.command === "string" ? entry.command : "";
  const env = entry.env && typeof entry.env === "object" && !Array.isArray(entry.env)
    ? Object.fromEntries(Object.entries(entry.env).sort(([a], [b]) => a.localeCompare(b))) : {};
  return HOOK_IDENTITY_PREFIX + JSON.stringify({command: entry.command, args: entry.args, env});
}

function sameHookCommand(left: string, right: string): boolean {
  if (left.startsWith(HOOK_IDENTITY_PREFIX) || right.startsWith(HOOK_IDENTITY_PREFIX)) return left === right;
  return sameShellCommand(left, right);
}

function cliHook(
  layout: RecallHostLayout,
  runtime: RecallRuntime,
): Record<string, unknown> {
  const runner = path.join(
    layout.containmentRoot,
    ".one-memory",
    cliHookRunnerName(layout.hostId),
  );
  if (layout.hostId === "zcode") {
    // ZCode's `process` hook launches the command directly, with no shell and
    // no environment overlay. A packaged runtimeCommand is the installed Node
    // binary; a development build runs the Electron executable instead, and
    // that one needs ELECTRON_RUN_AS_NODE, which only the shell form can set.
    if (!/(?:^|[\\/])electron(?:\.exe)?$/iu.test(runtime.runtimeCommand)) {
      return {
        type: "process",
        name: "memhub-zcode",
        command: runtime.runtimeCommand,
        args: [runner, "capture", "zcode"],
        timeoutMs: 5000,
      };
    }
    return {
      type: "command",
      name: "memhub-zcode",
      command:
        process.platform === "win32"
          ? `set "ELECTRON_RUN_AS_NODE=1" && "${runtime.runtimeCommand}" "${runner}" capture zcode`
          : `ELECTRON_RUN_AS_NODE=1 "${runtime.runtimeCommand}" "${runner}" capture zcode`,
      timeout: 5,
    };
  }
  return {
    type: "command",
    name: "memhub-qoder",
    command: runtime.runtimeCommand,
    args: [runner, "capture", "qoder"],
    env: { ELECTRON_RUN_AS_NODE: "1" },
    timeout: 5,
  };
}

async function planCliHooks(
  layout: RecallHostLayout,
  runtime: RecallRuntime,
  readFile: (target: string) => Promise<string | null>,
): Promise<CaptureFile[]> {
  const label = layout.hostLabel;
  if (!runtime.recallCliPath)
    throw new Error(`${label} needs recallCliPath for its hook`);
  const target = captureFilePath(layout);
  if (target === null) throw new Error(`${label} has no hook configuration file`);
  const runner = path.join(
    layout.containmentRoot,
    ".one-memory",
    cliHookRunnerName(layout.hostId),
  );
  const before = await readFile(target);
  const document = before === null ? {} : JSON.parse(before);
  if (!document || typeof document !== "object" || Array.isArray(document))
    throw new Error(`${label} configuration must be a JSON object`);
  if (
    document.hooks !== undefined &&
    (!document.hooks ||
      typeof document.hooks !== "object" ||
      Array.isArray(document.hooks))
  )
    throw new Error(`${label} hooks must be a JSON object`);
  const entry = cliHook(layout, runtime);
  const command = hookCommandIdentity(entry);
  const runnerBefore = await readFile(runner);
  if (
    runnerBefore !== null &&
    !runnerBefore.startsWith(`// Managed by MemHub: ${label}`)
  )
    throw new Error(
      `${label} hook runner already exists and is not managed by MemHub`,
    );
  const hooks = (document.hooks ?? {}) as Record<string, unknown>;
  const events =
    layout.hostId === "zcode"
      ? ((): Record<string, unknown> => {
          const existing = hooks.events;
          if (
            existing !== undefined &&
            (!existing ||
              typeof existing !== "object" ||
              Array.isArray(existing))
          )
            throw new Error(`${label} hook events must be a JSON object`);
          // Config-file hooks are off unless this is explicitly true; an
          // install that forgets it writes a hook ZCode will never run.
          hooks.enabled = true;
          return (hooks.events = { ...((existing as Record<string, unknown>) ?? {}) });
        })()
      : hooks;
  for (const event of COMMAND_HOSTS[layout.hostId]!) {
    if (events[event] !== undefined && !Array.isArray(events[event]))
      throw new Error(`${label} hook event must be an array`);
    const entries = events[event] ?? [];
    // Runtime upgrades may move node/electron. The owned runner path stays
    // fixed; replace only entries for that exact runner, preserving neighbors.
    const kept = (entries as unknown[]).flatMap((item: unknown) => {
      if (!item || typeof item !== "object") return [item];
      const group = item as Record<string, unknown>;
      if (!Array.isArray(group.hooks)) return [item];
      const keptHooks = group.hooks.filter((hook: unknown) => {
        if (!hook || typeof hook !== "object") return true;
        const own = hook as Record<string, unknown>;
        const ownRunner =
          (Array.isArray(own.args) &&
            own.args.length === 3 &&
            own.args[0] === runner &&
            own.args[1] === "capture" &&
            own.args[2] === layout.hostId) ||
          (typeof own.command === "string" && own.command.includes(runner));
        return !(own.name === `memhub-${layout.hostId}` && ownRunner);
      });
      return keptHooks.length ? [{ ...group, hooks: keptHooks }] : [];
    });
    events[event] = [...kept, { hooks: [entry] }];
  }
  document.hooks = hooks;
  return [
    {
      path: runner,
      before: runnerBefore,
      after: cliHookRunner(layout, runtime),
      command,
      kind: "owned",
    },
    {
      path: target,
      before,
      after: `${JSON.stringify(document, null, 2)}\n`,
      command,
      kind: "merge",
    },
  ];
}

/** No sh, environment assignments or shell quoting: both hosts read the same
 * args-style hook payload, and the installed runner keeps the command total. */
function cliHookRunner(
  layout: RecallHostLayout,
  runtime: RecallRuntime,
): string {
  const label = layout.hostLabel;
  const hostId = layout.hostId;
  const settings = JSON.stringify({
    recall: runtime.recallCliPath, capture: resolveCaptureCommand(runtime),
    discovery: runtime.discoveryPath, credential: runtime.credentialFile, data: runtime.dataDir,
  });
  return `// Managed by MemHub: ${label} prompt recall and visible-turn capture.\n"use strict";\nconst {spawn}=require("node:child_process");\nconst config=${settings};\nconst host=${JSON.stringify(hostId)};\nlet input=""; let child; let ended=false;\nconst finish=()=>{if(ended)return;ended=true;try{child?.kill();}catch{}process.exit(0);};\nconst timer=setTimeout(finish,4500);\nprocess.stdin.setEncoding("utf8");\nprocess.stdin.on("data",chunk=>{input+=chunk;if(Buffer.byteLength(input)>4*1024*1024)finish();});\nprocess.stdin.on("error",finish);\nprocess.stdin.on("end",()=>{\n  let payload;try{payload=JSON.parse(input);}catch{return finish();}\n  const event=payload.hook_event_name || payload.hookEventName;\n  if(!["UserPromptSubmit","SessionStart","Stop"].includes(event))return finish();\n  const env={...process.env,ONE_MEMORY_BROKER_DISCOVERY:config.discovery,ONE_MEMORY_CAPTURE_COMMAND:config.capture,ONE_MEMORY_CAPTURE_DEADLINE_S:"4"};\n  if(config.credential)env.ONE_MEMORY_HOST_CREDENTIAL_FILE=config.credential;\n  if(config.data)env.ONE_MEMORY_DATA_DIR=config.data;\n  const injecting=event!=="Stop";\n  if(injecting)env.ELECTRON_RUN_AS_NODE="1";else delete env.ELECTRON_RUN_AS_NODE;\n  try{child=spawn(injecting?process.execPath:config.capture,injecting?[config.recall,"--inject",host]:["capture",host],{env,windowsHide:true,stdio:["pipe","pipe","ignore"]});}catch{return finish();}\n  let output="";child.stdout.setEncoding("utf8");child.stdout.on("data",chunk=>{output+=chunk;if(Buffer.byteLength(output)>64*1024)finish();});\n  child.on("error",finish);child.stdin.on("error",()=>{});child.stdin.end(input);\n  child.on("close",code=>{if(ended)return;clearTimeout(timer);if(injecting&&code===0&&output.trim()){try{const value=JSON.parse(output);if(value.hookSpecificOutput?.additionalContext)process.stdout.write(JSON.stringify(value)+"\\n");}catch{}}ended=true;process.exitCode=0;});\n});\n`;
}

function mergeCommandHooks(
  raw: string | null,
  sourceId: string,
  command: string,
  events: readonly string[],
): string {
  let document: Record<string, unknown> = {};
  if (raw !== null && raw.trim() !== "") {
    const parsed: unknown = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      throw new Error(
        `${sourceId} hook configuration is not a JSON object; no files were changed`,
      );
    }
    document = parsed as Record<string, unknown>;
  }
  const hooks =
    document.hooks &&
    typeof document.hooks === "object" &&
    !Array.isArray(document.hooks)
      ? (document.hooks as Record<string, unknown>)
      : {};
  for (const event of events) {
    const entries = Array.isArray(hooks[event]) ? [...hooks[event]] : [];
    if (sourceId === "cursor") {
      // Replace the previous One Memory command for this event instead of
      // stacking one per install. A user can have several historical paths
      // from trial/current builds; leaving them all would make one prompt
      // emit several contexts.
      for (let index = entries.length - 1; index >= 0; index -= 1) {
        const entry = entries[index];
        if (
          entry &&
          typeof entry === "object" &&
          typeof (entry as { command?: unknown }).command === "string" &&
          namesCapture((entry as { command: string }).command, sourceId)
        ) {
          entries.splice(index, 1);
        }
      }
      if (
        !entries.some(
          (entry) =>
            entry &&
            typeof entry === "object" &&
            isCommand((entry as { command?: unknown }).command, command),
        )
      ) {
        entries.push({ command });
      }
    } else {
      // Claude Code, Codex and the other group-shaped hosts have the same
      // accumulation failure: a different historical binary/data root is not
      // byte-equal, so it is appended instead of replacing the old entry.
      // Drop only groups whose commands are recognizably ours for this host;
      // a mixed group keeps its foreign commands.
      for (let index = entries.length - 1; index >= 0; index -= 1) {
        const entry = entries[index];
        if (!entry || typeof entry !== "object") continue;
        const group = entry as { hooks?: unknown };
        if (!Array.isArray(group.hooks)) continue;
        const kept = group.hooks.filter((hook) => {
          if (!hook || typeof hook !== "object") return true;
          const value = (hook as { command?: unknown }).command;
          return !(typeof value === "string" && namesCapture(value, sourceId));
        });
        if (kept.length === 0) entries.splice(index, 1);
        else if (kept.length !== group.hooks.length)
          entries[index] = {
            ...(entry as Record<string, unknown>),
            hooks: kept,
          };
      }
      if (
        !entries.some(
          (entry) =>
            entry &&
            typeof entry === "object" &&
            Array.isArray((entry as { hooks?: unknown }).hooks) &&
            (entry as { hooks: Array<{ command?: unknown }> }).hooks.some(
              (hook) => isCommand(hook.command, command),
            ),
        )
      ) {
        entries.push({
          matcher: "",
          hooks: [{ type: "command", command, timeout: 10 }],
        });
      }
    }
    hooks[event] = entries;
  }
  document.hooks = hooks;
  if (sourceId === "cursor" && document.version === undefined) {
    document.version = 1;
  }
  return `${JSON.stringify(document, null, 2)}\n`;
}

function captureEnvironment(dataDir?: string): string {
  if (dataDir === undefined || dataDir === "") return "process.env";
  return `Object.assign({}, process.env, { ONE_MEMORY_DATA_DIR: ${JSON.stringify(dataDir)} })`;
}

function piExtension(command: string, dataDir?: string): string {
  return `// MemHub capture. Tool results are not sent.
import { spawnSync } from "node:child_process";

const command = ${JSON.stringify(command)};

function sessionId(ctx) {
  const file = ctx?.sessionManager?.getSessionFile?.();
  if (typeof file === "string" && file.trim()) return file.trim();
  return "pi";
}

function send(payload) {
  try {
    spawnSync(command, ["capture", "pi"], {
      input: JSON.stringify(payload),
      timeout: 3000,
      stdio: ["pipe", "ignore", "ignore"],
      env: ${captureEnvironment(dataDir)},
    });
  } catch {
    // A capture failure must not stop the turn.
  }
}

export default function oneMemoryCapture(pi) {
  pi.on("before_agent_start", (event, ctx) => {
    send({
      hook_event_name: "before_agent_start",
      session_id: sessionId(ctx),
      prompt: event?.prompt ?? "",
      cwd: event?.systemPromptOptions?.cwd,
    });
  });
  pi.on("turn_end", (event, ctx) => {
    send({
      hook_event_name: "turn_end",
      session_id: sessionId(ctx),
      message: event?.message,
    });
  });
}
`;
}

function openCodePlugin(command: string, dataDir?: string): string {
  return `// MemHub capture. Only text parts are sent.
import { spawnSync } from "node:child_process";

const command = ${JSON.stringify(command)};
const pending = new Map();

function remember(sessionId, role, text) {
  if (!sessionId || !text) return;
  const turn = pending.get(sessionId) ?? [];
  turn.push({ role, parts: [{ type: "text", text }] });
  pending.set(sessionId, turn);
}

function send(sessionId) {
  const messages = pending.get(sessionId);
  pending.delete(sessionId);
  if (!messages || messages.length === 0) return;
  try {
    spawnSync(command, ["capture", "opencode"], {
      input: JSON.stringify({
        hook_event_name: "session.status",
        status: "idle",
        session_id: sessionId,
        messages,
      }),
      timeout: 3000,
      stdio: ["pipe", "ignore", "ignore"],
      env: ${captureEnvironment(dataDir)},
    });
  } catch {
    // A capture failure must not stop the turn.
  }
}

export default async function oneMemoryCapture() {
  return {
    event: async ({ event }) => {
      try {
        const type = event?.type;
        const props = event?.properties ?? {};
        const sessionId = props.sessionID ?? props.sessionId ?? event?.sessionID;
        if (type === "message.part.updated" || type === "message.part.delta") {
          const part = props.part ?? props;
          if (part?.type === "text" && typeof part.text === "string") {
            remember(sessionId, props.role ?? "assistant", part.text);
          }
        }
        if (type === "session.idle" || (type === "session.status" && props.status === "idle")) {
          send(sessionId);
        }
      } catch {
        // Ignore a shape this OpenCode build does not use.
      }
    },
  };
}
`;
}
