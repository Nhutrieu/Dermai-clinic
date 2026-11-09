param(
    [ValidatePattern('^dermai-e2e-[a-z0-9-]+$')]
    [string]$ProjectName = ("dermai-e2e-" + (Get-Date -Format 'yyyyMMddHHmmss')),
    [switch]$KeepStack,
    [string]$ComposeOverride
)

$ErrorActionPreference = 'Continue'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$frontendRoot = Join-Path $repoRoot 'frontend'
$artifactRoot = Join-Path $frontendRoot "e2e-artifacts\$ProjectName"
if (Test-Path -LiteralPath $artifactRoot) { throw 'Choose a new project name; existing evidence is preserved.' }
New-Item -ItemType Directory -Path $artifactRoot -Force | Out-Null
$envFile = Join-Path $artifactRoot '.env.e2e'
$password = 'E2E-' + [Guid]::NewGuid().ToString('N') + '-Aa1!'
$compose = @('compose', '--env-file', $envFile, '-p', $ProjectName,
    '-f', (Join-Path $repoRoot 'docker-compose.yml'), '-f', (Join-Path $PSScriptRoot 'docker-compose.e2e.yml'))
if ($ComposeOverride) { $compose += @('-f', (Resolve-Path -LiteralPath $ComposeOverride -ErrorAction Stop).Path) }
$created = $false
$exitCode = 1
$savedEnvironment = @{}

function Set-TestEnvironment([string]$Name, [string]$Value) {
    if (-not $savedEnvironment.ContainsKey($Name)) {
        $savedEnvironment[$Name] = [Environment]::GetEnvironmentVariable($Name, 'Process')
    }
    [Environment]::SetEnvironmentVariable($Name, $Value, 'Process')
}

function Invoke-Compose([string[]]$Arguments, [string]$LogName) {
    & docker.exe @compose @Arguments 2>&1 | Tee-Object -FilePath (Join-Path $artifactRoot $LogName)
    if ($LASTEXITCODE -ne 0) { throw "Docker Compose failed; see $LogName." }
}

Push-Location $repoRoot
try {
    & docker.exe info --format '{{.ServerVersion}}'
    if ($LASTEXITCODE -ne 0) { throw 'Start Docker Desktop first.' }
    $existing = @(& docker.exe ps -aq --filter "label=com.docker.compose.project=$ProjectName")
    $existingVolumes = @(& docker.exe volume ls -q --filter "label=com.docker.compose.project=$ProjectName")
    if ($existing.Count -or $existingVolumes.Count) { throw 'E2E project already exists; use a fresh project name.' }

    # Set process values too, since shell environment has precedence over --env-file.
    $configuration = @{
        POSTGRES_DB = 'dermai'; POSTGRES_USER = 'dermai'; POSTGRES_PASSWORD = $password
        JWT_SECRET = ($password + $password); SERVICE_TOKEN = $password; BOOTSTRAP_TOKEN = $password
        DATA_ENCRYPTION_KEY = $password; PAYOS_FAKE_MODE = 'true'
        PAYOS_CLIENT_ID = ''; PAYOS_API_KEY = ''; PAYOS_CHECKSUM_KEY = ''
        SMTP_USERNAME = ''; SMTP_PASSWORD = ''; GOOGLE_CLIENT_ID = ''; GEMINI_API_KEY = ''
        PAYMENT_DEPOSIT_AMOUNT = '100000'
        AI_RESEARCH_MANIFEST_PATH = '/models/research_pipeline/manifest.json'
    }
    foreach ($entry in $configuration.GetEnumerator()) { Set-TestEnvironment $entry.Key $entry.Value }
    $configuration.GetEnumerator() | ForEach-Object { "$($_.Key)=$($_.Value)" } | Set-Content -Encoding ASCII $envFile
    Invoke-Compose -Arguments @('config', '--quiet') -LogName 'compose-config.log'
    $created = $true
    Invoke-Compose -Arguments @('up', '-d', '--build', '--wait', '--wait-timeout', '420') -LogName 'stack.log'

    $fixtureSql = "\set e2e_password '$password'`n" + (Get-Content -Raw -Encoding UTF8 (Join-Path $PSScriptRoot 'e2e-fixtures.sql'))
    $fixtureSql | & docker.exe @compose exec -T postgres psql -X -v ON_ERROR_STOP=1 -U dermai -d dermai -f -
    if ($LASTEXITCODE -ne 0) { throw 'Identity fixture failed.' }
    $visitId = [Guid]::NewGuid().ToString()
    $billingSql = "\set e2e_visit_id '$visitId'`n" + (Get-Content -Raw -Encoding UTF8 (Join-Path $PSScriptRoot 'e2e-billing-fixture.sql'))
    $billingSql | & docker.exe @compose exec -T postgres psql -X -v ON_ERROR_STOP=1 -U dermai -d dermai -f -
    if ($LASTEXITCODE -ne 0) { throw 'Billing fixture failed.' }

    $accounts = @{
        PATIENT_1 = 'patient-1@e2e.example.test'; PATIENT_2 = 'patient-2@e2e.example.test'
        RECEPTIONIST = 'reception@e2e.example.test'; DOCTOR = 'doctor@e2e.example.test'
        PHARMACIST = 'pharmacist@e2e.example.test'
    }
    foreach ($account in $accounts.GetEnumerator()) {
        Set-TestEnvironment "E2E_$($account.Key)_EMAIL" $account.Value
        Set-TestEnvironment "E2E_$($account.Key)_PASSWORD" $password
    }
    Set-TestEnvironment 'E2E_BASE_URL' 'http://localhost:53000'
    Set-TestEnvironment 'E2E_VIDEO' 'on'
    Set-TestEnvironment 'E2E_SEARCH_DAYS' '60'
    Set-TestEnvironment 'E2E_ARTIFACT_ROOT' $artifactRoot
    Set-TestEnvironment 'E2E_BILLING_APPOINTMENT_ID' $visitId
    Set-TestEnvironment 'E2E_AI_IMAGE_PATH' (Join-Path $frontendRoot 'e2e\fixtures\synthetic-eczema-e2e.png')

    $sourceHashes = @(& rg --files frontend/src frontend/e2e services ai-service/app tests -g '!target' -g '!node_modules' -g '!__pycache__' | ForEach-Object {
        $file = Get-Item -LiteralPath $_
        @{ path = $_.Replace('\', '/'); sha256 = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant() }
    })
    $sourceHashes | ConvertTo-Json -Depth 3 | Set-Content -Encoding UTF8 (Join-Path $artifactRoot 'source-hashes.json')
    @{
        commit = ((& git rev-parse HEAD) -join '').Trim()
        workingTreeDirty = [bool](& git status --porcelain)
        changedFiles = @(& git -c core.quotepath=false status --short)
        startedAt = [DateTimeOffset]::Now.ToString('o')
        composeProject = $ProjectName
        paymentProvider = 'FakePayOSGateway (no external money movement)'
        fixtures = 'Synthetic identities and prepaid same-day appointment; weekly closure NONE'
        aiHealth = Invoke-RestMethod 'http://localhost:53000/ai/health'
    } | ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8 (Join-Path $artifactRoot 'revision.json')

    Set-Location $frontendRoot
    & npm.cmd run test:e2e:typecheck
    if ($LASTEXITCODE -ne 0) { throw 'E2E TypeScript check failed.' }
    & npm.cmd run test:e2e 2>&1 | Tee-Object -FilePath (Join-Path $artifactRoot 'playwright.log')
    $exitCode = $LASTEXITCODE
    if ($exitCode -eq 0) {
        [xml]$junit = Get-Content -Raw -Encoding UTF8 (Join-Path $artifactRoot 'test-results\e2e-junit.xml')
        if (@($junit.SelectNodes('//testcase')).Count -eq 0 -or @($junit.SelectNodes('//testcase[skipped or failure or error]')).Count -gt 0) {
            Write-Host 'E2E gate incomplete: skipped cases, failures or no cases. See JUnit and JSON annotations.'
            $exitCode = 2
        }
    }
}
catch {
    Write-Host $_.Exception.Message
    $_.Exception.Message | Set-Content -Encoding UTF8 (Join-Path $artifactRoot 'runner-error.txt')
    $exitCode = 1
}
finally {
    Set-Location $repoRoot
    if ($created -and -not $KeepStack) {
        # Project was verified absent before creation. Only its test resources are removed.
        & docker.exe @compose down -v --remove-orphans 2>&1 | Tee-Object -FilePath (Join-Path $artifactRoot 'cleanup.log')
        if ($LASTEXITCODE -ne 0) { $exitCode = 1 }
    }
    if (-not $KeepStack) { Remove-Item -LiteralPath $envFile -Force -ErrorAction SilentlyContinue }
    foreach ($name in $savedEnvironment.Keys) {
        [Environment]::SetEnvironmentVariable($name, $savedEnvironment[$name], 'Process')
    }
    $password = $null
    Pop-Location
}
Write-Host "E2E evidence: $artifactRoot"
exit $exitCode
