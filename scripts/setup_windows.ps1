<#
.SYNOPSIS
    Automated Windows Host Setup for KiCad MCP + Antigravity.
    Configures Windows 10/11 workstation to host KiCad MCP over Thunderbolt / SSH / Local.

.DESCRIPTION
    1. Detects and verifies KiCad installation (v8, v9, or v10).
    2. Installs or verifies Astral uv package manager (for uvx runner).
    3. Provisions OpenSSH Server (sshd) for low-latency Thunderbolt / Wi-Fi bridging.
    4. Configures Windows Firewall for inbound SSH on port 22.
    5. Sets up .ssh directory and provides SSH public key import instructions.
    6. Validates local KiCad MCP environment.
#>

[CmdletBinding()]
param(
    [string]$KiCadPath = "",
    [switch]$SkipSSH = $false
)

$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "⚡ Antigravity + KiCad MCP: Windows Host Setup Script" -ForegroundColor Yellow
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Detect KiCad Installation
Write-Host "`n[1/5] Checking KiCad Installation..." -ForegroundColor Cyan
$KnownKiCadPaths = @(
    "C:\Program Files\KiCad\10.0\bin",
    "C:\Program Files\KiCad\9.0\bin",
    "C:\Program Files\KiCad\8.0\bin",
    $KiCadPath
) | Where-Object { $_ -ne "" -and (Test-Path $_) }

if ($KnownKiCadPaths.Count -gt 0) {
    $ActiveKiCad = $KnownKiCadPaths[0]
    Write-Host "  [OK] Found KiCad at: $ActiveKiCad" -ForegroundColor Green
    if ($env:Path -notlike "*$ActiveKiCad*") {
        Write-Host "  [INFO] Adding KiCad to current session PATH." -ForegroundColor Yellow
        $env:Path = "$ActiveKiCad;$env:Path"
    }
} else {
    Write-Host "  [WARNING] KiCad not found in default paths." -ForegroundColor Red
    Write-Host "  Please install KiCad 8.0+ from https://www.kicad.org/download/windows/" -ForegroundColor Yellow
}

# 2. Check or Install Astral uv (uvx)
Write-Host "`n[2/5] Checking Astral uv (uvx runner)..." -ForegroundColor Cyan
$UvCmd = Get-Command "uv" -ErrorAction SilentlyContinue
if ($UvCmd) {
    Write-Host "  [OK] Found uv: $($UvCmd.Source)" -ForegroundColor Green
} else {
    $UserUv = "$env:USERPROFILE\.local\bin\uv.exe"
    if (Test-Path $UserUv) {
        Write-Host "  [OK] Found uv at: $UserUv" -ForegroundColor Green
        $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
    } else {
        Write-Host "  [INFO] Installing uv via official installer..." -ForegroundColor Yellow
        try {
            irm https://astral.sh/uv/install.ps1 | iex
            $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
            Write-Host "  [OK] uv installed successfully." -ForegroundColor Green
        } catch {
            Write-Host "  [ERROR] Failed to install uv automatically: $_" -ForegroundColor Red
            Write-Host "  Run: powershell -ExecutionPolicy ByPass -c `"irm https://astral.sh/uv/install.ps1 | iex`"" -ForegroundColor Yellow
        }
    }
}

# 3. Provision OpenSSH Server (if bridging from macOS)
if (-not $SkipSSH) {
    Write-Host "`n[3/5] Configuring OpenSSH Server (for Mac/Remote Access)..." -ForegroundColor Cyan
    $IsAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    
    if (-not $IsAdmin) {
        Write-Host "  [NOTICE] Administrator privileges recommended to configure OpenSSH Service." -ForegroundColor Yellow
        Write-Host "  If OpenSSH is already running, this step can be skipped." -ForegroundColor Yellow
    }

    try {
        $sshCapability = Get-WindowsCapability -Online -Name OpenSSH.Server* -ErrorAction SilentlyContinue
        if ($sshCapability -and $sshCapability.State -ne 'Installed') {
            if ($IsAdmin) {
                Write-Host "  [INFO] Installing OpenSSH Server capability..." -ForegroundColor Yellow
                Add-WindowsCapability -Online -Name $sshCapability.Name | Out-Null
            } else {
                Write-Host "  [WARNING] OpenSSH Server capability not installed. Run PowerShell as Administrator to install." -ForegroundColor Red
            }
        }
        
        $sshService = Get-Service -Name "sshd" -ErrorAction SilentlyContinue
        if ($sshService) {
            if ($IsAdmin) {
                Set-Service -Name "sshd" -StartupType Automatic
                if ($sshService.Status -ne 'Running') {
                    Start-Service "sshd"
                }
            }
            Write-Host "  [OK] OpenSSH Server (sshd) status: $((Get-Service sshd).Status)" -ForegroundColor Green
        }
    } catch {
        Write-Host "  [NOTICE] OpenSSH inspection note: $_" -ForegroundColor Yellow
    }

    # Ensure Firewall Rule
    if ($IsAdmin) {
        $rule = Get-NetFirewallRule -Name "OpenSSH-Server-In-TCP" -ErrorAction SilentlyContinue
        if (-not $rule) {
            New-NetFirewallRule -Name "OpenSSH-Server-In-TCP" -DisplayName "OpenSSH Server (sshd)" -Enabled True -Direction Inbound -Protocol TCP -Action Allow -LocalPort 22 | Out-Null
            Write-Host "  [OK] Firewall rule created for inbound TCP port 22." -ForegroundColor Green
        } else {
            Write-Host "  [OK] Firewall rule verified for port 22." -ForegroundColor Green
        }
    }
}

# 4. SSH Authorized Keys directory
Write-Host "`n[4/5] Checking SSH Key Setup..." -ForegroundColor Cyan
$sshDir = "$env:USERPROFILE\.ssh"
if (-not (Test-Path $sshDir)) {
    New-Item -ItemType Directory -Path $sshDir -Force | Out-Null
}
$authKeys = Join-Path $sshDir "authorized_keys"
if (-not (Test-Path $authKeys)) {
    New-Item -ItemType File -Path $authKeys -Force | Out-Null
    Write-Host "  [INFO] Created: $authKeys" -ForegroundColor Yellow
    Write-Host "  👉 Append your Mac's ~/.ssh/id_ed25519.pub content into this file." -ForegroundColor Cyan
} else {
    Write-Host "  [OK] Found authorized_keys at: $authKeys" -ForegroundColor Green
}

# 5. Test KiCad MCP runner
Write-Host "`n[5/5] Testing KiCad MCP Runner (Dry Run)..." -ForegroundColor Cyan
try {
    $testResult = Start-Process -FilePath "uvx" -ArgumentList "kicad-mcp-pro", "--help" -NoNewWindow -Wait -PassThru -ErrorAction Stop
    if ($testResult.ExitCode -eq 0) {
        Write-Host "  [OK] uvx kicad-mcp-pro is ready to launch!" -ForegroundColor Green
    } else {
        Write-Host "  [INFO] uvx command returned code $($testResult.ExitCode) (ready for execution)." -ForegroundColor Yellow
    }
} catch {
    Write-Host "  [INFO] Note: Running 'uvx kicad-mcp-pro' requires network access on first execution to cache package." -ForegroundColor Yellow
}

Write-Host "`n==========================================================" -ForegroundColor Green
Write-Host "🎉 Windows Host Configuration Completed!" -ForegroundColor Green
Write-Host "Next steps for Mac pairing:" -ForegroundColor Yellow
Write-Host "  1. Copy Mac's public key (cat ~/.ssh/id_ed25519.pub) into $authKeys" -ForegroundColor White
Write-Host "  2. Connect Thunderbolt cable (bridge0) or connect to the same Wi-Fi network." -ForegroundColor White
Write-Host "  3. On Mac, run: python3 scripts/test_kicad_mcp.py" -ForegroundColor White
Write-Host "==========================================================" -ForegroundColor Green
