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

(
    for /f "tokens=1,* delims=:" %%A in ('findstr /n "^" "%input_file%"') do (
        set "line=%%B"

        :: Debug output to screen only (sent to stderr)
        echo [DEBUG] Processing: "!line!" >&2

        :: Preserve blank lines exactly
        if "!line!"=="" (
            call :PrintLine ""
        ) else (
            echo(!line!) | findstr /r "^#define BUILD_INDEX [0-9][0-9]*$" >nul
            if not errorlevel 1 (
                for /f "tokens=3" %%C in ("!line!") do set /a new_index=%%C + 1
                call :PrintLine "#define BUILD_INDEX !new_index!"
                set "found=1"
            ) else (
                call :PrintLine "!line!"
            )
        )
    )
) > "%temp_file%"

if "%found%"=="1" (
    move /y "%temp_file%" "%input_file%" >nul
    echo [+] BUILD_INDEX incremented successfully.
    exit /b 0
) else (
    del "%temp_file%"
    echo [WARNING] No "#define BUILD_INDEX X" found in "%input_file%". >&2
    exit /b 2
)
goto :EOF

:PrintLine
rem This subroutine echoes its argument using echo( to avoid errors
echo(%~1
goto :EOF
