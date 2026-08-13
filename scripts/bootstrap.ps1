# First-run helper for Windows PowerShell. Creates a real absolute STACK_PATH,
# starts the supported local baseline and proves app/default-engine readiness.
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $repoRoot

if (-not (Test-Path '.env')) {
    $composePath = $repoRoot.Replace('\', '/')
    $content = Get-Content '.env.example' -Raw
    $content = $content -replace '(?m)^STACK_PATH=.*$', "STACK_PATH=$composePath"
    [System.IO.File]::WriteAllText((Join-Path $repoRoot '.env'), $content, [System.Text.UTF8Encoding]::new($false))
    Write-Host "Created .env with STACK_PATH=$composePath"
} else {
    Write-Host 'Using existing .env (not overwritten)'
}

docker compose --profile chatterbox-nano config | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'docker compose config failed' }
docker compose --profile chatterbox-nano up -d --build
if ($LASTEXITCODE -ne 0) { throw 'docker compose up failed' }

for ($attempt = 1; $attempt -le 60; $attempt++) {
    try {
        $health = Invoke-RestMethod -Uri 'http://127.0.0.1:8881/api/health' -TimeoutSec 5
        if ($health.overall -eq 'ok') {
            $health | ConvertTo-Json -Compress
            Invoke-RestMethod -Uri 'http://127.0.0.1:8881/api/engines/health' -TimeoutSec 5 | ConvertTo-Json -Compress
            Write-Host 'Open http://127.0.0.1:8881'
            exit 0
        }
    } catch {
        Start-Sleep -Seconds 5
    }
}

throw 'Timed out waiting for the app. Run: docker compose ps'
