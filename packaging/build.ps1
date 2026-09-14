$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root
# Install requirements.txt and pyinstaller==6.22.3 in a virtual environment first.
python -m PyInstaller --clean --noconfirm --windowed --onedir --name YiBan --paths board --collect-all cv2 --collect-all cv2_enumerate_cameras --distpath dist --workpath build-work --specpath packaging packaging/launcher.py
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed' }
$cpu = Join-Path $root 'dist/YiBan/engine-cpu'
New-Item $cpu -ItemType Directory -Force | Out-Null
New-Item downloads -ItemType Directory -Force | Out-Null
gh release download v1.16.4 --repo lightvector/KataGo --pattern katago-v1.16.4-eigen-windows-x64.zip --dir downloads --clobber
if ($LASTEXITCODE -ne 0) { throw 'Engine download failed' }
gh release download v1.3 --repo lightvector/KataGo --pattern g170e-b10c128-s1141046784-d204142634.txt.gz --dir downloads --clobber
if ($LASTEXITCODE -ne 0) { throw 'Model download failed' }
Expand-Archive downloads/katago-v1.16.4-eigen-windows-x64.zip $cpu -Force
Copy-Item downloads/g170e-b10c128-s1141046784-d204142634.txt.gz "$cpu/model.txt.gz"
Copy-Item packaging/cpu-gtp.cfg "$cpu/gtp.cfg"
Copy-Item packaging/KataGo-LICENSE.txt "$cpu/LICENSE.txt"
# Include licenses for installed Python and dependency wheels in dist/YiBan/licenses.
# Compile with Inno Setup 6 (ISCC must be on PATH).
ISCC packaging/installer.iss
if ($LASTEXITCODE -ne 0) { throw 'Installer build failed' }
