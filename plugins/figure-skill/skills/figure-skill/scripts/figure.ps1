param(
    [Parameter(Position = 0, Mandatory = $true)]
    [ValidateSet("bootstrap", "doctor", "workflow", "qa", "runtime-path")]
    [string]$Command,

    [Parameter(Position = 1, ValueFromRemainingArguments = $true)]
    [string[]]$RemainingArguments
)

$ErrorActionPreference = "Stop"
$Launcher = Join-Path $PSScriptRoot "figure.py"
$PythonCommand = Get-Command python -ErrorAction SilentlyContinue

if ($PythonCommand) {
    & $PythonCommand.Source $Launcher $Command @RemainingArguments
    exit $LASTEXITCODE
}

$PyCommand = Get-Command py -ErrorAction SilentlyContinue
if ($PyCommand) {
    & $PyCommand.Source -3 $Launcher $Command @RemainingArguments
    exit $LASTEXITCODE
}

throw "Figure Skill requires Python 3.10 or newer. Install Python and run this command again."
