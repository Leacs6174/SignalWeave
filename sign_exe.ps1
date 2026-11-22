param(
    [Parameter(Mandatory = $false)]
    [string]$Executable = (Join-Path $PSScriptRoot "dist\SignalWeave\SignalWeave.exe")
)

$ErrorActionPreference = "Stop"
$subject = "CN=SignalWeave, O=Local Build, OU=Desktop Utility"
$certificate = Get-ChildItem Cert:\CurrentUser\My -CodeSigningCert |
    Where-Object { $_.Subject -eq $subject -and $_.HasPrivateKey } |
    Sort-Object NotAfter -Descending |
    Select-Object -First 1

if ($null -eq $certificate) {
    $certificate = New-SelfSignedCertificate `
        -Type CodeSigningCert `
        -Subject $subject `
        -CertStoreLocation "Cert:\CurrentUser\My" `
        -HashAlgorithm "SHA256" `
        -KeyAlgorithm "RSA" `
        -KeyLength 3072 `
        -KeyExportPolicy NonExportable `
        -NotAfter (Get-Date).AddYears(5)
}

if (-not (Test-Path -LiteralPath $Executable)) {
    throw "找不到待签名的 EXE：$Executable"
}

$signature = Set-AuthenticodeSignature `
    -FilePath $Executable `
    -Certificate $certificate `
    -HashAlgorithm "SHA256"

$publicDir = Join-Path $PSScriptRoot "signing"
New-Item -ItemType Directory -Path $publicDir -Force | Out-Null
Export-Certificate `
    -Cert $certificate `
    -FilePath (Join-Path $publicDir "SignalWeave.cer") `
    -Type CERT | Out-Null

$verified = Get-AuthenticodeSignature -LiteralPath $Executable
[pscustomobject]@{
    Exe = $Executable
    CertificateThumbprint = $certificate.Thumbprint
    SignatureStatus = $verified.Status
    SignerSubject = $verified.SignerCertificate.Subject
} | Format-List

if ($verified.SignerCertificate.Thumbprint -ne $certificate.Thumbprint) {
    throw "签名写入后无法读回匹配的证书"
}
