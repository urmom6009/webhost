param(
    [Parameter(Mandatory = $true)]
    [string]$Recipient,

    [string]$AgePath = ".\age.exe",

    [string]$Output = "stripe-secrets.env.age"
)

$ErrorActionPreference = "Stop"

function ConvertFrom-SecureStringPlaintext {
    param([Security.SecureString]$Secure)
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Secure)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
}

if (-not (Test-Path $AgePath)) {
    Write-Error "age.exe not found at $AgePath. Put age.exe in this folder or pass -AgePath C:\path\to\age.exe"
}

$stripeSecret = ConvertFrom-SecureStringPlaintext (Read-Host "Paste Stripe secret key, starts with sk_test_ or sk_live_" -AsSecureString)
$stripeWebhook = ConvertFrom-SecureStringPlaintext (Read-Host "Paste Stripe webhook signing secret, starts with whsec_" -AsSecureString)

if ($stripeSecret -notmatch '^sk_(test|live)_[A-Za-z0-9_]+$') {
    Write-Error "Stripe secret key does not look right. It should start with sk_test_ or sk_live_."
}

if ($stripeWebhook -notmatch '^whsec_[A-Za-z0-9_]+$') {
    Write-Error "Stripe webhook signing secret does not look right. It should start with whsec_."
}

$temp = New-TemporaryFile
try {
    Set-Content -Path $temp -Value @(
        "STRIPE_SECRET_KEY=$stripeSecret"
        "STRIPE_WEBHOOK_SECRET=$stripeWebhook"
    ) -Encoding utf8NoBOM

    & $AgePath -r $Recipient -o $Output $temp
    if ($LASTEXITCODE -ne 0) {
        Write-Error "age encryption failed"
    }

    Write-Host ""
    Write-Host "Created encrypted file: $Output"
    Write-Host "Send only this .age file back. Do not send screenshots or paste the secrets anywhere."
}
finally {
    Remove-Item -Force $temp -ErrorAction SilentlyContinue
    $stripeSecret = $null
    $stripeWebhook = $null
}
