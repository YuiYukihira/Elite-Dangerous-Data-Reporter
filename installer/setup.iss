#define AppVersion GetEnv("APP_VERSION")
#define InputDir   GetEnv("INPUT_DIR")
#define OutputDirA GetEnv("OUTPUT_DIR")
#define AppExe     "Elite Dangerous Data Reporter.exe"

#pragma message "AppVersion = {#AppVersion}"
#pragma message "InputDir   = {#InputDir}"
#pragma message "OutputDir  = {#OutputDirA}"
#pragma message "AppExe     = {#AppExe}"

[Setup]
AppName=Elite Dangerous Data Reporter
AppVersion={#AppVersion}
AppId={{f57e29cc-5cc7-4350-84c2-19f659dffad9}}
WizardStyle=modern
DefaultDirName={autopf}\EDDR
DefaultGroupName=YuiYukihira
OutputDir={#OutputDirA}
OutputBaseFilename=EDDR-Setup-{#AppVersion}
Compression=lzma
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=no

[Files]
Source: "{#InputDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"
Name: "startmenuicon"; Description: "Create a &Start Menu shortcut"; GroupDescription: "Additional shortcuts:"
Name: "quicklaunchicon"; Description: "Create a &Quick Launch shortcut"; GroupDescription: "Additional shortcuts:"

[Run]
Filename: "{app}\{#AppExe}"; Description: "Launch EDDR"; Flags: nowait postinstall skipifsilent