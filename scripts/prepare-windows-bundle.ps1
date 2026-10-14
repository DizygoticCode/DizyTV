# Prepare checksum-pinned, optional third-party components for a single Windows setup.
# Run: powershell -NoProfile -File scripts/prepare-windows-bundle.ps1
# Provide -AceInstallerPath <official original EXE> -AceSha256 <validated digest>
# This script does not modify or rebuild the Ace Stream executable.
[CmdletBinding()]
param(
  [string]$AceInstallerPath = '',
  [string]$AceSha256 = '',
  [switch]$SkipPublicDownloads
)
$ErrorActionPreference = 'Stop'
$vendor = Join-Path $PSScriptRoot 'vendor\windows'
New-Item -ItemType Directory -Path $vendor -Force | Out-Null

$inputs = @(
  @{
    Label = 'Vosk English (Apache-2.0 model)'
    Url = 'https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip'
    Sha256 = '30f26242c4eb449f948e42cb302dd7a686cb29a3423a8367f99ff41780942498'
    Filename = 'vosk-en.zip'
  },
  @{
    Label = 'FFmpeg 9.0.2 Essentials (third-party GPLv3 build)'
    Url = 'https://www.gyan.dev/ffmpeg/builds/packages/ffmpeg-9.0.2-essentials_build.zip'
    Sha256 = '60f467265b1e312373dbcd92200c2618a74850f98d3d078e94296bb3fa2047ba'
    Filename = 'ffmpeg-essentials.zip'
  }
)
function Assert-Digest([string]$Path, [string]$Sha) {
  if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
    throw "Required distribution file missing: $Path"
  }
  if ((Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash -ine $Sha) {
    throw "SHA-256 verification FAILED: $Path"
  }
}
if (-not $SkipPublicDownloads) {
  foreach ($item in $inputs) {
    $target = Join-Path $vendor $item.Filename
    if (-not (Test-Path -LiteralPath $target)) {
      Write-Host "Downloading $($item.Label) from official source..."
      $partial = $target + '.partial'
      try {
        Invoke-WebRequest -Uri $item.Url -UseBasicParsing -MaximumRedirection 5 -TimeoutSec 240 -OutFile $partial
        Assert-Digest $partial $item.Sha256
        Move-Item -LiteralPath $partial -Destination $target
      } finally {
        Remove-Item -LiteralPath $partial -Force -ErrorAction SilentlyContinue
      }
    }
    Assert-Digest $target $item.Sha256
  }
} else {
  foreach ($item in $inputs) {
    Assert-Digest (Join-Path $vendor $item.Filename) $item.Sha256
  }
}

# Copy the FFmpeg executable from the original verified distribution archive.
$staging = Join-Path $vendor '.ffmpeg-extract'
try {
  Remove-Item -LiteralPath $staging -Recurse -Force -ErrorAction SilentlyContinue
  Expand-Archive -LiteralPath (Join-Path $vendor 'ffmpeg-essentials.zip') -DestinationPath $staging
  $binaries = @(Get-ChildItem -LiteralPath $staging -Recurse -File -Filter ffmpeg.exe)
  if ($binaries.Count -ne 1) { throw 'Unexpected FFmpeg archive layout' }
  Copy-Item -LiteralPath $binaries[0].FullName -Destination (Join-Path $vendor 'ffmpeg.exe') -Force
  $licence = @(Get-ChildItem -LiteralPath $staging -Recurse -File |
    Where-Object { $_.Name -match '^(LICENSE|COPYING)(\.txt)?$' } | Select-Object -First 1)
  if ($licence.Count -gt 0) {
    Copy-Item -LiteralPath $licence[0].FullName -Destination (Join-Path $vendor 'FFmpeg-LICENSE.txt') -Force
  }
} finally {
  Remove-Item -LiteralPath $staging -Recurse -Force -ErrorAction SilentlyContinue
}
if ($AceInstallerPath -or $AceSha256) {
  if (-not $AceInstallerPath -or $AceSha256 -notmatch '^[A-Fa-f0-9]{64}$') {
    throw 'Supply BOTH the unmodified official Ace setup path and its independently verified 64-digit SHA256.'
  }
  Assert-Digest $AceInstallerPath $AceSha256
  $item = Get-Item -LiteralPath $AceInstallerPath
  if ($item.Length -lt 1048576 -or $item.Extension -ine '.exe') {
    throw 'Ace Stream package is not a plausible Windows installer'
  }
  $stream = [System.IO.File]::OpenRead($item.FullName)
  try {
    if ($stream.ReadByte() -ne 0x4d -or $stream.ReadByte() -ne 0x5a) {
      throw 'Ace Stream package does not have an EXE header'
    }
  } finally {
    $stream.Dispose()
  }
  Copy-Item -LiteralPath $item.FullName -Destination (Join-Path $vendor 'AceStreamSetup.exe') -Force
  $AceSha256.ToLowerInvariant() | Set-Content -LiteralPath (Join-Path $vendor 'AceStreamSetup.sha256') -NoNewline
  Write-Host 'Verified original Ace Stream EXE staged unchanged (no service modifications).'
} else {
  # Never accidentally carry a previously staged Ace binary into a new build.
  Remove-Item -LiteralPath (Join-Path $vendor 'AceStreamSetup.exe') -Force -ErrorAction SilentlyContinue
  Remove-Item -LiteralPath (Join-Path $vendor 'AceStreamSetup.sha256') -Force -ErrorAction SilentlyContinue
  Write-Warning 'Ace Stream NOT bundled: obtain original official setup, independently verify SHA-256, then supply -AceInstallerPath/-AceSha256.'
}
Write-Host "Verified Windows distribution assets prepared at $vendor"
