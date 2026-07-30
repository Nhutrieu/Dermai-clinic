[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$envPath = Join-Path $projectRoot ".env"

if (-not (Test-Path -LiteralPath $envPath)) {
    throw "Cannot find .env at $envPath"
}

$gmail = (Read-Host "Gmail address used to send OTP").Trim().ToLowerInvariant()
if ($gmail -notmatch '^[^\s@]+@gmail\.com$') {
    throw "Enter a valid @gmail.com address."
}

# SecureString prevents the App Password from appearing in terminal history.
$securePassword = Read-Host "16-character Google App Password" -AsSecureString
$passwordPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
try {
    $appPassword = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($passwordPointer).Replace(" ", "")
    if ($appPassword -notmatch '^[A-Za-z0-9]{16}$') {
        throw "The App Password must contain exactly 16 characters."
    }

    $content = [IO.File]::ReadAllText($envPath)
    $settings = [ordered]@{
        SMTP_HOST = "smtp.gmail.com"
        SMTP_PORT = "587"
        SMTP_USERNAME = $gmail
        SMTP_PASSWORD = $appPassword
        SMTP_AUTH = "true"
        SMTP_STARTTLS = "true"
        MAIL_FROM = $gmail
    }

    foreach ($entry in $settings.GetEnumerator()) {
        $pattern = "(?m)^" + [Regex]::Escape($entry.Key) + "=.*$"
        $line = $entry.Key + "=" + $entry.Value
        if ([Regex]::IsMatch($content, $pattern)) {
            $content = [Regex]::Replace($content, $pattern, $line)
        } else {
            if ($content.Length -gt 0 -and -not $content.EndsWith("`n")) { $content += "`r`n" }
            $content += $line + "`r`n"
        }
    }

    # UTF-8 without BOM is parsed consistently by Docker Compose on Windows.
    $utf8WithoutBom = New-Object Text.UTF8Encoding($false)
    [IO.File]::WriteAllText($envPath, $content, $utf8WithoutBom)
} finally {
    if ($passwordPointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($passwordPointer)
    }
    $appPassword = $null
}

Write-Host "Gmail SMTP settings were saved to .env without printing the App Password." -ForegroundColor Green
Write-Host "Restarting auth-service..."
Push-Location $projectRoot
try {
    docker compose up -d --force-recreate auth-service
    if ($LASTEXITCODE -ne 0) { throw "Could not restart auth-service." }
} finally {
    Pop-Location
}
Write-Host "Done. Register a new account to test OTP delivery to a real inbox." -ForegroundColor Green
