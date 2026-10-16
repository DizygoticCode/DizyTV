# Optional third-party Ace Stream installation for Windows DizyTV Setup.
# Only invoked after the person explicitly ticks the unchecked Inno task.
# DizyTV never redistributes or modifies the proprietary original installer.
param(
    [switch]$DryRun
)
$ErrorActionPreference = 'Stop'
$officialPage = 'https://docs.acestream.net/products/'
$uri = [Uri]'https://download.acestream.media/products/acestream-full/win/latest'
$allowedHosts = @('download.acestream.media','dl.acestream.org','download.acestream.org')
$maxBytes = 160MB

function Test-PublisherLocation([Uri]$location) {
    if ($location.Scheme -ne 'https' -or $location.Host -notin $allowedHosts) {
        throw 'Ace Stream publisher redirect is not an approved HTTPS endpoint.'
    }
}

function Download-OfficialAce([string]$output) {
    $handler = [System.Net.Http.HttpClientHandler]::new()
    $handler.AllowAutoRedirect = $false
    $client = [System.Net.Http.HttpClient]::new($handler)
    $client.Timeout = [TimeSpan]::FromMinutes(4)
    try {
        $next = $uri
        $response = $null
        for ($i = 0; $i -lt 6; $i++) {
            Test-PublisherLocation $next
            $response = $client.GetAsync($next, [System.Net.Http.HttpCompletionOption]::ResponseHeadersRead).GetAwaiter().GetResult()
            if ([int]$response.StatusCode -in @(301,302,303,307,308)) {
                $redirect = $response.Headers.Location
                if ($null -eq $redirect) { throw 'The publisher redirect did not include a location.' }
                $next = [Uri]::new($next, $redirect)
                $response.Dispose()
                $response = $null
                continue
            }
            if (-not $response.IsSuccessStatusCode) { throw 'Publisher returned an unsuccessful HTTP response.' }
            break
        }
        if ($null -eq $response -or -not $response.IsSuccessStatusCode) { throw 'Too many publisher redirects.' }
        if ($response.Content.Headers.ContentLength -gt $maxBytes) { throw 'Third-party installer is unexpectedly large.' }
        $mediaType = $response.Content.Headers.ContentType.MediaType
        if ($mediaType -in @('text/html','text/plain')) { throw 'Publisher returned text rather than an installer.' }
        $inputStream = $response.Content.ReadAsStreamAsync().GetAwaiter().GetResult()
        $saved = [System.IO.File]::Create($output)
        try {
            $buffer = New-Object byte[] 1048576
            [long]$total = 0
            while (($got = $inputStream.Read($buffer, 0, $buffer.Length)) -gt 0) {
                $total += $got
                if ($total -gt $maxBytes) { throw 'Third-party installer exceeded the download size limit.' }
                $saved.Write($buffer, 0, $got)
                Write-Progress -Activity 'Downloading official Ace Stream installer' -Status ("{0:N1} MiB" -f ($total / 1MB))
            }
            if ($total -lt 1048576) { throw 'Downloaded installer is too small.' }
            if ($response.Content.Headers.ContentLength.HasValue -and $total -ne $response.Content.Headers.ContentLength.Value) {
                throw 'Ace Stream installer download was incomplete.'
            }
        } finally {
            $saved.Dispose()
            $inputStream.Dispose()
            Write-Progress -Activity 'Downloading official Ace Stream installer' -Completed
        }
    } finally {
        if ($null -ne $response) { $response.Dispose() }
        $client.Dispose()
        $handler.Dispose()
    }
}

function Confirm-OfficialSigner([string]$filename) {
    $signature = Get-AuthenticodeSignature -LiteralPath $filename
    if ($signature.Status -ne 'Valid' -or $null -eq $signature.SignerCertificate) {
        throw 'The downloaded Ace Stream installer lacks a trusted valid Authenticode signature.'
    }
    $name = $signature.SignerCertificate.Subject
    # Exact known original Ace Stream company; never treat *any* valid signer
    # as official. If the publisher changes, require a fresh independent audit.
    if ($name -notmatch '(?i)(INNOVATIVE DIGITAL TECHNOLOGIES)') {
        throw 'The third-party installer signer is not the previously verified Ace Stream publisher.'
    }
}

if ($DryRun) {
    Test-PublisherLocation $uri
    Write-Output 'Official Ace Stream bootstrap validation OK; nothing downloaded or executed.'
    exit 0
}

$working = Join-Path $env:TEMP ("DizyTV-Ace-" + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $working -Force | Out-Null
$installer = Join-Path $working 'OfficialAceStreamSetup.exe'
try {
    Write-Host 'Ace Stream is optional proprietary P2P software; you will review its original publisher setup and licence.'
    Download-OfficialAce $installer
    Confirm-OfficialSigner $installer
    Write-Host 'Publisher identity verified. Launching the unchanged original installer...'
    $child = Start-Process -FilePath $installer -PassThru -Wait
    if ($child.ExitCode -ne 0) {
        throw 'The original Ace Stream installation was cancelled or did not complete successfully.'
    }
} catch {
    Write-Warning 'Optional Ace Stream setup could not be completed safely; DizyTV core installation is unaffected.'
    Write-Warning 'For a manual publisher install, use https://docs.acestream.net/products/'
    Write-Warning $_.Exception.Message
    exit 1
} finally {
    Remove-Item -LiteralPath $working -Recurse -Force -ErrorAction SilentlyContinue
}
