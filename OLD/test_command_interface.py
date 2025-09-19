#!/usr/bin/env python3
"""
Client programme that connects to a server (default host "localhost", port 4100),
waits 3 seconds and then continuously sends command packets every 5 seconds.

Each command packet is structured as follows (all numbers are 32-bit unsigned integers,
packed in network byte order):

    +--------------+----------------------+----------------------+----------------+
    | Start marker | Packet length field  | Message index field  | Message (ASCII)|
    +--------------+----------------------+----------------------+----------------+
                                                                   +---------------+
                                                                   | End marker    |
                                                                   +---------------+

The packet length equals 16 plus the length of the message.
After sending a command, the client waits for an acknowledgement from the server,
which must have the message "ACK <index>" (with the correct index) in its message field.
If the connection fails at any point, the client waits for 5 seconds before trying to reconnect.
"""

import argparse
import socket
import struct
import time

# Protocol constants and timings
START_MARKER = 0xBAADF00D
END_MARKER   = 0xDEADBEEF
DEFAULT_HOST = "192.168.1.178"
DEFAULT_PORT = 4100
INITIAL_WAIT_SECONDS = 3
SEND_INTERVAL_SECONDS = 5
RECONNECT_INTERVAL_SECONDS = 5


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


def create_packet(message: str, index: int) -> bytes:
    """
    Create a binary command packet.

    The packet structure is:
        - 4 bytes: start marker
        - 4 bytes: total packet length (16 + len(message))
        - 4 bytes: message index
        - N bytes: message (ASCII)
        - 4 bytes: end marker

    Args:
        message: The ASCII message to send.
        index: The message index.

    Returns:
        The binary packet as bytes.
    """
    message_bytes = message.encode("ascii")
    packet_length = 16 + len(message_bytes)
    header = struct.pack("!III", START_MARKER, packet_length, index)
    footer = struct.pack("!I", END_MARKER)
    packet = header + message_bytes + footer
    return packet


def recv_packet(sock: socket.socket) -> (int, str):
    """
    Receive a packet from the socket and return the message index and the ASCII message.

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

    # Compute the message body length (packet_length - 16)
    message_body_length = packet_length - 16
    message_bytes = recv_all(sock, message_body_length)

    # Read footer: 4 bytes (end marker)
    footer = recv_all(sock, 4)
    (end_marker,) = struct.unpack("!I", footer)
    if end_marker != END_MARKER:
        raise ValueError(f"Invalid end marker: {end_marker:#010x}")

    message = message_bytes.decode("ascii")
    return msg_index, message


def send_and_receive(sock: socket.socket, message: str, index: int) -> bool:
    """
    Send a command packet and wait for an acknowledgement packet.

    Retries if no response is received within 6 seconds.

    Args:
        sock: The connected socket.
        message: The command message to send.
        index: The message index.

    Returns:
        True if a valid acknowledgement was received, False otherwise.
    """
    packet = create_packet(message, index)
    max_attempts = 3  # Number of retry attempts
    timeout_seconds = 6

    for attempt in range(max_attempts):
        try:
            sock.sendall(packet)
            print(f"Sent message (index {index}): '{message}' (Attempt {attempt + 1})")
        except socket.error as e:
            print(f"Error sending packet: {e}")
            return False

        # Set socket timeout for receiving ACK
        sock.settimeout(timeout_seconds)

        try:
            ack_index, ack_message = recv_packet(sock)
        except socket.timeout:
            print(f"No response received within {timeout_seconds} seconds. Retrying...")
            continue  # Retry sending the message
        except Exception as e:
            print(f"Error receiving ack: {e}")
            return False  # If there's a critical error, exit

        expected_ack = f"ACK {index}"
        if ack_message.strip() == expected_ack:
            print(f"Received valid ack: '{ack_message}' (index {ack_index})")
            return True  # Exit loop if ACK is received
        else:
            print(f"Invalid ack received: '{ack_message}' (index {ack_index}), expected: '{expected_ack}'")

    print("Failed to receive valid ack after multiple attempts. Giving up on this message.")
    return False  # Message send failed after retries

def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Client programme that sends binary commands and checks for acknowledgements."
    )
    parser.add_argument(
        "--host",
        type=str,
        default=DEFAULT_HOST,
        help=f"Server host (default: {DEFAULT_HOST})"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"Server port (default: {DEFAULT_PORT})"
    )
    return parser.parse_args()


def main() -> None:
    """Main entry point for the client programme."""
    args = parse_arguments()

    # Five short three-word phrases to cycle through
    phrases = [
        "Red Blue Green",
        "Cat Dog Mouse",
        "One Two Three",
        "Run Jump Play",
        "Sun Moon Star",
        "log_level=INFO",
        "a horse is a horse",
        "of course of course",
        "and no one can talk to a horse of course",
        "that is of course unless the horse is the famous Mr. Ed"
        "I am a robot",
        "Spiderman, Spiderman, does whatever a spider can",
        "Spins a web, any size, catches thieves just like flies",
        "Look out, here comes the Spiderman",
        "Is he strong? Listen bud, he's got radioactive blood",
        "Can he swing from a thread? Take a look overhead",
        "Hey there, there goes the Spiderman",
        "In the chill of night, at the scene of a crime",
        "Like a streak of light, he arrives just in time",
        "Spiderman, Spiderman, friendly neighborhood Spiderman",
        "Wealth and fame, he's ignored, action is his reward",
        "To him, life is a great big bang-up, wherever there's a hang-up",
        "You'll find the Spiderman",
        "log_level=DEBUG",
    ]

    msg_index = 1
    phrase_index = 0

    while True:
        try:
            print(f"Attempting to connect to {args.host}:{args.port}...")
            with socket.create_connection((args.host, args.port)) as sock:
                print(f"Connected to {args.host}:{args.port}")
                # Initial wait before sending the first message
                time.sleep(INITIAL_WAIT_SECONDS)
                while True:
                    phrase = phrases[phrase_index]
                    if not send_and_receive(sock, phrase, msg_index):
                        print("Failed to send message or receive valid ack. Closing connection.")
                        break

                    msg_index += 1
                    phrase_index = (phrase_index + 1) % len(phrases)
                    time.sleep(SEND_INTERVAL_SECONDS)
        except (socket.error, ConnectionError) as e:
            print(f"Connection error: {e}. Retrying in {RECONNECT_INTERVAL_SECONDS} seconds.")
            time.sleep(RECONNECT_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
