@echo off
rem StartupValue - inicia a API (porta 8000) e o site (porta 3000) em modo local.
rem Para parar: feche as janelas "StartupValue API" e "StartupValue Site".
setlocal
title StartupValue
cd /d "%~dp0"

echo ================================================
echo   StartupValue - iniciando o ambiente local
echo ================================================
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo [ERRO] Python nao encontrado. Instale o Python 3.11+ e tente de novo.
  goto :fail
)
where npm >nul 2>nul
if errorlevel 1 (
  echo [ERRO] Node.js/npm nao encontrado. Instale o Node.js 24+ e tente de novo.
  goto :fail
)

python -c "import fastapi, uvicorn, alembic, httpx" >nul 2>nul
if errorlevel 1 (
  echo Instalando dependencias do backend - so na primeira vez...
  python -m pip install --require-hashes --no-deps -r "apps\backend\requirements-dev.lock.txt"
  if errorlevel 1 (
    echo [ERRO] Falha ao instalar as dependencias do backend.
    goto :fail
  )
  python -m pip install -e "apps\backend" --no-deps
  if errorlevel 1 (
    echo [ERRO] Falha ao registrar o pacote do backend.
    goto :fail
  )
)

if not exist "node_modules\" (
  echo Instalando dependencias do frontend - so na primeira vez...
  call npm ci
  if errorlevel 1 (
    echo [ERRO] Falha ao instalar as dependencias do frontend.
    goto :fail
  )
)

rem Banco SQLite local em apps\backend\tmp (ignorado pelo git).
set "DATABASE_URL=sqlite:///tmp/local.db"
if not exist "apps\backend\tmp\" mkdir "apps\backend\tmp"
set "NEW_DB=0"
if not exist "apps\backend\tmp\local.db" set "NEW_DB=1"

echo Preparando o banco de dados local...
pushd "apps\backend"
python -m alembic upgrade head >nul 2>nul
if errorlevel 1 (
  popd
  echo [ERRO] Falha ao preparar o banco de dados.
  goto :fail
)
popd

netstat -ano | findstr /r /c:":8000 .*LISTENING" >nul
if errorlevel 1 (
  echo Iniciando a API na porta 8000...
  start "StartupValue API" /d "%~dp0apps\backend" cmd /k python -m uvicorn app.main:app --port 8000
) else (
  echo A API ja esta rodando na porta 8000.
)

netstat -ano | findstr /r /c:":3000 .*LISTENING" >nul
if errorlevel 1 (
  echo Iniciando o site na porta 3000...
  start "StartupValue Site" /d "%~dp0" cmd /k npm --workspace apps/frontend run dev
) else (
  echo O site ja esta rodando na porta 3000.
)

echo.
echo Aguardando a API responder...
set /a TRIES=0
:wait_api
curl -s -o nul http://localhost:8000/health/live
if not errorlevel 1 goto :api_ready
set /a TRIES+=1
if %TRIES% geq 90 (
  echo [ERRO] A API nao respondeu em 90 segundos. Veja a janela "StartupValue API".
  goto :fail
)
timeout /t 1 /nobreak >nul
goto :wait_api
:api_ready

if "%NEW_DB%"=="1" (
  echo Criando a conta demo com uma simulacao pronta...
  python "apps\backend\scripts\seed_demo.py"
)

echo Aguardando o site responder...
set /a TRIES=0
:wait_site
curl -s -o nul http://localhost:3000/
if not errorlevel 1 goto :site_ready
set /a TRIES+=1
if %TRIES% geq 120 (
  echo [ERRO] O site nao respondeu em 120 segundos. Veja a janela "StartupValue Site".
  goto :fail
)
timeout /t 1 /nobreak >nul
goto :wait_site
:site_ready

start "" "http://localhost:3000/"
echo.
echo ================================================
echo   Pronto! Site: http://localhost:3000
echo   Conta demo:  demo@startupvalue.local
echo   Senha demo:  demo-startupvalue-2026
echo.
echo   Para parar, feche as janelas
echo   "StartupValue API" e "StartupValue Site".
echo ================================================
echo.
pause
exit /b 0

:fail
echo.
pause
exit /b 1
