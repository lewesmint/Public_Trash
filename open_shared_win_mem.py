import mmap
import os
import time
from ctypes import windll, c_void_p, sizeof, byref, create_string_buffer, WinError

def open_shared_memory(name="ABC", size=4096):
    """
    Open a Windows shared memory object by name.
    
    Args:
        name: Name of the shared memory object
        size: Size of the shared memory in bytes
    
    Returns:
        A memory map object if successful, None otherwise
    """
    # Constants for Windows API
    INVALID_HANDLE_VALUE = -1
    FILE_MAP_READ = 0x0004
    FILE_MAP_WRITE = 0x0002
    
    # Get handle to the shared memory
    handle = windll.kernel32.OpenFileMappingA(
        FILE_MAP_READ | FILE_MAP_WRITE,  # Access rights
        False,                           # Don't inherit handle
        name.encode('ascii')             # Name of mapping object
    )
    
    if handle == 0:
        error_code = windll.kernel32.GetLastError()
        print(f"Failed to open shared memory '{name}': {WinError(error_code)}")
        return None
    
    # Map view of the file
    map_view = windll.kernel32.MapViewOfFile(
        handle,                          # Handle to mapping object
        FILE_MAP_READ | FILE_MAP_WRITE,  # Access mode
        0,                               # High-order DWORD of offset
        0,                               # Low-order DWORD of offset
        size                             # Number of bytes to map
    )
    
    if map_view == 0:
        error_code = windll.kernel32.GetLastError()
        print(f"Failed to map view of file: {WinError(error_code)}")
        windll.kernel32.CloseHandle(handle)
        return None
    
    # Create a memory map from the pointer
    try:
        shared_mem = mmap.mmap(-1, size, tagname=name)
        print(f"Successfully opened shared memory '{name}'")
        return shared_mem
    except Exception as e:
        print(f"Error creating memory map: {e}")
        windll.kernel32.UnmapViewOfFile(map_view)
        windll.kernel32.CloseHandle(handle)
        return None

def main():
    # Try to open the shared memory
    shared_mem = open_shared_memory("ABC")
    
    if shared_mem:
        try:
            # Read data from shared memory
            shared_mem.seek(0)
            data = shared_mem.read(100)  # Read up to 100 bytes
            print(f"Read from shared memory: {data}")
            
            # Write to shared memory
            shared_mem.seek(0)
            shared_mem.write(b"Hello from Python!")
            shared_mem.flush()
            
            # Keep the script running to maintain access
            print("Press Ctrl+C to exit...")
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Exiting...")
        finally:
            shared_mem.close()

if __name__ == "__main__":
    main()
