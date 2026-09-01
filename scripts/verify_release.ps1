param(
    [string]$Python = "",
    [switch]$RepairDrawio,
    [switch]$SkipAcceptance
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$PluginRoot = Join-Path $ProjectRoot "plugins\figure-skill"
$SkillRoot = Join-Path $PluginRoot "skills\figure-skill"
$Version = (Get-Content -Raw -Encoding UTF8 (Join-Path $ProjectRoot "VERSION")).Trim()
if ($Version -notmatch '^\d+\.\d+\.\d+$') { throw "VERSION is not semantic: $Version" }

if (-not $Python) {
    $ProjectPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $ProjectPython)) {
        $BootstrapPython = Get-Command python -ErrorAction SilentlyContinue
        if (-not $BootstrapPython) { throw "Python is required to create the project environment" }
        & $BootstrapPython.Source -m venv (Join-Path $ProjectRoot ".venv")
        if ($LASTEXITCODE -ne 0) { throw "failed to create the project virtual environment" }
        & $ProjectPython -m pip install --disable-pip-version-check -r (Join-Path $SkillRoot "requirements.txt")
        if ($LASTEXITCODE -ne 0) { throw "failed to install project requirements" }
    }
    $Python = $ProjectPython
}

$env:PYTHONDONTWRITEBYTECODE = "1"
$ReportRoot = Join-Path $ProjectRoot "tmp\release-verification"
New-Item -ItemType Directory -Force -Path $ReportRoot | Out-Null

if ($RepairDrawio) {
    & (Join-Path $PSScriptRoot "setup_drawio_plugin.ps1")
    if ($LASTEXITCODE -ne 0) { throw "draw.io repair failed" }
}

$EnvironmentReport = Join-Path $ReportRoot "environment.json"
$CheckEnvironmentArgs = @(
    (Join-Path $SkillRoot "scripts\check_environment.py"),
    "--output", $EnvironmentReport
)
$PaperRepo = Join-Path $ProjectRoot ".external\upstreams\PaperBanana"
$AutoRepo = Join-Path $ProjectRoot ".external\upstreams\AutoFigure-Edit"
if (Test-Path -LiteralPath (Join-Path $PaperRepo "skill\run.py")) {
    $CheckEnvironmentArgs += @("--paperbanana-repo", $PaperRepo)
}
if (Test-Path -LiteralPath (Join-Path $AutoRepo "autofigure2.py")) {
    $CheckEnvironmentArgs += @("--autofigure-repo", $AutoRepo)
}
& $Python @CheckEnvironmentArgs | Out-Null
if ($LASTEXITCODE -ne 0) { throw "core environment check failed" }
$Environment = Get-Content -Raw -Encoding UTF8 $EnvironmentReport | ConvertFrom-Json

$TestRoot = Join-Path $SkillRoot "tests"
$AutomatedTestCount = [int](& $Python -c "import sys, unittest; print(unittest.defaultTestLoader.discover(sys.argv[1]).countTestCases())" $TestRoot | Select-Object -Last 1)
& $Python -m unittest discover -s $TestRoot -v
if ($LASTEXITCODE -ne 0) { throw "automated tests failed" }

$CodexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME ".codex" }
$QuickValidate = Join-Path $CodexHome "skills\.system\skill-creator\scripts\quick_validate.py"
if (-not (Test-Path -LiteralPath $QuickValidate)) {
    throw "Codex skill validator was not found: $QuickValidate"
}
& $Python $QuickValidate $SkillRoot
if ($LASTEXITCODE -ne 0) { throw "skill validation failed" }

$PluginValidate = Join-Path $CodexHome "skills\.system\plugin-creator\scripts\validate_plugin.py"
if (-not (Test-Path -LiteralPath $PluginValidate)) {
    throw "Codex plugin validator was not found: $PluginValidate"
}
& $Python $PluginValidate $PluginRoot
if ($LASTEXITCODE -ne 0) { throw "plugin validation failed" }
$MarketplacePath = Join-Path $ProjectRoot ".agents\plugins\marketplace.json"
$Marketplace = Get-Content -Raw -Encoding UTF8 $MarketplacePath | ConvertFrom-Json
$MarketplaceEntry = @($Marketplace.plugins | Where-Object { $_.name -eq "figure-skill" })
if ($Marketplace.name -ne "mwm-research" -or $MarketplaceEntry.Count -ne 1 -or $MarketplaceEntry[0].source.path -ne "./plugins/figure-skill") {
    throw "team marketplace manifest is inconsistent"
}

$AcceptanceStatus = "skipped"
if (-not $SkipAcceptance) {
    $AcceptanceSummary = Join-Path $ProjectRoot "manual-validation\public-acceptance-20260820\reports\acceptance-summary.json"
    if (-not (Test-Path -LiteralPath $AcceptanceSummary)) {
        throw "public acceptance summary is missing"
    }
    $Acceptance = Get-Content -Raw -Encoding UTF8 $AcceptanceSummary | ConvertFrom-Json
    $BadRoutes = @($Acceptance.routes | Where-Object { $_.Status -ne "pass" })
    if ($BadRoutes.Count -ne 0 -or $Acceptance.security.secret_match_files -ne 0) {
        throw "public acceptance evidence is not clean"
    }
    $AcceptanceStatus = $Acceptance.overall_status
}

$ShowcaseReport = Join-Path $ReportRoot "showcase-regression.json"
& $Python (Join-Path $ProjectRoot "scripts\verify_showcase.py") --work-root (Join-Path $ReportRoot "showcase") --output $ShowcaseReport
if ($LASTEXITCODE -ne 0) { throw "showcase regression failed" }
$Showcase = Get-Content -Raw -Encoding UTF8 $ShowcaseReport | ConvertFrom-Json

$ScanTargets = @(
    (Join-Path $ProjectRoot "plugins"),
    (Join-Path $ProjectRoot ".agents"),
    (Join-Path $ProjectRoot "scripts"),
    (Join-Path $ProjectRoot "showcase"),
    (Join-Path $ProjectRoot "README.md"),
    (Join-Path $ProjectRoot "CHANGELOG.md"),
    (Join-Path $ProjectRoot "THIRD_PARTY_NOTICES.md")
)
$SecretFiles = @(& rg -l 'sk-[A-Za-z0-9]' @ScanTargets 2>$null)
if ($SecretFiles.Count -ne 0) { throw "secret-like values found in release sources" }

$Result = [ordered]@{
    schema_version = "1.0"
    version = $Version
    status = "pass"
    verified_at = (Get-Date).ToString("o")
    python = $Environment.python
    core = $Environment.core
    automated_tests = $AutomatedTestCount
    skill_validation = "pass"
    plugin_validation = "pass"
    marketplace_validation = "pass"
    acceptance = $AcceptanceStatus
    showcase_regression = $Showcase.status
    showcase_cases = @($Showcase.cases).Count
    secret_matches = 0
    drawio_repair_requested = [bool]$RepairDrawio
}
$ResultPath = Join-Path $ReportRoot "release-verification.json"
$Result | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $ResultPath -Encoding UTF8
Write-Output "Release verification passed -> $ResultPath"
exit 0
