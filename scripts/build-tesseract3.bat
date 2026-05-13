@echo off
call "%~dp0_activate-msvc.bat" || exit /b 1
python -m te_builder --preset tesseract3 %*
