@echo off
REM ============================================
REM Daena Video Compressor - Launcher
REM ============================================
REM This script launches the Daena Video Compressor tool
REM with an interactive menu for easy use.
REM ============================================

title Daena Video Compressor

echo.
echo ============================================
echo   Daena Video Compressor
echo ============================================
echo.

REM Activate virtual environment
call venv_daena_main_py310\Scripts\activate 2>nul
if errorlevel 1 (
    echo [WARNING] Virtual environment not found. Using system Python.
)

REM Check if ffmpeg is available
where ffmpeg >nul 2>nul
if errorlevel 1 (
    echo [ERROR] FFmpeg not found! Please install FFmpeg and add it to PATH.
    echo Download from: https://ffmpeg.org/download.html
    pause
    exit /b 1
)

:menu
echo.
echo Select an option:
echo   1. List compression presets
echo   2. Compress single video (balanced)
echo   3. Compress single video (github-friendly)
echo   4. Compress to target size
echo   5. Batch compress folder
echo   6. Run with custom arguments
echo   7. Exit
echo.
set /p choice="Enter choice (1-7): "

if "%choice%"=="1" goto list_presets
if "%choice%"=="2" goto compress_balanced
if "%choice%"=="3" goto compress_github
if "%choice%"=="4" goto target_size
if "%choice%"=="5" goto batch_compress
if "%choice%"=="6" goto custom
if "%choice%"=="7" goto end

echo Invalid choice. Please try again.
goto menu

:list_presets
echo.
python Tools\daena_video_compressor.py --list-presets
goto menu

:compress_balanced
echo.
set /p input_file="Enter input video path: "
set /p output_file="Enter output path (or press Enter for auto): "
if "%output_file%"=="" (
    python Tools\daena_video_compressor.py "%input_file%" -p balanced
) else (
    python Tools\daena_video_compressor.py "%input_file%" -o "%output_file%" -p balanced
)
goto menu

:compress_github
echo.
set /p input_file="Enter input video path: "
set /p output_file="Enter output path (or press Enter for auto): "
if "%output_file%"=="" (
    python Tools\daena_video_compressor.py "%input_file%" -p github
) else (
    python Tools\daena_video_compressor.py "%input_file%" -o "%output_file%" -p github
)
goto menu

:target_size
echo.
set /p input_file="Enter input video path: "
set /p target_mb="Enter target size in MB (e.g., 95): "
set /p output_file="Enter output path (or press Enter for auto): "
if "%output_file%"=="" (
    python Tools\daena_video_compressor.py "%input_file%" --target-size %target_mb%
) else (
    python Tools\daena_video_compressor.py "%input_file%" -o "%output_file%" --target-size %target_mb%
)
goto menu

:batch_compress
echo.
set /p input_folder="Enter folder containing videos: "
set /p output_folder="Enter output folder (or press Enter for 'compressed' subfolder): "
set /p preset="Enter preset (high_quality/balanced/web/github/max): "
if "%output_folder%"=="" (
    python Tools\daena_video_compressor.py "%input_folder%" --batch -p %preset%
) else (
    python Tools\daena_video_compressor.py "%input_folder%" --batch -o "%output_folder%" -p %preset%
)
goto menu

:custom
echo.
echo Enter full command arguments:
echo Example: video.mp4 -o output.mp4 -p balanced
set /p args="python Tools\daena_video_compressor.py "
python Tools\daena_video_compressor.py %args%
goto menu

:end
echo.
echo Goodbye!
exit /b 0
