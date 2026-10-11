# Runs only during a DizyTV Windows upgrade, before Inno Setup replaces files.
# Scope termination to --worker processes running from this exact installed executable.
# Never stop a worker while a recording is active or due imminently.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$InstalledExePath,
    [Parameter(Mandatory=$true)][string]$DataDirectory
)
$ErrorActionPreference = 'Stop'
try {
    $exe = [IO.Path]::GetFullPath($InstalledExePath)
    function Is-InstalledDizyWorker($p) {
        return ($null -ne $p -and
            -not [string]::IsNullOrEmpty($p.ExecutablePath) -and
            [string]::Equals([IO.Path]::GetFullPath($p.ExecutablePath), $exe, [StringComparison]::OrdinalIgnoreCase) -and
            $p.CommandLine -match '(?i)(?:^|\s)--worker(?:\s|$)')
    }
    $workers = @(Get-CimInstance Win32_Process -Filter "Name = 'DizyTV.exe'" |
        Where-Object { Is-InstalledDizyWorker $_ })
    if ($workers.Count -eq 0) { exit 0 }

    $statePath = Join-Path $DataDirectory 'state.json'
    if (Test-Path -LiteralPath $statePath) {
        $state = Get-Content -LiteralPath $statePath -Encoding UTF8 -Raw | ConvertFrom-Json
        $now = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
        $busy = @($state.jobs | Where-Object {
            $_.status -in @('recording','starting') -or
            ($_.status -eq 'queued' -and [long]$_.start -le ($now + 120) -and [long]$_.end -gt $now)
        })
        if ($busy.Count -gt 0) {
            [Console]::Error.WriteLine('Recording active or due within two minutes. Stop/finish it in DizyTV, then run Setup again.')
            exit 2
        }
    }

    # Earlier 0.1.x workers have no cooperative stop IPC. Only an idle, exactly
    # matched DizyTV recorder may be terminated, leaving state and video intact.
    foreach ($worker in $workers) {
        $current = Get-CimInstance Win32_Process -Filter ("ProcessId = {0}" -f $worker.ProcessId)
        if (Is-InstalledDizyWorker $current) {
            Stop-Process -Id ([int]$worker.ProcessId) -ErrorAction Stop
        }
    }
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        $remaining = @(Get-CimInstance Win32_Process -Filter "Name = 'DizyTV.exe'" |
            Where-Object { Is-InstalledDizyWorker $_ })
        if ($remaining.Count -eq 0) { exit 0 }
        Start-Sleep -Milliseconds 200
    }
    [Console]::Error.WriteLine('Background DizyTV recorder did not exit; installation cannot safely continue.')
    exit 3
}
catch {
    [Console]::Error.WriteLine('Could not verify/stop the DizyTV recorder safely: ' + $_.Exception.Message)
    exit 3
}
