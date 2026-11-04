import {spawn} from "node:child_process";
import {access, mkdir, mkdtemp, readFile, writeFile} from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import {describe, expect, it} from "vitest";
import {applyRecallInstall, planRecallInstall, previewRecallInstall, rollbackRecallInstall, verifyRecallInstall, zcodeLayout} from "./recall-installer.js";
import {captureCommandFor, inspectCapture} from "./capture-hooks.js";

async function fixture() {
  const root = await mkdtemp(path.join(os.tmpdir(), "memhub-zcode-中文 空格-"));
  const layout = zcodeLayout(path.join(root, ".zcode"));
  await mkdir(path.join(layout.containmentRoot, "cli"), {recursive: true});
  const cli = path.join(root, "recall.cjs");
  await writeFile(cli, `let input='';process.stdin.on('data',x=>input+=x);process.stdin.on('end',()=>{const p=JSON.parse(input);process.stdout.write(JSON.stringify({hookSpecificOutput:{hookEventName:p.hook_event_name,additionalContext:'ZCode fixture memory '+p.prompt}}));});`);
  return {root,layout,runtime:{runtimeCommand:process.execPath,mcpEntryPath:path.join(root,"mcp.cjs"),recallCliPath:cli,captureCommand:process.execPath,discoveryPath:path.join(root,"broker.json"),dataDir:path.join(root,"data")}};
}

const original = {
  plugins: {enabledPlugins: {"computer-use@zcode-plugins-official": true}},
  skills: {"/tmp/example/SKILL.md": {enable: false}},
  mcp: {servers: {neighbor: {command: "leave-alone"}}},
  hooks: {events: {UserPromptSubmit: [{hooks: [{type: "command", command: "my-other-hook"}]}]}},
};

describe("ZCode one-click hooks", () => {
  it("does not mistake a clean config file for a damaged MemHub installation", async () => {
    const {layout,runtime}=await fixture();
    await writeFile(layout.configPath!,JSON.stringify(original));
    const result=await inspectCapture(layout,captureCommandFor(layout,runtime),async target=>readFile(target,"utf8").catch(()=>null));
    expect(result).toEqual({ours:false,findings:[]});
  });

  it("installs MCP and hooks in one config file, reinstalls once, then removes only owned entries", async () => {
    const {layout,runtime}=await fixture();
    await writeFile(layout.configPath!,JSON.stringify(original));
    const plan=await planRecallInstall(layout,runtime);
    const preview=await previewRecallInstall(plan);
    expect(preview.files.filter(x=>x.path===layout.configPath)).toHaveLength(1);
    await applyRecallInstall(plan,preview.fingerprint);
    await verifyRecallInstall(layout);
    let config=JSON.parse(await readFile(layout.configPath!,"utf8"));
    expect(config.mcp.servers["one-memory"]).toBeDefined();
    expect(config.mcp.servers.neighbor).toEqual(original.mcp.servers.neighbor);
    expect(config.hooks.enabled).toBe(true);
    expect(config.hooks.events.UserPromptSubmit).toHaveLength(2);
    expect(config.hooks.events.Stop[0].hooks[0].args.slice(-2)).toEqual(["capture","zcode"]);
    expect(config.hooks.events.Stop[0].hooks[0].type).toBe("process");
    expect(config.plugins).toEqual(original.plugins);
    await applyRecallInstall(await planRecallInstall(layout,runtime));
    await verifyRecallInstall(layout);
    config=JSON.parse(await readFile(layout.configPath!,"utf8"));
    expect(config.hooks.events.UserPromptSubmit).toHaveLength(2);
    config.newUserSetting="preserve-after-install";
    await writeFile(layout.configPath!,JSON.stringify(config));
    await rollbackRecallInstall(layout);
    const restored=JSON.parse(await readFile(layout.configPath!,"utf8"));
    expect(restored.newUserSetting).toBe("preserve-after-install");
    expect(restored.mcp.servers.neighbor).toEqual(original.mcp.servers.neighbor);
    expect(restored.plugins).toEqual(original.plugins);
    expect(restored.hooks.events.UserPromptSubmit).toEqual(original.hooks.events.UserPromptSubmit);
    await expect(access(path.join(layout.containmentRoot,".one-memory","zcode-hook.cjs"))).rejects.toThrow();
  },20000);

  it("executes its installed process entry with Chinese paths and returns only valid injected JSON", async () => {
    const {layout,runtime}=await fixture();
    await applyRecallInstall(await planRecallInstall(layout,runtime));
    const config=JSON.parse(await readFile(layout.configPath!,"utf8"));
    const hook=config.hooks.events.UserPromptSubmit[0].hooks[0];
    const run=(input:string)=>new Promise<{code:number|null,stdout:string}>((resolve,reject)=>{
      const child=spawn(hook.command,hook.args,{windowsHide:true,stdio:["pipe","pipe","pipe"]});
      let stdout="";child.stdout.on("data",x=>stdout+=x);child.on("error",reject);child.on("close",code=>resolve({code,stdout}));child.stdin.end(input);
    });
    const result=await run(JSON.stringify({hook_event_name:"UserPromptSubmit",session_id:"zcode-test",turnId:"turn-1",prompt:"上次的约定"}));
    expect(result.code).toBe(0);
    expect(JSON.parse(result.stdout).hookSpecificOutput.additionalContext).toContain("上次的约定");
    expect(await run("malformed input")).toEqual({code:0,stdout:""});
    expect(await run(JSON.stringify({hook_event_name:"Stop"}))).toEqual({code:0,stdout:""});
    await rollbackRecallInstall(layout);
  },20000);

  it("refuses malformed hooks and a missing hook runtime before changing the host", async () => {
    const {layout,runtime}=await fixture();
    await writeFile(layout.configPath!,JSON.stringify({hooks:"invalid"}));
    const plan=await planRecallInstall(layout,runtime);
    await expect(previewRecallInstall(plan)).rejects.toThrow("hooks must be a JSON object");
    expect(JSON.parse(await readFile(layout.configPath!,"utf8"))).toEqual({hooks:"invalid"});
    await expect(planRecallInstall(layout,{...runtime,recallCliPath:undefined})).rejects.toThrow("recallCliPath");
  });

  it("detects a removed hook even while MCP and skill still exist", async () => {
    const {layout,runtime}=await fixture();
    await applyRecallInstall(await planRecallInstall(layout,runtime));
    const config=JSON.parse(await readFile(layout.configPath!,"utf8"));
    delete config.hooks.events.Stop;
    await writeFile(layout.configPath!,JSON.stringify(config));
    await expect(verifyRecallInstall(layout)).rejects.toThrow("hook verification failed");
  },20000);
});
