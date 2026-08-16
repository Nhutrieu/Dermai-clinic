param(
    [switch]$IncludeE2E
)

$ErrorActionPreference = "Continue"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$artifactRoot = Join-Path $repoRoot "test-results\release"
New-Item -ItemType Directory -Force -Path $artifactRoot | Out-Null

$results = [System.Collections.Generic.List[object]]::new()

function Invoke-ReleaseTest {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$WorkingDirectory,
        [Parameter(Mandatory = $true)][string]$Executable,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )

    $safeName = $Name.ToLowerInvariant() -replace "[^a-z0-9]+", "-"
    $logPath = Join-Path $artifactRoot "$safeName.log"
    $startedAt = [DateTimeOffset]::Now
    Write-Host "[$Name] $Executable $($Arguments -join ' ')"

    Push-Location $WorkingDirectory
    try {
        # Tee the real command output so the report can be audited after the run.
        & $Executable @Arguments 2>&1 | Tee-Object -FilePath $logPath
        $exitCode = $LASTEXITCODE
        if ($null -eq $exitCode) { $exitCode = 0 }
    }
    catch {
        $_ | Out-String | Set-Content -Encoding UTF8 -Path $logPath
        $exitCode = 1
    }
    finally {
        Pop-Location
    }

    $finishedAt = [DateTimeOffset]::Now
    $results.Add([PSCustomObject]@{
        name = $Name
        status = if ($exitCode -eq 0) { "PASS" } else { "FAIL" }
        exitCode = $exitCode
        startedAt = $startedAt.ToString("o")
        finishedAt = $finishedAt.ToString("o")
        durationSeconds = [Math]::Round(($finishedAt - $startedAt).TotalSeconds, 2)
        log = $logPath.Substring($repoRoot.Length + 1).Replace("\", "/")
    })
}

Invoke-ReleaseTest -Name "Frontend build" -WorkingDirectory (Join-Path $repoRoot "frontend") -Executable "npm.cmd" -Arguments @("run", "build")
Invoke-ReleaseTest -Name "Frontend unit tests" -WorkingDirectory (Join-Path $repoRoot "frontend") -Executable "npm.cmd" -Arguments @("test")
$maven = Get-Command mvn.cmd, mvn -ErrorAction SilentlyContinue | Select-Object -First 1
if ($maven) {
    Invoke-ReleaseTest -Name "Java services" -WorkingDirectory $repoRoot -Executable $maven.Source -Arguments @("test")
}
else {
    # The project requires Java 21; the pinned Maven container keeps the run reproducible on machines without Maven.
    $mount = "type=bind,source=$repoRoot,target=/src"
    Invoke-ReleaseTest -Name "Java services" -WorkingDirectory $repoRoot -Executable "docker.exe" -Arguments @(
        "run", "--rm", "--mount", $mount, "-w", "/src",
        "maven:3.9-eclipse-temurin-21", "mvn", "-q", "test"
    )
}
Invoke-ReleaseTest -Name "AI service" -WorkingDirectory (Join-Path $repoRoot "ai-service") -Executable "python.exe" -Arguments @("-m", "pytest", "tests", "-q", "-p", "no:cacheprovider")

# Unit tests exercise the evaluator, but release evidence must also prove that the
# promoted checkpoint still matches the hashes recorded in the model artifacts.
$checksumStartedAt = [DateTimeOffset]::Now
$checksumLogPath = Join-Path $artifactRoot "ai-checkpoint-integrity.log"
$checksumExitCode = 0
try {
    $checkpointPath = Join-Path $repoRoot "ai-service\models\best_model.pth"
    $manifestPath = Join-Path $repoRoot "ai-service\reports\ai_evidence\manifest.json"
    $comparisonPath = Join-Path $repoRoot "ai-service\reports\model_comparison_scin_v1.json"
    if (-not (Test-Path -LiteralPath $checkpointPath)) { throw "Checkpoint is missing: $checkpointPath" }
    if (-not (Test-Path -LiteralPath $manifestPath)) { throw "Evaluation manifest is missing: $manifestPath" }
    if (-not (Test-Path -LiteralPath $comparisonPath)) { throw "Model comparison report is missing: $comparisonPath" }

    $manifest = Get-Content -Raw -Encoding UTF8 -LiteralPath $manifestPath | ConvertFrom-Json
    $comparison = Get-Content -Raw -Encoding UTF8 -LiteralPath $comparisonPath | ConvertFrom-Json
    $actualHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $checkpointPath).Hash.ToLowerInvariant()
    $manifestHash = [string]$manifest.checkpoint.sha256
    $expectedHash = [string]$manifest.checkpoint.expected_sha256
    $comparisonHash = [string]$comparison.promoted_checkpoint_sha256
    $recordedHashes = @($manifestHash, $expectedHash, $comparisonHash) | ForEach-Object { $_.ToLowerInvariant() }
    if ($recordedHashes.Where({ [string]::IsNullOrWhiteSpace($_) }).Count -gt 0) {
        throw "At least one promoted-checkpoint hash is empty."
    }
    if ($recordedHashes.Where({ $_ -ne $actualHash }).Count -gt 0) {
        throw "Checkpoint SHA-256 does not match the evaluation manifest and model comparison report."
    }
    if ($manifest.checkpoint.expected_sha256_match -ne $true) {
        throw "Evaluation manifest does not attest that the expected checkpoint hash matched."
    }

    @(
        "checkpoint=ai-service/models/best_model.pth"
        "sha256=$actualHash"
        "manifestExpectedMatch=$($manifest.checkpoint.expected_sha256_match -eq $true)"
        "status=PASS"
    ) | Set-Content -Encoding UTF8 -LiteralPath $checksumLogPath
}
catch {
    $checksumExitCode = 1
    @(
        "status=FAIL"
        "error=$($_.Exception.Message)"
    ) | Set-Content -Encoding UTF8 -LiteralPath $checksumLogPath
}
$checksumFinishedAt = [DateTimeOffset]::Now
$results.Add([PSCustomObject]@{
    name = "AI checkpoint integrity"
    status = if ($checksumExitCode -eq 0) { "PASS" } else { "FAIL" }
    exitCode = $checksumExitCode
    startedAt = $checksumStartedAt.ToString("o")
    finishedAt = $checksumFinishedAt.ToString("o")
    durationSeconds = [Math]::Round(($checksumFinishedAt - $checksumStartedAt).TotalSeconds, 2)
    log = $checksumLogPath.Substring($repoRoot.Length + 1).Replace("\", "/")
})

if ($IncludeE2E) {
    $junitPath = Join-Path $repoRoot "frontend\test-results\e2e-junit.xml"
    # Remove the previous machine artifact so a successful command can never be
    # credited using JUnit from an older run.
    Remove-Item -LiteralPath $junitPath -Force -ErrorAction SilentlyContinue
    Invoke-ReleaseTest -Name "Browser E2E" -WorkingDirectory (Join-Path $repoRoot "frontend") -Executable "npm.cmd" -Arguments @("run", "test:e2e")
    $e2eResult = $results[$results.Count - 1]
    if ($e2eResult.status -eq "PASS") {
        if (-not (Test-Path -LiteralPath $junitPath)) {
            $e2eResult.status = "BLOCKED"
            $e2eResult | Add-Member -NotePropertyName detail -NotePropertyValue "Playwright exited successfully but did not create fresh JUnit evidence." -Force
        }
        else {
            try {
                $startedAt = [DateTimeOffset]::Parse([string]$e2eResult.startedAt)
                $junitFile = Get-Item -LiteralPath $junitPath
                if ($junitFile.LastWriteTimeUtc -lt $startedAt.UtcDateTime) {
                    throw "JUnit evidence predates this Playwright run."
                }
                [xml]$junit = Get-Content -Raw -Encoding UTF8 -LiteralPath $junitPath
                $cases = @($junit.SelectNodes("//testcase"))
                $skipped = @($junit.SelectNodes("//testcase[skipped]"))
                $failures = @($junit.SelectNodes("//testcase[failure or error]"))
                if ($cases.Count -eq 0) {
                    $e2eResult.status = "BLOCKED"
                    $e2eResult | Add-Member -NotePropertyName detail -NotePropertyValue "JUnit contains no browser test cases." -Force
                }
                elseif ($failures.Count -gt 0) {
                    $e2eResult.status = "FAIL"
                    $e2eResult | Add-Member -NotePropertyName detail -NotePropertyValue "$($failures.Count)/$($cases.Count) browser cases failed in JUnit." -Force
                }
                elseif ($skipped.Count -gt 0) {
                    # A green Playwright exit with skipped scenarios is incomplete evidence, not a genuine pass.
                    $e2eResult.status = "BLOCKED"
                    $e2eResult | Add-Member -NotePropertyName detail -NotePropertyValue "$($skipped.Count)/$($cases.Count) browser cases skipped." -Force
                }
            }
            catch {
                $e2eResult.status = "BLOCKED"
                $e2eResult | Add-Member -NotePropertyName detail -NotePropertyValue "JUnit evidence is missing, stale or invalid: $($_.Exception.Message)" -Force
            }
        }
    }
}
else {
    $now = [DateTimeOffset]::Now.ToString("o")
    $results.Add([PSCustomObject]@{
        name = "Browser E2E"
        status = "NOT_RUN"
        exitCode = $null
        startedAt = $now
        finishedAt = $now
        durationSeconds = 0
        log = $null
        detail = "Omitted because -IncludeE2E was not supplied."
    })
}

$gitStatus = @(git -C $repoRoot status --porcelain)
$summary = [PSCustomObject]@{
    commit = (git -C $repoRoot rev-parse HEAD).Trim()
    workingTreeDirty = $gitStatus.Count -gt 0
    generatedAt = [DateTimeOffset]::Now.ToString("o")
    overallStatus = if ($results.Where({ $_.status -eq "FAIL" }).Count -gt 0) {
        "FAIL"
    } elseif ($results.Where({ $_.status -eq "BLOCKED" }).Count -gt 0) {
        "BLOCKED"
    } elseif ($results.Where({ $_.status -eq "NOT_RUN" }).Count -gt 0) {
        "NOT_RUN"
    } else {
        "PASS"
    }
    results = $results
}
$summaryPath = Join-Path $artifactRoot "summary.json"
$summary | ConvertTo-Json -Depth 6 | Set-Content -Encoding UTF8 -Path $summaryPath

Write-Host "Release test summary: $summaryPath"
# A release gate is only green when every required stage produced PASS evidence.
# BLOCKED and NOT_RUN must stop CI instead of silently publishing an incomplete build.
if ($summary.overallStatus -ne "PASS") { exit 1 }
