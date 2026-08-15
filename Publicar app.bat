@echo off
chcp 65001 > nul
cd /d "%~dp0celular"

set GRADLE=C:\Gradle\gradle-8.7\bin\gradle.bat

if not exist "%GRADLE%" (
    echo.
    echo No se encontro Gradle en %GRADLE%
    echo.
    echo La app se compila en la maquina de desarrollo, no en la del cliente.
    echo.
    pause
    exit /b 1
)

echo Compilando la app firmada. La primera vez tarda unos minutos...
echo.

call "%GRADLE%" :app:publicar --no-daemon

if errorlevel 1 (
    echo.
    echo No se pudo publicar. El motivo esta unas lineas mas arriba.
    echo.
    pause
    exit /b 1
)

echo.
pause
