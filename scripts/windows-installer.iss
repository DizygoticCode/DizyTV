#define AppVersion "0.1.9-alpha"
#define BundleRoot AddBackslash(SourcePath) + "vendor\windows"
#if FileExists(BundleRoot + "\AceStreamSetup.exe") && FileExists(BundleRoot + "\AceStreamSetup.sha256")
  #define HasAceInstaller
#endif
#if FileExists(BundleRoot + "\ffmpeg.exe")
  #define HasFFmpeg
#endif
#if FileExists(BundleRoot + "\vosk-en.zip")
  #define HasEnglishModel
#endif
[Setup]
AppId={{3F1997BD-12C5-4C17-B013-09C82DA8BAF6}
AppName=DizyTV
AppVersion={#AppVersion}
AppPublisher=DizygoticCode
AppPublisherURL=https://github.com/DizygoticCode/DizyTV
DefaultDirName={localappdata}\Programs\DizyTV
DefaultGroupName=DizyTV
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=DizyTV-Setup-0.1.9-alpha-windows-x64
SetupIconFile=..\assets\branding\dizytv.ico
UninstallDisplayIcon={app}\DizyTV.exe
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
Compression=lzma2
SolidCompression=yes
CloseApplications=yes
RestartApplications=no

[Files]
Source: "windows-stop-worker.ps1"; Flags: dontcopy
Source: "..\dist\DizyTV\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\THIRD-PARTY-NOTICES.md"; DestDir: "{app}"
Source: "windows-install-vosk-model.ps1"; DestDir: "{tmp}"; Flags: deleteafterinstall
#ifdef HasFFmpeg
Source: "vendor\windows\ffmpeg.exe"; DestDir: "{app}\tools"; Tasks: ffmpegsetup; Flags: ignoreversion
Source: "vendor\windows\FFmpeg-LICENSE.txt"; DestDir: "{app}\tools"; Tasks: ffmpegsetup; Flags: ignoreversion
#endif
#ifdef HasEnglishModel
Source: "vendor\windows\vosk-en.zip"; DestDir: "{tmp}"; Tasks: vosken; Flags: deleteafterinstall
#endif
#ifdef HasAceInstaller
; The ORIGINAL verified third-party EXE, not its engine bits, is included.
Source: "vendor\windows\AceStreamSetup.exe"; DestDir: "{tmp}"; Tasks: acestreamsetup; Flags: deleteafterinstall
#endif

[Icons]
Name: "{group}\DizyTV"; Filename: "{app}\DizyTV.exe"
Name: "{autodesktop}\DizyTV"; Filename: "{app}\DizyTV.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked
; These boxes are always optional. English defaults to ticked only when
; the verified local English model is included by the packaging job.
#ifdef HasEnglishModel
Name: "vosken"; Description: "Offline subtitles: English (US) speech model (~40 MB; preselected)"; Flags: checkedonce
#endif
Name: "voskde"; Description: "Offline subtitles: German (download verified model during setup)"; Flags: unchecked
Name: "voskes"; Description: "Offline subtitles: Spanish (download verified model during setup)"; Flags: unchecked
Name: "voskfr"; Description: "Offline subtitles: French (download verified model during setup)"; Flags: unchecked
Name: "voskit"; Description: "Offline subtitles: Italian (download verified model during setup)"; Flags: unchecked
Name: "vosknl"; Description: "Offline subtitles: Dutch (download verified model during setup)"; Flags: unchecked
Name: "voskpl"; Description: "Offline subtitles: Polish (download verified model during setup)"; Flags: unchecked
Name: "voskpt"; Description: "Offline subtitles: Portuguese (download verified model during setup)"; Flags: unchecked
Name: "voskru"; Description: "Offline subtitles: Russian (download verified model during setup)"; Flags: unchecked
Name: "vosktr"; Description: "Offline subtitles: Turkish (download verified model during setup)"; Flags: unchecked
#ifdef HasFFmpeg
Name: "ffmpegsetup"; Description: "Install FFmpeg for speech-generated subtitles (portable, bundled)"; Flags: checkedonce
#endif
#ifdef HasAceInstaller
Name: "acestreamsetup"; Description: "Launch original Ace Stream setup after DizyTV (unchanged third-party P2P software)"; Flags: unchecked
#endif

[Run]
#ifdef HasEnglishModel
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File ""{tmp}\windows-install-vosk-model.ps1"" -Language en -BundledArchive ""{tmp}\vosk-en.zip"""; Description: "Install bundled English speech model"; Tasks: vosken; Flags: runhidden skipifsilent waituntilterminated
#endif
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File ""{tmp}\windows-install-vosk-model.ps1"" -Language de"; Description: "Install verified German speech model"; Tasks: voskde; Flags: runhidden skipifsilent waituntilterminated
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File ""{tmp}\windows-install-vosk-model.ps1"" -Language es"; Description: "Install verified Spanish speech model"; Tasks: voskes; Flags: runhidden skipifsilent waituntilterminated
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File ""{tmp}\windows-install-vosk-model.ps1"" -Language fr"; Description: "Install verified French speech model"; Tasks: voskfr; Flags: runhidden skipifsilent waituntilterminated
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File ""{tmp}\windows-install-vosk-model.ps1"" -Language it"; Description: "Install verified Italian speech model"; Tasks: voskit; Flags: runhidden skipifsilent waituntilterminated
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File ""{tmp}\windows-install-vosk-model.ps1"" -Language nl"; Description: "Install verified Dutch speech model"; Tasks: vosknl; Flags: runhidden skipifsilent waituntilterminated
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File ""{tmp}\windows-install-vosk-model.ps1"" -Language pl"; Description: "Install verified Polish speech model"; Tasks: voskpl; Flags: runhidden skipifsilent waituntilterminated
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File ""{tmp}\windows-install-vosk-model.ps1"" -Language pt"; Description: "Install verified Portuguese speech model"; Tasks: voskpt; Flags: runhidden skipifsilent waituntilterminated
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File ""{tmp}\windows-install-vosk-model.ps1"" -Language ru"; Description: "Install verified Russian speech model"; Tasks: voskru; Flags: runhidden skipifsilent waituntilterminated
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File ""{tmp}\windows-install-vosk-model.ps1"" -Language tr"; Description: "Install verified Turkish speech model"; Tasks: vosktr; Flags: runhidden skipifsilent waituntilterminated
#ifdef HasAceInstaller
; Run original Ace setup normally: it presents its OWN licence and consent.
Filename: "{tmp}\AceStreamSetup.exe"; Description: "Install Ace Stream using its original unmodified setup"; Tasks: acestreamsetup; Flags: postinstall skipifsilent waituntilterminated
#endif

[Code]
// This runs before Restart Manager checks open DLLs/executables.
// The 0.1.1 recorder intentionally stays open after the UI exits.
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ExistingExe, StopScript, PowerShell, Args: String;
  ExitCode: Integer;
begin
  Result := '';
  ExistingExe := ExpandConstant('{app}\DizyTV.exe');
  if not FileExists(ExistingExe) then Exit;

  try
    ExtractTemporaryFile('windows-stop-worker.ps1');
  except
    Result := 'The embedded DizyTV updater check is unavailable. No application files were replaced.';
    Exit;
  end;
  StopScript := ExpandConstant('{tmp}\windows-stop-worker.ps1');
  PowerShell := ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe');
  Args := '-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "' + StopScript +
    '" -InstalledExePath "' + ExistingExe +
    '" -DataDirectory "' + ExpandConstant('{localappdata}\DizyTV') + '"';

  if not Exec(PowerShell, Args, '', SW_HIDE, ewWaitUntilTerminated, ExitCode) then
  begin
    Result := 'DizyTV Setup could not check the existing background recorder. Close DizyTV and retry.';
    Exit;
  end;
  if ExitCode = 4 then
    Result := 'Close the open DizyTV application before upgrading. No files were replaced.'
  else if ExitCode = 2 then
    Result := 'A DizyTV recording is active or due soon. Let it finish (or stop it in the app) and run Setup again.'
  else if ExitCode <> 0 then
    Result := 'The DizyTV background recorder could not be closed safely. Please check Task Manager and retry.';
end;
