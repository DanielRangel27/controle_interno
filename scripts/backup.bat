@echo off
REM Script de backup automatico - Controle Interno PGM.
REM
REM Como usar:
REM   1. Ajuste PROJECT_DIR para o caminho real do projeto na maquina servidora.
REM   2. Garanta que o usuario que vai rodar o agendador tenha credenciais
REM      do GitHub configuradas no Windows Credential Manager (PAT do
REM      repositorio https://github.com/DanielRangel27/backups.git).
REM   3. Cadastre uma tarefa no "Agendador de Tarefas" do Windows que execute
REM      este .bat (ex.: diariamente as 18:00).

setlocal

set "PROJECT_DIR=C:\Users\pgm-a\controle_interno"
set "PYTHON=python"

cd /d "%PROJECT_DIR%" || (
    echo [ERRO] Diretorio do projeto nao encontrado: %PROJECT_DIR%
    exit /b 1
)

echo [%date% %time%] Iniciando backup...
"%PYTHON%" manage.py backup_git
set "EXITCODE=%ERRORLEVEL%"

if "%EXITCODE%"=="0" (
    echo [%date% %time%] Backup concluido com sucesso.
) else (
    echo [%date% %time%] Backup falhou com codigo %EXITCODE%.
)

endlocal & exit /b %EXITCODE%
