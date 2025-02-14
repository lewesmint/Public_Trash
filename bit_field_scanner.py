import re
import json
import struct
import sys
from typing import Any, Dict, Optional

# Define known primitive sizes (in bits)
TYPE_SIZES = {
    "char": 8,    # 1 byte = 8 bits
    "short": 16,  # 2 bytes = 16 bits
    "int": 32,    # 4 bytes = 32 bits
    "long": 64    # 8 bytes = 64 bits
}

# Detect system endianness
SYSTEM_ENDIANNESS = "little" if sys.byteorder == "little" else "big"


class PreprocessorRegistry:
    """Global registry for preprocessor definitions (constants)."""
    _definitions: Dict[str, Any] = {}

    @classmethod
    def update(cls, defs: Dict[str, Any]) -> None:
        cls._definitions.update(defs)

    @classmethod
    def get_definitions(cls) -> Dict[str, Any]:
        return cls._definitions.copy()


class BitFieldRegistry:
    """A registry for storing parsed struct definitions."""
    _registry: Dict[str, "BitFieldParser"] = {}

    @classmethod
    def register(cls, name: str, parser: "BitFieldParser") -> None:
        cls._registry[name] = parser

    @classmethod
    def get(cls, name: str) -> Optional["BitFieldParser"]:
        return cls._registry.get(name, None)

    @classmethod
    def exists(cls, name: str) -> bool:
        return name in cls._registry


class BitFieldParser:
    """
    Parses a C struct definition (with bit-fields, arrays, nested structs, and comments)
    and provides methods for encoding/decoding values and JSON serialization.
    """
    def __init__(self, struct_definition: str, definitions: Optional[Dict[str, Any]] = None,
                 endianness: str = SYSTEM_ENDIANNESS):
        # Update global definitions if provided.
        if definitions:
            PreprocessorRegistry.update(definitions)
        self.definitions = PreprocessorRegistry.get_definitions()

        # Preprocess: remove comments and substitute definitions
        self.struct_definition = self._preprocess_definition(struct_definition)
        self.endianness = endianness
        self.struct_name = self._extract_struct_name()
        self.bit_masks: Dict[str, int] = {}
        self.bit_shifts: Dict[str, int] = {}
        self.field_types: Dict[str, str] = {}
        self.field_sizes: Dict[str, int] = {}  # in bits per element (or total for bit-fields)
        self.field_array_lengths: Dict[str, Optional[int]] = {}  # None if not an array
        self.nested_structs: Dict[str, "BitFieldParser"] = {}  # name -> parser for nested struct
        self.total_bits: int = 0

        # Keep track of which fields are bitfields.
        self.bitfield_names = set()

        self._parse_struct()
        BitFieldRegistry.register(self.struct_name, self)

    def _preprocess_definition(self, definition: str) -> str:
        """Remove C comments and substitute preprocessor definitions."""
        # Remove single-line comments (// ...)
        definition = re.sub(r'//.*', '', definition)
        # Remove multi-line comments (/* ... */)
        definition = re.sub(r'/\*.*?\*/', '', definition, flags=re.DOTALL)
        # Substitute preprocessor definitions from the global registry.
        for key, value in self.definitions.items():
            pattern = r'\b' + re.escape(key) + r'\b'
            definition = re.sub(pattern, str(value), definition)
        return definition.strip()

    def _extract_struct_name(self) -> str:
        """Extract the struct name from a typedef definition."""
        match = re.search(
            r'typedef\s+struct\s*{[^}]*}\s*(\w+)\s*;',
            self.struct_definition,
            re.DOTALL
        )
        if match:
            return match.group(1)
        raise ValueError("Could not determine struct name from typedef.")

    def _parse_struct(self) -> None:
        """
        Parse the struct definition to build:
          - bit_masks and bit_shifts for each field,
          - field types and sizes (including handling arrays),
          - nested struct references.
        """
        bit_position = 0

        # Regex for bit-fields: e.g. "int count : 10;"
        bit_field_pattern = re.compile(r'(\w+)\s+(\w+)\s*:\s*(\d+)\s*;')
        # Regex for normal fields (non-bit-fields, optionally with arrays),
        # using negative lookahead to skip fields with a colon.
        normal_field_pattern = re.compile(
            r'(\w+)\s+(\w+)(?!\s*:)\s*(\[[^\]]+\])?\s*;'
        )

        # Process bit-fields.
        for dtype, name, size_str in bit_field_pattern.findall(self.struct_definition):
            size = int(size_str)
            self.field_types[name] = dtype
            self.field_sizes[name] = size  # For bit-fields, total size equals the bit-width.
            self.field_array_lengths[name] = None  # Not an array.
            self.bit_masks[name] = ((1 << size) - 1) << bit_position
            self.bit_shifts[name] = bit_position
            bit_position += size
            self.bitfield_names.add(name)  # Mark this as a bit-field.

        # Process normal fields (which may include arrays or nested structs).
        for match in normal_field_pattern.findall(self.struct_definition):
            dtype, name, array_part = match
            # Skip if this field was already processed as a bit-field.
            if name in self.field_types:
                continue

            # Check if this field is a nested struct (dtype exists in registry)
            if BitFieldRegistry.exists(dtype):
                nested_parser = BitFieldRegistry.get(dtype)
                self.nested_structs[name] = nested_parser
                # Check if it's declared as an array.
                if array_part:
                    array_length = int(array_part.strip("[]").strip())
                    self.field_array_lengths[name] = array_length
                    total_field_bits = nested_parser.total_bits * array_length
                else:
                    self.field_array_lengths[name] = None
                    total_field_bits = nested_parser.total_bits

                # Align bit_position to the nested struct's total bit width if needed.
                if bit_position % nested_parser.total_bits != 0:
                    padding = nested_parser.total_bits - (bit_position % nested_parser.total_bits)
                    bit_position += padding

                self.field_types[name] = dtype  # Store nested struct type name.
                self.field_sizes[name] = total_field_bits
                self.bit_shifts[name] = bit_position
                self.bit_masks[name] = ((1 << total_field_bits) - 1) << bit_position
                bit_position += total_field_bits
            else:
                # Primitive field.
                base_size = TYPE_SIZES.get(dtype)
                if base_size is None:
                    raise ValueError(f"Unknown type: {dtype}")

                # Check if this is an array field.
                if array_part:
                    array_length = int(array_part.strip("[]").strip())
                    self.field_array_lengths[name] = array_length
                    total_field_bits = base_size * array_length
                else:
                    self.field_array_lengths[name] = None
                    total_field_bits = base_size

                # Align to the primitive type's size.
                if bit_position % base_size != 0:
                    padding = base_size - (bit_position % base_size)
                    bit_position += padding

                self.field_types[name] = dtype
                self.field_sizes[name] = base_size  # size per element
                self.bit_shifts[name] = bit_position
                self.bit_masks[name] = ((1 << total_field_bits) - 1) << bit_position
                bit_position += total_field_bits

        self.total_bits = bit_position

    def to_json(self, values: Dict[str, Any]) -> str:
        """Return a JSON representation of the struct (with field metadata and values)."""
        fields = []
        for name in self.bit_masks.keys():
            if name in self.nested_structs:
                # Handle nested structs.
                if self.field_array_lengths.get(name) is not None:
                    nested_values = values.get(name, [])
                    nested_json_list = [
                        json.loads(self.nested_structs[name].to_json(elem))
                        for elem in nested_values
                    ]
                    field_info = {
                        "name": name,
                        "type": self.nested_structs[name].struct_name,
                        "array_length": self.field_array_lengths.get(name),
                        "nested": nested_json_list
                    }
                else:
                    nested_values = values.get(name, {})
                    nested_json = json.loads(self.nested_structs[name].to_json(nested_values))
                    field_info = {
                        "name": name,
                        "type": self.nested_structs[name].struct_name,
                        "array_length": None,
                        "nested": nested_json
                    }
            else:
                field_info = {
                    "name": name,
                    "type": self.field_types[name],
                    "size_per_element": (self.field_sizes[name]
                                         if self.field_array_lengths.get(name) is None
                                         else TYPE_SIZES[self.field_types[name]]),
                    "array_length": self.field_array_lengths.get(name),
                    "bit_offset": self.bit_shifts[name]
                }
                # Only include the mask if this field is a bitfield.
                if name in self.bitfield_names:
                    field_info["mask"] = hex(self.bit_masks[name])
                field_info["value"] = values.get(name, 0)
            fields.append(field_info)

        data = {
            "struct_name": self.struct_name,
            "endianness": self.endianness,
            "total_bits": self.total_bits,
            "total_bytes": (self.total_bits + 7) // 8,
            "fields": fields
        }
        return json.dumps(data, indent=4)

    def encode(self, values: Dict[str, Any]) -> bytes:
        """
        Pack the provided values (including arrays and nested structs) into a binary
        representation according to the calculated bit layout.
        """
        packed_value = 0
        for name in self.bit_masks.keys():
            shift = self.bit_shifts[name]
            if name in self.nested_structs:
                nested_parser = self.nested_structs[name]
                if self.field_array_lengths.get(name) is not None:
                    arr = values.get(name, [])
                    for i, elem in enumerate(arr):
                        nested_bytes = nested_parser.encode(elem)
                        nested_int = int.from_bytes(nested_bytes, byteorder=self.endianness)
                        packed_value |= nested_int << (shift + i * nested_parser.total_bits)
                else:
                    nested_bytes = nested_parser.encode(values.get(name, {}))
                    nested_int = int.from_bytes(nested_bytes, byteorder=self.endianness)
                    packed_value |= nested_int << shift
            else:
                dtype = self.field_types[name]
                base_bits = TYPE_SIZES[dtype]
                if self.field_array_lengths.get(name) is not None:
                    arr = values.get(name, [])
                    for i, elem in enumerate(arr):
                        elem_val = int(elem) & ((1 << base_bits) - 1)
                        packed_value |= elem_val << (shift + i * base_bits)
                else:
                    elem_val = int(values.get(name, 0)) & ((1 << base_bits) - 1)
                    packed_value |= elem_val << shift
        byte_length = (self.total_bits + 7) // 8
        return packed_value.to_bytes(byte_length, byteorder=self.endianness)

    def decode(self, binary_data: bytes) -> Dict[str, Any]:
        """
        Unpack a binary value into a dictionary of field values.
        Array fields return lists; nested structs return dictionaries.
        """
        packed_value = int.from_bytes(binary_data, byteorder=self.endianness)
        result: Dict[str, Any] = {}
        for name in self.bit_masks.keys():
            shift = self.bit_shifts[name]
            mask = self.bit_masks[name]
            field_int = (packed_value & mask) >> shift

            if name in self.nested_structs:
                nested_parser = self.nested_structs[name]
                if self.field_array_lengths.get(name) is not None:
                    arr = []
                    total = self.field_array_lengths[name]
                    for i in range(total):
                        elem_int = (field_int >> (i * nested_parser.total_bits)) & ((1 << nested_parser.total_bits) - 1)
                        elem_bytes = elem_int.to_bytes((nested_parser.total_bits + 7) // 8, byteorder=self.endianness)
                        arr.append(nested_parser.decode(elem_bytes))
                    result[name] = arr
                else:
                    elem_bytes = field_int.to_bytes((nested_parser.total_bits + 7) // 8, byteorder=self.endianness)
                    result[name] = nested_parser.decode(elem_bytes)
            else:
                dtype = self.field_types[name]
                base_bits = TYPE_SIZES[dtype]
                if self.field_array_lengths.get(name) is not None:
                    arr = []
                    total = self.field_array_lengths[name]
                    for i in range(total):
                        elem_val = (field_int >> (i * base_bits)) & ((1 << base_bits) - 1)
                        arr.append(elem_val)
                    result[name] = arr
                else:
                    result[name] = field_int
        return result


# === Example usage ===
if __name__ == "__main__":
    # Preprocessor definitions (could be used for array sizes or bit-field widths)
    definitions = {
        "NUM_ITEMS": 3,
        "MAX_BUFFER": 256,
        "FLAG_WIDTH": 2
    }

    # Define a sub-struct (nested struct)
    sub_struct = """
    typedef struct {
        int sub_flag : FLAG_WIDTH;  // use preprocessor constant for bit-width
        short sub_value : 5;
    } sub_t;
    """

    # Define a main struct that uses:
    # - Primitive bit-fields and a normal field,
    # - An array field (using a preprocessor definition for size),
    # - A nested struct and an array of nested structs,
    # - And a char buffer declared using a constant.
    main_struct = """
    typedef struct {
        char flag : 1;
        int count : 10;
        int arr[NUM_ITEMS]; // array of ints
        sub_t nested;       // a nested struct
        sub_t nest_arr[NUM_ITEMS]; // array of nested structs
        char buffer[MAX_BUFFER];   // array of chars
        short error_code;
        int timestamp;
    } main_t;
    """

    # Parse the sub-struct first.
    sub_parser = BitFieldParser(sub_struct, definitions=definitions)
    # Then parse the main struct.
    main_parser = BitFieldParser(main_struct, definitions=definitions)

    # Example data for main_t
    values = {
        "flag": 1,
        "count": 100,
        "arr": [10, 20, 30],
        "nested": {"sub_flag": 3, "sub_value": 15},
        "nest_arr": [
            {"sub_flag": 1, "sub_value": 5},
            {"sub_flag": 2, "sub_value": 10},
            {"sub_flag": 3, "sub_value": 15}
        ],
        "buffer": [ord(c) for c in "Hello, world!"[:definitions["MAX_BUFFER"]]],  # example buffer data
        "error_code": 500,
        "timestamp": 1616161616
    }

    encoded = main_parser.encode(values)
    print("Encoded Hex:", encoded.hex())

    decoded = main_parser.decode(encoded)
    print("Decoded Values:", decoded)

    json_repr = main_parser.to_json(values)
    print("JSON Representation:\n", json_repr)
