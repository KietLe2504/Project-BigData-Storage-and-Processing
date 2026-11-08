. (Join-Path $PSScriptRoot 'common.ps1')
# Dependencies are installed only in this disposable test container. Tests
# create/drop random aero_m5_test_* databases, never the serving database.
Invoke-M5Compose -Arguments @('run', '--rm', '--volume', ($script:M5Root + ':/app:ro'),
    '-e', 'M5_TEST_MONGO_URI=mongodb://mongo:27017', 'loader', 'sh', '-c',
    'python -m pip install -r requirements-dev.txt && python -m pytest -q -p no:cacheprovider') -LogName 'test_m5.log'
