<#
.SYNOPSIS
  Crée le certificat HTTPS de développement reconnu par les téléphones (iPhone et Android).

.DESCRIPTION
  1. Installe (une fois) l'autorité locale « mkcert » dans Windows.
  2. Crée un certificat pour l'adresse Wi-Fi du PC, localhost et 127.0.0.1.
  3. Copie le certificat de l'autorité dans certs\bhh-dev-ca.crt : c'est lui qu'on installe
     sur les téléphones (page https://<adresse-du-PC>:5173/bhh-dev-ca.crt).

  À relancer seulement si l'adresse IP du PC change. Les téléphones n'ont alors rien à refaire.

.PARAMETER Ip
  Adresse à mettre dans le certificat. Par défaut : l'adresse IPv4 de la carte Wi-Fi.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File config\pwa\generer-certificat.ps1
  powershell -ExecutionPolicy Bypass -File config\pwa\generer-certificat.ps1 -Ip 192.168.1.25
#>
param([string]$Ip)

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$certs = Join-Path $here "certs"

# --- mkcert : dans le PATH, sinon là où winget l'a installé -------------------------
$mkcert = (Get-Command mkcert -ErrorAction SilentlyContinue).Source
if (-not $mkcert) {
  $mkcert = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\FiloSottile.mkcert*\mkcert.exe" -ErrorAction SilentlyContinue |
    Select-Object -First 1 -ExpandProperty FullName
}
if (-not $mkcert) {
  Write-Host "mkcert est introuvable. Installez-le avec :" -ForegroundColor Yellow
  Write-Host "  winget install --id FiloSottile.mkcert -e"
  exit 1
}

# --- adresse du PC sur le Wi-Fi ------------------------------------------------------------
if (-not $Ip) {
  $Ip = Get-NetIPAddress -AddressFamily IPv4 |
    Where-Object { $_.InterfaceAlias -match "Wi-?Fi|WLAN|Sans fil" -and $_.IPAddress -notlike "169.254.*" } |
    Select-Object -First 1 -ExpandProperty IPAddress
}
if (-not $Ip) {
  Write-Host "Adresse Wi-Fi introuvable : relancez avec -Ip <adresse du PC>." -ForegroundColor Yellow
  exit 1
}

New-Item -ItemType Directory -Force $certs | Out-Null
# The PC name on the Wi-Fi (mDNS): it keeps working when the IP address changes (iPhone at least).
$name = "$($env:COMPUTERNAME.ToLower()).local"

Write-Host "1/3  Autorité locale (Windows peut demander une confirmation : répondez Oui)..."
# Only the Windows store (browsers); not the Java one, which needs admin rights and is useless here.
$env:TRUST_STORES = "system"
& $mkcert -install

Write-Host "2/3  Certificat pour $Ip, $name, localhost et 127.0.0.1..."
& $mkcert -cert-file (Join-Path $certs "dev-cert.pem") -key-file (Join-Path $certs "dev-key.pem") $Ip $name localhost 127.0.0.1 ::1

Write-Host "3/3  Certificat à installer sur les téléphones..."
$caroot = (& $mkcert -CAROOT).Trim()
Copy-Item (Join-Path $caroot "rootCA.pem") (Join-Path $certs "bhh-dev-ca.crt") -Force
Set-Content -Path (Join-Path $certs "adresse.txt") -Value $Ip -Encoding ascii
Set-Content -Path (Join-Path $certs "nom.txt") -Value $name -Encoding ascii

Write-Host ""
Write-Host "Terminé." -ForegroundColor Green
Write-Host "  Lancer l'application :  cd frontend ; npm run dev:phone"
Write-Host "  Sur chaque téléphone :  https://${Ip}:5173/bhh-dev-ca.crt  (voir INSTALLATION-IPHONE.md / INSTALLATION-ANDROID.md)"
Write-Host "  Puis l'application   :  https://${Ip}:5173   ou   https://${name}:5173 (suit le PC si son IP change)"
Write-Host ""
Write-Host "Ne partagez jamais le fichier rootCA-key.pem de $caroot : il permet de fabriquer des certificats." -ForegroundColor Yellow
