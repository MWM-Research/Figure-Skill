param(
    [switch]$Force,
    [switch]$RepairDrawio
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Version = (Get-Content -Raw -Encoding UTF8 (Join-Path $ProjectRoot "VERSION")).Trim()
$Dist = Join-Path $ProjectRoot "dist"
$Archive = Join-Path $Dist "figure-skill-v$Version.zip"
if ((Test-Path -LiteralPath $Archive) -and -not $Force) {
    throw "release archive already exists; pass -Force to replace it: $Archive"
}

$VerifyArgs = @()
if ($RepairDrawio) { $VerifyArgs += "-RepairDrawio" }
& (Join-Path $PSScriptRoot "verify_release.ps1") @VerifyArgs
if ($LASTEXITCODE -ne 0) { throw "release verification failed" }

New-Item -ItemType Directory -Force -Path $Dist | Out-Null
$Stage = Join-Path $ProjectRoot ("tmp\release-stage-{0}-{1}" -f $Version, [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $Stage | Out-Null

function Copy-Tree([string]$Source, [string]$Destination) {
    $SourceRoot = (Resolve-Path -LiteralPath $Source).Path
    foreach ($File in Get-ChildItem -LiteralPath $SourceRoot -Recurse -File) {
        if ($File.FullName -match '[\\/]__pycache__[\\/]' -or $File.Extension -in @(".pyc", ".pyo")) { continue }
        $Relative = $File.FullName.Substring($SourceRoot.Length + 1)
        $Target = Join-Path $Destination $Relative
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Target) | Out-Null
        Copy-Item -LiteralPath $File.FullName -Destination $Target -Force
    }
}

foreach ($FileName in @("README.md", "VERSION", "CHANGELOG.md", "THIRD_PARTY_NOTICES.md", ".gitignore")) {
    Copy-Item -LiteralPath (Join-Path $ProjectRoot $FileName) -Destination (Join-Path $Stage $FileName) -Force
}
Copy-Tree (Join-Path $ProjectRoot "plugins") (Join-Path $Stage "plugins")
Copy-Tree (Join-Path $ProjectRoot ".agents") (Join-Path $Stage ".agents")
Copy-Tree (Join-Path $ProjectRoot "scripts") (Join-Path $Stage "scripts")
Copy-Tree (Join-Path $ProjectRoot ".github") (Join-Path $Stage ".github")

$Evidence = Join-Path $Stage "evidence\public-acceptance-20260820"
New-Item -ItemType Directory -Force -Path $Evidence | Out-Null
$EvidenceFiles = @(
    "ACCEPTANCE_REPORT.md",
    "DELIVERABLES.md",
    "sources\SOURCES.md",
    "sources\download-hashes.json",
    "reports\acceptance-summary.json",
    "reports\deliverable-hashes.json",
    "reports\visual-qa-contact-sheet.png",
    "inputs\methods.txt",
    "scripts\download_sources.ps1",
    "scripts\prepare_iris.py",
    "scripts\render_and_compare_reconstructions.py",
    "scripts\make_contact_sheet.py"
)
$AcceptanceRoot = Join-Path $ProjectRoot "manual-validation\public-acceptance-20260820"
foreach ($Relative in $EvidenceFiles) {
    $Source = Join-Path $AcceptanceRoot $Relative
    if (-not (Test-Path -LiteralPath $Source)) { throw "release evidence is missing: $Relative" }
    $Target = Join-Path $Evidence $Relative
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Target) | Out-Null
    Copy-Item -LiteralPath $Source -Destination $Target -Force
}

$StagedFiles = Get-ChildItem -LiteralPath $Stage -Recurse -File
$Manifest = [ordered]@{
    schema_version = "1.0"
    version = $Version
    built_at = (Get-Date).ToString("o")
    file_count = $StagedFiles.Count
    excludes = @("API keys", ".venv", ".external", "tmp", "full manual-validation outputs", "failed reconstruction artifacts")
}
$Manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $Stage "release-manifest.json") -Encoding UTF8

if (Test-Path -LiteralPath $Archive) {
    Remove-Item -LiteralPath $Archive -Force
}
$Items = Get-ChildItem -LiteralPath $Stage -Force | Select-Object -ExpandProperty FullName
Compress-Archive -LiteralPath $Items -DestinationPath $Archive -CompressionLevel Optimal

Add-Type -AssemblyName System.IO.Compression.FileSystem
$Zip = [IO.Compression.ZipFile]::OpenRead($Archive)
try {
    $Entries = @($Zip.Entries | ForEach-Object { $_.FullName.Replace('\\', '/') })
    foreach ($Required in @(
        "VERSION",
        "README.md",
        ".agents/plugins/marketplace.json",
        "plugins/figure-skill/.codex-plugin/plugin.json",
        "plugins/figure-skill/skills/figure-skill/SKILL.md",
        "plugins/figure-skill/skills/figure-skill/requirements-lock.txt",
        "plugins/figure-skill/skills/figure-skill/scripts/figure.py",
        "plugins/figure-skill/skills/figure-skill/scripts/figure.ps1",
        "plugins/figure-skill/skills/figure-skill/scripts/adapters/raster_illustration_adapter.py",
        "plugins/figure-skill/skills/figure-skill/scripts/configure_image_key.ps1",
        "scripts/verify_release.ps1",
        "release-manifest.json"
    )) {
        if ($Required -notin $Entries) { throw "release archive is missing: $Required" }
    }
    if (@($Entries | Where-Object { $_ -match '(^|/)(__pycache__|\.venv|\.external)(/|$)|\.pyc$' }).Count -ne 0) {
        throw "release archive contains an excluded runtime path"
    }
}
finally {
    $Zip.Dispose()
}

$Hash = (Get-FileHash -LiteralPath $Archive -Algorithm SHA256).Hash
$HashPath = "$Archive.sha256"
"$Hash  $([IO.Path]::GetFileName($Archive))" | Set-Content -LiteralPath $HashPath -Encoding ASCII
$DistManifest = [ordered]@{
    schema_version = "1.0"
    version = $Version
    archive = $Archive
    bytes = (Get-Item $Archive).Length
    sha256 = $Hash
    entry_count = $Entries.Count
    verification = "pass"
}
$DistManifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $Dist "release-manifest.json") -Encoding UTF8
Write-Output "Release built -> $Archive"
