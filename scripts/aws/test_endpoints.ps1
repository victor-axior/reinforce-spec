#!/usr/bin/env pwsh
# End-to-end Docker API endpoint test

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  ReinforceSpec API End-to-End Test" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

$baseUrl = "http://localhost:8000"

# Test 1: Health
Write-Host "[1/4] Testing GET /v1/health..." -ForegroundColor Yellow
try {
    $health = Invoke-WebRequest -UseBasicParsing -Uri "$baseUrl/v1/health" -TimeoutSec 20
    Write-Host "  ✓ Status: $($health.StatusCode)" -ForegroundColor Green
    $healthJson = $health.Content | ConvertFrom-Json
    Write-Host "  ✓ Version: $($healthJson.version)" -ForegroundColor Green
} catch {
    Write-Host "  ✗ FAILED: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# Test 2: Readiness
Write-Host "`n[2/4] Testing GET /v1/health/ready..." -ForegroundColor Yellow
try {
    $ready = Invoke-WebRequest -UseBasicParsing -Uri "$baseUrl/v1/health/ready" -TimeoutSec 20
    Write-Host "  ✓ Status: $($ready.StatusCode)" -ForegroundColor Green
    $readyJson = $ready.Content | ConvertFrom-Json
    Write-Host "  ✓ Ready status: $($readyJson.status)" -ForegroundColor Green
} catch {
    Write-Host "  ✗ FAILED: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# Test 3: Validation (single candidate → should reject with 422)
Write-Host "`n[3/4] Testing POST /v1/specs (validation rejection)..." -ForegroundColor Yellow
$badBody = '{"candidates":[{"content":"only one"}]}'
try {
    Invoke-WebRequest -UseBasicParsing -Method POST -Uri "$baseUrl/v1/specs" `
        -ContentType "application/json" -Body $badBody -TimeoutSec 30 | Out-Null
    Write-Host "  ✗ FAILED: Expected 422 but got success" -ForegroundColor Red
    exit 1
} catch {
    if ($_.Exception.Response -and ([int]$_.Exception.Response.StatusCode) -eq 422) {
        Write-Host "  ✓ Correctly rejected with 422" -ForegroundColor Green
    } else {
        Write-Host "  ✗ FAILED: $($_.Exception.Message)" -ForegroundColor Red
        exit 1
    }
}

# Test 4: Full scoring_only evaluation
Write-Host "`n[4/4] Testing POST /v1/specs (full evaluation)..." -ForegroundColor Yellow
$goodBody = @'
{
  "candidates": [
    {"content": "# Spec A: Payment API\n- OAuth2 with mTLS\n- PCI-DSS Level 1\n- Encryption at rest/transit"},
    {"content": "# Spec B: Payment API\n- Basic auth\n- No encryption"}
  ],
  "selection_method": "scoring_only",
  "description": "Payment gateway security comparison"
}
'@

try {
    Write-Host "  (This may take 60-90 seconds with real LLM calls)" -ForegroundColor Gray
    $resp = Invoke-WebRequest -UseBasicParsing -Method POST -Uri "$baseUrl/v1/specs" `
        -ContentType "application/json" -Body $goodBody -TimeoutSec 120
    Write-Host "  ✓ Status: $($resp.StatusCode)" -ForegroundColor Green
    
    $json = $resp.Content | ConvertFrom-Json
    Write-Host "  ✓ Request ID: $($json.request_id)" -ForegroundColor Green
    Write-Host "  ✓ Selection method: $($json.selection_method)" -ForegroundColor Green
    Write-Host "  ✓ Selected candidate: $($json.selected.index)" -ForegroundColor Green
    Write-Host "  ✓ Composite score: $($json.selected.composite_score)" -ForegroundColor Green
    Write-Host "  ✓ Latency: $($json.latency_ms) ms" -ForegroundColor Green
    Write-Host "  ✓ Candidates evaluated: $($json.all_candidates.Count)" -ForegroundColor Green
} catch {
    Write-Host "  ✗ FAILED: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  ✓ All tests passed!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
