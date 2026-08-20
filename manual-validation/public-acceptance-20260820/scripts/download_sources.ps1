$ErrorActionPreference = "Stop"
$AcceptanceRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Raw = Join-Path $AcceptanceRoot "sources\raw"
New-Item -ItemType Directory -Force -Path $Raw | Out-Null

$Downloads = @(
    @{ Name = "iris.zip"; Url = "https://archive.ics.uci.edu/static/public/53/iris.zip" },
    @{ Name = "neural-network-ground-truth.svg"; Url = "https://upload.wikimedia.org/wikipedia/commons/1/15/Neural_Network.svg" },
    @{ Name = "neural-network-ground-truth.png"; Url = "https://upload.wikimedia.org/wikipedia/commons/thumb/1/15/Neural_Network.svg/960px-Neural_Network.svg.png" },
    @{ Name = "artificial-neuron-scheme.png"; Url = "https://upload.wikimedia.org/wikipedia/commons/5/57/Artificial_Neuron_Scheme.png" }
)

foreach ($Item in $Downloads) {
    $Target = Join-Path $Raw $Item.Name
    Invoke-WebRequest -Uri $Item.Url -OutFile $Target -TimeoutSec 60
    if (-not (Test-Path -LiteralPath $Target) -or (Get-Item $Target).Length -eq 0) {
        throw "download failed: $($Item.Url)"
    }
}

Expand-Archive -LiteralPath (Join-Path $Raw "iris.zip") -DestinationPath (Join-Path $Raw "iris") -Force
[xml](Get-Content -Raw -Encoding UTF8 (Join-Path $Raw "neural-network-ground-truth.svg")) | Out-Null

$Hashes = Get-ChildItem -LiteralPath $Raw -Recurse -File | ForEach-Object {
    [PSCustomObject]@{
        Path = $_.FullName.Substring($AcceptanceRoot.Length + 1).Replace("\", "/")
        Bytes = $_.Length
        Sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash
    }
}
$Hashes | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath (Join-Path $AcceptanceRoot "sources\download-hashes.json") -Encoding UTF8
Write-Output "Public sources downloaded and hashed -> $Raw"
