@echo off
REM Inicia o servidor de producao local da rede interna.
REM Edite IP/PORTA conforme necessario.

setlocal

set "PROJECT_DIR=C:\Users\pgm-a\controle_interno"
set "BIND=0.0.0.0:8088"

cd /d "%PROJECT_DIR%" || (
    echo [ERRO] Diretorio do projeto nao encontrado: %PROJECT_DIR%
    exit /b 1
)

REM Libera qualquer host na rede interna para evitar cadastro de IP individual.
REM OBS: para ambiente exposto fora da rede local, restrinja no .env.
set "DJANGO_ALLOWED_HOSTS=*"

echo Servindo o sistema em http://%COMPUTERNAME%:8088/  (Ctrl+C para parar)
python -m waitress --listen=%BIND% controle_interno.wsgi:application

endlocal
