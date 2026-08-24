param(
    [string]$Output = "output\four_track_fractal_posters_v1_run_01"
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$ffmpegBin = "C:\ProgramData\miniconda3\envs\earth\Library\bin"
if (-not (Test-Path (Join-Path $ffmpegBin "ffmpeg.exe"))) {
    throw "ffmpeg.exe not found: $ffmpegBin"
}

$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    throw "Virtualenv Python not found: $venvPython"
}

$env:Path = "$ffmpegBin;$env:Path"

& $venvPython "tools\render_d1_four_track_fractal_batch.py" `
    --inventory "corpus\inventory\audio_source_inventory.v1.json" `
    --sources `
        "08. Monkberry Moon Delight.mp3" `
        "12 - Sunny Afternoon.mp3" `
        "19 - Picture Book.mp3" `
        "Road_Trip.mp3" `
    --output $Output

if ($LASTEXITCODE -ne 0) {
    throw "Four-track fractal batch failed with exit code $LASTEXITCODE"
}

$manifest = Join-Path $repoRoot (Join-Path $Output "batch_manifest.json")
if (-not (Test-Path $manifest)) {
    throw "Batch completed but batch_manifest.json is missing: $manifest"
}

$svgFiles = Get-ChildItem (Join-Path $repoRoot $Output) -Recurse -Filter "poster.fractal.svg"
if ($svgFiles.Count -ne 4) {
    throw "Expected exactly 4 fractal SVG posters; found $($svgFiles.Count)"
}

foreach ($svg in $svgFiles) {
    if ($svg.Length -le 0) {
        throw "Empty SVG: $($svg.FullName)"
    }

    $content = Get-Content -Raw $svg.FullName
    if ($content -match "DIAGNOSTIC LOCAL|NOT A SPECTROGRAM|eight_axis_scalar_bar_map") {
        throw "Diagnostic chart was emitted instead of fractal poster: $($svg.FullName)"
    }
}

Write-Host ""
Write-Host "SUCCESS: four fractal posters created." -ForegroundColor Green
Write-Host "Manifest: $manifest" -ForegroundColor Green

$svgFiles | Select-Object FullName, Length
Get-Content -Raw $manifest
