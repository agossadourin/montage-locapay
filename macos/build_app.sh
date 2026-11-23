#!/bin/bash
# Crée « Raccord.app » (dans /Applications, ou ~/Applications à défaut).
# L'app est un lanceur léger : elle exécute le code de ce dossier, donc chaque
# « git pull » est pris en compte au prochain lancement, sans reconstruire l'app.
set -e
REPO="$(cd "$(dirname "$0")/.." && pwd)"
NOM="Raccord"
EXE="Raccord"
VERSION="$(cat "$REPO/VERSION" 2>/dev/null || echo 0.0.0)"

DEST="/Applications"
[ -w "$DEST" ] || DEST="$HOME/Applications"
mkdir -p "$DEST"
APP="$DEST/$NOM.app"
# ancienne version (« Montage Locapay ») : remplacée par Raccord
rm -rf "/Applications/Montage Locapay.app" "$HOME/Applications/Montage Locapay.app" 2>/dev/null || true

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp "$REPO/macos/AppIcon.icns" "$APP/Contents/Resources/AppIcon.icns"

cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>$NOM</string>
  <key>CFBundleDisplayName</key><string>$NOM</string>
  <key>CFBundleIdentifier</key><string>app.raccord.mac</string>
  <key>CFBundleExecutable</key><string>$EXE</string>
  <key>CFBundleIconFile</key><string>AppIcon</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>$VERSION</string>
  <key>CFBundleVersion</key><string>$VERSION</string>
  <key>LSMinimumSystemVersion</key><string>12.0</string>
  <key>LSApplicationCategoryType</key><string>public.app-category.video</string>
  <key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
PLIST

cat > "$APP/Contents/MacOS/$EXE" <<LANCEUR
#!/bin/bash
REPO="$REPO"
export PATH="/opt/homebrew/bin:/usr/local/bin:\$HOME/.local/bin:\$PATH"
LOG="\$HOME/Library/Logs/Raccord.log"
if [ ! -x "\$REPO/.venv/bin/python" ]; then
  osascript -e 'display alert "Raccord" message "Installation incomplète : lancez Installer.command dans le dossier du projet."'
  exit 1
fi
echo "=== \$(date) — lancement ===" >> "\$LOG"
exec "\$REPO/.venv/bin/python" "\$REPO/app/fenetre.py" >> "\$LOG" 2>&1
LANCEUR
chmod +x "$APP/Contents/MacOS/$EXE"

codesign --force --deep -s - "$APP" >/dev/null 2>&1 || true
touch "$APP"
echo "✅ App créée : $APP (version $VERSION)"
