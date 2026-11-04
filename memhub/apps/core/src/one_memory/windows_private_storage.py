"""Windows owner/DACL validation for private import staging files."""
import os
import subprocess
from pathlib import Path

_SCRIPT = r"""
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
"""
def windows_private_storage(path: Path, *, initialize: bool = False) -> None:
    if os.name != "nt":
        return
    executable = (
        Path(os.environ.get("SystemRoot", r"C:\Windows"))
        / "System32/WindowsPowerShell/v1.0/powershell.exe"
    )
    try:
        subprocess.run(
            [str(executable), "-NoProfile", "-NonInteractive", "-Command", _SCRIPT],
            env={
                **os.environ,
                "MEMHUB_PRIVATE_PATH": str(path),
                "MEMHUB_PRIVATE_INITIALIZE": "1" if initialize else "0",
            },
            capture_output=True,
            check=True,
            timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except (subprocess.SubprocessError, OSError):
        raise OSError("windows_private_storage_unavailable") from None


def private_directory(path: Path, *, parents: bool = False) -> None:
    try:
        path.mkdir(parents=parents, mode=0o700)
    except FileExistsError:
        windows_private_storage(path)
    else:
        windows_private_storage(path, initialize=True)
