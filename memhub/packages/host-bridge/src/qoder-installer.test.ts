import {spawn} from "node:child_process";
import {mkdir, mkdtemp, readFile, writeFile, access} from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import {describe, expect, it} from "vitest";
import {applyRecallInstall, planRecallInstall, previewRecallInstall, qoderLayout, rollbackRecallInstall, verifyRecallInstall} from "./recall-installer.js";
import {captureCommandFor, inspectCapture} from "./capture-hooks.js";

async function fixture() {
  const root = await mkdtemp(path.join(os.tmpdir(), "memhub-qoder-中文 空格-"));
  const layout = qoderLayout(path.join(root, ".qoder-cn"));
  await mkdir(layout.containmentRoot);
  const cli = path.join(root, "recall.cjs");
  await writeFile(cli, `let input='';process.stdin.on('data',x=>input+=x);process.stdin.on('end',()=>{const p=JSON.parse(input);process.stdout.write(JSON.stringify({hookSpecificOutput:{hookEventName:p.hook_event_name,additionalContext:'Qoder fixture memory '+p.prompt}}));});`);
  return {root,layout,runtime:{runtimeCommand:process.execPath,mcpEntryPath:path.join(root,"mcp.cjs"),recallCliPath:cli,captureCommand:process.execPath,discoveryPath:path.join(root,"broker.json"),dataDir:path.join(root,"data")}};
}

const original = {theme:"keep",mcpServers:{neighbor:{command:"leave-alone"}},hooks:{UserPromptSubmit:[{hooks:[{type:"command",command:"my-other-hook"}]}]}};

describe("Qoder CN one-click hooks", () => {
  it("does not mistake a clean settings file for a damaged MemHub installation", async () => {
    const {layout,runtime}=await fixture();
    await writeFile(layout.configPath!,JSON.stringify(original));
    const result=await inspectCapture(layout,captureCommandFor(layout,runtime),async target=>readFile(target,"utf8").catch(()=>null));
    expect(result).toEqual({ours:false,findings:[]});
  });

  it("replaces its old runtime entry after a runtime move", async () => {
    const {layout,runtime}=await fixture();
    await writeFile(layout.configPath!,JSON.stringify(original));
    await applyRecallInstall(await planRecallInstall(layout,runtime));
    const config=JSON.parse(await readFile(layout.configPath!,"utf8"));
    for(const event of ["UserPromptSubmit","Stop","SessionStart"]){
      for(const group of config.hooks[event])for(const hook of group.hooks ?? [])if(hook.name==="memhub-qoder")hook.command="old-runtime-path";
    }
    await writeFile(layout.configPath!,JSON.stringify(config));
    await applyRecallInstall(await planRecallInstall(layout,runtime));
    await verifyRecallInstall(layout);
    const repaired=JSON.parse(await readFile(layout.configPath!,"utf8"));
    expect(repaired.hooks.UserPromptSubmit).toHaveLength(2);
    expect(JSON.stringify(repaired)).not.toContain("old-runtime-path");
    await rollbackRecallInstall(layout);
  },20000);

  it("installs MCP and hooks in one settings file, reinstalls once, then removes only owned entries", async () => {
    const {layout,runtime}=await fixture();
    await writeFile(layout.configPath!,JSON.stringify(original));
    const plan=await planRecallInstall(layout,runtime);
    const preview=await previewRecallInstall(plan);
    expect(preview.files.filter(x=>x.path===layout.configPath)).toHaveLength(1);
    await applyRecallInstall(plan,preview.fingerprint);
    await verifyRecallInstall(layout);
    let config=JSON.parse(await readFile(layout.configPath!,"utf8"));
    expect(config.mcpServers["one-memory"]).toBeDefined();
    expect(config.mcpServers.neighbor).toEqual(original.mcpServers.neighbor);
    expect(config.hooks.UserPromptSubmit).toHaveLength(2);
    expect(config.hooks.Stop[0].hooks[0].args.slice(-2)).toEqual(["capture","qoder"]);
    await applyRecallInstall(await planRecallInstall(layout,runtime));
    await verifyRecallInstall(layout);
    config=JSON.parse(await readFile(layout.configPath!,"utf8"));
    expect(config.hooks.UserPromptSubmit).toHaveLength(2);
    config.newUserSetting="preserve-after-install";
    await writeFile(layout.configPath!,JSON.stringify(config));
    await rollbackRecallInstall(layout);
    const restored=JSON.parse(await readFile(layout.configPath!,"utf8"));
    expect(restored).toEqual({...original,newUserSetting:"preserve-after-install"});
    await expect(access(path.join(layout.containmentRoot,".one-memory","qoder-hook.cjs"))).rejects.toThrow();
  },20000);

  it("executes its installed args/env entry with Chinese paths and returns only valid injected JSON", async () => {
    const {layout,runtime}=await fixture();
    await applyRecallInstall(await planRecallInstall(layout,runtime));
    const config=JSON.parse(await readFile(layout.configPath!,"utf8"));
    const hook=config.hooks.UserPromptSubmit[0].hooks[0];
    const run=(input:string)=>new Promise<{code:number|null,stdout:string}>((resolve,reject)=>{
      const child=spawn(hook.command,hook.args,{env:{...process.env,...hook.env},windowsHide:true,stdio:["pipe","pipe","pipe"]});
      let stdout="";child.stdout.on("data",x=>stdout+=x);child.on("error",reject);child.on("close",code=>resolve({code,stdout}));child.stdin.end(input);
    });
    const result=await run(JSON.stringify({hook_event_name:"UserPromptSubmit",session_id:"qoder-test",prompt:"上次的约定"}));
    expect(result.code).toBe(0);
    expect(JSON.parse(result.stdout).hookSpecificOutput.additionalContext).toContain("上次的约定");
    expect(await run("malformed input")).toEqual({code:0,stdout:""});
    expect(await run(JSON.stringify({hook_event_name:"Stop"}))).toEqual({code:0,stdout:""});
    await rollbackRecallInstall(layout);
  },20000);

  it("refuses malformed settings and a missing hook runtime before changing the host", async () => {
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
    delete config.hooks.Stop;
    await writeFile(layout.configPath!,JSON.stringify(config));
    await expect(verifyRecallInstall(layout)).rejects.toThrow("hook verification failed");
  },20000);
});
