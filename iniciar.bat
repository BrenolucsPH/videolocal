@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  echo Python 3.11 ou superior nao foi encontrado. Instale pelo site python.org e marque "Add Python to PATH".
  pause
  exit /b 1
)
py -3 -c "import sys; raise SystemExit(sys.version_info < (3, 11))" >nul 2>nul
if errorlevel 1 (
  echo Este projeto precisa do Python 3.11 ou superior.
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  echo Preparando ambiente isolado do VideoLocal...
  py -3 -m venv .venv
  if errorlevel 1 goto erro
)
echo Conferindo yt-dlp e suporte oficial pelo PyPI...
.venv\Scripts\python.exe -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto erro
echo Abrindo VideoLocal...
start "" .venv\Scripts\pythonw.exe app.py
if errorlevel 1 goto erro
exit /b 0
:erro
echo Algo deu errado. Consulte README.md para orientacoes.
pause
exit /b 1
