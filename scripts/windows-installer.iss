#define AppVersion "0.1.2-alpha"
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
OutputBaseFilename=DizyTV-Setup-0.1.2-alpha-windows-x64
SetupIconFile=..\assets\branding\dizytv.ico
UninstallDisplayIcon={app}\DizyTV.exe
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
Compression=lzma2
SolidCompression=yes
CloseApplications=yes
RestartApplications=no

[Files]
Source: "..\dist\DizyTV\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\THIRD-PARTY-NOTICES.md"; DestDir: "{app}"

[Icons]
Name: "{group}\DizyTV"; Filename: "{app}\DizyTV.exe"
Name: "{autodesktop}\DizyTV"; Filename: "{app}\DizyTV.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Code]
// This runs before Restart Manager checks open DLLs/executables.
// The 0.1.1 recorder intentionally stays open after the UI exits.
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ExistingExe, StopScript, PowerShell, Args: String;
  ExitCode: Integer;
begin
  Result := '';
  ExistingExe := ExpandConstant('{app}\\DizyTV.exe');
  if not FileExists(ExistingExe) then Exit;

  ExtractTemporaryFile('windows-stop-worker.ps1');
  StopScript := ExpandConstant('{tmp}\\windows-stop-worker.ps1');
  PowerShell := ExpandConstant('{sys}\\WindowsPowerShell\\v1.0\\powershell.exe');
  Args := '-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "' + StopScript +
    '" -InstalledExePath "' + ExistingExe +
    '" -DataDirectory "' + ExpandConstant('{localappdata}\\DizyTV') + '"';

  if not Exec(PowerShell, Args, '', SW_HIDE, ewWaitUntilTerminated, ExitCode) then
  begin
    Result := 'DizyTV Setup could not check the existing background recorder. Close DizyTV and retry.';
    Exit;
  end;
  if ExitCode = 2 then
    Result := 'A DizyTV recording is active or due soon. Let it finish (or stop it in the app) and run Setup again.'
  else if ExitCode <> 0 then
    Result := 'The DizyTV background recorder could not be closed safely. Please check Task Manager and retry.';
end;
