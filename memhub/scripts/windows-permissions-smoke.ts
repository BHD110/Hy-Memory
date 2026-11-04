import assert from 'node:assert/strict';
import {mkdtemp,mkdir,writeFile,readFile} from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {HostPermissions} from '../packages/runtime-control/src/host-permissions';
import {readHostCredentialFile} from '../packages/host-bridge/src/broker-client';
import {windowsPrivateStorage} from '../packages/host-bridge/src/windows-private-storage';
import {hermesLayout,cursorLayout,qoderLayout,mcpConfigPath,readInstalledRecallCommand} from '../packages/host-bridge/src/recall-installer';
async function main(){
 const root=await mkdtemp(path.join(os.tmpdir(),'memhub-win-e2e-'));
 const dataDir=path.join(root,'data'); await mkdir(dataDir);
 const runtime={runtimeCommand:process.execPath,mcpEntryPath:path.join(root,'mock-mcp.cjs'),recallCliPath:path.join(root,'mock-cli.cjs'),captureCommand:process.execPath,discoveryPath:path.join(dataDir,'broker.json')};
 await writeFile(runtime.mcpEntryPath,'process.exit(0)'); await writeFile(runtime.recallCliPath,'process.exit(0)');
 const hermes=process.argv.includes('--hermes');
 const qoder=process.argv.includes('--qoder');
 const layout=qoder?qoderLayout(path.join(root,'.qoder-cn')):hermes?hermesLayout(path.join(root,'hermes')):cursorLayout(path.join(root,'cursor')); await mkdir(layout.containmentRoot);
 await writeFile(mcpConfigPath(layout),hermes?'model:\n  default: keep\n# preserve neighbor\n':JSON.stringify({mcpServers:{neighbor:{command:'keep'}}}));
 const p=await HostPermissions.open(dataDir,runtime); console.log('PASS storage open');
 const preview=await p.previewInstall(layout); console.log('PASS preview');
 const result=await p.install(layout,preview.fingerprint); assert.equal(result.permission.state,'install-only'); console.log('PASS install');
 const command=await readInstalledRecallCommand(layout); assert.ok(command);
 const secret=await readHostCredentialFile(command.env.ONE_MEMORY_HOST_CREDENTIAL_FILE);
 await assert.rejects(p.hostGrantStore.authenticate(secret),{code:'host_grant_not_approved'}); console.log('PASS install-only denied');
 const receipt=result.permission.receipt!;
 const granted=await p.setPermission(layout,{installationId:receipt.installationId,expectedRevision:receipt.revision,allowedTools:['om_recall'],allowedScopes:['all-apps'],userConfirmed:true});
 await p.hostGrantStore.authorize(secret,{tool:'om_recall',scopes:['all-apps']}); console.log('PASS approve and authorize');
 const reopened=await HostPermissions.open(dataDir,runtime); assert.equal((await reopened.getPermission(layout)).state,'approved'); console.log('PASS reopen');
 await reopened.revokePermission(layout,{installationId:receipt.installationId,expectedRevision:granted.receipt!.revision,userConfirmed:true});
 await assert.rejects(reopened.hostGrantStore.authenticate(secret),{code:'host_grant_authentication_failed'}); console.log('PASS revoke');
 const config=await readFile(mcpConfigPath(layout),'utf8');
 if(hermes){assert.ok(config.includes('default: keep'));assert.ok(config.includes('# preserve neighbor'));}
 else assert.equal(JSON.parse(config).mcpServers.neighbor.command,'keep'); console.log('PASS neighbor preserved');
 await assert.rejects(windowsPrivateStorage(root)); console.log('PASS inherited public ACL rejected');
 console.log('Fixture retained:',root);
}
main().catch(e=>{console.error(e);process.exitCode=1});
