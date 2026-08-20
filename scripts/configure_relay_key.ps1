param(
    [string]$VariableName = "AUTOFIGURE_API_KEY",
    [string]$StatusPath = ""
)

$ErrorActionPreference = "Stop"
$secureValue = Read-Host "Paste the NEW relay API key (input is hidden)" -AsSecureString
if ($secureValue.Length -eq 0) {
    Write-Host "No key was entered. Nothing was changed." -ForegroundColor Yellow
    Read-Host "Press Enter to close"
    exit 1
}

$pointer = [IntPtr]::Zero
$plainValue = $null
try {
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureValue)
    $plainValue = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    [Environment]::SetEnvironmentVariable($VariableName, $plainValue, "User")
}
finally {
    $plainValue = $null
    if ($pointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
    }
    $secureValue.Dispose()
}

$configured = -not [string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($VariableName, "User"))
if (-not $configured) {
    Write-Host "The key could not be saved." -ForegroundColor Red
    Read-Host "Press Enter to close"
    exit 1
}

if ($StatusPath) {
    $status = [ordered]@{
        schema_version = "1.0"
        variable = $VariableName
        configured = $true
        scope = "User"
        configured_at = (Get-Date).ToString("o")
    }
    $statusDirectory = Split-Path -Parent $StatusPath
    if ($statusDirectory) {
        New-Item -ItemType Directory -Force -Path $statusDirectory | Out-Null
    }
    $status | ConvertTo-Json | Set-Content -LiteralPath $StatusPath -Encoding UTF8
}

Write-Host "Key saved securely as $VariableName in the current Windows user environment." -ForegroundColor Green
Write-Host "Return to Codex after closing this window."
Read-Host "Press Enter to close"
