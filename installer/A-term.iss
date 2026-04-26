; Inno Setup script for A-term
; Build app first so dist\A-term\ exists.

#define MyAppName "A-term"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "A-term"
#define MyAppExeName "A-term.exe"

[Setup]
AppId={{B25BB2B5-42F5-45CC-8F29-E25C2110BBE5}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\A-term
DefaultGroupName=A-term
OutputDir=..\dist-installer
OutputBaseFilename=A-term-Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop icon"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
Source: "..\dist\A-term\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs

[Icons]
Name: "{group}\A-term"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\A-term"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch A-term"; Flags: nowait postinstall skipifsilent
