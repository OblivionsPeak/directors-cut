@echo off
pyinstaller --clean --noconfirm --onefile --noconsole --name DirectorsCut --icon icon.ico ^
  --collect-all imageio_ffmpeg ^
  --add-data "templates;templates" --add-data "static;static" app.py
echo.
echo Built dist\DirectorsCut.exe
