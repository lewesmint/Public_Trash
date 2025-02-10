#!/usr/bin/env python3
import socket
import select
import time


def main():
    host = 'localhost'  # Change to the server's address if needed
    port = 4200

    # Create a TCP/IP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((host, port))
        print("Connected to server at {}:{}".format(host, port))
    except socket.error as err:
        print("Failed to connect: {}".format(err))
        return

    # Set the socket to non-blocking mode
    sock.setblocking(0)

    messages = ["HELLO", "GOODDAY", "BYEBYE"]
    msg_index = 0
    next_send_time = time.time() + 5  # Schedule first send in 5 seconds

    while True:
        now = time.time()
        # Determine the timeout for select based on the next scheduled send
        timeout = next_send_time - now
        if timeout < 0:
            timeout = 0

        # Wait for the socket to become readable or for the timeout to expire
        readable, _, _ = select.select([sock], [], [], timeout)

        # If the socket is ready, receive data from the server
        if readable:
            try:
                data = sock.recv(1024)
                if not data:
                    print("Server closed the connection.")
                    break
                print("Received:", data.decode('utf-8'))
            except socket.error as err:
                print("Error receiving data: {}".format(err))
                break

        # Check if it's time to send the next message
        now = time.time()
        if now >= next_send_time:
            message = messages[msg_index]
            try:
                sock.sendall(message.encode('utf-8'))
                print("Sent:", message)
            except socket.error as err:
                print("Error sending data: {}".format(err))
                break

            # Schedule the next send and update the message index
            next_send_time = now + 5
            msg_index = (msg_index + 1) % len(messages)

    sock.close()


if __name__ == '__main__':
    main()
