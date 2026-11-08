. (Join-Path $PSScriptRoot 'common.ps1')
# Keep ETL/EDA idle. The existing batch Compose network must be running.
Invoke-M5Compose -Arguments @('-f', 'compose.hdfs.yml', 'config', '--quiet')
Invoke-M5Compose -Arguments @('-f', 'compose.hdfs.yml', '--profile', 'hdfs', 'run', '--rm', '--build', 'hdfs-loader') -LogName 'load_hdfs.log'
