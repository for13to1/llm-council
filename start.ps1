# LLM Council - Start script (PowerShell)

Write-Host "Starting LLM Council..." -ForegroundColor Cyan
Write-Host ""
Write-Host "Starting backend on http://localhost:8001..." -ForegroundColor Yellow
$backend = Start-Process -FilePath "uv" -ArgumentList "run","python","-m","backend.main" -PassThru -NoNewWindow

Write-Host ""
Write-Host "LLM Council is running at http://localhost:8001" -ForegroundColor Green
Write-Host ""
Write-Host "Press Ctrl+C to stop" -ForegroundColor Gray

try {
    while ($true) {
        if ($backend.HasExited) { break }
        Start-Sleep -Seconds 1
    }
}
finally {
    if (!$backend.HasExited) { Stop-Process -Id $backend.Id -Force -ErrorAction SilentlyContinue }
    Write-Host "Server stopped." -ForegroundColor Cyan
}
