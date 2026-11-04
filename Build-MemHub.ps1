param()
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "memhub")
function Check-Exit { if ($LASTEXITCODE) { throw "Build failed with exit code $LASTEXITCODE." } }

# Pin the installer used for this port while retaining the upstream lockfile.
$env:npm_config_manage_package_manager_versions = "false"
$env:electron_config_cache = Join-Path $env:LOCALAPPDATA "MemHub-Windows\electron-cache"
$env:UV_CACHE_DIR = Join-Path $env:LOCALAPPDATA "MemHub-Windows\python-cache"
uv sync --directory apps/core --frozen --no-dev
Check-Exit
& apps/core/.venv/Scripts/python.exe scripts/apply_hy_sdk_compat.py
Check-Exit
& apps/core/.venv/Scripts/python.exe scripts/fetch_embedding_model.py
Check-Exit
npx.cmd --yes pnpm@10.32.1 --config.auto-install-peers=true install --frozen-lockfile --ignore-scripts
Check-Exit
node apps/desktop/node_modules/electron/install.js
Check-Exit
foreach ($project in "packages/host-bridge","packages/runtime-control","apps/cli","apps/desktop","apps/web") {
    Push-Location $project
    try {
        if ($project -eq "apps/web") {
            & .\node_modules\.bin\tsc.cmd -b
            Check-Exit
            & .\node_modules\.bin\vite.cmd build
        } else {
            & .\node_modules\.bin\tsup.cmd
        }
        Check-Exit
        if ($project -eq "packages/host-bridge") {
            node scripts/build-hook-assets.mjs
            Check-Exit
            node scripts/build-hermes-provider-assets.mjs
            Check-Exit
        }
    } finally { Pop-Location }
}
