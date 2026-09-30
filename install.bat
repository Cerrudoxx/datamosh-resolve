@echo off
chcp 65001 >nul
title Datamosh-Resolve Installer

echo ========================================================
echo   DATAMOSH-RESOLVE — Installer for DaVinci Resolve
echo ========================================================
echo.

:: 1. Detect DaVinci Resolve Fusion Scripts paths
set "FUSION_APPDATA=%APPDATA%\Blackmagic Design\DaVinci Resolve\Support\Fusion"
set "SCRIPTS_EDIT=%FUSION_APPDATA%\Scripts\Edit"
set "PROGRAMDATA_SCRIPTS=C:\ProgramData\Blackmagic Design\DaVinci Resolve\Fusion\Scripts"

echo [1/4] Cleaning legacy duplicate scripts...
:: Remove duplicate from Comp folder to prevent double entries in DaVinci
if exist "%FUSION_APPDATA%\Scripts\Comp\Datamosher_Pro.py" del /F /Q "%FUSION_APPDATA%\Scripts\Comp\Datamosher_Pro.py" >nul 2>&1
if exist "%PROGRAMDATA_SCRIPTS%\Edit\Datamosher_Pro.py" del /F /Q "%PROGRAMDATA_SCRIPTS%\Edit\Datamosher_Pro.py" >nul 2>&1
if exist "%PROGRAMDATA_SCRIPTS%\Comp\Datamosher_Pro.py" del /F /Q "%PROGRAMDATA_SCRIPTS%\Comp\Datamosher_Pro.py" >nul 2>&1

echo [2/4] Preparing target directory...
if not exist "%SCRIPTS_EDIT%" mkdir "%SCRIPTS_EDIT%"

echo [3/4] Installing Datamosher Pro tool and libraries...
copy /Y "%~dp0Datamosher_Pro.py" "%SCRIPTS_EDIT%\Datamosher_Pro.py" >nul

:: Copy core libraries alongside the script
xcopy /E /I /Y "%~dp0DatamoshLib" "%SCRIPTS_EDIT%\DatamoshLib" >nul
xcopy /E /I /Y "%~dp0pymosh" "%SCRIPTS_EDIT%\pymosh" >nul

echo [4/4] Checking system dependencies...
where ffmpeg >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] FFmpeg was not detected in system PATH.
    echo           FFmpeg is required for video bitstream surgery.
    echo           Run in PowerShell: winget install Gyan.FFmpeg
) else (
    echo   [OK] FFmpeg detected.
)

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] Python was not detected in system PATH.
) else (
    echo   [OK] Python detected.
)

echo.
echo ========================================================
echo   INSTALLATION COMPLETED SUCCESSFULLY!
echo ========================================================
echo.
echo How to run in DaVinci Resolve:
echo   Open DaVinci Resolve and go to the top menu:
echo   Workspace -> Scripts -> Datamosher_Pro
echo.
pause
