param(
    [string]$Python = "python",
    [switch]$SkipInstall,
    [switch]$Recreate
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$ExternalRoot = Join-Path $ProjectRoot ".external"
$Upstreams = Join-Path $ExternalRoot "upstreams"
$Environments = Join-Path $ExternalRoot "venvs"
$PaperRepo = Join-Path $Upstreams "PaperBanana"
$AutoRepo = Join-Path $Upstreams "AutoFigure-Edit"
$PaperCommit = "836455537e863b5a2f40dace487a782c0bc5ef94"
$AutoCommit = "16f3749e9d512bdf7b7b55c162307bc289750b7a"

New-Item -ItemType Directory -Force -Path $Upstreams, $Environments | Out-Null

function Ensure-Upstream([string]$Url, [string]$Path, [string]$Commit) {
    if (-not (Test-Path -LiteralPath (Join-Path $Path ".git"))) {
        git clone --filter=blob:none --no-checkout $Url $Path
        if ($LASTEXITCODE -ne 0) { throw "git clone failed: $Url" }
    }
    git -C $Path fetch --depth 1 origin $Commit
    if ($LASTEXITCODE -ne 0) { throw "git fetch failed: $Commit" }
    git -C $Path checkout --detach $Commit
    if ($LASTEXITCODE -ne 0) { throw "git checkout failed: $Commit" }
}

Ensure-Upstream "https://github.com/dwzhu-pku/PaperBanana.git" $PaperRepo $PaperCommit
Ensure-Upstream "https://github.com/ResearAI/AutoFigure-Edit.git" $AutoRepo $AutoCommit

$PaperVenv = Join-Path $Environments "paperbanana"
$AutoVenv = Join-Path $Environments "autofigure-edit"
foreach ($Venv in @($PaperVenv, $AutoVenv)) {
    if ($Recreate -or -not (Test-Path -LiteralPath (Join-Path $Venv "Scripts\python.exe"))) {
        $VenvArgs = @("-m", "venv")
        if ($Recreate) { $VenvArgs += "--clear" }
        $VenvArgs += $Venv
        & $Python @VenvArgs
        if ($LASTEXITCODE -ne 0) { throw "failed to create environment: $Venv" }
    }
}

if (-not $SkipInstall) {
    & (Join-Path $PaperVenv "Scripts\python.exe") -m pip install --disable-pip-version-check -r (Join-Path $PaperRepo "requirements.txt")
    if ($LASTEXITCODE -ne 0) { throw "PaperBanana dependency installation failed" }
    & (Join-Path $AutoVenv "Scripts\python.exe") -m pip install --disable-pip-version-check -r (Join-Path $AutoRepo "requirements.txt")
    if ($LASTEXITCODE -ne 0) { throw "AutoFigure-Edit dependency installation failed" }
}

& (Join-Path $PaperVenv "Scripts\python.exe") -m pip check
if ($LASTEXITCODE -ne 0) { throw "PaperBanana dependency consistency check failed" }
& (Join-Path $AutoVenv "Scripts\python.exe") -m pip check
if ($LASTEXITCODE -ne 0) { throw "AutoFigure-Edit dependency consistency check failed" }

& (Join-Path $PaperVenv "Scripts\python.exe") (Join-Path $PaperRepo "skill\run.py") --help | Out-Null
if ($LASTEXITCODE -ne 0) { throw "PaperBanana CLI smoke test failed" }
& (Join-Path $AutoVenv "Scripts\python.exe") (Join-Path $AutoRepo "autofigure2.py") --help | Out-Null
if ($LASTEXITCODE -ne 0) { throw "AutoFigure-Edit CLI smoke test failed" }

$Result = [ordered]@{
    schema_version = "1.0"
    paperbanana = [ordered]@{
        repo = $PaperRepo
        commit = $PaperCommit
        python = (Join-Path $PaperVenv "Scripts\python.exe")
        isolated = $true
        pip_check = "pass"
        cli_smoke_test = "pass"
    }
    autofigure_edit = [ordered]@{
        repo = $AutoRepo
        commit = $AutoCommit
        python = (Join-Path $AutoVenv "Scripts\python.exe")
        isolated = $true
        pip_check = "pass"
        cli_smoke_test = "pass"
        local_sam3_note = "SAM3 is an upstream separate install; use fal/roboflow credentials or install SAM3 explicitly."
    }
}
$Report = Join-Path $ExternalRoot "setup-report.json"
$Result | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $Report -Encoding UTF8
Write-Output "External backends ready: $Report"
