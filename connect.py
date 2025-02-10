#!/usr/bin/env python3
import socket
import select
import time


def hex_to_bytes(s):
    """
    Convert a hex string that may contain "0x" prefixes into bytes.
    For example, "0x48 0x45 0x4c 0x4c 0x4f" becomes b'HELLO'.
    """
    tokens = s.split()
    tokens = [token[2:] if token.lower().startswith("0x") else token for token in tokens]
    return bytes.fromhex(" ".join(tokens))


def format_bytes_in_32bit_blocks(data):
    """
    Format bytes as hexadecimal in groups of 4 bytes, each prefixed with '0x'.
    For example, b'\x01\x02\x03\x04\x05\x06' becomes '0x01020304 0x0506'.
    """
    groups = []
    for i in range(0, len(data), 4):
        block = data[i:i + 4]
        hex_block = ''.join("{:02x}".format(b) for b in block)
        groups.append("0x" + hex_block)
    return ' '.join(groups)


def main():
    host = 'localhost'
    port = 4200

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((host, port))
        print("Connected to {}:{}".format(host, port))
    except socket.error as err:
        print("Connection failed:", err)
        return

    sock.setblocking(0)

    # Define messages as hex strings (with "0x" prefixes) and convert them.
    messages = [
        hex_to_bytes("0x48 0x45 0x4c 0x4c 0x4f"),         # HELLO
        hex_to_bytes("0x47 0x4f 0x4f 0x44 0x44 0x41 0x59"), # GOODDAY
        hex_to_bytes("0x42 0x59 0x45 0x42 0x59 0x45")        # BYEBYE
    ]
    msg_index = 0
    next_send_time = time.time() + 5

    while True:
        now = time.time()
        timeout = max(0, next_send_time - now)

        readable, _, _ = select.select([sock], [], [], timeout)

        if readable:
            try:
                data = sock.recv(1024)
                if not data:
                    print("Server closed the connection.")
                    break
                print("Received (hex):", format_bytes_in_32bit_blocks(data))
            except socket.error as err:
                print("Receive error:", err)
                break

        now = time.time()
        if now >= next_send_time:
            message = messages[msg_index]
            try:
                sock.sendall(message)
                print("Sent (hex):", format_bytes_in_32bit_blocks(message))
            except socket.error as err:
                print("Send error:", err)
                break

            next_send_time = now + 5
            msg_index = (msg_index + 1) % len(messages)

    sock.close()


if __name__ == '__main__':
    main()
