. (Join-Path $PSScriptRoot 'common.ps1')
Invoke-M5Compose -Arguments @('stop')
Write-Host 'M5 stopped. MongoDB data remains in its named volume.'
