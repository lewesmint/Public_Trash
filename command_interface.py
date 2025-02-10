#!/usr/bin/env python3
"""
Server programme that listens for command packets from a client,
parses them and sends an appropriate acknowledgement (ACK) packet in
response. The packet structure is as follows (all numbers are 32-bit unsigned
integers in network byte order):

    +--------------+----------------------+----------------------+----------------+
    | Start marker | Packet length field  | Message index field  | Message (ASCII)|
    +--------------+----------------------+----------------------+----------------+
                                                                   +---------------+
                                                                   | End marker    |
                                                                   +---------------+

The packet length equals 16 plus the length of the message.

The ACK packet is similarly structured. Its message field contains
"ACK <received_index>" (where <received_index> is taken from the received
command packet). The header’s message index field is set to a global
acknowledgement counter (which increments for each ACK sent).
"""

import argparse
import socket
import struct

# Protocol constants
START_MARKER = 0xBAADF00D
END_MARKER = 0xDEADBEEF
DEFAULT_PORT = 4100

# Global acknowledgement counter for header's message index in ACK packets.
ack_counter = 1


def recv_all(sock: socket.socket, n: int) -> bytes:
    """
    Receive exactly n bytes from the socket.

    Args:
        sock: The connected socket.
        n: Number of bytes to receive.

    Returns:
        A bytes object containing the received data.

    Raises:
        ConnectionError: If the connection is closed before n bytes are received.
    """
    data = bytearray()
    while len(data) < n:
        packet = sock.recv(n - len(data))
        if not packet:
            raise ConnectionError("Socket closed before receiving all expected data")
        data.extend(packet)
    return bytes(data)


def recv_command_packet(sock: socket.socket) -> (int, str):
    """
    Receive a command packet from the socket and return the message index
    and the ASCII message.

    The expected packet structure is:
        - 4 bytes: start marker
        - 4 bytes: packet length
        - 4 bytes: message index
        - N bytes: message (ASCII)
        - 4 bytes: end marker

    Args:
        sock: The connected socket.

    Returns:
        A tuple of (message_index, message).

    Raises:
        ValueError: If the packet does not have valid markers or lengths.
    """
    # Read header: 12 bytes (start marker, packet length, message index)
    header = recv_all(sock, 12)
    start_marker, packet_length, msg_index = struct.unpack("!III", header)
    if start_marker != START_MARKER:
        raise ValueError(f"Invalid start marker: {start_marker:#010x}")
    if packet_length < 16:
        raise ValueError(f"Packet length too short: {packet_length}")
    # Message body length is total packet length minus header and footer (16 bytes)
    message_body_length = packet_length - 16
    message_bytes = recv_all(sock, message_body_length)
    footer = recv_all(sock, 4)
    (end_marker,) = struct.unpack("!I", footer)
    if end_marker != END_MARKER:
        raise ValueError(f"Invalid end marker: {end_marker:#010x}")
    message = message_bytes.decode("ascii")
    return msg_index, message


def create_ack_packet(received_index: int) -> bytes:
    """
    Create an acknowledgement (ACK) packet in response to a command packet.

    The ACK packet structure is:
        - 4 bytes: start marker
        - 4 bytes: packet length (16 + length of ACK message)
        - 4 bytes: ACK message index (global counter)
        - N bytes: ACK message (ASCII), in the format "ACK <received_index>"
        - 4 bytes: end marker

    Args:
        received_index: The message index from the received command packet.

    Returns:
        The binary ACK packet as bytes.
    """
    global ack_counter
    ack_message = f"ACK {received_index}"
    ack_message_bytes = ack_message.encode("ascii")
    ack_packet_length = 16 + len(ack_message_bytes)
    header = struct.pack("!III", START_MARKER, ack_packet_length, ack_counter)
    footer = struct.pack("!I", END_MARKER)
    packet = header + ack_message_bytes + footer
    ack_counter += 1
    return packet


def parse_arguments() -> argparse.Namespace:
    """
    Parse command-line arguments.

    Returns:
        Parsed arguments.
    """
    parser = argparse.ArgumentParser(
        description="Server programme that receives command packets and sends ACKs."
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"Port to listen on (default: {DEFAULT_PORT})"
    )
    return parser.parse_args()


def main() -> None:
    """Main entry point for the server programme."""
    args = parse_arguments()
    host = ""  # Bind to all interfaces
    port = args.port

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_sock:
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_sock.bind((host, port))
        server_sock.listen(5)
        print(f"Server listening on port {port}...")

        while True:
            print("Waiting for a new connection...")
            try:
                conn, addr = server_sock.accept()
                print(f"Accepted connection from {addr}")
            except KeyboardInterrupt:
                print("Shutting down server.")
                break

            with conn:
                while True:
                    try:
                        msg_index, message = recv_command_packet(conn)
                    except (ConnectionError, ValueError) as e:
                        print(f"Connection closed or error: {e}")
                        break

                    print(f"Received command (index {msg_index}): {message}")
                    ack_packet = create_ack_packet(msg_index)
                    try:
                        conn.sendall(ack_packet)
                        print(f"Sent ACK for command index {msg_index}")
                    except socket.error as e:
                        print(f"Error sending ACK: {e}")
                        break


if __name__ == "__main__":
    main()
