#define AppVersion "0.1.0-alpha"
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
OutputBaseFilename=DizyTV-Setup-0.1.0-alpha-windows-x64
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
