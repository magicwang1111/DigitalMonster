$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$dataDir = Join-Path $projectRoot 'data'
New-Item -ItemType Directory -Force -Path $dataDir | Out-Null
& scp 'seetacloud-5090x2:/root/autodl-tmp/DigitalMonster/data/access.token' (Join-Path $dataDir 'remote.token')
if ($LASTEXITCODE -ne 0) { throw 'Failed to retrieve the access token.' }
$existing = Get-NetTCPConnection -State Listen -LocalPort 8765 -ErrorAction SilentlyContinue
if (-not $existing) {
    Start-Process -FilePath 'ssh.exe' -ArgumentList '-N','-o','ExitOnForwardFailure=yes','-o','ServerAliveInterval=30','-L','127.0.0.1:8765:127.0.0.1:8765','seetacloud-5090x2' -WindowStyle Hidden
    Start-Sleep -Seconds 2
} else {
    $owner = Get-CimInstance Win32_Process -Filter "ProcessId=$($existing[0].OwningProcess)"
    if ($owner.Name -ne 'ssh.exe' -or $owner.CommandLine -notmatch '127\.0\.0\.1:8765:127\.0\.0\.1:8765' -or $owner.CommandLine -notmatch 'seetacloud-5090x2') {
        throw 'Port 8765 belongs to another service. Stop it or use a verified SSH tunnel before opening the dashboard.'
    }
}
Invoke-RestMethod 'http://127.0.0.1:8765/health' | Out-Null
$token = (Get-Content -Raw (Join-Path $dataDir 'remote.token')).Trim()
Write-Output 'Dashboard: http://127.0.0.1:8765 (tunnel ready; token saved locally)'
Start-Process "http://127.0.0.1:8765/#$token"
