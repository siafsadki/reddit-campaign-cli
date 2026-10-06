param(
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Write-Step([string]$Message) {
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Ask-YesNo([string]$Question, [bool]$Default = $false) {
    $suffix = if ($Default) { "[Y/n]" } else { "[y/N]" }
    while ($true) {
        $answer = Read-Host "$Question $suffix"
        if ([string]::IsNullOrWhiteSpace($answer)) { return $Default }
        if ($answer -match "^(y|yes|oui|نعم)$") { return $true }
        if ($answer -match "^(n|no|non|لا)$") { return $false }
        Write-Host "Please answer y/yes or n/no." -ForegroundColor Yellow
    }
}

function Run-Python([string[]]$Arguments) {
    & $script:PythonExe @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Python command failed with exit code $LASTEXITCODE."
    }
}

function Find-Python {
    $candidates = @(
        "py",
        "python",
        "C:\Users\bertn\AppData\Local\Python\pythoncore-3.14-64\python.exe"
    )
    foreach ($candidate in $candidates) {
        try {
            if ($candidate -in @("py", "python")) {
                $command = Get-Command $candidate -ErrorAction SilentlyContinue
                if (-not $command) { continue }
                $script:PythonExe = $candidate
            } else {
                if (-not (Test-Path $candidate)) { continue }
                $script:PythonExe = $candidate
            }
            $version = & $script:PythonExe -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
            $parts = $version.Trim().Split(".")
            if ([int]$parts[0] -gt 3 -or ([int]$parts[0] -eq 3 -and [int]$parts[1] -ge 11)) {
                Write-Host "Python $($version.Trim()) found: $script:PythonExe" -ForegroundColor Green
                return
            }
        } catch {
            continue
        }
    }
    throw "Python 3.11 or newer was not found."
}

Write-Host "Reddit Campaign CLI - guided startup" -ForegroundColor Green
Write-Host "No Reddit action will run without your confirmation."

Write-Step "Checking Python"
Find-Python

Write-Step "Checking dependencies"
$missing = @()
foreach ($module in @("click", "rich", "websockets")) {
    & $script:PythonExe -c "import $module" 2>$null
    if ($LASTEXITCODE -ne 0) { $missing += $module }
}
if ($missing.Count -gt 0) {
    Write-Host "Missing packages: $($missing -join ', ')" -ForegroundColor Yellow
    if (-not (Ask-YesNo "Install project dependencies now?" $true)) {
        throw "Dependencies are required before the application can run."
    }
    Run-Python @("-m", "pip", "install", "-e", ".")
} else {
    Write-Host "Dependencies are installed." -ForegroundColor Green
}

Write-Step "Checking campaign configuration"
if (-not (Test-Path "campaign.toml")) {
    if (Ask-YesNo "campaign.toml is missing. Create it from the example?" $true) {
        Copy-Item "campaign.example.toml" "campaign.toml"
        Write-Host "Created campaign.toml. Edit it with your product and Reddit details." -ForegroundColor Yellow
        if (-not (Ask-YesNo "Have you finished editing campaign.toml?" $false)) {
            Write-Host "Pause here. Edit campaign.toml and run this script again." -ForegroundColor Yellow
            exit 0
        }
    } else {
        throw "campaign.toml is required for campaign execution."
    }
}

Write-Step "Checking the Chrome extension"
Write-Host "Load this folder in chrome://extensions using 'Load unpacked':"
Write-Host (Join-Path $PSScriptRoot "extension") -ForegroundColor White
if (-not (Ask-YesNo "Is the extension loaded and enabled in Chrome?" $false)) {
    if (Ask-YesNo "Open chrome://extensions now?" $true) {
        Start-Process "chrome.exe" "chrome://extensions"
    }
    Write-Host "Load/reload the extension, then run this script again." -ForegroundColor Yellow
    exit 0
}

Write-Step "Checking the local WebSocket connection"
Write-Host "The Python server starts only when browser mode is launched."
Write-Host "Keep Chrome open and make sure Reddit is logged in."
if (-not (Ask-YesNo "Start a safe dry-run now (no posting)?" $true)) {
    Write-Host "Startup cancelled before browser access." -ForegroundColor Yellow
    exit 0
}

$env:PYTHONIOENCODING = "utf-8"
Run-Python @("main.py", "browser", "--dry-run")

if ($DryRun) {
    Write-Host "Dry-run completed. No real campaign was started." -ForegroundColor Green
    exit 0
}

Write-Step "Starting the real campaign"
Write-Host "The next command may browse Reddit and publish comments/posts according to campaign.toml." -ForegroundColor Yellow
if (-not (Ask-YesNo "Proceed with real Reddit actions?" $false)) {
    Write-Host "Safe stop. Nothing was posted." -ForegroundColor Green
    exit 0
}

Run-Python @("main.py", "browser")
