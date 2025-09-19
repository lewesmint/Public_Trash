import argparse
import ctypes
import random
import signal
import socket
import struct
import sys
import threading
import time
from typing import List, Tuple
import datetime
import logging

# ANSI_BLUE = "\033[94m"
# ANSI_RED = "\033[91m"
# ANSI_GREEN = "\033[92m"
# ANSI_RESET = "\033[0m"

class ColoredLogger(logging.Logger):
    """Custom logger that maintains colored TX/RX formatting."""
    ANSI_BLUE = "\033[94m"
    ANSI_RED = "\033[91m"
    ANSI_GREEN = "\033[92m"
    ANSI_RESET = "\033[0m"

    def __init__(self, name, connection, level=logging.NOTSET):
        super().__init__(name, level)
        self.connection = connection
        self.mode_prefix = "S: " if getattr(connection.args, 'mode', 'client') == 'server' else "C: "
        
        # Set up console handler if not already present
        if not self.handlers:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            self.addHandler(console_handler)

    def _format_message(self, msg, msg_type="CN"):
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
        if msg_type == "TX":
            color = self.ANSI_BLUE
        elif msg_type == "RX":
            color = self.ANSI_RED
        else:  # CN for connection messages
            color = self.ANSI_GREEN
            msg_type = "CN"
        return f"{timestamp}: {self.mode_prefix}{color}{msg_type}: {msg}{self.ANSI_RESET}"

    def info(self, msg, data=None):
        """Log an info message with optional hex dump."""
        msg_type = getattr(self.connection.thread_local, 'msg_type', "CN")
        formatted_msg = self._format_message(msg, msg_type)
        
        # Print directly instead of using super().info()
        print(formatted_msg)
        
        if data is not None:
            self.connection.print_hex_words(data, msg_type == "TX")

# Register the custom logger class
logging.setLoggerClass(ColoredLogger)

class AppState:
    """Manages application-wide state"""
    def __init__(self):
        self.shutdown_flag = threading.Event()
        self.mode_prefix = "C: "  # Default to client mode

    def set_mode(self, is_server: bool):
        self.mode_prefix = "S: " if is_server else "C: "

# Create single instance at module level
app = AppState()

def disable_quickedit():
    if sys.platform != 'win32':
        return # QuickEdit mode is Windows-only

    STD_INPUT_HANDLE = -10
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.GetStdHandle(STD_INPUT_HANDLE)
    mode = ctypes.c_uint32()

    if kernel32.GetConsoleMode(handle, ctypes.byref(mode)) == 0:
        return # Failed to get console mode

    ENABLE_EXTENDED_FLAGS = 0x0080
    ENABLE_QUICK_EDIT_MODE = 0x0040
    new_mode = (mode.value & ~ ENABLE_QUICK_EDIT_MODE) | ENABLE_EXTENDED_FLAGS
    kernel32.SetConsoleMode(handle, new_mode)

def parse_arguments():
    parser = argparse.ArgumentParser(description="Threaded TCP Client/Server")
    parser.add_argument("--server", "-s", type=str, default="127.0.0.1",
                       help="Server to connect to (default: 127.0.0.1)")
    parser.add_argument("--port", "-p", type=int, default=4200,
                       help="Port to use (for both client and server modes)")
    parser.add_argument("--interval", type=float, default=50,
                       help="Interval between sends in milliseconds (default: 50ms)")
    parser.add_argument("--mode", "-m", type=str, choices=['client', 'server'],
                       default='client', help="Operation mode (default: client)")
    parser.add_argument("--endian", type=str, choices=['big', 'little'],
                       default='big', help="Endianness of data (default: big)")
    parser.add_argument("--no-send", action="store_true",
                       help="Disable sending data")
    
    args = parser.parse_args()
    args.interval = args.interval / 1000  # Convert milliseconds to seconds
    args.endian_fmt = '>' if args.endian == 'big' else '<'
    return args

def service_shutdown(signum, frame):
    print('\nCaught signal {0}'.format(signum))
    app.shutdown_flag.set()

def create_data_chunks(endian_fmt: str, count: int) -> List[bytes]:
    """Create framed data blocks with random data and proper count field."""
    # Calculate maximum words that fit within MTU
    max_words = (1500 - 12) // 4  # MTU minus framing overhead
    
    # Generate random number of data words
    num_words = random.randint(max_words // 2, max_words)
    
    # Create the complete framed block
    values = [0xBAADF00D]  # Start marker
    
    # Add length and count field with proper count value
    total_length = (num_words + 3) * 4  # Total length including framing
    values.append((total_length << 16) | (count & 0xFFFF))  # Pack length and count
    
    # Add random data
    values.extend(random.randint(0, 0xFFFFFFFF) for _ in range(num_words))
    
    # Add end marker
    values.append(0xDEADBEEF)
    
    # Pack into single block
    format_str = endian_fmt + 'I' * len(values)
    complete_block = struct.pack(format_str, *values)
    
    # Split the block into at least 2 chunks
    chunks = []
    remaining = len(complete_block)
    offset = 0
    
    while remaining > 0:
        # For first chunk, ensure we leave enough for at least one more chunk
        if not chunks:
            max_size = min(1024, remaining - 16)  # Leave at least 16 bytes for next chunk
        else:
            max_size = min(1024, remaining)
            
        min_size = min(16, remaining)
        chunk_size = random.randint(min_size, max_size)
        
        chunks.append(complete_block[offset:offset + chunk_size])
        offset += chunk_size
        remaining -= chunk_size
    
    # Ensure at least 2 chunks
    if len(chunks) == 1:
        mid = len(chunks[0]) // 2
        chunks = [chunks[0][:mid], chunks[0][mid:]]
    
    return chunks

def validate_block(data: bytes, endian_fmt: str) -> bool:
    """Validate a received data block."""
    # Check minimum size for header (start marker + length|count) and end marker
    if len(data) < 12:  # Minimum size check (start + length|count + end)
        print(f"Block too small: {len(data)} bytes")
        return False
        
    if len(data) % 4 != 0:  # Multiple of 4 check
        print(f"Block length {len(data)} not multiple of 4")
        return False
        
    # First check start marker and get length|count
    start_marker, length_count = struct.unpack(endian_fmt + "2I", data[:8])
    
    if start_marker != 0xBAADF00D:
        print(f"Invalid start marker: 0x{start_marker:08X}")
        return False
    
    # Extract frame length from upper 16 bits
    frame_length = (length_count >> 16) & 0xFFFF
    
    # Validate total frame length
    if frame_length != len(data):
        print(f"Length mismatch: expected {frame_length}, got {len(data)}")
        return False
        
    # Check end marker
    end_marker = struct.unpack(endian_fmt + "I", data[-4:])[0]
    if end_marker != 0xDEADBEEF:
        print(f"Invalid end marker: 0x{end_marker:08X}")
        return False
    
    return True

class Connection:
    """Base connection handler with common functionality."""
    def __init__(self, args):
        self.args = args
        self.connection_active_flag = threading.Event()  # Flag to control connection lifecycle
        self.sock = None
        self.thread_local = threading.local()
        self.thread_local.msg_type = "CN"  # Set default for main thread
        self.shutdown_flag = threading.Event()
        self.last_time_received = None
        self.sender = None
        self.receiver = None
        
        # Add thread coordination and state management
        self.count = 0
        self.count_lock = threading.Lock()  # Lock for thread-safe counter operations
        self.last_received_count = -1
        self.stats = {
            'sent_frames': 0,
            'received_frames': 0,
            'invalid_frames': 0,
            'connection_resets': 0
        }
        self.stats_lock = threading.Lock()  # Lock for thread-safe stats updates
        
        # HexDumper state
        self.tx_offset = 0
        self.rx_offset = 0

        # Initialize logger
        self.logger = ColoredLogger(self.__class__.__name__, self)

    def update_stats(self, key, increment=1):
        """Thread-safe update of statistics."""
        with self.stats_lock:
            self.stats[key] = self.stats.get(key, 0) + increment
    
    def get_next_count(self):
        """Thread-safe increment and return of count."""
        with self.count_lock:
            count = self.count
            self.count += 1
            return count
    
    def format_byte(self, pos, data, offset):
        """Format a single byte with dot notation."""
        if pos < offset:
            return '..'
        if pos < offset + len(data):
            return "{:02X}".format(data[pos - offset])
        return '..'

    def format_word(self, word_pos, data, offset):
        """Format a 32-bit word with dot notation."""
        return ''.join([self.format_byte(pos, data, offset) 
                       for pos in range(word_pos, word_pos + 4)])

    def format_line(self, line_pos, data, offset):
        """Format a line of four 32-bit words."""
        words = [self.format_word(word_pos, data, offset) 
                for word_pos in range(line_pos, line_pos + 16, 4)]
        return '  ' + ' '.join(words)

    def print_hex_words(self, data, is_tx=True):
        """Print hex words with proper dot notation."""
        offset = self.tx_offset if is_tx else self.rx_offset
        start_line = (offset // 16) * 16
        end_line = ((offset + len(data) + 15) // 16) * 16

        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
        msg_type = self.thread_local.msg_type  # Get current thread's message type
        
        if msg_type == "TX":
            color = ColoredLogger.ANSI_BLUE
        elif msg_type == "RX":
            color = ColoredLogger.ANSI_RED
        else:  # CN for connection messages
            color = ColoredLogger.ANSI_GREEN
            msg_type = "CN"
        
        mode_prefix = "S: " if getattr(self.args, 'mode', 'client') == 'server' else "C: "
        
        for line_pos in range(start_line, end_line, 16):
            line = self.format_line(line_pos, data, offset)
            print(f"{timestamp}: {mode_prefix}{color}{msg_type}: {line}{ColoredLogger.ANSI_RESET}")

        # Update offset
        if is_tx:
            self.tx_offset += len(data)
        else:
            self.rx_offset += len(data)

    def reset_offsets(self):
        """Reset TX and RX offsets."""
        self.tx_offset = 0
        self.rx_offset = 0

    def print_msg(self, message: str, data: bytes = None):
        """Legacy method - now uses logger"""
        self.logger.info(message, data)

    def print_stats(self):
        """Print current connection statistics."""
        with self.stats_lock:
            stats_copy = self.stats.copy()
        
        self.logger.info("Connection statistics:")
        for key, value in stats_copy.items():
            self.logger.info(f"  {key}: {value}")

    def start_threads(self, sock: socket.socket):
        """Start sender and receiver threads."""
        self.sock = sock
        
        def sender_wrapper():
            self.thread_local.msg_type = "TX"
            self._sender_thread()
            
        def receiver_wrapper():
            self.thread_local.msg_type = "RX"
            self._receiver_thread()
        
        self.sender = threading.Thread(
            target=sender_wrapper,
            name="SenderThread"
        )
        self.receiver = threading.Thread(
            target=receiver_wrapper,
            name="ReceiverThread"
        )
        
        self.sender.daemon = True  # Make threads daemon to exit when main thread exits
        self.receiver.daemon = True
        
        self.sender.start()
        self.receiver.start()
        
        return self.sender, self.receiver

    def _sender_thread(self):
        """Internal sender thread method."""
        # If no-send is enabled in client mode, just sleep
        if getattr(self.args, 'no_send', False):
            self.print_msg("Sender thread disabled by --no-send flag")
            while not self.connection_active_flag.is_set() and not app.shutdown_flag.is_set():
                time.sleep(1)
            return

        CHUNK_GAP = 0.005  # 5ms gap between chunks
        while not self.connection_active_flag.is_set() and not app.shutdown_flag.is_set():
            try:
                count = self.get_next_count()
                chunks = create_data_chunks(self.args.endian_fmt, count)
                total_size = sum(len(chunk) for chunk in chunks)
                total_chunks = len(chunks)

                first_chunk_values = struct.unpack(self.args.endian_fmt + 'II', chunks[0][:8])
                length = (first_chunk_values[1] >> 16) & 0xFFFF
                print("")
                self.print_msg(f"Sending frame #{count}, length: {length} bytes, split into {total_chunks} chunks")
                
                for i, chunk in enumerate(chunks):
                    if self.connection_active_flag.is_set() or app.shutdown_flag.is_set():
                        break
                    self._send_chunk(chunk, i, total_chunks, length)
                    
                    if i < len(chunks) - 1:
                        time.sleep(0)
                        # time.sleep(CHUNK_GAP)
                
                self.update_stats('sent_frames')
                
                # if self.connection_active_flag.wait(self.args.interval) or app.shutdown_flag.wait(self.args.interval):
                #     break
                if self.connection_active_flag.wait(0) or app.shutdown_flag.wait(0):
                    break

            except socket.error as e:
                self.print_msg(f"Send error: {e}")
                break
                
        self.print_msg("Sender thread exiting")

    def _send_chunk(self, chunk, chunk_index=0, total_chunks=0, frame_length=0):
        """Send a chunk of data showing complete words."""
        chunk_info = f"Chunk {chunk_index+1}/{total_chunks}" if total_chunks > 0 else "Chunk"
        progress = f", {len(chunk)} bytes" if frame_length == 0 else f", {len(chunk)} bytes ({min(100, int((chunk_index+1) * 100 / total_chunks))}% of frame)"
        self.print_msg(f"{chunk_info}{progress}:", chunk)
        self.sock.sendall(chunk)

    def _receiver_thread(self):
        """Internal receiver thread method."""
        buffer = bytearray()
        current_frame = None
        expected_frame_length = 0
        
        while not self.connection_active_flag.is_set() and not app.shutdown_flag.is_set():
            try:
                # Set a timeout on the socket so we can check for shutdown regularly
                self.sock.settimeout(0.5)
                try:
                    data = self.sock.recv(1024)
                    if not data:
                        self.print_msg("Connection closed by peer")
                        break
                    
                    # Determine if we're in the middle of receiving a frame
                    if current_frame is None and len(buffer) >= 8:
                        # We have enough data to check for a frame header
                        if struct.unpack(self.args.endian_fmt + "I", buffer[:4])[0] == 0xBAADF00D:
                            length_count = struct.unpack(self.args.endian_fmt + "I", buffer[4:8])[0]
                            expected_frame_length = (length_count >> 16) & 0xFFFF
                            current_frame = f"#{length_count & 0xFFFF}"
                    
                    # Prepare chunk info for display
                    chunk_info = ""
                    if current_frame is not None:
                        progress = f"{len(buffer)}/{expected_frame_length}" if expected_frame_length > 0 else f"{len(buffer)} bytes"
                        percent = min(100, int(len(buffer) * 100 / expected_frame_length)) if expected_frame_length > 0 else 0
                        chunk_info = f" for frame {current_frame} ({progress} bytes, {percent}% complete)"
                        
                    self.print_msg(f"Received chunk #{len(data)} bytes{chunk_info}:", data)

                    # Append new data to buffer (only here, after successful receive)
                    buffer.extend(data)
                    
                except socket.timeout:
                    # Just a timeout, check if we should shut down
                    continue
                except socket.error as e:
                    if isinstance(e, ConnectionResetError):
                        self.print_msg("Connection reset by server")
                    else:
                        self.print_msg(f"Receive error: {e}")
                    break
                
                # Process complete frames in the buffer
                while len(buffer) >= 12:  # Minimum frame size (start marker + length|count + end marker)
                    # Check for start marker
                    if len(buffer) >= 4 and struct.unpack(self.args.endian_fmt + "I", buffer[:4])[0] == 0xBAADF00D:
                        # If we have enough bytes to read length field
                        if len(buffer) >= 8:
                            length_count = struct.unpack(self.args.endian_fmt + "I", buffer[4:8])[0]
                            frame_length = (length_count >> 16) & 0xFFFF
                            
                            # If we have a complete frame
                            if len(buffer) >= frame_length:
                                frame = buffer[:frame_length]
                                
                                # Validate the frame
                                if validate_block(frame, self.args.endian_fmt):
                                    # Extract count from lower 16 bits
                                    count = length_count & 0xFFFF
                                    self.print_msg(f"Valid frame #{count} received, length: {frame_length} bytes, complete!")
                                    
                                    # Track statistics
                                    self.update_stats('received_frames')
                                    self.last_received_count = count
                                    self.last_time_received = time.time()
                                    
                                else:
                                    self.print_msg(f"Invalid frame detected, discarding")
                                    self.update_stats('invalid_frames')
                                
                                
                               
                                
                                # Reset frame tracking
                                current_frame = None
                                expected_frame_length = 0
                                # Remove processed frame from buffer
                                buffer = buffer[frame_length:]
                                continue
                            else:
                                # Not enough data for complete frame yet
                                break
                        else:
                            # Not enough data to read length field
                            break
                    else:
                        # No valid start marker, advance buffer by 1 byte to find next potential frame
                        buffer = buffer[1:]
                    
                # If buffer is getting too large without finding valid frames, reset it
                if len(buffer) > 16384:  # 16KB limit
                    self.print_msg(f"Buffer overflow, resetting (size: {len(buffer)})")
                    buffer = bytearray()
                    
            except socket.error as e:
                self.print_msg(f"Receive error: {e}")
                break
            
        self.print_msg("Receiver thread exiting")

    def cleanup(self):
        """Clean up resources properly."""
        self.print_msg("Cleaning up resources...")
        
        # Signal threads to stop
        self.connection_active_flag.set()
        
        # Close socket safely
        if self.sock:
            try:
                # Shutdown the socket first to interrupt any blocking operations
                self.sock.shutdown(socket.SHUT_RDWR)
            except (OSError, socket.error) as e:
                # The socket might already be closed or disconnected
                self.print_msg(f"Socket already closed: {e}")
                pass
            finally:
                try:
                    self.sock.close()
                except:
                    pass
                self.sock = None
        
        # Wait for threads to terminate with timeout
        if self.sender and self.sender.is_alive():
            self.sender.join(timeout=2.0)
            if self.sender.is_alive():
                self.print_msg("Warning: Sender thread did not terminate gracefully")
        
        if self.receiver and self.receiver.is_alive():
            self.receiver.join(timeout=2.0)
            if self.receiver.is_alive():
                self.print_msg("Warning: Receiver thread did not terminate gracefully")
        
        # Reset state for potential reuse
        self.sender = None
        self.receiver = None
        self.reset_offsets()
        self.print_msg("Cleanup complete")

class ClientConnection(Connection):
    """Client-specific connection handler."""
    def __init__(self, args):
        super().__init__(args)
        self.reconnect_delay = 1.0  # Initial reconnect delay in seconds
        self.max_reconnect_delay = 30.0  # Maximum reconnect delay
        self.connection_attempts = 0
        
    def run(self):
        """Run the client connection."""
        while not self.connection_active_flag.is_set() and not app.shutdown_flag.is_set():
            try:
                # Calculate backoff for reconnection attempts
                if self.connection_attempts > 0:
                    delay = min(self.reconnect_delay * (2 ** (self.connection_attempts - 1)), self.max_reconnect_delay)
                    self.print_msg(f"Waiting {delay:.1f} seconds before reconnecting...")
                    
                    # Use a loop with short timeouts to check shutdown flags frequently
                    wait_start = time.time()
                    while (time.time() - wait_start) < delay:
                        if self.connection_active_flag.is_set() or app.shutdown_flag.is_set():
                            break
                        time.sleep(0.1)  # Short sleep interval
                    
                    # Check if we should exit
                    if self.connection_active_flag.is_set() or app.shutdown_flag.is_set():
                        break
                
                self.connection_attempts += 1
                self.print_msg(f"Attempting to connect to {self.args.server}:{self.args.port} (attempt #{self.connection_attempts})")
                
                # Create a new socket for each connection attempt
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.settimeout(10.0)  # 10 second connection timeout
                
                self.sock.connect((self.args.server, self.args.port))
                self.sock.settimeout(None)  # Reset to blocking mode after connection
                
                self.print_msg(f"Connected to {self.args.server}:{self.args.port}")
                self.update_stats('connection_resets', 1)
                
                # Start sender and receiver threads
                self.start_threads(self.sock)
                
                # Reset connection attempt counter on successful connection
                self.connection_attempts = 0
                
                # Wait for threads to exit
                while not self.connection_active_flag.is_set() and not app.shutdown_flag.is_set():
                    if not self.sender.is_alive() and not self.receiver.is_alive():
                        self.print_msg("Connection threads have exited")
                        break
                    # Simple sleep instead of using event wait
                    time.sleep(0.5)  # Check every 0.5 seconds
                
                # Ensure socket is closed before reconnecting
                if self.sock:
                    try:
                        self.sock.close()
                    except:
                        pass
                    self.sock = None
                
                if not self.connection_active_flag.is_set():
                    self.print_msg("Connection lost. Will attempt to reconnect...")
                
            except socket.error as e:
                self.print_msg(f"Connection error: {e}")
                
                # Close the socket if it exists
                if self.sock:
                    try:
                        self.sock.close()
                    except:
                        pass
                    self.sock = None
            
            except Exception as e:
                self.print_msg(f"Unexpected error: {e}")
                import traceback
                self.print_msg(traceback.format_exc())
                
                if self.sock:
                    try:
                        self.sock.close()
                    except:
                        pass
                    self.sock = None

class ServerConnection(Connection):
    """Server-specific connection handler."""
    def __init__(self, args):
        super().__init__(args)
        self.client_connections = []
        self.clients_lock = threading.Lock()
    
    def run(self):
        """Run the server connection."""
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            server_socket.bind(('', self.args.port))
            server_socket.listen(5)
            self.print_msg(f"Server listening on port {self.args.port}")
            
            while not self.connection_active_flag.is_set() and not app.shutdown_flag.is_set():
                try:
                    server_socket.settimeout(1.0)
                    try:
                        client_sock, addr = server_socket.accept()
                        self.print_msg(f"New connection from {addr[0]}:{addr[1]}")
                        
                        # Create a new connection handler for this client
                        client_handler = ClientHandler(self.args, client_sock, addr)
                        
                        # Add to our list of active clients
                        with self.clients_lock:
                            self.client_connections.append(client_handler)
                            
                        # Start client handler threads
                        client_handler.start()
                        
                    except socket.timeout:
                        # Check for inactive clients and clean them up
                        self._cleanup_inactive_clients()
                        continue
                        
                except socket.error as e:
                    if not self.connection_active_flag.is_set():
                        self.print_msg(f"Server socket error: {e}")
                    break
                    
        finally:
            self.print_msg("Server shutting down...")
            server_socket.close()
            self._cleanup_all_clients()
    
    def _cleanup_inactive_clients(self):
        """Remove and clean up disconnected clients."""
        with self.clients_lock:
            active_clients = []
            for client in self.client_connections:
                if client.is_active():
                    active_clients.append(client)
                else:
                    self.print_msg(f"Cleaning up inactive client {client.addr}")
                    client.cleanup()
            
            removed = len(self.client_connections) - len(active_clients)
            if removed > 0:
                self.print_msg(f"Removed {removed} inactive client(s)")
                
            self.client_connections = active_clients
    
    def _cleanup_all_clients(self):
        """Clean up all client connections."""
        with self.clients_lock:
            for client in self.client_connections:
                self.print_msg(f"Shutting down client {client.addr}")
                client.cleanup()
            self.client_connections = []
    
    def cleanup(self):
        """Clean up resources."""
        self.connection_active_flag.set()
        self._cleanup_all_clients()
        super().cleanup()

class ClientHandler(Connection):
    """Handles an individual client connection on the server."""
    def __init__(self, args, sock, addr):
        super().__init__(args)
        self.sock = sock
        self.addr = addr
        self.last_activity = time.time()
        self.active = True
    
    def start(self):
        """Start the client handler threads."""
        self.sender, self.receiver = self.start_threads(self.sock)
        return self
    
    def is_active(self):
        """Check if this client connection is still active."""
        # Connection is active if either sender or receiver thread is alive
        return (self.sender and self.sender.is_alive()) or (self.receiver and self.receiver.is_alive())
    
    def _sender_thread(self):
        """Sender thread for this client."""
        try:
            # Call the parent implementation
            super()._sender_thread()
        finally:
            self.active = False
    
    def _receiver_thread(self):
        """Receiver thread for this client."""
        try:
            buffer = bytearray()
            
            while not self.connection_active_flag.is_set():
                try:
                    data = self.sock.recv(1024)
                    if not data:
                        self.print_msg("Connection closed by peer")
                        break

                    # Update activity timestamp
                    self.last_activity = time.time()
                    
                    self.print_msg("Received chunk:", data)
                    
                    # Append new data to buffer (only here, after successful receive)
                    buffer.extend(data)
                    
                    # Process complete frames in the buffer
                    while len(buffer) >= 12:  # Minimum frame size (start marker + length|count + end marker)
                        # Check for start marker
                        if len(buffer) >= 4 and struct.unpack(self.args.endian_fmt + "I", buffer[:4])[0] == 0xBAADF00D:
                            if len(buffer) >= 8:
                                length_count = struct.unpack(self.args.endian_fmt + "I", buffer[4:8])[0]
                                frame_length = (length_count >> 16) & 0xFFFF
                                
                                # If we have a complete frame
                                if len(buffer) >= frame_length:
                                    frame = buffer[:frame_length]
                                    
                                    # Validate the frame
                                    if validate_block(frame, self.args.endian_fmt):
                                        # Extract count from lower 16 bits
                                        count = length_count & 0xFFFF
                                        self.print_msg(f"Valid frame #{count} received, length: {frame_length} bytes")
                                        
                                        # Track statistics
                                        self.update_stats('received_frames')
                                        self.last_received_count = count
                                        self.last_time_received = time.time()
                                        
                                    else:
                                        self.print_msg(f"Invalid frame detected, discarding")
                                        self.update_stats('invalid_frames')
                                    
                                    # Remove processed frame from buffer
                                    buffer = buffer[frame_length:]
                                    continue
                                else:
                                    # Not enough data for complete frame yet
                                    break
                            else:
                                # Not enough data to read length field
                                break
                        else:
                            # No valid start marker, advance buffer by 1 byte to find next potential frame
                            buffer = buffer[1:]
                        
                    # If buffer is getting too large without finding valid frames, reset it
                    if len(buffer) > 16384:  # 16KB limit
                        self.print_msg(f"Buffer overflow, resetting (size: {len(buffer)})")
                        buffer = bytearray()
                        
                except socket.error as e:
                    self.print_msg(f"Receive error: {e}")
                    break
                
            self.print_msg("Receiver thread exiting")
        finally:
            self.active = False

def main():
    disable_quickedit()
    args = parse_arguments()
    
    # Set mode in app state
    app.set_mode(args.mode == 'server')
    
    # Reset application shutdown flag
    app.shutdown_flag.clear()
    
    # Create appropriate connection type
    connection = ServerConnection(args) if args.mode == 'server' else ClientConnection(args)
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, service_shutdown)
    signal.signal(signal.SIGTERM, service_shutdown)

    try:
        connection.run()
    except KeyboardInterrupt:
        print("\nKeyboard interrupt detected, shutting down...")
        app.shutdown_flag.set()
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Give threads a moment to notice the shutdown flag
        time.sleep(0.2)
        
        # Clean up resources
        try:
            print("\nCleaning up resources...")
            connection.cleanup()
        except Exception as e:
            print(f"Error during cleanup: {e}")
            
    print("Program terminated")

if __name__ == '__main__':
    main()

