. (Join-Path $PSScriptRoot 'common.ps1')
$M5Tag = Get-Date -Format 'yyyyMMdd_HHmmss'
$M5Bundle = Join-Path $script:M5Root ('evidence\M5_HANDOFF_' + $M5Tag)
New-Item -ItemType Directory -Force $M5Bundle | Out-Null
Invoke-M5Compose -Arguments @('ps') -LogName 'compose_status.log'
Invoke-M5Compose -Arguments @('run', '--rm', 'loader', 'python', '-m', 'm5.verify_batch') -LogName 'verify_m5.log'
Copy-Item -LiteralPath (Join-Path $script:M5Root 'logs') -Destination $M5Bundle -Recurse
Copy-Item -LiteralPath (Join-Path $script:M5Root 'doc_guide') -Destination $M5Bundle -Recurse
Get-ChildItem (Join-Path $script:M5Root 'evidence') -File |
    Where-Object { $_.Extension -in @('.json', '.png', '.jpg', '.jpeg', '.txt', '.csv') } |
    Copy-Item -Destination $M5Bundle
Compress-Archive -Path (Join-Path $M5Bundle '*') -DestinationPath ($M5Bundle + '.zip')
Write-Host ('Evidence ZIP: ' + $M5Bundle + '.zip')
