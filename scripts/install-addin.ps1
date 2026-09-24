<#
.SYNOPSIS
    Builds and installs the RevitPy host add-in for the current user.

.DESCRIPTION
    Builds src/RevitPy.Addin for the requested Revit version (unless -SkipBuild),
    copies the output to %APPDATA%\Autodesk\Revit\Addins\<version>\RevitPy\ and
    writes the RevitPy.addin manifest next to it. Optionally creates
    %APPDATA%\RevitPy\settings.ini pointing at a Python installation.

.PARAMETER RevitVersion
    2024, 2025, 2026 or 2027.

.PARAMETER PythonDll
    Optional full path to python3XX.dll (CPython 3.11-3.14, x64) to record in
    settings.ini. Without it the add-in searches PATH and per-user Python installs.

.PARAMETER PythonPath
    Optional extra sys.path entry, typically a virtual environment's
    Lib\site-packages that has revitpy installed.

.EXAMPLE
    ./scripts/install-addin.ps1 -RevitVersion 2025 -PythonPath C:\dev\revitpy\.venv\Lib\site-packages
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("2024", "2025", "2026", "2027")]
    [string]$RevitVersion,

    [string]$PythonDll,

    [string]$PythonPath,

    [string]$Configuration = "Release",

    [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$project = Join-Path $repoRoot "src\RevitPy.Addin\RevitPy.Addin.csproj"
$buildOutput = Join-Path $repoRoot "src\RevitPy.Addin\bin\$Configuration\$RevitVersion"

if (-not $SkipBuild) {
    dotnet build $project -c $Configuration "-p:RevitVersion=$RevitVersion"
    if ($LASTEXITCODE -ne 0) { throw "Build failed" }
}

if (-not (Test-Path (Join-Path $buildOutput "RevitPy.Addin.dll"))) {
    throw "Build output not found in $buildOutput"
}

$addinsRoot = Join-Path $env:APPDATA "Autodesk\Revit\Addins\$RevitVersion"
$target = Join-Path $addinsRoot "RevitPy"
New-Item -ItemType Directory -Force -Path $target | Out-Null
Copy-Item -Path (Join-Path $buildOutput "*.dll") -Destination $target -Force
Copy-Item -Path (Join-Path $repoRoot "src\RevitPy.Addin\RevitPy.addin") -Destination $addinsRoot -Force
Write-Host "Installed RevitPy add-in to $target"

$settingsDir = Join-Path $env:APPDATA "RevitPy"
$settingsFile = Join-Path $settingsDir "settings.ini"
if (($PythonDll -or $PythonPath) -and -not (Test-Path $settingsFile)) {
    New-Item -ItemType Directory -Force -Path $settingsDir | Out-Null
    $lines = @("# RevitPy add-in settings")
    if ($PythonDll) { $lines += "python_dll = $PythonDll" }
    if ($PythonPath) { $lines += "python_path = $PythonPath" }
    $lines | Set-Content -Path $settingsFile -Encoding UTF8
    Write-Host "Wrote $settingsFile"
}
elseif (Test-Path $settingsFile) {
    Write-Host "Keeping existing $settingsFile"
}

Write-Host "Restart Revit $RevitVersion; the 'RevitPy' ribbon tab provides Run Script and MCP Server."
