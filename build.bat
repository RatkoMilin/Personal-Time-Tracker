@echo off
REM Builds dist\PersonalTimeTracker.exe (a single file, no Python needed to run it).
python -m pip install -r requirements-dev.txt || goto :error
python -m pytest -q || goto :error
python -m PyInstaller --noconfirm --onefile --windowed --name PersonalTimeTracker ^
  --icon assets\icon.ico --add-data "assets;assets" --hidden-import pystray._win32 main.pyw || goto :error
echo.
echo Gotovo: dist\PersonalTimeTracker.exe
goto :eof
:error
echo Build nije uspeo.
exit /b 1
