#Requires -Version 5.1
#Requires -RunAsAdministrator

<#
.SYNOPSIS
    Enterprise deployment script for RevitPy installer

.DESCRIPTION
    This script provides enterprise deployment capabilities for RevitPy including:
    - Silent installation across multiple machines
    - Group Policy deployment support
    - Configuration management
    - Logging and reporting
    - Rollback capabilities

.PARAMETER Action
    The deployment action to perform (Install, Uninstall, Update, Configure)

.PARAMETER ConfigFile
    Path to organization-specific configuration file

.PARAMETER TargetComputers
    Array of computer names to deploy to (default: local computer)

.PARAMETER RevitVersions
    Comma-separated list of Revit versions to configure (e.g., "2023,2024,2025")

.PARAMETER Silent
    Perform silent installation without user interaction

.PARAMETER LogPath
    Path for deployment logs (default: current directory)

.PARAMETER MSITransform
    Path to MSI transform file for customization

.EXAMPLE
    .\Deploy-RevitPy.ps1 -Action Install -Silent

.EXAMPLE
    .\Deploy-RevitPy.ps1 -Action Install -TargetComputers @("PC001", "PC002") -RevitVersions "2024,2025"

.EXAMPLE
    .\Deploy-RevitPy.ps1 -Action Configure -ConfigFile "\\server\share\revitpy-config.yaml"
#>

[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("Install", "Uninstall", "Update", "Configure", "Repair")]
    [string]$Action,

    [Parameter()]
    [string]$ConfigFile = "",

    [Parameter()]
    [string[]]$TargetComputers = @($env:COMPUTERNAME),

    [Parameter()]
    [string]$RevitVersions = "",

    [Parameter()]
    [switch]$Silent,

    [Parameter()]
    [string]$LogPath = ".\logs",

    [Parameter()]
    [string]$MSITransform = "",

    [Parameter()]
    [string]$InstallerPath = ".\RevitPy-Setup-1.0.0.exe",

    [Parameter()]
    [int]$MaxConcurrentDeployments = 5,

    [Parameter()]
    [int]$TimeoutMinutes = 30,

    [Parameter()]
    [switch]$WhatIf
)

# Script configuration
$script:ScriptVersion = "1.0.0"
$script:LogFile = ""
$script:DeploymentResults = @()

# Initialize logging
function Initialize-Logging {
    param([string]$LogPath)
    
    if (-not (Test-Path $LogPath)) {
        New-Item -Path $LogPath -ItemType Directory -Force | Out-Null
    }
    
    $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $script:LogFile = Join-Path $LogPath "RevitPy-Deployment-$timestamp.log"
    
    Write-Log "RevitPy Enterprise Deployment Script v$script:ScriptVersion" -Level Info
    Write-Log "Action: $Action" -Level Info
    Write-Log "Target Computers: $($TargetComputers -join ', ')" -Level Info
    Write-Log "Log File: $script:LogFile" -Level Info
}

# Logging function
function Write-Log {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Message,
        
        [Parameter()]
        [ValidateSet("Info", "Warning", "Error", "Debug")]
        [string]$Level = "Info",
        
        [Parameter()]
        [string]$Computer = $env:COMPUTERNAME
    )
    
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logEntry = "[$timestamp] [$Level] [$Computer] $Message"
    
    # Write to console with color coding
    switch ($Level) {
        "Info" { Write-Host $logEntry -ForegroundColor Green }
        "Warning" { Write-Host $logEntry -ForegroundColor Yellow }
        "Error" { Write-Host $logEntry -ForegroundColor Red }
        "Debug" { Write-Host $logEntry -ForegroundColor Gray }
    }
    
    # Write to log file
    if ($script:LogFile) {
        Add-Content -Path $script:LogFile -Value $logEntry -Encoding UTF8
    }
}

# Test prerequisites
function Test-Prerequisites {
    param([string]$Computer)
    
    Write-Log "Testing prerequisites on $Computer" -Computer $Computer
    
    $prerequisites = @{
        "PowerShell 5.1+" = $PSVersionTable.PSVersion.Major -ge 5
        "Administrator Rights" = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
        "Network Connectivity" = Test-Connection -ComputerName $Computer -Count 1 -Quiet
        "WMI Access" = $null
        "Installer File" = Test-Path $InstallerPath
    }
    
    # Test WMI access for remote computers
    if ($Computer -ne $env:COMPUTERNAME) {
        try {
            Get-WmiObject -Class Win32_OperatingSystem -ComputerName $Computer -ErrorAction Stop | Out-Null
            $prerequisites["WMI Access"] = $true
        }
        catch {
            $prerequisites["WMI Access"] = $false
        }
    }
    else {
        $prerequisites["WMI Access"] = $true
    }
    
    $failedPrerequisites = $prerequisites.GetEnumerator() | Where-Object { -not $_.Value }
    
    if ($failedPrerequisites) {
        Write-Log "Prerequisites failed on $Computer :" -Level Error -Computer $Computer
        $failedPrerequisites | ForEach-Object {
            Write-Log "  - $($_.Key)" -Level Error -Computer $Computer
        }
        return $false
    }
    
    Write-Log "All prerequisites met on $Computer" -Level Info -Computer $Computer
    return $true
}

# Install RevitPy
function Install-RevitPy {
    param(
        [string]$Computer,
        [string]$InstallerPath,
        [string]$RevitVersions,
        [string]$MSITransform,
        [bool]$Silent
    )
    
    Write-Log "Starting RevitPy installation on $Computer" -Computer $Computer
    
    $installArgs = @()
    
    if ($Silent) {
        $installArgs += "/quiet"
    }
    
    if ($RevitVersions) {
        $installArgs += "REVIT_VERSIONS=`"$RevitVersions`""
    }
    
    if ($MSITransform) {
        $installArgs += "TRANSFORMS=`"$MSITransform`""
    }
    
    $argumentList = $installArgs -join " "
    
    try {
        if ($Computer -eq $env:COMPUTERNAME) {
            # Local installation
            $process = Start-Process -FilePath $InstallerPath -ArgumentList $argumentList -Wait -PassThru -NoNewWindow
        }
        else {
            # Remote installation using Invoke-Command
            $scriptBlock = {
                param($InstallerPath, $ArgumentList)
                $process = Start-Process -FilePath $InstallerPath -ArgumentList $ArgumentList -Wait -PassThru -NoNewWindow
                return $process.ExitCode
            }
            
            $exitCode = Invoke-Command -ComputerName $Computer -ScriptBlock $scriptBlock -ArgumentList $InstallerPath, $argumentList
        }
        
        $exitCode = if ($Computer -eq $env:COMPUTERNAME) { $process.ExitCode } else { $exitCode }
        
        if ($exitCode -eq 0) {
            Write-Log "RevitPy installation completed successfully on $Computer" -Level Info -Computer $Computer
            return $true
        }
        else {
            Write-Log "RevitPy installation failed on $Computer with exit code: $exitCode" -Level Error -Computer $Computer
            return $false
        }
    }
    catch {
        Write-Log "RevitPy installation exception on $Computer : $($_.Exception.Message)" -Level Error -Computer $Computer
        return $false
    }
}

# Uninstall RevitPy
function Uninstall-RevitPy {
    param([string]$Computer)
    
    Write-Log "Starting RevitPy uninstallation on $Computer" -Computer $Computer
    
    $scriptBlock = {
        # Find RevitPy in installed programs
        $revitPy = Get-WmiObject -Class Win32_Product | Where-Object { $_.Name -like "*RevitPy*" }
        
        if ($revitPy) {
            try {
                $revitPy.Uninstall()
                return 0
            }
            catch {
                return 1
            }
        }
        else {
            return 2  # Not found
        }
    }
    
    try {
        $result = if ($Computer -eq $env:COMPUTERNAME) {
            & $scriptBlock
        }
        else {
            Invoke-Command -ComputerName $Computer -ScriptBlock $scriptBlock
        }
        
        switch ($result) {
            0 { 
                Write-Log "RevitPy uninstalled successfully on $Computer" -Level Info -Computer $Computer
                return $true
            }
            1 { 
                Write-Log "RevitPy uninstallation failed on $Computer" -Level Error -Computer $Computer
                return $false
            }
            2 { 
                Write-Log "RevitPy not found on $Computer" -Level Warning -Computer $Computer
                return $true
            }
        }
    }
    catch {
        Write-Log "RevitPy uninstallation exception on $Computer : $($_.Exception.Message)" -Level Error -Computer $Computer
        return $false
    }
}

# Configure RevitPy
function Set-RevitPyConfiguration {
    param(
        [string]$Computer,
        [string]$ConfigFile
    )
    
    Write-Log "Configuring RevitPy on $Computer" -Computer $Computer
    
    if (-not $ConfigFile -or -not (Test-Path $ConfigFile)) {
        Write-Log "Configuration file not found: $ConfigFile" -Level Error -Computer $Computer
        return $false
    }
    
    $scriptBlock = {
        param($ConfigContent, $ConfigFile)
        
        $revitPyPath = "${env:ProgramFiles}\RevitPy"
        $configDestination = Join-Path $revitPyPath "config\organization.yaml"
        
        if (Test-Path $revitPyPath) {
            try {
                Set-Content -Path $configDestination -Value $ConfigContent -Encoding UTF8
                return $true
            }
            catch {
                return $false
            }
        }
        else {
            return $false
        }
    }
    
    try {
        $configContent = Get-Content $ConfigFile -Raw
        
        $result = if ($Computer -eq $env:COMPUTERNAME) {
            & $scriptBlock -ConfigContent $configContent -ConfigFile $ConfigFile
        }
        else {
            Invoke-Command -ComputerName $Computer -ScriptBlock $scriptBlock -ArgumentList $configContent, $ConfigFile
        }
        
        if ($result) {
            Write-Log "RevitPy configuration updated successfully on $Computer" -Level Info -Computer $Computer
            return $true
        }
        else {
            Write-Log "RevitPy configuration update failed on $Computer" -Level Error -Computer $Computer
            return $false
        }
    }
    catch {
        Write-Log "RevitPy configuration exception on $Computer : $($_.Exception.Message)" -Level Error -Computer $Computer
        return $false
    }
}

# Process single computer
function Invoke-ComputerDeployment {
    param(
        [string]$Computer,
        [string]$Action,
        [hashtable]$Parameters
    )
    
    $result = @{
        Computer = $Computer
        Action = $Action
        StartTime = Get-Date
        Success = $false
        Message = ""
        EndTime = $null
    }
    
    try {
        # Test prerequisites
        if (-not (Test-Prerequisites -Computer $Computer)) {
            $result.Message = "Prerequisites failed"
            return $result
        }
        
        # Perform action
        switch ($Action) {
            "Install" {
                $result.Success = Install-RevitPy -Computer $Computer -InstallerPath $Parameters.InstallerPath -RevitVersions $Parameters.RevitVersions -MSITransform $Parameters.MSITransform -Silent $Parameters.Silent
            }
            "Uninstall" {
                $result.Success = Uninstall-RevitPy -Computer $Computer
            }
            "Configure" {
                $result.Success = Set-RevitPyConfiguration -Computer $Computer -ConfigFile $Parameters.ConfigFile
            }
            "Repair" {
                $installParams = @{
                    Computer = $Computer
                    InstallerPath = $Parameters.InstallerPath
                    RevitVersions = $Parameters.RevitVersions
                    MSITransform = $Parameters.MSITransform
                    Silent = $true
                }
                # Add repair flag to installer
                $result.Success = Install-RevitPy @installParams
            }
        }
        
        if ($result.Success) {
            $result.Message = "$Action completed successfully"
        }
        else {
            $result.Message = "$Action failed"
        }
    }
    catch {
        $result.Success = $false
        $result.Message = "Exception: $($_.Exception.Message)"
        Write-Log "Deployment exception on $Computer : $($_.Exception.Message)" -Level Error -Computer $Computer
    }
    finally {
        $result.EndTime = Get-Date
    }
    
    return $result
}

# Main deployment function
function Start-Deployment {
    Write-Log "Starting $Action deployment to $($TargetComputers.Count) computer(s)" -Level Info
    
    $deploymentParameters = @{
        InstallerPath = $InstallerPath
        RevitVersions = $RevitVersions
        MSITransform = $MSITransform
        Silent = $Silent.IsPresent
        ConfigFile = $ConfigFile
    }
    
    # Process computers in parallel batches
    $jobs = @()
    $batchSize = [Math]::Min($MaxConcurrentDeployments, $TargetComputers.Count)
    
    for ($i = 0; $i -lt $TargetComputers.Count; $i += $batchSize) {
        $batch = $TargetComputers[$i..([Math]::Min($i + $batchSize - 1, $TargetComputers.Count - 1))]
        
        foreach ($computer in $batch) {
            if ($PSCmdlet.ShouldProcess($computer, $Action)) {
                $job = Start-Job -ScriptBlock {
                    param($Computer, $Action, $Parameters, $Functions)
                    
                    # Re-import functions in job context
                    $Functions.GetEnumerator() | ForEach-Object {
                        Invoke-Expression $_.Value
                    }
                    
                    Invoke-ComputerDeployment -Computer $Computer -Action $Action -Parameters $Parameters
                } -ArgumentList $computer, $Action, $deploymentParameters, $Functions
                
                $jobs += $job
            }
        }
        
        # Wait for current batch to complete before starting next batch
        if ($jobs) {
            $timeoutSeconds = $TimeoutMinutes * 60
            $jobs | Wait-Job -Timeout $timeoutSeconds | Out-Null
            
            # Collect results and clean up completed jobs
            foreach ($job in $jobs) {
                $result = Receive-Job -Job $job
                $script:DeploymentResults += $result
                Remove-Job -Job $job -Force
            }
            $jobs = @()
        }
    }
}

# Generate deployment report
function New-DeploymentReport {
    Write-Log "Generating deployment report" -Level Info
    
    $report = @{
        ScriptVersion = $script:ScriptVersion
        Action = $Action
        StartTime = Get-Date
        TotalComputers = $TargetComputers.Count
        SuccessfulDeployments = ($script:DeploymentResults | Where-Object { $_.Success }).Count
        FailedDeployments = ($script:DeploymentResults | Where-Object { -not $_.Success }).Count
        Results = $script:DeploymentResults
    }
    
    $reportPath = Join-Path $LogPath "RevitPy-Deployment-Report-$(Get-Date -Format 'yyyyMMdd-HHmmss').json"
    $report | ConvertTo-Json -Depth 10 | Out-File $reportPath -Encoding UTF8
    
    Write-Log "Deployment Summary:" -Level Info
    Write-Log "  Total Computers: $($report.TotalComputers)" -Level Info
    Write-Log "  Successful: $($report.SuccessfulDeployments)" -Level Info
    Write-Log "  Failed: $($report.FailedDeployments)" -Level Info
    Write-Log "  Report saved to: $reportPath" -Level Info
    
    # Display failed deployments
    $failedDeployments = $script:DeploymentResults | Where-Object { -not $_.Success }
    if ($failedDeployments) {
        Write-Log "Failed Deployments:" -Level Warning
        $failedDeployments | ForEach-Object {
            Write-Log "  $($_.Computer): $($_.Message)" -Level Error
        }
    }
}

# Export functions for jobs (this is a workaround for the job context)
$Functions = @{
    'Test-Prerequisites' = ${function:Test-Prerequisites}.ToString()
    'Install-RevitPy' = ${function:Install-RevitPy}.ToString()
    'Uninstall-RevitPy' = ${function:Uninstall-RevitPy}.ToString()
    'Set-RevitPyConfiguration' = ${function:Set-RevitPyConfiguration}.ToString()
    'Invoke-ComputerDeployment' = ${function:Invoke-ComputerDeployment}.ToString()
    'Write-Log' = ${function:Write-Log}.ToString()
}

# Main execution
try {
    Initialize-Logging -LogPath $LogPath
    
    # Validate parameters
    if ($Action -in @("Install", "Repair") -and -not (Test-Path $InstallerPath)) {
        throw "Installer file not found: $InstallerPath"
    }
    
    if ($Action -eq "Configure" -and (-not $ConfigFile -or -not (Test-Path $ConfigFile))) {
        throw "Configuration file not found: $ConfigFile"
    }
    
    Start-Deployment
    New-DeploymentReport
    
    Write-Log "Deployment completed" -Level Info
}
catch {
    Write-Log "Deployment failed: $($_.Exception.Message)" -Level Error
    exit 1
}
finally {
    # Cleanup any remaining jobs
    Get-Job | Remove-Job -Force
}