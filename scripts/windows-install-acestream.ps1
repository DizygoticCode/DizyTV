# Optional original Ace Stream setup helper for DizyTV's Windows Inno installer.
# Not bundled and NOT installed unless the user checks the third-party task.
# Runs only after the core DizyTV installer has completed.
param([switch]$TestOnly)
$ErrorActionPreference = 'Stop'
$official = 'https://download.acestream.media/products/acestream-full/win/latest'
$officialPage = 'https://docs.acestream.media/products/'
$allowedHosts = @('download.acestream.media','dl.acestream.org')
$maxBytes = 180MB

function Find-ExistingAceEngine {
    # Preserve a previously installed original vendor engine. Do not
    # redownload or overwrite it merely because DizyTV is being upgraded.
    $folders = @()
    if ($env:APPDATA) { $folders += (Join-Path $env:APPDATA 'ACEStream\engine') }
    if ($env:LOCALAPPDATA) { $folders += (Join-Path $env:LOCALAPPDATA 'ACEStream\engine') }
    foreach ($key in @('HKCU:\Software\ACEStream','HKCU:\Software\Wow6432Node\ACEStream')) {
        try {
            $item = Get-ItemProperty -Path $key -ErrorAction Stop
            if ($item.InstallDir) {
                $folders += $item.InstallDir
                $folders += (Join-Path $item.InstallDir 'engine')
            }
        } catch { }
    }
    foreach ($folder in $folders) {
        if ((Test-Path -LiteralPath (Join-Path $folder 'ace_engine.exe') -PathType Leaf) -or
            (Test-Path -LiteralPath (Join-Path $folder 'ace_console.exe') -PathType Leaf)) {
            return $true
        }
    }
    return $false
}

$target = Join-Path $env:TEMP ("dizytv-ace-" + [Guid]::NewGuid().ToString('N') + '.exe')
$http = $null
try {
    Write-Host 'Ace Stream is optional third-party P2P software.'
    Write-Host 'DizyTV does not modify its installer or accept the publisher EULA.'
    if (Find-ExistingAceEngine) {
        Write-Host 'Official Ace Stream engine is already present; leaving that installation unchanged.'
        exit 0
    }
    Add-Type -AssemblyName System.Net.Http
    $handler = New-Object System.Net.Http.HttpClientHandler
    $handler.AllowAutoRedirect = $false
    $http = New-Object System.Net.Http.HttpClient($handler)
    $http.Timeout = [TimeSpan]::FromMinutes(3)
    $uri = [Uri]::new($official)
    $response = $null
    for ($step=0; $step -le 5; $step++) {
        if ($uri.Scheme -ne 'https' -or $uri.Host -notin $allowedHosts -or
            $uri.UserInfo -or $uri.Fragment) {
            throw 'Ace installer redirect left verified HTTPS publisher domains'
        }
        if ($TestOnly) {
            Write-Host ('Validated allowed vendor download origin: ' + $uri.Host)
            exit 0
        }
        if ($response) { $response.Dispose() }
        $response = $http.GetAsync($uri,[System.Net.Http.HttpCompletionOption]::ResponseHeadersRead).GetAwaiter().GetResult()
        $status = [int]$response.StatusCode
        if ($status -in @(301,302,303,307,308)) {
            $next=$response.Headers.Location
            if (-not $next) { throw 'Publisher redirect had no destination' }
            $uri = [Uri]::new($uri,$next)
            continue
        }
        if ($status -ne 200) { throw ('Publisher returned HTTP ' + $status) }
        break
    }
    if (-not $response -or [int]$response.StatusCode -ne 200) {
        throw 'Too many Ace installer redirects'
    }
    if ($response.Content.Headers.ContentLength -gt $maxBytes) {
        throw 'Ace installer is larger than the permitted download limit'
    }
    $stream = $response.Content.ReadAsStreamAsync().GetAwaiter().GetResult()
    $dest = [IO.File]::Open($target,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write)
    try {
        $buffer = New-Object byte[] 1048576
        $total = [long]0
        while (($n=$stream.Read($buffer,0,$buffer.Length)) -gt 0) {
            $total += $n
            if ($total -gt $maxBytes) { throw 'Ace download exceeded size limit' }
            $dest.Write($buffer,0,$n)
        }
    } finally { $dest.Dispose(); $stream.Dispose() }
    if ($total -lt 1024*100) { throw 'Downloaded Ace file is unexpectedly small' }
    # An installer can be large: verify its PE magic from a two-byte read,
    # not a full executable buffer allocation in the installer process.
    $peek=[IO.File]::OpenRead($target)
    try {
        if ($peek.ReadByte() -ne 0x4d -or $peek.ReadByte() -ne 0x5a) {
            throw 'Publisher returned HTML or a non-Windows executable'
        }
    } finally { $peek.Dispose() }
    $signature=Get-AuthenticodeSignature -LiteralPath $target
    if ($signature.Status -ne 'Valid' -or -not $signature.SignerCertificate) {
        throw 'Original Ace installer has no valid trusted Authenticode signature'
    }
    $subject=$signature.SignerCertificate.Subject
    # Fail closed until the signer matches a verified vendor identity.
    # Do not accept an arbitrary *valid* code-signed EXE returned by a CDN.
    if ($subject -notmatch '(^|[, ])(?:CN|O)=(?:"?)(?:Ace Stream|Innovative Digital Technologies)(?:[,"]|$)') {
        throw 'Original Ace installer signer is not on the approved publisher list'
    }
    Write-Host 'Verified trusted publisher signature. Opening the original setup UI and licence.'
    $process = Start-Process -FilePath $target -Wait -PassThru
    if ($process.ExitCode -ne 0) { throw ('Ace setup finished with code ' + $process.ExitCode) }
    Write-Host 'Original Ace Stream setup completed.'
} catch {
    Write-Warning ('Ace Stream optional bootstrap did not complete: ' + $_.Exception.Message)
    Write-Warning ('DizyTV is installed. For a manual attempt, use ' + $officialPage)
    exit 1
} finally {
    if ($response) { $response.Dispose() }
    if ($http) { $http.Dispose() }
    if (Test-Path -LiteralPath $target) { Remove-Item -LiteralPath $target -Force -ErrorAction SilentlyContinue }
}
