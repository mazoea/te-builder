@echo off
rem Activate a Visual Studio Developer environment for the current cmd
rem session so that MSBuild + cl.exe are on PATH. Safe to call from any
rem build-*.bat wrapper. No-op if msbuild is already on PATH.
rem
rem Strategy: ask vswhere for the latest install, then call its VsDevCmd.bat
rem with -arch=x64 -no_logo. If vswhere is missing, fall back to the
rem default install path so the caller still sees a clear error.

where msbuild >nul 2>nul && goto :eof

set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
if not exist "%VSWHERE%" set "VSWHERE=%ProgramFiles%\Microsoft Visual Studio\Installer\vswhere.exe"
if not exist "%VSWHERE%" (
    echo [ERROR] vswhere.exe not found. Install Visual Studio Build Tools or VS 2017+ to enable MSBuild detection.
    exit /b 1
)

for /f "usebackq tokens=*" %%i in (`"%VSWHERE%" -latest -products * -property installationPath`) do (
    if exist "%%i\Common7\Tools\VsDevCmd.bat" (
        call "%%i\Common7\Tools\VsDevCmd.bat" -arch=x64 -no_logo >nul
        where msbuild >nul 2>nul && goto :eof
    )
)

echo [ERROR] Could not activate an MSBuild environment via VsDevCmd.bat.
exit /b 1
