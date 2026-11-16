# Gera dist\VideoLocal\VideoLocal.exe
# Uso (PowerShell, na pasta do projeto):  .\build.ps1
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
Set-Location $root

$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Host "Criando ambiente virtual..."
    py -3 -m venv .venv
}

Write-Host "Instalando dependencias..."
& $python -m pip install --disable-pip-version-check -q -r requirements.txt -r requirements-build.txt
if ($LASTEXITCODE -ne 0) { throw "Falha ao instalar dependencias." }

Write-Host "Gerando icones..."
& $python tools\make_icon.py
if ($LASTEXITCODE -ne 0) { throw "Falha ao gerar icones." }

Write-Host "Empacotando com PyInstaller..."
& $python -m PyInstaller --noconfirm --clean --log-level WARN `
    --windowed --name VideoLocal `
    --icon (Join-Path $root "assets\icon.ico") `
    --add-data "$(Join-Path $root 'assets');assets" `
    --collect-data customtkinter `
    --collect-data yt_dlp_ejs `
    --specpath build --workpath build --distpath dist `
    app.py
if ($LASTEXITCODE -ne 0) { throw "Falha no PyInstaller." }

# O FFmpeg viaja ao lado do executavel (bin\), onde o app o procura.
$target = Join-Path $root "dist\VideoLocal\bin"
New-Item -ItemType Directory -Force $target | Out-Null
$copied = $false
foreach ($tool in "ffmpeg.exe", "ffprobe.exe") {
    $source = Join-Path $root "bin\$tool"
    if (Test-Path $source) { Copy-Item $source $target -Force; $copied = $true }
}
if (-not $copied) {
    Write-Warning "bin\ffmpeg.exe nao encontrado: o executavel funciona, mas sem MP3 e sem as melhores qualidades."
}

Write-Host ""
Write-Host "Pronto: $(Join-Path $root 'dist\VideoLocal\VideoLocal.exe')"
