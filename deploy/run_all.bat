@echo off
REM Copyright (c) 2019-2024 Roke Manor Research Ltd
REM Run Apex first and wait for a moment for it to create database

start bin\apex.exe
timeout 4
start bin\apex_gui.exe
