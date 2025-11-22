#Requires -Version 5.1
#Requires -RunAsAdministrator

<#
.SYNOPSIS
    Build script for RevitPy enterprise installer

.DESCRIPTION
    This script orchestrates the complete build process for the RevitPy installer system:
    - Builds the main .NET solution
    - Compiles custom actions assembly
    - Creates WiX installer packages
    - Generates MSI transforms
    - Builds bootstrap installer
    - Runs automated tests
    - Packages final distribution

.PARAMETER Configuration
    Build configuration (Debug or Release)

.PARAMETER Platform
    Target platform (x64, AnyCPU)

.PARAMETER SkipTests
    Skip automated testing

.PARAMETER SignCode
    Sign assemblies and installer packages

.PARAMETER CertificateThumbprint
    Code signing certificate thumbprint

.EXAMPLE
    .\build-installer.ps1 -Configuration Release -Platform x64

.EXAMPLE
    .\build-installer.ps1 -Configuration Release -SignCode -CertificateThumbprint "ABC123..."
#>

[CmdletBinding()]
param(
    [Parameter()]
    [ValidateSet("Debug", "Release")]
    [string]$Configuration = "Release",

    [Parameter()]
    [ValidateSet("x64", "AnyCPU")]
    [string]$Platform = "x64",

    [Parameter()]
    [switch]$SkipTests,

    [Parameter()]
    [switch]$SignCode,

    [Parameter()]
    [string]$CertificateThumbprint = "",

    [Parameter()]
    [string]$OutputPath = ".\dist",

    [Parameter()]
    [switch]$Clean
)

# Build configuration
$script:BuildStartTime = Get-Date
$script:BuildErrors = @()
$script:BuildWarnings = @()

function Write-BuildLog {
    param(
        [string]$Message,
        [ValidateSet("Info", "Warning", "Error", "Success")]
        [string]$Level = "Info"
    )

    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $prefix = "[$timestamp] [$Level]"

    switch ($Level) {
        "Info" { Write-Host "$prefix $Message" -ForegroundColor White }
        "Warning" {
            Write-Host "$prefix $Message" -ForegroundColor Yellow
            $script:BuildWarnings += $Message
        }
        "Error" {
            Write-Host "$prefix $Message" -ForegroundColor Red
            $script:BuildErrors += $Message
        }
        "Success" { Write-Host "$prefix $Message" -ForegroundColor Green }
    }
}

function Test-Prerequisites {
    Write-BuildLog "Checking build prerequisites..." -Level Info

    $prerequisites = @{
        "Administrator Rights" = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
        "MSBuild Available" = $null -ne (Get-Command "msbuild.exe" -ErrorAction SilentlyContinue)
        "WiX Toolset" = Test-Path "${env:ProgramFiles(x86)}\WiX Toolset*" -or Test-Path "${env:ProgramFiles}\WiX Toolset*"
        ".NET Framework 4.8" = $null -ne (Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full\" -Name Release -ErrorAction SilentlyContinue)
        "Solution File" = Test-Path "..\RevitPy.sln"
    }

    if ($SignCode -and -not $CertificateThumbprint) {
        $prerequisites["Code Signing Certificate"] = $false
        Write-BuildLog "Code signing requested but no certificate thumbprint provided" -Level Error
    }
    elseif ($SignCode) {
        $cert = Get-ChildItem "Cert:\CurrentUser\My\$CertificateThumbprint" -ErrorAction SilentlyContinue
        $prerequisites["Code Signing Certificate"] = $null -ne $cert
    }

    $failed = $prerequisites.GetEnumerator() | Where-Object { -not $_.Value }

    if ($failed) {
        Write-BuildLog "Prerequisites failed:" -Level Error
        $failed | ForEach-Object { Write-BuildLog "  - $($_.Key)" -Level Error }
        throw "Prerequisites not met"
    }

    Write-BuildLog "All prerequisites met" -Level Success
}

function Initialize-BuildEnvironment {
    Write-BuildLog "Initializing build environment..." -Level Info

    # Clean output directory
    if ($Clean -and (Test-Path $OutputPath)) {
        Remove-Item $OutputPath -Recurse -Force
    }

    if (-not (Test-Path $OutputPath)) {
        New-Item -Path $OutputPath -ItemType Directory -Force | Out-Null
    }

    # Set up build directories
    $buildDirs = @(
        "bin"
        "obj"
        "temp"
        "packages"
        "transforms"
        "tests"
    )

    foreach ($dir in $buildDirs) {
        $fullPath = Join-Path $OutputPath $dir
        if (-not (Test-Path $fullPath)) {
            New-Item -Path $fullPath -ItemType Directory -Force | Out-Null
        }
    }

    Write-BuildLog "Build environment initialized" -Level Success
}

function Build-Solution {
    Write-BuildLog "Building RevitPy solution..." -Level Info

    try {
        $solutionPath = Resolve-Path "..\RevitPy.sln"

        # Restore NuGet packages
        Write-BuildLog "Restoring NuGet packages..." -Level Info
        $restoreResult = & nuget restore $solutionPath
        if ($LASTEXITCODE -ne 0) {
            throw "NuGet restore failed"
        }

        # Build solution
        $msbuildArgs = @(
            $solutionPath
            "/p:Configuration=$Configuration"
            "/p:Platform=`"Any CPU`""
            "/verbosity:minimal"
            "/maxcpucount"
        )

        Write-BuildLog "Running MSBuild..." -Level Info
        $buildResult = & msbuild @msbuildArgs

        if ($LASTEXITCODE -ne 0) {
            throw "Solution build failed with exit code $LASTEXITCODE"
        }

        Write-BuildLog "Solution build completed successfully" -Level Success
    }
    catch {
        Write-BuildLog "Solution build failed: $($_.Exception.Message)" -Level Error
        throw
    }
}

function Build-CustomActions {
    Write-BuildLog "Building custom actions assembly..." -Level Info

    try {
        $customActionsProject = ".\customactions\CustomActions.csproj"

        $msbuildArgs = @(
            $customActionsProject
            "/p:Configuration=$Configuration"
            "/p:Platform=AnyCPU"
            "/verbosity:minimal"
        )

        $buildResult = & msbuild @msbuildArgs

        if ($LASTEXITCODE -ne 0) {
            throw "Custom actions build failed with exit code $LASTEXITCODE"
        }

        # Copy custom actions to output
        $customActionsOutput = ".\customactions\bin\$Configuration\CustomActions.CA.dll"
        if (Test-Path $customActionsOutput) {
            Copy-Item $customActionsOutput (Join-Path $OutputPath "bin") -Force
            Write-BuildLog "Custom actions built successfully" -Level Success
        }
        else {
            throw "Custom actions output not found: $customActionsOutput"
        }
    }
    catch {
        Write-BuildLog "Custom actions build failed: $($_.Exception.Message)" -Level Error
        throw
    }
}

function Build-MSIPackage {
    Write-BuildLog "Building MSI package..." -Level Info

    try {
        $installerProject = ".\RevitPy.Installer.wixproj"

        # Use dotnet CLI for WiX v4
        $buildArgs = @(
            "build"
            $installerProject
            "--configuration"
            $Configuration
            "--verbosity"
            "minimal"
        )

        if ($Platform -eq "x64") {
            $buildArgs += @("--property", "Platform=x64")
        }

        $buildResult = & dotnet @buildArgs

        if ($LASTEXITCODE -ne 0) {
            throw "MSI build failed with exit code $LASTEXITCODE"
        }

        # Copy MSI to output
        $msiOutput = ".\bin\$Configuration\RevitPy-1.0.0.msi"
        if (Test-Path $msiOutput) {
            Copy-Item $msiOutput (Join-Path $OutputPath "packages") -Force
            Write-BuildLog "MSI package built successfully" -Level Success
        }
        else {
            throw "MSI output not found: $msiOutput"
        }
    }
    catch {
        Write-BuildLog "MSI build failed: $($_.Exception.Message)" -Level Error
        throw
    }
}

function Build-BootstrapInstaller {
    Write-BuildLog "Building bootstrap installer..." -Level Info

    try {
        $bootstrapProject = ".\bootstrap\RevitPy.Bootstrap.wixproj"

        # Use dotnet CLI for WiX v4
        $buildArgs = @(
            "build"
            $bootstrapProject
            "--configuration"
            $Configuration
            "--verbosity"
            "minimal"
        )

        $buildResult = & dotnet @buildArgs

        if ($LASTEXITCODE -ne 0) {
            throw "Bootstrap build failed with exit code $LASTEXITCODE"
        }

        # Copy bootstrap to output
        $bootstrapOutput = ".\bootstrap\bin\$Configuration\RevitPy-Setup-1.0.0.exe"
        if (Test-Path $bootstrapOutput) {
            Copy-Item $bootstrapOutput (Join-Path $OutputPath "packages") -Force
            Write-BuildLog "Bootstrap installer built successfully" -Level Success
        }
        else {
            throw "Bootstrap output not found: $bootstrapOutput"
        }
    }
    catch {
        Write-BuildLog "Bootstrap build failed: $($_.Exception.Message)" -Level Error
        throw
    }
}

function New-MSITransforms {
    Write-BuildLog "Creating MSI transforms..." -Level Info

    try {
        $msiPath = Join-Path $OutputPath "packages\RevitPy-1.0.0.msi"
        $transformsPath = Join-Path $OutputPath "transforms"

        $transformScript = ".\transforms\Create-MSITransforms.ps1"

        $transformArgs = @{
            MSIPath = $msiPath
            OutputPath = $transformsPath
            OrganizationName = "Enterprise"
        }

        & $transformScript @transformArgs

        if ($LASTEXITCODE -eq 0) {
            Write-BuildLog "MSI transforms created successfully" -Level Success
        }
        else {
            Write-BuildLog "Transform creation failed" -Level Warning
        }
    }
    catch {
        Write-BuildLog "Transform creation failed: $($_.Exception.Message)" -Level Error
        # Don't throw - transforms are optional
    }
}

function Invoke-CodeSigning {
    param([string[]]$FilesToSign)

    if (-not $SignCode -or -not $CertificateThumbprint) {
        return
    }

    Write-BuildLog "Code signing files..." -Level Info

    foreach ($file in $FilesToSign) {
        if (Test-Path $file) {
            try {
                $signTool = "${env:ProgramFiles(x86)}\Windows Kits\10\bin\x64\signtool.exe"
                if (-not (Test-Path $signTool)) {
                    $signTool = "${env:ProgramFiles(x86)}\Microsoft SDKs\Windows\v10.0A\bin\NETFX 4.8 Tools\x64\signtool.exe"
                }

                if (Test-Path $signTool) {
                    $signArgs = @(
                        "sign"
                        "/sha1"
                        $CertificateThumbprint
                        "/t"
                        "http://timestamp.comodoca.com/authenticode"
                        "/fd"
                        "sha256"
                        "/v"
                        $file
                    )

                    & $signTool @signArgs

                    if ($LASTEXITCODE -eq 0) {
                        Write-BuildLog "Signed: $(Split-Path $file -Leaf)" -Level Success
                    }
                    else {
                        Write-BuildLog "Failed to sign: $(Split-Path $file -Leaf)" -Level Warning
                    }
                }
                else {
                    Write-BuildLog "SignTool not found - skipping code signing" -Level Warning
                }
            }
            catch {
                Write-BuildLog "Code signing error for $file : $($_.Exception.Message)" -Level Warning
            }
        }
    }
}

function Invoke-InstallerTesting {
    if ($SkipTests) {
        Write-BuildLog "Skipping automated tests" -Level Info
        return
    }

    Write-BuildLog "Running automated tests..." -Level Info

    try {
        $testScript = ".\testing\Test-RevitPyInstaller.ps1"
        $installerPath = Join-Path $OutputPath "packages\RevitPy-Setup-1.0.0.exe"
        $testOutputPath = Join-Path $OutputPath "tests"

        if (-not (Test-Path $installerPath)) {
            Write-BuildLog "Installer not found for testing: $installerPath" -Level Warning
            return
        }

        $testArgs = @{
            InstallerPath = $installerPath
            TestScope = "Quick"  # Use quick tests for build validation
            OutputPath = $testOutputPath
            CleanupAfterTest = $true
        }

        & $testScript @testArgs

        if ($LASTEXITCODE -eq 0) {
            Write-BuildLog "Automated tests passed" -Level Success
        }
        else {
            Write-BuildLog "Some tests failed - check test reports" -Level Warning
        }
    }
    catch {
        Write-BuildLog "Test execution failed: $($_.Exception.Message)" -Level Warning
    }
}

function New-DistributionPackage {
    Write-BuildLog "Creating distribution package..." -Level Info

    try {
        $distributionPath = Join-Path $OutputPath "RevitPy-Installer-Distribution"

        if (Test-Path $distributionPath) {
            Remove-Item $distributionPath -Recurse -Force
        }

        New-Item -Path $distributionPath -ItemType Directory -Force | Out-Null

        # Copy installer packages
        $packagesSource = Join-Path $OutputPath "packages"
        $packagesDestination = Join-Path $distributionPath "installers"
        Copy-Item $packagesSource $packagesDestination -Recurse -Force

        # Copy transforms
        $transformsSource = Join-Path $OutputPath "transforms"
        if (Test-Path $transformsSource) {
            $transformsDestination = Join-Path $distributionPath "transforms"
            Copy-Item $transformsSource $transformsDestination -Recurse -Force
        }

        # Copy deployment scripts
        $deploymentSource = ".\deployment"
        $deploymentDestination = Join-Path $distributionPath "deployment"
        Copy-Item $deploymentSource $deploymentDestination -Recurse -Force

        # Copy documentation
        $docsSource = ".\docs"
        $docsDestination = Join-Path $distributionPath "docs"
        Copy-Item $docsSource $docsDestination -Recurse -Force

        # Copy test results if available
        $testsSource = Join-Path $OutputPath "tests"
        if (Test-Path $testsSource) {
            $testsDestination = Join-Path $distributionPath "test-reports"
            Copy-Item $testsSource $testsDestination -Recurse -Force
        }

        # Create README for distribution
        $readmeContent = @"
# RevitPy Installer Distribution Package

## Contents

- **installers/**: Main installer packages
  - RevitPy-Setup-1.0.0.exe (Bootstrap installer)
  - RevitPy-1.0.0.msi (MSI package)

- **transforms/**: MSI transform files for customization
  - Enterprise-Silent.mst
  - Developer-Workstation.mst
  - Revit2024-Only.mst
  - Minimal-Installation.mst

- **deployment/**: PowerShell scripts and Group Policy templates
  - Deploy-RevitPy.ps1 (Enterprise deployment script)
  - Group-Policy-Template.xml
  - RevitPy.admx (Administrative template)

- **docs/**: Comprehensive documentation
  - RevitPy-Installer-Guide.md (Complete installation guide)

- **test-reports/**: Automated test results (if tests were run)

## Quick Start

For end users:
```
.\installers\RevitPy-Setup-1.0.0.exe
```

For enterprise deployment:
```
.\deployment\Deploy-RevitPy.ps1 -Action Install -TargetComputers @("PC001", "PC002") -Silent
```

For more information, see docs/RevitPy-Installer-Guide.md

---
Generated on $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
Build Configuration: $Configuration
"@

        Set-Content -Path (Join-Path $distributionPath "README.md") -Value $readmeContent -Encoding UTF8

        # Create distribution archive
        $archivePath = Join-Path $OutputPath "RevitPy-Installer-$Configuration-$(Get-Date -Format 'yyyyMMdd').zip"
        Compress-Archive -Path $distributionPath -DestinationPath $archivePath -Force

        Write-BuildLog "Distribution package created: $archivePath" -Level Success
    }
    catch {
        Write-BuildLog "Distribution package creation failed: $($_.Exception.Message)" -Level Error
        throw
    }
}

function Write-BuildSummary {
    $buildDuration = ((Get-Date) - $script:BuildStartTime).TotalMinutes

    Write-BuildLog "Build Summary:" -Level Info
    Write-BuildLog "  Configuration: $Configuration" -Level Info
    Write-BuildLog "  Platform: $Platform" -Level Info
    Write-BuildLog "  Duration: $([math]::Round($buildDuration, 2)) minutes" -Level Info
    Write-BuildLog "  Warnings: $($script:BuildWarnings.Count)" -Level $(if ($script:BuildWarnings.Count -gt 0) { "Warning" } else { "Info" })
    Write-BuildLog "  Errors: $($script:BuildErrors.Count)" -Level $(if ($script:BuildErrors.Count -gt 0) { "Error" } else { "Info" })

    if ($script:BuildWarnings) {
        Write-BuildLog "Build Warnings:" -Level Warning
        $script:BuildWarnings | ForEach-Object { Write-BuildLog "  - $_" -Level Warning }
    }

    if ($script:BuildErrors) {
        Write-BuildLog "Build Errors:" -Level Error
        $script:BuildErrors | ForEach-Object { Write-BuildLog "  - $_" -Level Error }
    }

    $outputFiles = Get-ChildItem $OutputPath -Recurse -File | Measure-Object
    Write-BuildLog "Output files created: $($outputFiles.Count)" -Level Info
    Write-BuildLog "Output directory: $(Resolve-Path $OutputPath)" -Level Info

    if ($script:BuildErrors.Count -eq 0) {
        Write-BuildLog "BUILD SUCCEEDED" -Level Success
        return 0
    }
    else {
        Write-BuildLog "BUILD FAILED" -Level Error
        return 1
    }
}

# Main build execution
try {
    Write-BuildLog "Starting RevitPy installer build..." -Level Success
    Write-BuildLog "Configuration: $Configuration, Platform: $Platform" -Level Info

    Test-Prerequisites
    Initialize-BuildEnvironment
    Build-Solution
    Build-CustomActions
    Build-MSIPackage
    Build-BootstrapInstaller
    New-MSITransforms

    # Sign code if requested
    if ($SignCode) {
        $filesToSign = @(
            (Join-Path $OutputPath "packages\RevitPy-1.0.0.msi")
            (Join-Path $OutputPath "packages\RevitPy-Setup-1.0.0.exe")
        )
        Invoke-CodeSigning -FilesToSign $filesToSign
    }

    Invoke-InstallerTesting
    New-DistributionPackage

    exit (Write-BuildSummary)
}
catch {
    Write-BuildLog "Build failed with exception: $($_.Exception.Message)" -Level Error
    Write-BuildLog "Stack trace: $($_.ScriptStackTrace)" -Level Error
    exit 1
}
