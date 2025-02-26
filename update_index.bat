@echo off
setlocal enabledelayedexpansion

set "input_file=include\AppSettings.h"
set "temp_file=%input_file%.tmp"
set "found=0"

:: Check if the file exists
if not exist "%input_file%" (
    echo [ERROR] File "%input_file%" not found. >&2
    exit /b 1
)

:: Process the file line by line and write to a temp file
(
    for /f "delims=" %%A in ('type "%input_file%"') do (
        set "line=%%A"

        :: DEBUGGING - Print to SCREEN ONLY, not to the file
        echo [DEBUG] Processing: "!line!" >&2

        :: Check for "#define BUILD_INDEX X"
        echo "!line!" | findstr /r "^#define BUILD_INDEX [0-9][0-9]*$" >nul
        if not errorlevel 1 (
            for /f "tokens=3" %%B in ("!line!") do set /a new_index=%%B + 1
            echo #define BUILD_INDEX !new_index!
            set "found=1"
        ) else (
            echo !line!
        )
    )
) > "%temp_file%"

:: If BUILD_INDEX was found, replace the original file
if "%found%"=="1" (
    move /y "%temp_file%" "%input_file%" > nul
    echo [+] BUILD_INDEX incremented successfully.
    exit /b 0
) else (
    del "%temp_file%"
    echo [WARNING] No "#define BUILD_INDEX X" found in "%input_file%". >&2
    exit /b 2
)
