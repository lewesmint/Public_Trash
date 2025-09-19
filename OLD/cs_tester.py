import socket
import argparse
import time
import threading


def generate_data(length):
    """Generate a byte sequence cycling from 1 to 255, then 0, then back to 1."""
    return bytearray((i % 256) for i in range(1, length + 1))


def sender(conn, interval, shutdown_event):
    """Continuously send data in exponentially increasing sizes until shutdown."""
    size = 10  # Initial size
    max_size = 5120  # Maximum size

    while not shutdown_event.is_set():
        data = generate_data(size)
        try:
            conn.sendall(data)
            print(f"Sent {size} bytes")
        except (socket.error, BrokenPipeError) as e:
            print(f"Send error: {e}")
            shutdown_event.set()
            break

        time.sleep(interval)
        size *= 2
        if size > max_size:
            size = 10  # Reset size


def receiver(conn, shutdown_event):
    """Continuously receive data until the connection is closed or an error occurs."""
    while not shutdown_event.is_set():
        try:
            data = conn.recv(1024)
            if not data:  # No data means the connection was closed.
                print("Connection closed by client.")
                shutdown_event.set()
                break
            print(f"Received: {data.decode(errors='ignore')}")
        except socket.error as e:
            print(f"Receive error: {e}")
            shutdown_event.set()
            break


def handle_connection(conn, addr, interval):
    """Handle a client connection by starting sender and receiver threads."""
    print(f"Connection established with {addr}")
    shutdown_event = threading.Event()

    send_thread = threading.Thread(target=sender, args=(conn, interval, shutdown_event))
    recv_thread = threading.Thread(target=receiver, args=(conn, shutdown_event))

    send_thread.start()
    recv_thread.start()

    # Wait for both threads to finish before returning.
    send_thread.join()
    recv_thread.join()
    print("Connection handler terminating.")


def start_server(host, port, interval):
    """Start the TCP server to accept and handle incoming connections."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((host, port))
        server_socket.listen(1)
        print(f"Listening on {host}:{port}...")

        while True:
            try:
                conn, addr = server_socket.accept()
                with conn:
                    handle_connection(conn, addr, interval)
            except socket.error as e:
                print(f"Socket error: {e}")
            except KeyboardInterrupt:
                print("Server shutting down.")
                break


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="TCP server that sends exponentially increasing data blocks concurrently with receiving data."
    )
    parser.add_argument(
        "--host", type=str, default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port", type=int, default=4200,
        help="Port to listen on (default: 4200)"
    )
    parser.add_argument(
        "--interval", type=float, default=5,
        help="Interval between sends in seconds (default: 5)"
    )
    args = parser.parse_args()

    try:
        start_server(args.host, args.port, args.interval)
    except KeyboardInterrupt:
        print("Server stopped by user.")
