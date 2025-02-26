@echo off
setlocal enabledelayedexpansion

set "input_file=build_version.h"
set "temp_file=%input_file%.tmp"
set "found=0"

:: Check if the file exists
if not exist "%input_file%" (
    echo [!] Error: File "%input_file%" not found.
    exit /b 1
)

:: Process the file line by line, preserving blank lines
(
    for /f "tokens=1,* delims=:" %%A in ('findstr /n "^" "%input_file%"') do (
        set "line=%%B"
        
        :: Preserve blank lines (empty %%B means it's a blank line)
        if "!line!"=="" (
            echo.
        ) else (
            echo !line! | findstr /r "^#define BUILD_INDEX [0-9][0-9]*$" >nul
            if not errorlevel 1 (
                for /f "tokens=3" %%C in ("!line!") do set /a new_index=%%C + 1
                echo #define BUILD_INDEX !new_index!
                set "found=1"
            ) else (
                echo !line!
            )
        )
    )
) > "%temp_file%"

:: If BUILD_INDEX was found, replace the original file
if "%found%"=="1" (
    move /y "%temp_file%" "%input_file%" > nul
    echo [+] BUILD_INDEX incremented successfully.
) else (
    del "%temp_file%"
    echo [!] Warning: No "#define BUILD_INDEX X" found in "%input_file%".
)

exit /b
