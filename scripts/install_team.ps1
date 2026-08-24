param(
    [ValidateSet("all", "paperbanana", "autofigure-edit")]
    [string]$Backends = "all",
    [switch]$SkipExternalBackends,
    [switch]$Recreate
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$SkillRoot = Join-Path $ProjectRoot "plugins\figure-skill\skills\figure-skill"
$Launcher = Join-Path $SkillRoot "scripts\figure.py"

foreach ($Command in @("git", "python", "codex")) {
    if (-not (Get-Command $Command -ErrorAction SilentlyContinue)) {
        throw "$Command is required for the Figure Skill team installer."
    }
}

git -C $ProjectRoot rev-parse --is-inside-work-tree | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Run this installer from a Git checkout of Figure-Skill." }

$Marketplaces = codex plugin marketplace list
if ($LASTEXITCODE -ne 0) { throw "Failed to list Codex plugin marketplaces." }
$MarketplaceText = $Marketplaces -join "`n"
if ($MarketplaceText -notmatch '(?m)^mwm-research\s') {
    codex plugin marketplace add $ProjectRoot
    if ($LASTEXITCODE -ne 0) { throw "Failed to add the MWM Research marketplace." }
}
else {
    codex plugin marketplace upgrade mwm-research 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Output "Marketplace mwm-research is local or cannot be upgraded; using its configured source."
    }
}

codex plugin add figure-skill@mwm-research
if ($LASTEXITCODE -ne 0) { throw "Failed to install figure-skill@mwm-research." }

python $Launcher bootstrap
if ($LASTEXITCODE -ne 0) { throw "Failed to bootstrap the Figure Skill core runtime." }

if (-not $SkipExternalBackends) {
    $BackendArgs = @("backends", "install", "--backend", $Backends)
    if ($Recreate) { $BackendArgs += "--recreate" }
    python $Launcher @BackendArgs
    if ($LASTEXITCODE -ne 0) { throw "Failed to install one or more external Figure Skill backends." }
}

$DoctorReport = Join-Path $ProjectRoot "tmp\team-install-doctor.json"
python $Launcher doctor --output $DoctorReport | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Figure Skill health check failed." }

Write-Output "Figure Skill team installation completed."
Write-Output "Health report: $DoctorReport"
Write-Output "Open a new Codex task and invoke `$figure-skill."
if ($SkipExternalBackends) {
    Write-Output "External backends were skipped and can be installed later with: python `"$Launcher`" backends install --backend all"
}
