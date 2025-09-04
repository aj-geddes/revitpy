# RevitPy Build Script
param(
    [string]$Configuration = "Debug",
    [string]$Platform = "x64",
    [switch]$RunTests,
    [switch]$Clean,
    [switch]$Restore
)

$ErrorActionPreference = "Stop"

Write-Host "RevitPy Build Script" -ForegroundColor Green
Write-Host "===================" -ForegroundColor Green
Write-Host "Configuration: $Configuration" -ForegroundColor Yellow
Write-Host "Platform: $Platform" -ForegroundColor Yellow
Write-Host ""

# Get script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$SolutionFile = Join-Path $ScriptDir "RevitPy.sln"

try {
    # Clean if requested
    if ($Clean) {
        Write-Host "Cleaning solution..." -ForegroundColor Yellow
        dotnet clean $SolutionFile --configuration $Configuration --verbosity minimal
        if ($LASTEXITCODE -ne 0) { throw "Clean failed" }
        Write-Host "Clean completed successfully" -ForegroundColor Green
    }

    # Restore packages if requested or if this is a clean build
    if ($Restore -or $Clean) {
        Write-Host "Restoring NuGet packages..." -ForegroundColor Yellow
        dotnet restore $SolutionFile --verbosity minimal
        if ($LASTEXITCODE -ne 0) { throw "Restore failed" }
        Write-Host "Restore completed successfully" -ForegroundColor Green
    }

    # Build the solution
    Write-Host "Building solution..." -ForegroundColor Yellow
    $buildArgs = @(
        "build", $SolutionFile,
        "--configuration", $Configuration,
        "--no-restore",
        "--verbosity", "minimal"
    )
    
    if ($Platform -eq "x64") {
        $buildArgs += "--arch", "x64"
    }

    & dotnet @buildArgs
    if ($LASTEXITCODE -ne 0) { throw "Build failed" }
    
    Write-Host "Build completed successfully" -ForegroundColor Green

    # Run tests if requested
    if ($RunTests) {
        Write-Host "Running tests..." -ForegroundColor Yellow
        
        $testArgs = @(
            "test", $SolutionFile,
            "--configuration", $Configuration,
            "--no-build",
            "--verbosity", "normal",
            "--logger", "console;verbosity=detailed"
        )

        & dotnet @testArgs
        if ($LASTEXITCODE -ne 0) { throw "Tests failed" }
        
        Write-Host "All tests passed" -ForegroundColor Green
    }

    Write-Host ""
    Write-Host "Build completed successfully!" -ForegroundColor Green
    Write-Host "Output directory: .\src\{ProjectName}\bin\$Configuration\net6.0" -ForegroundColor Yellow

} catch {
    Write-Host ""
    Write-Host "Build failed: $_" -ForegroundColor Red
    exit 1
}