@echo off
chcp 65001 >nul
title Datamosh-Resolve Installer

echo ========================================================
echo   DATAMOSH-RESOLVE — Installer for DaVinci Resolve
echo ========================================================
echo.

:: 1. Detect DaVinci Resolve Fusion paths
set "FUSION_APPDATA=%APPDATA%\Blackmagic Design\DaVinci Resolve\Support\Fusion"
set "SCRIPTS_EDIT=%FUSION_APPDATA%\Scripts\Edit"
set "FUSION_MODULES=%FUSION_APPDATA%\Modules"
set "PROGRAMDATA_SCRIPTS=C:\ProgramData\Blackmagic Design\DaVinci Resolve\Fusion\Scripts"

echo [1/4] Cleaning legacy duplicate scripts and subfolders...
:: Remove duplicate from Comp folder to prevent double entries in DaVinci
if exist "%FUSION_APPDATA%\Scripts\Comp\Datamosher_Pro.py" del /F /Q "%FUSION_APPDATA%\Scripts\Comp\Datamosher_Pro.py" >nul 2>&1
if exist "%PROGRAMDATA_SCRIPTS%\Edit\Datamosher_Pro.py" del /F /Q "%PROGRAMDATA_SCRIPTS%\Edit\Datamosher_Pro.py" >nul 2>&1
if exist "%PROGRAMDATA_SCRIPTS%\Comp\Datamosher_Pro.py" del /F /Q "%PROGRAMDATA_SCRIPTS%\Comp\Datamosher_Pro.py" >nul 2>&1

:: Remove submodules from Scripts folder if placed there previously (prevents menu clutter!)
if exist "%SCRIPTS_EDIT%\DatamoshLib" rmdir /S /Q "%SCRIPTS_EDIT%\DatamoshLib" >nul 2>&1
if exist "%SCRIPTS_EDIT%\pymosh" rmdir /S /Q "%SCRIPTS_EDIT%\pymosh" >nul 2>&1

echo [2/4] Preparing target directories...
if not exist "%SCRIPTS_EDIT%" mkdir "%SCRIPTS_EDIT%"
if not exist "%FUSION_MODULES%" mkdir "%FUSION_MODULES%"

echo [3/4] Installing Datamosher Pro tool and modules...
:: Install main user script into Scripts/Edit
copy /Y "%~dp0Datamosher_Pro.py" "%SCRIPTS_EDIT%\Datamosher_Pro.py" >nul

:: Install core libraries into Fusion Modules (avoids listing subfolders in DaVinci Scripts menu)
xcopy /E /I /Y "%~dp0DatamoshLib" "%FUSION_MODULES%\DatamoshLib" >nul
xcopy /E /I /Y "%~dp0pymosh" "%FUSION_MODULES%\pymosh" >nul

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
