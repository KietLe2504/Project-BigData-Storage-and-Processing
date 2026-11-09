param(
    [Parameter(Mandatory = $true)][string]$SnapshotPath,
    [switch]$CheckOnly,
    [switch]$AllowPartial
)
. (Join-Path $PSScriptRoot 'common.ps1')
$M5Snapshot = (Resolve-Path -LiteralPath $SnapshotPath).Path
if (-not (Test-Path -LiteralPath (Join-Path $M5Snapshot 'manifest.json'))) {
    throw 'SnapshotPath must be the directory containing manifest.json and JSONL files.'
}
$M5Arguments = @('run', '--rm', '--build')
if ($CheckOnly) { $M5Arguments += '--no-deps' }
$M5Arguments += @('--volume', ($M5Snapshot + ':/data/snapshot:ro'),
    'loader', 'python', '-m', 'm5.load_batch', '--snapshot', '/data/snapshot')
if ($CheckOnly) { $M5Arguments += '--check-only' }
if ($AllowPartial) { $M5Arguments += '--allow-partial' }
Invoke-M5Compose -Arguments $M5Arguments -LogName 'load_m2.log'
