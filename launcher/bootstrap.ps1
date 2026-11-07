# Traduco launcher bootstrap (Windows): installs uv into .runtime\uv (no admin rights),
# then hands over to the Python launcher. All logic lives in launcher\.
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$LauncherArgs)
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$UvVersion = '0.13.4'

$env:UV_UNMANAGED_INSTALL = Join-Path $Root '.runtime\uv'
$env:UV_NO_MODIFY_PATH = '1'
$env:UV_PYTHON_INSTALL_DIR = Join-Path $Root '.runtime\python'
$env:UV_CACHE_DIR = Join-Path $Root '.runtime\uv-cache'
$env:UV_PROJECT_ENVIRONMENT = Join-Path $Root '.runtime\launcher-venv'
$env:PYTHONUTF8 = '1'
$Uv = Join-Path $env:UV_UNMANAGED_INSTALL 'uv.exe'

if (-not (Test-Path $Uv)) {
    $Existing = Get-Command uv -ErrorAction SilentlyContinue
    if ($Existing) {
        $Uv = $Existing.Source
    } else {
        Write-Host "[0] Installing uv $UvVersion into .runtime\uv ..."
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        $Proxy = if ($env:HTTPS_PROXY) { $env:HTTPS_PROXY } else { $env:HTTP_PROXY }
        if ($Proxy) { [Net.WebRequest]::DefaultWebProxy = New-Object Net.WebProxy($Proxy) }
        $Url = "https://github.com/astral-sh/uv/releases/download/$UvVersion/uv-installer.ps1"
        Invoke-RestMethod $Url | Invoke-Expression
    }
}

# --offline: no network at all, not even for uv (the bundle carries Python, wheels and Pandoc)
if ($LauncherArgs -contains '--offline') { $env:UV_OFFLINE = '1' }

$env:TRADUCO_UV = $Uv
& $Uv run --frozen --no-dev --project launcher python -m launcher @LauncherArgs
exit $LASTEXITCODE
