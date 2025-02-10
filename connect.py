#!/usr/bin/env python3
import socket
import select
import time
import re


def hex_to_bytes(s):
    """
    Convert a hex string that may contain multiple "0x" prefixes into bytes.
    
    This function uses a regular expression to extract all groups of hex digits.
    For example:
      "0xABCD0xDEFA" -> b'\xab\xcd\xde\xfa'
      "0x48454c4c4f" -> b'HELLO'
    """
    # Find all groups of hex digits that may be preceded by "0x"
    matches = re.findall(r'(?:0x)?([0-9A-Fa-f]+)', s)
    # Join the matches with spaces so that bytes.fromhex() can process them
    hex_str = " ".join(matches)
    return bytes.fromhex(hex_str)


def format_bytes_in_32bit_blocks(data):
    """
    Format bytes as hexadecimal in groups of 4 bytes, each prefixed with '0x'.
    For example, b'\x01\x02\x03\x04\x05\x06' becomes:
      '0x01020304 0x0506'
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

    # Create a TCP/IP socket and connect to the server
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((host, port))
        print("Connected to {}:{}".format(host, port))
    except socket.error as err:
        print("Connection error:", err)
        return

    sock.setblocking(0)

    # Define messages as hex strings. Even if concatenated without spaces,
    # our hex_to_bytes() function will extract the separate tokens.
    messages = [
        hex_to_bytes("0x48454c4c4f"),         # HELLO
        hex_to_bytes("0x474f4f44444159"),       # GOODDAY
        hex_to_bytes("0x425945425945")          # BYEBYE
    ]
    # For example, the following would also work:
    # hex_to_bytes("0xABCD" + "0xDEFA")
    # becomes hex_to_bytes("0xABCD0xDEFA")
    # and returns b'\xab\xcd\xde\xfa'.

    msg_index = 0
    next_send_time = time.time() + 5  # schedule first send in 5 seconds

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
