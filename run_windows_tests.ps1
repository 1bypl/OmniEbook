$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

$pythonLauncher = Get-Command py -ErrorAction SilentlyContinue
if ($pythonLauncher) {
    & $pythonLauncher.Source -3 -m unittest discover -s tests -p "test_portable.py" -v
} else {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pythonCommand) {
        throw "Python 3 is required. Install Python and add it to PATH."
    }
    & $pythonCommand.Source -m unittest discover -s tests -p "test_portable.py" -v
}

if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
