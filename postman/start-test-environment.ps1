param([switch]$Stop, [switch]$Build)

$ErrorActionPreference = 'Continue'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$project = 'dermai-e2e-postman-20261109'
$artifactRoot = Join-Path $repoRoot "frontend\e2e-artifacts\$project"
$envFile = Join-Path $artifactRoot '.env.e2e'
$exportPath = Join-Path $PSScriptRoot 'DermAI_Clinic_Test_20261109.postman_environment.json'
if (-not (Test-Path -LiteralPath $envFile)) { throw 'The private test stack configuration is missing. Prepare a new isolated stack before resuming.' }
$compose = @('compose', '--env-file', $envFile, '-p', $project,
    '-f', (Join-Path $repoRoot 'docker-compose.yml'),
    '-f', (Join-Path $repoRoot 'tests\docker-compose.e2e.yml'),
    '-f', (Join-Path $PSScriptRoot 'docker-compose.test.yml'))
$configuration = @{}
$savedEnvironment = @{}
foreach ($line in Get-Content -Encoding UTF8 -LiteralPath $envFile) {
    if ($line -match '^([A-Z_0-9]+)=(.*)$') { $configuration[$Matches[1]] = $Matches[2] }
}

function Invoke-TestCompose([string[]]$Arguments) {
    & docker.exe @compose @Arguments
    if ($LASTEXITCODE -ne 0) { throw 'The Postman test stack command failed.' }
}

function Set-PostmanValue([string]$Key, $Value) {
    $entry = $script:postmanEnvironment.values | Where-Object key -eq $Key | Select-Object -First 1
    if ($entry) { $entry.value = [string]$Value }
    else { $script:postmanEnvironment.values += [PSCustomObject]@{ key = $Key; value = [string]$Value; type = 'default'; enabled = $true } }
}

function Invoke-TestApi([string]$Path, [string]$Token) {
    return Invoke-RestMethod -Uri ("http://localhost:53000/api/v1" + $Path) -Headers @{Authorization = "Bearer $Token"} -TimeoutSec 15 -ErrorAction Stop
}

function Get-VisitEvidence($Suites) {
    foreach ($suite in $Suites) {
        foreach ($spec in $suite.specs) {
            foreach ($test in $spec.tests) {
                foreach ($attachment in $test.results[-1].attachments) {
                    if ($attachment.name -eq 'visit-lifecycle-result.json' -and $attachment.body) {
                        [System.Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($attachment.body)) | ConvertFrom-Json
                    }
                }
            }
        }
        Get-VisitEvidence $suite.suites
    }
}

Push-Location $repoRoot
try {
    foreach ($key in $configuration.Keys) {
        $savedEnvironment[$key] = [Environment]::GetEnvironmentVariable($key, 'Process')
        [Environment]::SetEnvironmentVariable($key, $configuration[$key], 'Process')
    }
    if ($Stop) {
        Invoke-TestCompose -Arguments @('stop')
        Write-Host 'Postman test services stopped. Database, accounts and environment files are retained.'
    }
    else {
        $arguments = @('up', '-d', '--wait', '--wait-timeout', '420')
        if ($Build) { $arguments += '--build' }
        Invoke-TestCompose -Arguments $arguments
        $script:postmanEnvironment = Get-Content -Raw -Encoding UTF8 (Join-Path $PSScriptRoot 'DermAI_Clinic_Local.postman_environment.example.json') | ConvertFrom-Json
        $script:postmanEnvironment.name = 'DermAI Clinic - Isolated Postman Test 20261109 (Restored)'
        $tokens = @{}
        foreach ($account in @(
            @{role='admin';email='admin@e2e.example.test'},
            @{role='patient';email='patient-1@e2e.example.test'},
            @{role='doctor';email='doctor@e2e.example.test'},
            @{role='receptionist';email='reception@e2e.example.test'},
            @{role='pharmacist';email='pharmacist@e2e.example.test'}
        )) {
            $payload = @{email=$account.email; password=$configuration.POSTGRES_PASSWORD} | ConvertTo-Json
            $login = Invoke-RestMethod -Uri 'http://localhost:53000/api/v1/auth/login' -Method Post -ContentType 'application/json' -Body $payload -TimeoutSec 20 -ErrorAction Stop
            if ($login.role -ne $account.role.ToUpperInvariant()) { throw 'Test login returned the wrong role.' }
            $tokens[$account.role] = $login.accessToken
            Set-PostmanValue ($account.role + '_email') $account.email
            Set-PostmanValue ($account.role + '_password') $configuration.POSTGRES_PASSWORD
            Set-PostmanValue ($account.role + '_token') $login.accessToken
            Set-PostmanValue ($account.role + '_refresh_token') $login.refreshToken
            Write-Host ("Verified test login: " + $login.role)
        }
        $patient = Invoke-TestApi '/patients/me' $tokens.patient
        $doctor = Invoke-TestApi '/doctors/me' $tokens.doctor
        $reception = Invoke-TestApi '/auth/me' $tokens.receptionist
        $medicines = @(Invoke-TestApi '/medicines' $tokens.doctor)
        $services = @(Invoke-TestApi ("/services?doctorId=" + $doctor.id) $tokens.patient)
        $timestamp = Get-Date -Format 'yyyyMMddHHmmss'
        $values = @{
            base_url='http://localhost:53000'; ai_service_url='http://localhost:58000'; inventory_service_url='http://localhost:58010'
            patient_id=$patient.id; patient_identity_id=$patient.identityId; patient_phone=$patient.phone
            doctor_id=$doctor.id; doctor_identity_id=$doctor.identityId; receptionist_identity_id=$reception.identityId
            service_token=$configuration.SERVICE_TOKEN; duration_minutes='30'; slot_minutes='30'
            run_file_uploads='false'; run_sse='false'; cash_amount_received='500000'
            new_patient_email="postman.patient.$timestamp@e2e.example.test"; new_patient_password=$configuration.POSTGRES_PASSWORD
            new_staff_email="postman.staff.$timestamp@e2e.example.test"; new_staff_password=$configuration.POSTGRES_PASSWORD
            medicine_sku="PM-MED-$timestamp"; product_sku="PM-PRODUCT-$timestamp"; batch_number="PM-BATCH-$timestamp"
            service_code="PM-SERVICE-$timestamp"; expiry_date=(Get-Date).AddYears(1).ToString('yyyy-MM-dd')
            from_utc=[DateTimeOffset]::Now.AddDays(-1).ToUniversalTime().ToString('o')
            to_utc=[DateTimeOffset]::Now.AddDays(60).ToUniversalTime().ToString('o')
            patient_2_email='patient-2@e2e.example.test'; patient_2_password=$configuration.POSTGRES_PASSWORD
        }
        if ($medicines.Count) { $values.medicine_id = $medicines[0].id; $values.product_id = $medicines[0].id }
        if ($services.Count) { $values.service_id = $services[0].id }
        foreach ($offset in @(@{days=1;prefix='slot'}, @{days=2;prefix='reschedule'}, @{days=21;prefix='follow_up'})) {
            $day = (Get-Date).AddDays($offset.days).ToString('yyyy-MM-dd')
            $availability = Invoke-TestApi ("/appointments/availability?doctorId=" + $doctor.id + "&date=$day&durationMinutes=30") $tokens.patient
            $slot = $availability.items | Where-Object { $_.status -eq 'AVAILABLE' -and ([DateTimeOffset]$_.startAt).ToOffset([TimeSpan]::FromHours(7)).Hour -ge 8 } | Select-Object -First 1
            if ($slot) {
                $values[$offset.prefix + '_start_utc'] = $slot.startAt
                $values[$offset.prefix + '_end_utc'] = $slot.endAt
                if ($offset.prefix -eq 'slot') { $values.appointment_date = $day }
                if ($offset.prefix -eq 'follow_up') { $values.follow_up_utc = $slot.startAt }
            }
        }
        $reportPath = Join-Path $artifactRoot 'test-results\e2e-results.json'
        if (Test-Path -LiteralPath $reportPath) {
            $report = Get-Content -Raw -Encoding UTF8 $reportPath | ConvertFrom-Json
            $visit = @(Get-VisitEvidence $report.suites | Where-Object testCase -eq 'E2E-FLOW-001') | Select-Object -Last 1
            if ($visit) {
                $values.appointment_id=$visit.appointmentId; $values.medical_record_id=$visit.medicalRecordId
                $values.prescription_id=$visit.prescriptionId; $values.invoice_id=$visit.invoiceId
                $payment=Invoke-TestApi ("/payments/booking/"+$visit.appointmentId) $tokens.patient
                $values.payment_id=$payment.id; $values.order_code=$payment.orderCode
            }
        }
        foreach ($key in $values.Keys) { Set-PostmanValue $key $values[$key] }
        $script:postmanEnvironment | ConvertTo-Json -Depth 12 | Set-Content -Encoding UTF8 -LiteralPath $exportPath
        Write-Host "Environment exported: $exportPath"
        Write-Host 'Test stack is running and will be retained. Re-import the exported environment in Postman.'
    }
}
finally {
    foreach ($key in $savedEnvironment.Keys) { [Environment]::SetEnvironmentVariable($key, $savedEnvironment[$key], 'Process') }
    Pop-Location
}
