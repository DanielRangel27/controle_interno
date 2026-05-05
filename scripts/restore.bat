@echo off
REM Script de restauracao de backup - Controle Interno PGM.
REM
REM ATENCAO: este script SUBSTITUI o banco de dados atual.
REM Antes de rodar, pare o servidor (Ctrl+C no runserver.bat).
REM
REM Como usar:
REM   1. Ajuste PROJECT_DIR se o projeto nao estiver no caminho padrao.
REM   2. Garanta que o repositorio de backup ja foi clonado uma vez
REM      (rode "scripts\backup.bat" ao menos uma vez antes do restore).
REM   3. Execute este .bat (modo interativo, pede confirmacao):
REM        scripts\restore.bat
REM
REM Modos suportados:
REM   [1] SQLite -> copia o arquivo db.sqlite3 do repo de backup por cima do atual.
REM   [2] JSON   -> roda "migrate" + "flush" + "loaddata" usando um dump db-YYYY-MM-DD-HHMMSS.json.
REM
REM Antes de qualquer alteracao, este script faz uma copia de seguranca do
REM banco atual em "%PROJECT_DIR%\backups_local\db-pre-restore-<timestamp>.sqlite3".
REM Se algo der errado, basta copiar esse arquivo de volta para "db.sqlite3".

setlocal enabledelayedexpansion

set "PROJECT_DIR=C:\Users\pgm-a\controle_interno"
set "PYTHON=python"
set "BACKUP_REPO=%PROJECT_DIR%\_backup_repo"
set "BACKUP_SUBDIR=procuradoria"
set "TARGET_DB=%PROJECT_DIR%\db.sqlite3"
set "SAFETY_DIR=%PROJECT_DIR%\backups_local"
set "SAFETY_FILE="

cd /d "%PROJECT_DIR%" || (
    echo [ERRO] Diretorio do projeto nao encontrado: %PROJECT_DIR%
    exit /b 1
)

if not exist "%BACKUP_REPO%\.git" (
    echo [ERRO] Repositorio de backup nao encontrado em: %BACKUP_REPO%
    echo Rode "%PROJECT_DIR%\scripts\backup.bat" pelo menos uma vez para clonar o repositorio.
    exit /b 1
)

echo =====================================================
echo  Restauracao de backup - Controle Interno PGM
echo =====================================================
echo.
echo ATENCAO: esta operacao SUBSTITUI o banco de dados atual.
echo Verifique se o servidor (runserver.bat / waitress) esta PARADO.
echo.

echo Atualizando repositorio de backup local...
git -C "%BACKUP_REPO%" fetch origin >nul 2>&1
git -C "%BACKUP_REPO%" pull --ff-only >nul 2>&1
echo.

echo Modos disponiveis:
echo   [1] SQLite  - substitui db.sqlite3 inteiro, restore rapido.
echo   [2] JSON    - flush + loaddata de um dump db-YYYY-MM-DD-HHMMSS.json.
echo.
set "MODE="
set /p "MODE=Escolha 1 ou 2: "

if "%MODE%"=="1" goto :mode_sqlite
if "%MODE%"=="2" goto :mode_json
echo [ERRO] Modo invalido: %MODE%
exit /b 1

:mode_sqlite
set "DEFAULT_SQLITE=%BACKUP_REPO%\%BACKUP_SUBDIR%\db.sqlite3"
if not exist "%DEFAULT_SQLITE%" (
    echo [ERRO] Backup SQLite nao encontrado em: %DEFAULT_SQLITE%
    exit /b 1
)
echo.
echo Backup SQLite mais recente:
for %%F in ("%DEFAULT_SQLITE%") do echo   %%~fF  -- %%~zF bytes -- %%~tF
echo.
echo Origem:
echo   [1] Usar o backup mais recente acima.
echo   [2] Informar caminho completo de outro arquivo .sqlite3.
set "SQ_OPT="
set /p "SQ_OPT=Escolha 1 ou 2: "

if "%SQ_OPT%"=="1" (
    set "SOURCE=%DEFAULT_SQLITE%"
) else if "%SQ_OPT%"=="2" (
    set "SOURCE="
    set /p "SOURCE=Caminho completo do arquivo .sqlite3: "
) else (
    echo [ERRO] Opcao invalida: %SQ_OPT%
    exit /b 1
)

if not exist "!SOURCE!" (
    echo [ERRO] Arquivo de origem nao encontrado: !SOURCE!
    exit /b 1
)

call :confirm_or_exit "!SOURCE!" "SQLite"
if errorlevel 1 exit /b %ERRORLEVEL%

call :snapshot_db
if errorlevel 1 exit /b %ERRORLEVEL%

echo.
echo Substituindo "%TARGET_DB%"...
copy /Y "!SOURCE!" "%TARGET_DB%" >nul
if errorlevel 1 (
    echo [ERRO] Falha ao copiar banco. Restore abortado.
    echo O banco anterior esta preservado em: %SAFETY_FILE%
    exit /b 1
)
echo [OK] db.sqlite3 substituido pelo backup.
goto :post_restore

:mode_json
set "JSON_DIR=%BACKUP_REPO%\%BACKUP_SUBDIR%\backups"
if not exist "%JSON_DIR%" (
    echo [ERRO] Diretorio de dumps JSON nao encontrado: %JSON_DIR%
    exit /b 1
)

set "LATEST_JSON="
for /f "delims=" %%F in ('dir /B /O-N "%JSON_DIR%\db-*.json" 2^>nul') do (
    if not defined LATEST_JSON set "LATEST_JSON=%JSON_DIR%\%%F"
)
if not defined LATEST_JSON (
    echo [ERRO] Nenhum dump JSON encontrado em: %JSON_DIR%
    exit /b 1
)

echo.
echo Dumps disponiveis (mais recentes primeiro):
dir /B /O-N "%JSON_DIR%\db-*.json"
echo.
echo Mais recente: %LATEST_JSON%
echo.
echo Origem:
echo   [1] Usar o dump mais recente.
echo   [2] Informar nome do arquivo. Exemplo: db-2026-05-04-180012.json
set "JS_OPT="
set /p "JS_OPT=Escolha 1 ou 2: "

if "%JS_OPT%"=="1" (
    set "SOURCE=%LATEST_JSON%"
) else if "%JS_OPT%"=="2" (
    set "JSON_NAME="
    set /p "JSON_NAME=Nome do arquivo JSON: "
    set "SOURCE=%JSON_DIR%\!JSON_NAME!"
) else (
    echo [ERRO] Opcao invalida: %JS_OPT%
    exit /b 1
)

if not exist "!SOURCE!" (
    echo [ERRO] Arquivo de origem nao encontrado: !SOURCE!
    exit /b 1
)

call :confirm_or_exit "!SOURCE!" "JSON"
if errorlevel 1 exit /b %ERRORLEVEL%

call :snapshot_db
if errorlevel 1 exit /b %ERRORLEVEL%

echo.
echo Aplicando migrations (garantindo schema)...
"%PYTHON%" manage.py migrate --noinput
if errorlevel 1 (
    echo [ERRO] Falha em "migrate". Restore abortado antes de tocar nos dados.
    echo Snapshot do banco anterior: %SAFETY_FILE%
    exit /b 1
)

echo.
echo Limpando dados existentes (flush)...
"%PYTHON%" manage.py flush --noinput
if errorlevel 1 (
    echo [ERRO] Falha em "flush". Restore abortado.
    echo Snapshot do banco anterior: %SAFETY_FILE%
    exit /b 1
)

echo.
echo Carregando dump JSON...
"%PYTHON%" manage.py loaddata "!SOURCE!"
if errorlevel 1 (
    echo [ERRO] Falha em "loaddata".
    echo Para reverter, copie "%SAFETY_FILE%" de volta para "%TARGET_DB%".
    exit /b 1
)
echo [OK] Dados restaurados a partir do dump JSON.
goto :post_restore

:post_restore
echo.
echo =====================================================
echo  Restauracao concluida com sucesso.
echo =====================================================
echo  Snapshot do banco anterior: %SAFETY_FILE%
echo.
echo  Proximos passos:
echo   1. Reinicie o servidor com "scripts\runserver.bat".
echo   2. Faca login no sistema e valide telas principais.
echo   3. Se algo deu errado, pare o servidor e copie o snapshot
echo      acima de volta para "%TARGET_DB%".
echo.
endlocal & exit /b 0


REM =========================================================
REM Subrotinas
REM =========================================================

:confirm_or_exit
echo.
echo --- RESUMO DA OPERACAO ---
echo Modo:    %~2
echo Origem:  %~1
echo Destino: %TARGET_DB%
echo --------------------------
echo.
echo Esta acao SUBSTITUI o banco atual. Digite CONFIRMAR para prosseguir.
set "CONFIRMA="
set /p "CONFIRMA=Confirmacao: "
if /I not "!CONFIRMA!"=="CONFIRMAR" (
    echo Operacao cancelada pelo usuario.
    exit /b 2
)
exit /b 0

:snapshot_db
if not exist "%TARGET_DB%" (
    echo [AVISO] Banco atual nao existe; pulando snapshot.
    set "SAFETY_FILE=(nenhum)"
    exit /b 0
)
if not exist "%SAFETY_DIR%" mkdir "%SAFETY_DIR%"
for /f "usebackq delims=" %%I in (`powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"`) do set "STAMP=%%I"
if not defined STAMP set "STAMP=%RANDOM%"
set "SAFETY_FILE=%SAFETY_DIR%\db-pre-restore-%STAMP%.sqlite3"
copy /Y "%TARGET_DB%" "%SAFETY_FILE%" >nul
if errorlevel 1 (
    echo [ERRO] Falha ao criar snapshot de seguranca em %SAFETY_FILE%
    exit /b 1
)
echo Snapshot criado: %SAFETY_FILE%
exit /b 0
