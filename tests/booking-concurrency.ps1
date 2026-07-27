param([string]$ProjectPath = (Split-Path $PSScriptRoot -Parent))

$ErrorActionPreference = "Stop"
$marker = "E2E_CONCURRENCY_" + [Guid]::NewGuid().ToString("N")
$doctorId = [Guid]::NewGuid()
$doctorIdentityId = [Guid]::NewGuid()
$appointmentOne = [Guid]::NewGuid()
$appointmentTwo = [Guid]::NewGuid()
$patientOne = [Guid]::NewGuid()
$patientTwo = [Guid]::NewGuid()
$identityOne = [Guid]::NewGuid()
$identityTwo = [Guid]::NewGuid()
$startAt = "2099-01-05T08:00:00Z"
$endAt = "2099-01-05T08:30:00Z"

function Insert-Sql([Guid]$appointmentId,[Guid]$patientId,[Guid]$patientIdentityId,[bool]$holdLock) {
  $pause = if ($holdLock) { "SELECT pg_sleep(2);" } else { "" }
  return "BEGIN; INSERT INTO appointment.appointments(id,patient_id,patient_identity_id,doctor_id,doctor_identity_id,start_at,end_at,status,reason) VALUES ('$appointmentId','$patientId','$patientIdentityId','$doctorId','$doctorIdentityId','$startAt','$endAt','PENDING','$marker'); $pause COMMIT;"
}

$runner = {
  param($workingDirectory,$sql)
  Set-Location $workingDirectory
  $output = & docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U dermai -d dermai -c $sql 2>&1 | Out-String
  [pscustomobject]@{ ExitCode = $LASTEXITCODE; Output = $output }
}

$first = Start-Job -ScriptBlock $runner -ArgumentList $ProjectPath,(Insert-Sql $appointmentOne $patientOne $identityOne $true)
Start-Sleep -Milliseconds 250
$second = Start-Job -ScriptBlock $runner -ArgumentList $ProjectPath,(Insert-Sql $appointmentTwo $patientTwo $identityTwo $false)

try {
  Wait-Job $first,$second | Out-Null
  $results = @(Receive-Job $first; Receive-Job $second)
  $successCount = @($results | Where-Object ExitCode -eq 0).Count
  $conflictCount = @($results | Where-Object { $_.Output -match "no_doctor_overlap|conflicting key value violates exclusion constraint" }).Count
  if ($successCount -ne 1 -or $conflictCount -ne 1) {
    $results | ForEach-Object { Write-Host $_.Output }
    throw "Expected exactly one successful booking and one database conflict."
  }
  Write-Host "PASS: database accepted exactly one of two concurrent bookings."
}
finally {
  Remove-Job $first,$second -Force -ErrorAction SilentlyContinue
  Set-Location $ProjectPath
  & docker compose exec -T postgres psql -U dermai -d dermai -c "DELETE FROM appointment.appointments WHERE reason='$marker';" | Out-Null
}
