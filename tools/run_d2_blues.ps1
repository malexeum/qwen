param(
    [string]$Seed = "d2-blues-v1",
    [string]$OutputDir = "artifacts/d2/posters"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$svg = Join-Path $OutputDir "d2_blues_v1_poster.svg"
$metadata = Join-Path $OutputDir "d2_blues_v1_poster.metadata.json"

python -m py_compile tools/blues_d2_physical_layers.py tools/render_d2_blues_poster.py
python -m pytest tests/test_d2_blues_poster.py -q
python tools/render_d2_blues_poster.py --seed $Seed --svg-output $svg --metadata-output $metadata

if (-not (Test-Path $svg)) { throw "Missing SVG: $svg" }
if (-not (Test-Path $metadata)) { throw "Missing metadata: $metadata" }

Write-Host "D2 Blues SVG: $svg"
Write-Host "D2 Blues metadata: $metadata"
