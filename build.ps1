<#
.SYNOPSIS
    Builds the RevitPy host add-in for one or more Revit versions.
.EXAMPLE
    ./build.ps1                          # all supported versions
    ./build.ps1 -RevitVersion 2025,2026 -Configuration Debug
#>
[CmdletBinding()]
param(
    [ValidateSet("2024", "2025", "2026", "2027")]
    [string[]]$RevitVersion = @("2024", "2025", "2026", "2027"),
    [string]$Configuration = "Release"
)

$ErrorActionPreference = "Stop"
$project = Join-Path $PSScriptRoot "src\RevitPy.Addin\RevitPy.Addin.csproj"

foreach ($version in $RevitVersion) {
    Write-Host "==> Building RevitPy.Addin for Revit $version ($Configuration)"
    # Each Revit version uses a different target framework; clear restore state.
    Remove-Item -Recurse -Force (Join-Path $PSScriptRoot "src\RevitPy.Addin\obj") -ErrorAction SilentlyContinue
    dotnet build $project -c $Configuration "-p:RevitVersion=$version"
    if ($LASTEXITCODE -ne 0) { throw "Build failed for Revit $version" }
}

Write-Host "Output: src\RevitPy.Addin\bin\$Configuration\<version>\"
