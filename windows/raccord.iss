; Raccord — installateur Windows (Inno Setup 6). Compilé par GitHub Actions :
;   iscc /DMaVersion=1.6.0 windows\raccord.iss   ->   dist\Raccord-Setup-1.6.0.exe
; Le Setup copie l'app puis lance windows\installer.ps1, qui installe Python, ffmpeg et le modèle
; dans le dossier de Raccord (aucun droit administrateur nécessaire).

#ifndef MaVersion
  #define MaVersion "0.0.0"
#endif

[Setup]
AppId={{57FBB8C0-562E-4CD9-AD53-2043EAAD9AD8}
AppName=Raccord
AppVersion={#MaVersion}
AppVerName=Raccord {#MaVersion}
AppPublisher=Raccord
DefaultDirName={localappdata}\Programs\Raccord
DefaultGroupName=Raccord
DisableProgramGroupPage=yes
DisableDirPage=auto
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=Raccord-Setup-{#MaVersion}
SetupIconFile=Raccord.ico
UninstallDisplayIcon={app}\windows\Raccord.ico
UninstallDisplayName=Raccord
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
CloseApplications=yes

[Languages]
Name: "fr"; MessagesFile: "compiler:Languages\French.isl"

[Messages]
fr.FinishedLabel=Raccord est installé. Vos vidéos montées iront dans Vidéos › Raccord.

[Tasks]
Name: "bureau"; Description: "Créer une icône sur le Bureau"
Name: "ollama"; Description: "Installer aussi l'IA locale gratuite (Ollama, environ 4 Go)"; Flags: unchecked

[Files]
Source: "..\app\*"; DestDir: "{app}\app"; Excludes: "__pycache__,*.pyc"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "..\requirements\windows*.txt"; DestDir: "{app}\requirements"; Flags: ignoreversion
Source: "installer.ps1"; DestDir: "{app}\windows"; Flags: ignoreversion
Source: "ollama.ps1"; DestDir: "{app}\windows"; Flags: ignoreversion
Source: "Raccord.ico"; DestDir: "{app}\windows"; Flags: ignoreversion
Source: "..\macos\AppIcon.png"; DestDir: "{app}\macos"; Flags: ignoreversion
Source: "..\VERSION"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\CHANGELOG.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\Lancer Raccord (Windows).bat"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\Raccord"; Filename: "{app}\.venv\Scripts\pythonw.exe"; Parameters: "-X utf8 ""{app}\app\fenetre.py"""; WorkingDir: "{app}"; IconFilename: "{app}\windows\Raccord.ico"; Comment: "Le montage face caméra, dans votre style"
Name: "{autodesktop}\Raccord"; Filename: "{app}\.venv\Scripts\pythonw.exe"; Parameters: "-X utf8 ""{app}\app\fenetre.py"""; WorkingDir: "{app}"; IconFilename: "{app}\windows\Raccord.ico"; Tasks: bureau
Name: "{autoprograms}\Raccord (outils)\Installer l'IA locale (Ollama)"; Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\windows\ollama.ps1"""; WorkingDir: "{app}"
Name: "{autoprograms}\Raccord (outils)\Réparer l'installation"; Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\windows\installer.ps1"" -DepuisSetup"; WorkingDir: "{app}"
Name: "{autoprograms}\Raccord (outils)\Lancer Raccord avec la console"; Filename: "{app}\Lancer Raccord (Windows).bat"; WorkingDir: "{app}"; IconFilename: "{app}\windows\Raccord.ico"

[Run]
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\windows\installer.ps1"" -DepuisSetup"; WorkingDir: "{app}"; StatusMsg: "Installation de Python, ffmpeg et du modèle de transcription (10 à 20 minutes)..."; Flags: waituntilterminated
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\windows\ollama.ps1"""; WorkingDir: "{app}"; StatusMsg: "Installation de l'IA locale..."; Tasks: ollama; Flags: waituntilterminated
Filename: "{app}\.venv\Scripts\pythonw.exe"; Parameters: "-X utf8 ""{app}\app\fenetre.py"""; WorkingDir: "{app}"; Description: "Ouvrir Raccord"; Flags: postinstall nowait skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\.venv"
Type: filesandordirs; Name: "{app}\outils"
Type: filesandordirs; Name: "{app}\app"
