#!/usr/bin/env python3
import select
import socket
import time


def main():
    host = ''  # Bind to all available interfaces
    port = 4200

    # Create a TCP/IP server socket
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        # Allow reuse of the address
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((host, port))
        server_socket.listen(1)
        print("Server listening on port", port)

        # Accept a single client connection
        conn, addr = server_socket.accept()
        print("Connected by", addr)

        # Set the connection to non-blocking mode
        conn.setblocking(0)

        messages = ["HELLO", "GOODDAY", "BYEBYE"]
        msg_index = 0
        next_send_time = time.time() + 5  # Schedule the first send in 5 seconds

        while True:
            now = time.time()
            # Calculate timeout until the next send time
            timeout = next_send_time - now
            if timeout < 0:
                timeout = 0

            # Wait until the socket is ready for reading, or until timeout
            readable, _, _ = select.select([conn], [], [], timeout)

            # If the socket is ready, receive data
            if readable:
                try:
                    data = conn.recv(1024)
                    if not data:
                        print("Client disconnected.")
                        break
                    print("Received:", data.decode('utf-8'))
                except socket.error as err:
                    print("Socket error during receiving:", err)
                    break

            # Check if it's time to send a message
            now = time.time()
            if now >= next_send_time:
                message = messages[msg_index]
                try:
                    conn.sendall(message.encode('utf-8'))
                    print("Sent:", message)
                except socket.error as err:
                    print("Socket error during sending:", err)
                    break
                # Schedule the next send and update the message index
                next_send_time = now + 5
                msg_index = (msg_index + 1) % len(messages)

    except socket.error as err:
        print("Socket error:", err)
    finally:
        try:
            conn.close()
        except Exception:
            pass
        server_socket.close()


if __name__ == '__main__':
    main()
