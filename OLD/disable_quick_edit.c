#include <windows.h>
#include <stdio.h>

void disable_quick_edit_mode() {
    HANDLE hInput = GetStdHandle(STD_INPUT_HANDLE);
    if (hInput == INVALID_HANDLE_VALUE) {
        fprintf(stderr, "Error: Unable to get console input handle\n");
        return;
    }

    DWORD mode;
    if (!GetConsoleMode(hInput, &mode)) {
        fprintf(stderr, "Error: Unable to get console mode\n");
        return;
    }

    // Disable QuickEdit Mode (0x40) but keep other modes unchanged
    mode &= ~ENABLE_QUICK_EDIT_MODE;
    if (!SetConsoleMode(hInput, mode)) {
        fprintf(stderr, "Error: Unable to set console mode\n");
    }
}

int main() {
    disable_quick_edit_mode();

    printf("QuickEdit Mode disabled. Running application...\n");

    while (1) {
        printf("Logging...\n");
        Sleep(1000);
    }

    return 0;
}
