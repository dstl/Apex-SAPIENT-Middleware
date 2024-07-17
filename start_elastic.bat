@echo off
REM Copyright (c) 2019-2024 Roke Manor Research Ltd

if "%1"=="" (set destinationPath=".") else (set destinationPath=%1)

echo Starting elasticsearch from %destinationPath%
%destinationPath%\elasticsearch-8.11.1\bin\elasticsearch
