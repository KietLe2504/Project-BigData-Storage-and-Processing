$ok = 0
$fail = 0
$missing = @()

for ($year = 2022; $year -le 2026; $year++) {
    $endMonth = if ($year -eq 2026) { 3 } else { 12 }

    for ($month = 1; $month -le $endMonth; $month++) {
        $mm = "{0:D2}" -f $month
        $path = "/aero/processed/year=$year/month=$mm"

        docker compose exec -T namenode hdfs dfs -test -e "$path/_SUCCESS" 2>$null

        if ($LASTEXITCODE -eq 0) {
            $ok++
        } else {
            $fail++
            $missing += "$year-$mm"
        }
    }
}

Write-Host "SUCCESS=$ok FAILED=$fail TOTAL=$($ok + $fail)"
if ($missing.Count -gt 0) {
    Write-Host "Missing partitions: $($missing -join ', ')"
}
