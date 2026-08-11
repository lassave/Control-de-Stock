@echo off
chcp 65001 > nul
cd /d "%~dp0servidor"

set PYTHON=.venv\Scripts\python.exe

if not exist "%PYTHON%" (
    echo Preparando el entorno por primera vez. Esto tarda un par de minutos...
    python -m venv .venv
)

REM En Windows, "python" puede ser el acceso directo de la Microsoft Store,
REM que abre la tienda y no ejecuta nada. Sin esta comprobacion, la ventana
REM se cierra con un error incomprensible en la PC del cliente.
if not exist "%PYTHON%" (
    echo.
    echo No se pudo preparar el entorno porque falta Python.
    echo.
    echo Instalalo desde https://www.python.org/downloads/ y tildá
    echo "Add python.exe to PATH" durante la instalacion.
    echo Despues volve a hacer doble clic en este archivo.
    echo.
    pause
    exit /b 1
)

"%PYTHON%" -m pip install --quiet --upgrade pip
"%PYTHON%" -m pip install --quiet -r requirements.txt

"%PYTHON%" iniciar.py
pause
