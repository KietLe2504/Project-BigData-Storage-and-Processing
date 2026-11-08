param(
    [Parameter(Mandatory=$true)][string]$SupplementPath,
    [Parameter(Mandatory=$true)][string]$BaseSnapshotPath
)
. (Join-Path $PSScriptRoot 'common.ps1')
$M5RouteSupplement = (Resolve-Path $SupplementPath).Path
$M5RouteBase = (Resolve-Path $BaseSnapshotPath).Path
Invoke-M5Compose -Arguments @('run', '--rm', '-T', '--no-deps',
    '--volume', ($M5RouteSupplement + ':/data/route-supplement:ro'),
    '--volume', ($M5RouteBase + ':/data/base-snapshot:ro'),
    'loader', 'python', '-m', 'm5.route_carriers', '--supplement', '/data/route-supplement',
    '--base-snapshot', '/data/base-snapshot') -LogName 'load_route_carriers.log'
