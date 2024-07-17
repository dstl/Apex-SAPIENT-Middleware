@echo off

REM Copyright (c) 2019-2024 Roke Manor Research Ltd
REM
REM Produces Apex deliveries in multiple formats
REM apex-vX.Y.Z-deploy.zip = Apex compiled binaries
REM apex-vX.Y.Z-python.zip = Apex sources with a pre-configured python virtual environment
REM apex-vX.Y.Z-source.zip = Apex sources only
REM
REM Requires the zip file with apex sources (from gitlab)
REM Ideally run it out of source to avoid creating files in the apex repo
REM Example:
REM   apex\make_apex_delivery apex-vX.Y.Z.zip
REM Outputs will be produced in the directory apex-vX.Y.Z-delivery

setlocal EnableDelayedExpansion

set START_TIME=%time%

if "%1" EQU "" (
  echo Error: Arg1 not specified, needs to be the apex zip file downloaded from gitlab
  goto ERROR
)

set APEX_ZIP=%1
if not exist !APEX_ZIP! (
  echo Error: Specified file !APEX_ZIP! cannot be opened !
  goto ERROR
)

if "!APEX_ZIP!" NEQ "" (
  echo Processing !APEX_ZIP!

  REM Get filename part of the zip, to use a directory
  for %%f in ("!APEX_ZIP!") do set APEX_VERSION=%%~nf

  REM Start clean, Wipe existing !APEX_VERSION! dir
  if exist !APEX_VERSION! rd !APEX_VERSION! /s /q
  echo Extracting !APEX_ZIP! to %cd%\!APEX_VERSION!
  python -m zipfile -e %APEX_ZIP% .

  SET APEX_DELIVERY_DIR=!APEX_VERSION!-delivery
  if exist !APEX_DELIVERY_DIR! (
    REM Retain/backup/cycle some previous deliveries
    echo Backing up previous !APEX_DELIVERY_DIR!
    if exist __!APEX_DELIVERY_DIR! rd /s /q __!APEX_DELIVERY_DIR!
    if exist _!APEX_DELIVERY_DIR! ren _!APEX_DELIVERY_DIR! __!APEX_DELIVERY_DIR!
    ren !APEX_DELIVERY_DIR! _!APEX_DELIVERY_DIR!
  )

  mkdir !APEX_DELIVERY_DIR!

  SET APEX_DEPLOY_ZIP=!APEX_DELIVERY_DIR!\!APEX_VERSION!-deploy.zip
  SET APEX_PYTHON_ZIP=!APEX_DELIVERY_DIR!\!APEX_VERSION!-python.zip
  SET APEX_SOURCE_ZIP=!APEX_DELIVERY_DIR!\!APEX_VERSION!-source.zip

  if exist !APEX_VERSION!\apex_config.json (
    echo Extraction looks OK

    echo Creating Delivery Item: !APEX_SOURCE_ZIP!
    copy !APEX_ZIP! !APEX_SOURCE_ZIP!

    pushd !APEX_VERSION!
    echo Creating Python Virtual Environment
    python -m venv venv

    echo Activating venv and installing packages
    call venv\scripts\activate.bat & poetry install --all-extras

    echo Installed Apex package is
    call venv\scripts\activate.bat & pip show apex
    popd

    REM First create a clean venv zip, before calling building with nuitka
    echo Creating Delivery Item: Apex Sources with Python Virtual Environment
    python -m zipfile -c !APEX_PYTHON_ZIP! !APEX_VERSION!

    REM Now build with nuitka
    pushd !APEX_VERSION!
    echo Building Apex with Nuitka, this will take a while.
    call venv\scripts\activate.bat & cd deploy & call build_nuitka.bat & cd..
    popd

    if not exist !APEX_VERSION!\deploy\apex.zip (
      echo Apex build with Nuitka Failed
      goto ERROR
    ) else (
      echo Creating Delivery Item: !APEX_DEPLOY_ZIP!
      copy !APEX_VERSION!\deploy\apex.zip !APEX_DEPLOY_ZIP!
    )

    echo Copying changelog.txt
    copy !APEX_VERSION!\changelog.txt !APEX_DELIVERY_DIR!\.
    goto SUCCESS
  ) else (
    echo !APEX_ZIP! did not extract expected contents
    goto ERROR
  )
) else (
  echo Error: Arg1 not specified, needs to be the apex zip file downloaded from git
  goto ERROR
)

:ERROR
echo Failed Execution
goto END

:SUCCESS
echo Successful Execution, contents of !APEX_DELIVERY_DIR!
dir !APEX_DELIVERY_DIR!
echo Start Time=%START_TIME% End Time=%time%

:END

endlocal
