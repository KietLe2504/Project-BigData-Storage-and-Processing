. (Join-Path $PSScriptRoot 'common.ps1')
Invoke-M5Compose -Arguments @('config', '--quiet')
Invoke-M5Compose -Arguments @('up', '-d', '--build', '--wait', '--wait-timeout', '180', 'mongo', 'dashboard') -LogName 'start_m5.log'
Invoke-M5Compose -Arguments @('ps')
Write-Host 'M5 ready. Default dashboard URL: http://localhost:8501 (see compose ps if port overridden).'
