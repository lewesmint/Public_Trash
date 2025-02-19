import ctypes
import sys

def disable_quickedit():
    if sys.platform != "win32":
        return  # QuickEdit mode is Windows-only
    
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.GetStdHandle(-10)  # STD_INPUT_HANDLE
    mode = ctypes.c_uint32()

    if kernel32.GetConsoleMode(handle, ctypes.byref(mode)) == 0:
        return  # Failed to get console mode
    
    # Disable QuickEdit mode but keep other flags
    ENABLE_EXTENDED_FLAGS = 0x0080
    ENABLE_QUICK_EDIT_MODE = 0x0040

    new_mode = (mode.value & ~ENABLE_QUICK_EDIT_MODE) | ENABLE_EXTENDED_FLAGS
    kernel32.SetConsoleMode(handle, new_mode)

disable_quickedit()
