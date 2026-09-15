[Setup]
AppId={{982FB3D0-46CA-4A3F-8E2C-D03C2B86E002}
AppName=YiBan
AppVersion=0.3.0
AppPublisher=YangRkai
AppPublisherURL=https://github.com/YangRkai/yiban
DefaultDirName={localappdata}\Programs\YiBan
DefaultGroupName=YiBan
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist\installer
OutputBaseFilename=YiBan-Setup-0.3.0-x64
Compression=lzma2/fast
SolidCompression=yes
WizardStyle=modern
LicenseFile=..\LICENSE
UninstallDisplayIcon={app}\YiBan.exe
[Tasks]
Name: desktopicon; Description: "Create a desktop shortcut"; Flags: unchecked
[Files]
Source: "..\dist\YiBan\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "board\*,*smoke*,acceptance-export.zip,camera-settings.json,compute-settings.json,runtime.json,runtime.cpu.json"
Source: "..\board\runtime.example.json"; DestDir: "{app}\board"; Flags: ignoreversion
Source: "..\board\runtime.cpu.example.json"; DestDir: "{app}\board"; Flags: ignoreversion
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "INSTALL-NOTES.txt"; DestDir: "{app}"; Flags: ignoreversion
[Icons]
Name: "{group}\YiBan"; Filename: "{app}\YiBan.exe"
Name: "{autodesktop}\YiBan"; Filename: "{app}\YiBan.exe"; Tasks: desktopicon
[Run]
Filename: "{app}\YiBan.exe"; Description: "Launch YiBan"; Flags: nowait postinstall skipifsilent

