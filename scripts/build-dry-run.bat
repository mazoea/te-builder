@echo off
rem No MSBuild activation needed for --dry-run, but keep it for consistency
rem so users get the right toolset auto-detected when actually building.
call "%~dp0_activate-msvc.bat"
python -m te_builder --preset externals.basic --dry-run %*
