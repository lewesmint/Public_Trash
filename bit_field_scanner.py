import re
import json
import struct
import sys

# Define known primitive sizes (Platform Dependent)
TYPE_SIZES = {
    "char": 8,   # 1 byte = 8 bits
    "short": 16, # 2 bytes = 16 bits
    "int": 32,   # 4 bytes = 32 bits
    "long": 64   # 8 bytes = 64 bits
}

# Detect system endianness
SYSTEM_ENDIANNESS = "little" if sys.byteorder == "little" else "big"


class BitFieldRegistry:
    """Registry to store and manage struct definitions."""
    _registry = {}

    @classmethod
    def register(cls, name, parser):
        cls._registry[name] = parser

    @classmethod
    def get(cls, name):
        return cls._registry.get(name, None)

    @classmethod
    def exists(cls, name):
        return name in cls._registry


class BitFieldParser:
    def __init__(self, struct_name, struct_definition, endianness=SYSTEM_ENDIANNESS):
        self.struct_name = struct_name
        self.struct_definition = struct_definition
        self.endianness = endianness
        self.bit_masks = {}
        self.bit_shifts = {}
        self.field_types = {}
        self.field_sizes = {}
        self.total_bits = 0
        self.nested_structs = {}  # Store nested struct instances
        self.parse_struct()

        # Register this struct globally
        BitFieldRegistry.register(struct_name, self)

    def parse_struct(self):
        """Parse the C struct definition to extract bit-fields, normal fields, and nested structures."""
        bit_position = 0

        # Extract bit-fields: (type, name, bit_size)
        bitfields = re.findall(r'(\w+)\s+(\w+) *: *(\d+);', self.struct_definition)

        # Extract normal fields: (type, name)
        normal_fields = re.findall(r'(\w+)\s+(\w+);', self.struct_definition)

        for dtype, name, size in bitfields:
            size = int(size)
            self.field_types[name] = dtype
            self.field_sizes[name] = size
            self.bit_masks[name] = ((1 << size) - 1) << bit_position
            self.bit_shifts[name] = bit_position
            bit_position += size  # Move bit counter

        for dtype, name in normal_fields:
            # Check if dtype is a nested struct
            if BitFieldRegistry.exists(dtype):
                nested_parser = BitFieldRegistry.get(dtype)
                self.nested_structs[name] = nested_parser
                nested_size = nested_parser.total_bits

                # Ensure correct byte alignment
                if bit_position % nested_size != 0:
                    padding_needed = nested_size - (bit_position % nested_size)
                    bit_position += padding_needed

                self.bit_shifts[name] = bit_position
                self.bit_masks[name] = ((1 << nested_size) - 1) << bit_position
                bit_position += nested_size
            else:
                # Regular primitive type
                field_size = TYPE_SIZES[dtype]
                self.field_types[name] = dtype
                self.field_sizes[name] = field_size

                # Ensure correct byte alignment
                if bit_position % field_size != 0:
                    padding_needed = field_size - (bit_position % field_size)
                    bit_position += padding_needed

                self.bit_shifts[name] = bit_position
                self.bit_masks[name] = ((1 << field_size) - 1) << bit_position
                bit_position += field_size

        self.total_bits = bit_position  # Store total struct size in bits

    def to_json(self, values):
        """Convert structure values to JSON with type metadata and bit masks."""
        data = {
            "endianness": self.endianness,
            "fields": [],
            "total_bits": self.total_bits,
            "total_bytes": (self.total_bits + 7) // 8
        }

        for name in self.bit_masks.keys():
            if name in self.nested_structs:
                nested_json = self.nested_structs[name].to_json(values.get(name, {}))
                data["fields"].append({
                    "name": name,
                    "type": self.nested_structs[name].struct_name,
                    "nested": json.loads(nested_json)
                })
            else:
                data["fields"].append({
                    "name": name,
                    "type": self.field_types[name],
                    "size": self.field_sizes[name],
                    "bit_offset": self.bit_shifts[name],
                    "mask": hex(self.bit_masks[name]),
                    "value": values.get(name, 0)
                })

        return json.dumps(data, indent=4)

    def encode(self, values):
        """Pack values into a binary format."""
        packed_value = 0
        for name, value in values.items():
            if name in self.nested_structs:
                nested_bytes = self.nested_structs[name].encode(value)
                nested_value = int.from_bytes(nested_bytes, byteorder=self.endianness)
                packed_value |= (nested_value << self.bit_shifts[name])
            elif name in self.bit_masks:
                packed_value |= ((value << self.bit_shifts[name]) & self.bit_masks[name])
        return packed_value.to_bytes((self.total_bits + 7) // 8, byteorder=self.endianness)

    def decode(self, binary_data):
        """Decode a binary value into fields."""
        packed_value = int.from_bytes(binary_data, byteorder=self.endianness)
        decoded = {}
        for name in self.bit_masks.keys():
            if name in self.nested_structs:
                nested_size = (self.nested_structs[name].total_bits + 7) // 8
                nested_value = (packed_value & self.bit_masks[name]) >> self.bit_shifts[name]
                nested_bytes = nested_value.to_bytes(nested_size, byteorder=self.endianness)
                decoded[name] = self.nested_structs[name].decode(nested_bytes)
            else:
                decoded[name] = (packed_value & self.bit_masks[name]) >> self.bit_shifts[name]
        return decoded


# Example usage
if __name__ == "__main__":
    # Define sub-struct
    struct_sub = """
    typedef struct {
        int sub_flag : 2;
        short sub_value : 5;
    } sub_t;
    """

    # Define main struct referencing sub-struct
    struct_main = """
    typedef struct {
        char flag : 1;
        int count : 10;
        sub_t nested;
        short error_code;
        int timestamp;
    } main_t;
    """

    # Register and parse structures
    sub_parser = BitFieldParser("sub_t", struct_sub)
    main_parser = BitFieldParser("main_t", struct_main)

    # Example data
    values = {
        "flag": 1,
        "count": 100,
        "nested": {"sub_flag": 2, "sub_value": 15},
        "error_code": 500,
        "timestamp": 1616161616
    }

    # Encode and decode
    encoded_data = main_parser.encode(values)
    print("Encoded Hex:", encoded_data.hex())
    decoded_values = main_parser.decode(encoded_data)
    print("Decoded Values:", decoded_values)

    # Convert to JSON
    json_data = main_parser.to_json(values)
    print("JSON Representation:\n", json_data)
