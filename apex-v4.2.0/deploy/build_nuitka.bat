@echo off
REM Copyright (c) 2019-2024 Roke Manor Research Ltd
pushd "%~dp0\.."

echo Building apex_gui.exe
python -m nuitka --mingw64 --standalone --python-flag=no_docstrings ^
    --plugin-enable=pyside6 --include-qt-plugins=sensible,styles ^
    --windows-disable-console --windows-icon-from-ico=apex-logo.ico ^
    --include-data-file=apex-logo.ico=apex-logo.ico ^
    --output-dir=deploy\build sapient_apex_gui\apex_gui.py

echo Building apex.exe
python -m nuitka --mingw64 --standalone --python-flag=no_docstrings ^
    --include-package=apex --windows-icon-from-ico=apex-logo.ico ^
    --output-dir=deploy\build sapient_apex_server\apex.py

echo Building replay.exe
python -m nuitka --mingw64 --standalone --python-flag=no_docstrings ^
    --windows-icon-from-ico=apex-logo.ico ^
    --output-dir=deploy\build sapient_apex_replay\replay.py

if exist deploy\bin rd /s /q deploy\bin
mkdir deploy\bin

xcopy /y /q /s deploy\build\apex_gui.dist deploy\bin
xcopy /y /q /s deploy\build\apex.dist deploy\bin
xcopy /y /q /s deploy\build\replay.dist deploy\bin
popd

pushd "%~dp0"
copy ..\apex_config.json .
copy ..\replay_config.json .
copy ..\install_elastic.bat .
copy ..\start_elastic.bat .

echo Zipping binaries
python -m zipfile -c apex.zip bin apex_config.json replay_config.json elasticsearch-8.11.1 acknowledgements.txt install_elastic.bat start_elastic.bat run_all.bat
popd

echo Done
