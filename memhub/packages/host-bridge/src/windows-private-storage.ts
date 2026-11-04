import { execFile } from "node:child_process";
import path from "node:path";
import { promisify } from "node:util";

const run = promisify(execFile);

/** Validate Windows ACLs instead of treating synthetic POSIX mode bits as security. */
export async function windowsPrivateStorage(target: string, initialize = false): Promise<void> {
  if (process.platform !== "win32") return;
  const script = `
$ErrorActionPreference='Stop'
$p=$env:MEMHUB_PRIVATE_PATH
$item=Get-Item -LiteralPath $p -Force
if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'reparse_point' }
$sid=[Security.Principal.WindowsIdentity]::GetCurrent().User
if ($env:MEMHUB_PRIVATE_INITIALIZE -eq '1') {
  if (!$item.PSIsContainer) { throw 'directory_required' }
  $acl=New-Object Security.AccessControl.DirectorySecurity
  $acl.SetOwner($sid)
  $acl.SetAccessRuleProtection($true,$false)
  foreach ($id in @($sid.Value,'S-1-5-18','S-1-5-32-544')) {
    $principal=New-Object Security.Principal.SecurityIdentifier($id)
    $rule=New-Object Security.AccessControl.FileSystemAccessRule($principal,'FullControl','ContainerInherit,ObjectInherit','None','Allow')
    $acl.AddAccessRule($rule)
  }
  [IO.Directory]::SetAccessControl($p,$acl)
}
$acl=if ($item.PSIsContainer) { [IO.Directory]::GetAccessControl($p) } else { [IO.File]::GetAccessControl($p) }
if ($acl.GetOwner([Security.Principal.SecurityIdentifier]).Value -ne $sid.Value) { throw 'owner_mismatch' }
$allowed=@($sid.Value,'S-1-5-18','S-1-5-32-544')
foreach ($rule in $acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier])) {
  if ($rule.AccessControlType -eq 'Allow' -and $rule.IdentityReference.Value -notin $allowed) { throw 'public_acl' }
}
`;
  await run(path.join(process.env.SystemRoot ?? "C:\\Windows", "System32", "WindowsPowerShell", "v1.0", "powershell.exe"),
    ["-NoProfile", "-NonInteractive", "-Command", script], {
      windowsHide: true, timeout: 10000,
      env: { ...process.env, MEMHUB_PRIVATE_PATH: target, MEMHUB_PRIVATE_INITIALIZE: initialize ? "1" : "0" },
    });
}
