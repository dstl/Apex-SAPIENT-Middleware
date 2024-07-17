@echo off
REM Copyright (c) 2019-2024 Roke Manor Research Ltd

if "%1"=="" (set destinationPath=".") else (set destinationPath=%1)
echo Downloading elasticsearch to %destinationPath%
curl -L -o elastic.zip https://artifacts.elastic.co/downloads/elasticsearch/elasticsearch-8.11.1-windows-x86_64.zip

if exist %destinationPath%\elasticsearch-8.11.1 (
    rmdir /s /q %destinationPath%\elasticsearch-8.11.1
)

powershell.exe -nologo -noprofile -command Expand-Archive .\elastic.zip -DestinationPath %destinationPath%
del .\elastic.zip

echo elasticsearch installed to %destinationPath%
echo You can start it with
echo   start_elastic.bat %destinationPath%
