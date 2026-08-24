param()

$ErrorActionPreference = "Stop"
$SecureKey = Read-Host "Enter your personal image API key" -AsSecureString
$Pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureKey)
try {
    $PlainKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($Pointer)
    if ([string]::IsNullOrWhiteSpace($PlainKey)) {
        throw "The image API key cannot be empty."
    }
    [Environment]::SetEnvironmentVariable("FIGURE_IMAGE_API_KEY", $PlainKey, "User")
    $env:FIGURE_IMAGE_API_KEY = $PlainKey
}
finally {
    if ($Pointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($Pointer)
    }
    $PlainKey = $null
    $SecureKey = $null
}

Write-Output "Configured FIGURE_IMAGE_API_KEY for the current Windows user. Open a new Codex task before testing Figure Skill."
