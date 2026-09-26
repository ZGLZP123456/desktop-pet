; ============================================================
;  桌面宠物 · Inno Setup 安装脚本
;  编译：ISCC.exe packaging\desktop_pet_installer.iss
;  产物：installer\桌面宠物_安装程序_v1.0.0.exe
; ============================================================

#define AppName "桌面宠物"
#define AppVersion "1.0.0"
#define AppPublisher "桌面宠物"
#define AppExeName "DesktopPet.exe"

[Setup]
; AppId 固定不变，保证后续版本能识别为「升级」而不是并存安装
AppId={{B7E4F1C2-5A3D-4E8B-9C1F-2D6A7B8E9F01}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\DesktopPet
DefaultGroupName={#AppName}
; 单目录程序，不需要让用户选开始菜单分组
DisableProgramGroupPage=yes
; 按用户安装，不弹 UAC 提权框（装到 %LOCALAPPDATA%\Programs）
PrivilegesRequired=lowest
OutputDir=..\installer
OutputBaseFilename=桌面宠物_安装程序_v{#AppVersion}
SetupIconFile=app.ico
UninstallDisplayIcon={app}\{#AppExeName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
; 打包的是 64 位 exe
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; 覆盖安装时自动关闭正在运行的旧版本
CloseApplications=yes
; 卸载时保留 %APPDATA%\桌面宠物 里的配置，重装后设置还在
UninstallDisplayName={#AppName}

[Languages]
Name: "chinese"; MessagesFile: "ChineseSimplified.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加任务:"; Flags: checkedonce

[Files]
; 打包 PyInstaller 产出的整个目录（exe + _internal 依赖）
Source: "..\dist\DesktopPet\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\卸载 {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "立即运行 {#AppName}"; Flags: nowait postinstall skipifsilent
