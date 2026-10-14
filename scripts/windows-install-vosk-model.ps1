# Installs opt-in offline Vosk models into the user's DizyTV data folder.
# English ZIP can be carried inside the DizyTV installer. Others download on
# demand directly from the original model publisher, with pinned SHA-256.
[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][ValidateSet('en','de','es','fr','it','nl','pl','pt','ru','tr')]
  [string]$Language,
  [string]$BundledArchive = ''
)
$ErrorActionPreference = 'Stop'
$catalogue = @{
  de = @('vosk-model-small-de-0.15','b7e53c90b1f0a38456f4cd62b366ecd58803cd97cd42b06438e2c131713d5e43')
  en = @('vosk-model-small-en-us-0.15','30f26242c4eb449f948e42cb302dd7a686cb29a3423a8367f99ff41780942498')
  es = @('vosk-model-small-es-0.42','09b239888f633ef2f0b4e09736e3d9936acfd810bc65d53fad45261762c6511f')
  fr = @('vosk-model-small-fr-0.22','cabf6180e177eb9b3a9a9d43a437bd5e549f3a7d09525e5d69a3fed787be12ad')
  it = @('vosk-model-small-it-0.22','9ec65e75861d1c6c2e457cccd932705340dcdf233f5b239f00733b4de0bf3267')
  nl = @('vosk-model-small-nl-0.22','039811c3b829de64e4f123a9f684a53784005b212a346ac0b899dc7efce2ed0a')
  pl = @('vosk-model-small-pl-0.22','c4cd16498ea544f446f9e9a55cbd602b71cfe5a2b6f2b0834d81e1b6fce15f0d')
  pt = @('vosk-model-small-pt-0.3','6e1ce909032e1afa7a88e68a3d628ecafff302bdf195befab308826c395e93b7')
  ru = @('vosk-model-small-ru-0.22','961d5ff98a17f4aa6de69864d0aa71fa5bac682301d2b5d17a3f24c5c99a46d4')
  tr = @('vosk-model-small-tr-0.3','8c8d07cec1bce31add14967c16891c84152cdf76d391e33c08278119b9ea96e5')
}
# Correct SHA256 values are copied from independently published Vosk model
# checksums; all must be 64 hex chars and match on download.
$entry=$catalogue[$Language]
$modelName=$entry[0]
$sha=$entry[1]
if ($sha -notmatch '^[0-9a-f]{64}$') { throw "Unverified $Language model checksum. Refusing download." }
$root=Join-Path $env:LOCALAPPDATA 'DizyTV\models'
$destination=Join-Path $root $modelName
if ((Test-Path -LiteralPath (Join-Path $destination 'am') -PathType Container) -and
    (Test-Path -LiteralPath (Join-Path $destination 'conf') -PathType Container)) {
  Write-Host "$modelName already installed; nothing to replace."
  exit 0
}
New-Item -ItemType Directory -Path $root -Force | Out-Null
$work=Join-Path $env:TEMP ("DizyTV-Model-"+[guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $work | Out-Null
try {
  $archive=Join-Path $work 'model.zip'
  if ($BundledArchive) {
    if (-not (Test-Path -LiteralPath $BundledArchive -PathType Leaf)) {
      throw 'Bundled model archive missing'
    }
    Copy-Item -LiteralPath $BundledArchive -Destination $archive
  } else {
    $url="https://alphacephei.com/vosk/models/$modelName.zip"
    Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 240 -MaximumRedirection 4 -OutFile $archive
  }
  if ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $sha) {
    throw 'Vosk model checksum mismatch. No model installed.'
  }
  $unpack=Join-Path $work 'unpacked'
  Expand-Archive -LiteralPath $archive -DestinationPath $unpack
  $candidate=Join-Path $unpack $modelName
  if (-not (Test-Path -LiteralPath (Join-Path $candidate 'am') -PathType Container) -or
      -not (Test-Path -LiteralPath (Join-Path $candidate 'conf') -PathType Container)) {
    throw 'Invalid Vosk model archive structure'
  }
  if (Test-Path -LiteralPath $destination) {
    throw 'Model destination exists with unexpected content; not overwriting'
  }
  Move-Item -LiteralPath $candidate -Destination $destination
  Write-Host "$Language Vosk model installed for DizyTV."
} finally {
  Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue
}
