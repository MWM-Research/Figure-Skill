$ErrorActionPreference = "Stop"

if (-not (Get-Command codex -ErrorAction SilentlyContinue)) {
    throw "Codex CLI is not available on PATH"
}

$ListOutput = (& codex plugin list 2>&1 | Out-String)
$ListCode = $LASTEXITCODE
if ($ListCode -ne 0 -and $ListOutput -match "openai-bundled") {
    $Package = Get-AppxPackage OpenAI.Codex
    if (-not $Package) { throw "OpenAI.Codex AppX package was not found" }
    $CurrentBundled = Join-Path $Package.InstallLocation "app\resources\plugins\openai-bundled"
    $Manifest = Join-Path $CurrentBundled ".agents\plugins\marketplace.json"
    if (-not (Test-Path -LiteralPath $Manifest)) {
        throw "Current OpenAI bundled marketplace manifest was not found: $Manifest"
    }
    & codex plugin marketplace remove openai-bundled --json | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Failed to remove stale openai-bundled marketplace" }
    & codex plugin marketplace add $CurrentBundled --json | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Failed to add current openai-bundled marketplace" }
}
elseif ($ListCode -ne 0) {
    throw "Codex plugin list failed for a reason unrelated to openai-bundled: $ListOutput"
}

& codex plugin marketplace add jgraph/drawio-mcp --ref main --json | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Failed to add the official draw.io marketplace" }
& codex plugin add drawio@drawio --json | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Failed to install the official draw.io plugin" }

$FinalList = (& codex plugin list 2>&1 | Out-String)
if ($LASTEXITCODE -ne 0 -or $FinalList -notmatch "drawio@drawio\s+installed, enabled") {
    throw "drawio plugin did not reach installed, enabled state"
}

Write-Output "drawio@drawio is installed and enabled. Start a new Codex task if the current task does not expose the new skill yet."
