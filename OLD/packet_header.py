import struct

class PacketHeader:
    """Represents a 32-bit packed message header with encoding and decoding."""

    MSG_TYPE_MASK   = 0x0000000F  # Bits 0-3
    MSG_SOURCE_MASK = 0x000000F0  # Bits 4-7
    COUNTER_MASK    = 0x0000FF00  # Bits 8-15
    LENGTH_MASK     = 0xFFFF0000  # Bits 16-31

    def __init__(self, msg_type, msg_source, counter, length):
        """Initialize a PacketHeader with individual field values and pack them."""
        self.msg_type = msg_type
        self.msg_source = msg_source
        self.counter = counter
        self.length = length
        self._pack()  # Automatically pack the values

    def _pack(self):
        """Packs the message fields into a 32-bit integer, adjusting for endianness."""
        packed = (
            (self.length << 16) |
            (self.counter << 8) |
            (self.msg_source << 4) |
            (self.msg_type)
        )
        self.packed = struct.unpack("<I", struct.pack(">I", packed))[0]  # Swap endianness if needed

    def _unpack(self):
        """Unpacks the 32-bit integer back into fields (used for from_hex)."""
        unpacked = struct.unpack(">I", struct.pack("<I", self.packed))[0]  # Swap endianness
        self.length = (unpacked & self.LENGTH_MASK) >> 16
        self.counter = (unpacked & self.COUNTER_MASK) >> 8
        self.msg_source = (unpacked & self.MSG_SOURCE_MASK) >> 4
        self.msg_type = unpacked & self.MSG_TYPE_MASK

    def __repr__(self):
        """Compact representation with proper tab alignment and lowercase labels."""
        def mask_info(mask, shift, label):
            masked_value = (self.packed & mask)
            extracted_value = masked_value >> shift
            return (f"{label:<10}  0x{extracted_value:02X}\t(mask: 0x{mask:08X}) : 0x{masked_value:08X}"
                    f" >> {shift:02}: = {extracted_value:6}d")

        return (
            f"packed\t\t                             0x{self.packed:08X}\n"
            f"{mask_info(self.MSG_TYPE_MASK, 0, 'msg_type')}\n"
            f"{mask_info(self.MSG_SOURCE_MASK, 4, 'msg_source')}\n"
            f"{mask_info(self.COUNTER_MASK, 8, 'counter')}\n"
            f"{mask_info(self.LENGTH_MASK, 16, 'length')}"
        )

    @staticmethod
    def from_hex(hex_string):
        """Creates a PacketHeader from a packed hexadecimal string."""
        packed_value = int(hex_string.lstrip("0x"), 16)  # Strip '0x' if present
        packet = PacketHeader(0, 0, 0, 0)  # Initialize with placeholders
        packet.packed = packed_value
        packet._unpack()  # Unpack the stored values
        return packet

    @staticmethod
    def pack_hex_string(hex_string):
        """Creates a PacketHeader from a packed hex string (with or without 0x prefix)."""
        return PacketHeader.from_hex(hex_string)


# Example Usage
packet = PacketHeader(msg_type=0, msg_source=6, counter=181, length=52)
print(packet)

# decoded_packet = PacketHeader.from_hex("004EB510")
# print(decoded_packet)
#
# packed_from_string = PacketHeader.pack_hex_string("0x004EB510")
# print(packed_from_string)
#
# packed_from_string_no_prefix = PacketHeader.pack_hex_string("004EB510")
# print(packed_from_string_no_prefix)
