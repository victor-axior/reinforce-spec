<#
.SYNOPSIS
    Test the production API endpoints.

.DESCRIPTION
    Runs E2E tests against the deployed API. Uses RS_API_BASE_URL env var
    or auto-discovers the ALB DNS via AWS CLI.

.EXAMPLE
    $env:RS_API_BASE_URL = "https://reinforce.axior.dev"
    ./test_production.ps1
#>

# Get API base URL from env or discover via AWS CLI
$baseUrl = $env:RS_API_BASE_URL
if (-not $baseUrl) {
    Write-Host "RS_API_BASE_URL not set, discovering ALB DNS..."
    $albDns = & aws elbv2 describe-load-balancers `
        --query "LoadBalancers[?contains(LoadBalancerName, 'reinforce')].DNSName" `
        --output text 2>$null
    if ($albDns) {
        $baseUrl = "https://$albDns"
    } else {
        Write-Host "ERROR: Could not discover ALB. Set RS_API_BASE_URL env var." -ForegroundColor Red
        exit 1
    }
}

Write-Host "Using API: $baseUrl`n"

# Disable SSL certificate validation for ALB DNS test (self-signed certs)
if (-not ([System.Management.Automation.PSTypeName]'TrustAllCertsPolicy').Type) {
    add-type @"
using System.Net;
using System.Security.Cryptography.X509Certificates;
public class TrustAllCertsPolicy : ICertificatePolicy {
    public bool CheckValidationResult(
        ServicePoint srvPoint, X509Certificate certificate,
        WebRequest request, int certificateProblem) {
        return true;
    }
}
"@
}
[System.Net.ServicePointManager]::CertificatePolicy = New-Object TrustAllCertsPolicy
[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12

Write-Host "Testing Production API`n"

# Test 1: Health
Write-Host "1. Testing /v1/health"
$health = Invoke-RestMethod -Uri "$baseUrl/v1/health" -Method GET
Write-Host "   Status: $($health.status), Version: $($health.version)"

# Test 2: Policy Status
Write-Host "`n2. Testing /v1/policy/status"
$policy = Invoke-RestMethod -Uri "$baseUrl/v1/policy/status" -Method GET
Write-Host "   Policy Version: $($policy.version), Stage: $($policy.stage)"

# Test 3: POST /v1/specs (tests database write)
Write-Host "`n3. Testing POST /v1/specs (database write)"
$body = @{
    description = "RDS deployment test"
    candidates = @(
        @{
            content = "Test spec 1 for RDS PostgreSQL"
            source_model = "test-model"
        },
        @{
            content = "Test spec 2 for RDS PostgreSQL"
            source_model = "test-model"
        }
    )
} | ConvertTo-Json -Depth 3

Write-Host "   Request body (truncated)"

try {
    $specs = Invoke-RestMethod -Uri "$baseUrl/v1/specs" -Method POST -Body $body -ContentType "application/json"
    Write-Host "   Selected: $($specs.selected.name)"
    Write-Host "   Evaluation ID: $($specs.evaluation_id)"
    
    # Test 4: POST feedback (tests more database writes)
    Write-Host "`n4. Testing POST /v1/specs/feedback (database write)"
    $feedbackBody = @{
        request_id = $specs.request_id
        rating = 5.0
        comment = "RDS deployment test feedback"
    } | ConvertTo-Json
    
    $feedback = Invoke-RestMethod -Uri "$baseUrl/v1/specs/feedback" -Method POST -Body $feedbackBody -ContentType "application/json"
    Write-Host "   Feedback stored: $($feedback.status)"
}
catch {
    $statusCode = $_.Exception.Response.StatusCode.value__
    $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
    $responseBody = $reader.ReadToEnd()
    Write-Host "   Status Code: $statusCode" -ForegroundColor Red
    Write-Host "   Response: $responseBody" -ForegroundColor Red
}

Write-Host "`n=== All tests completed ==="
