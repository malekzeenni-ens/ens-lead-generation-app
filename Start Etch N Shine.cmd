@echo off
setlocal EnableExtensions
title Etch N Shine Lead Generation

pushd "%~dp0" >nul 2>&1
if errorlevel 1 goto :bad_location

if not exist "package.json" goto :bad_location

where npm.cmd >nul 2>&1
if errorlevel 1 goto :missing_node

where cargo.exe >nul 2>&1
if errorlevel 1 goto :missing_rust

if not exist "node_modules\" goto :missing_setup
if not exist ".venv\Scripts\python.exe" goto :missing_setup
if not exist "scripts\run-desktop-dev.ps1" goto :missing_setup

if /I "%~1"=="--check" goto :ready

echo.
echo Starting Etch N Shine Lead Generation...
echo Keep this window open while the application is running.
echo If it is already running, this launcher selects the existing window.
echo The first startup can take longer while the desktop host compiles.
echo.

call npm.cmd run desktop:dev
set "ENS_LAUNCH_EXIT=%ERRORLEVEL%"

if "%ENS_LAUNCH_EXIT%"=="0" goto :finished

echo.
echo The application stopped with error code %ENS_LAUNCH_EXIT%.
echo Review the messages above, then press any key to close this window.
pause >nul
popd
exit /b %ENS_LAUNCH_EXIT%

:missing_node
echo.
echo Node.js and npm were not found.
echo Install Node.js 22 or newer, then try again.
goto :setup_failed

:missing_rust
echo.
echo Rust and Cargo were not found.
echo Install the stable Rust toolchain, then try again.
goto :setup_failed

:missing_setup
echo.
echo The local development dependencies are not installed yet.
echo Open PowerShell in this folder and run:
echo.
echo   uv sync --all-packages --dev --locked
echo   npm.cmd ci
goto :setup_failed

:bad_location
echo.
echo The Etch N Shine project folder could not be opened.
goto :setup_failed_no_popd

:setup_failed
popd

:setup_failed_no_popd
echo.
echo Press any key to close this window.
pause >nul
exit /b 1

:ready
echo Etch N Shine desktop launcher is ready.
popd
exit /b 0

:finished
echo.
echo Etch N Shine launch request completed.
popd
exit /b 0
