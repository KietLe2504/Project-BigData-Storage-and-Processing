$ErrorActionPreference = 'Stop'
$script:M5Root = Split-Path -Parent $PSScriptRoot
$script:M5Docker = if ([Environment]::OSVersion.Platform -eq 'Win32NT') {
    (Get-Command docker.exe -ErrorAction Stop).Source
} else {
    (Get-Command docker -ErrorAction Stop).Source
}

if ([Environment]::OSVersion.Platform -eq 'Win32NT') {
    # Support PowerShell launched from WSL, which may inherit Linux PATH or
    # PATHEXT. These changes affect this process only, not Windows settings.
    $M5WindowsPaths = @(
        (Split-Path -Parent $script:M5Docker),
        [Environment]::GetEnvironmentVariable('Path', 'Machine'),
        [Environment]::GetEnvironmentVariable('Path', 'User'),
        $env:PATH
    )
    $env:PATH = $M5WindowsPaths -join ';'
    if ($env:PATHEXT -notmatch '(?i)(^|;)\.EXE(;|$)') {
        $env:PATHEXT = '.COM;.EXE;.BAT;.CMD'
    }
}

function Invoke-M5Compose {
    param([string[]]$Arguments, [string]$LogName = '')
    Push-Location $script:M5Root
    $previousPreference = $ErrorActionPreference
    try {
        # Native stderr includes normal Docker/Spark progress, not just errors.
        $ErrorActionPreference = 'Continue'
        if ($LogName) {
            New-Item -ItemType Directory -Force (Join-Path $script:M5Root 'logs') | Out-Null
            & $script:M5Docker compose -f compose.yml @Arguments 2>&1 |
                ForEach-Object { $_.ToString() } |
                Tee-Object -FilePath (Join-Path $script:M5Root ('logs\' + $LogName))
        } else {
            & $script:M5Docker compose -f compose.yml @Arguments
        }
        $exitCode = $LASTEXITCODE
        if ($null -eq $exitCode -or $exitCode -ne 0) {
            throw "M5 command failed (exit $exitCode). Check logs or docker compose output."
        }
    } finally {
        $ErrorActionPreference = $previousPreference
        Pop-Location
    }
}
