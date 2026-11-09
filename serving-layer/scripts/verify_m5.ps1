. (Join-Path $PSScriptRoot 'common.ps1')
Invoke-M5Compose -Arguments @('run', '--rm', '--build', 'loader', 'python', '-m', 'm5.verify_batch') -LogName 'verify_m5.log'
