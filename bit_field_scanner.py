import re
import json
import sys
from typing import Any, Dict, Optional

# Known primitive sizes (in bits)
TYPE_SIZES: Dict[str, int] = {
    "char": 8,    # 1 byte
    "short": 16,  # 2 bytes
    "int": 32,    # 4 bytes
    "long": 64    # 8 bytes
}

# Default endianness based on system.
SYSTEM_ENDIANNESS: str = "little" if sys.byteorder == "little" else "big"

class StructParserError(Exception):
    """Custom exception class for StructParser errors."""
    pass

class StructParser:
    """
    An instance-based parser that maintains registries for:
      - Preprocessor definitions (constants)
      - Parsed struct layouts

    Usage:
      1. Create an empty parser: parser = StructParser()
      2. Update it with preprocessor definitions:
             parser.update_definitions({"MAX_BUFFER_LEN": 5, "ITEM_3_BITS": 16})
      3. Parse struct definitions (one at a time) that may reference previously defined constants
         or nested structs.
      4. If a struct definition references an undefined constant or nested struct,
         an exception is thrown.
      5. You can export a parsed struct's layout to JSON:
             json_str = parser.to_json("my_t")
      6. You can later import a JSON layout with import_from_json().
    """
    def __init__(self, endianness: str = SYSTEM_ENDIANNESS, definitions: Optional[Dict[str, Any]] = None):
        self.endianness: str = endianness
        self.preproc_defs: Dict[str, Any] = definitions.copy() if definitions else {}
        self.struct_registry: Dict[str, Dict[str, Any]] = {}  # Maps struct name to layout dictionary.
        self.field_symbols: Dict[str, Dict[int, str]] = {}  # Maps "struct_name.field_name" to symbolic values.

    def update_definitions(self, defs: Dict[str, Any]) -> None:
        """Update the parser with additional preprocessor definitions."""
        self.preproc_defs.update(defs)

    def _preprocess_definition(self, definition: str) -> str:
        """Remove comments and substitute preprocessor constants.
           Throws an exception if a referenced constant is missing.
        """
        # Remove single-line comments (// ...).
        definition = re.sub(r'//.*', '', definition)
        # Remove multi-line comments (/* ... */).
        definition = re.sub(r'/\*.*?\*/', '', definition, flags=re.DOTALL)
        # Substitute preprocessor definitions.
        for key, value in self.preproc_defs.items():
            pattern = r'\b' + re.escape(key) + r'\b'
            definition = re.sub(pattern, str(value), definition)
        # Check for unresolved tokens in array declarations.
        unresolved = re.findall(r'\[([A-Za-z_][A-Za-z0-9_]*)]', definition)
        if unresolved:
            raise StructParserError(f"Preprocessor constant(s) {unresolved} not defined.")
        return definition.strip()

    @staticmethod
    def _extract_struct_name(definition: str) -> str:
        """
        Extract the struct name from a typedef declaration.
        Expects a declaration like: typedef struct { ... } my_t;
        """
        match = re.search(r'typedef\s+struct\s*{[^}]*}\s*(\w+)\s*;', definition, re.DOTALL)
        if match:
            return match.group(1)
        raise StructParserError("Could not determine struct name.")

    def _parse_struct(self, definition: str) -> Dict[str, Any]:
        """
        Parses the preprocessed struct definition and computes its layout.
        Returns a dictionary containing:
          - struct_name, endianness, total_bits, total_bytes.
          - A list of field descriptions.
            * For bit-fields: name, type, bit_offset, bit_width, mask.
            * For primitive fields: name, type, bit_offset, size (or element_size and total_bits if array).
            * For nested struct fields: includes the nested layout.
        """
        layout: Dict[str, Any] = {}
        bit_masks: Dict[str, int] = {}      # Computed mask for each field.
        bit_shifts: Dict[str, int] = {}     # Bit offset for each field.
        field_types: Dict[str, str] = {}    # Field types as declared.
        field_sizes: Dict[str, int] = {}    # For bit-fields: width; for primitives: per-element size.
        field_array_lengths: Dict[str, Optional[int]] = {}  # None if not an array.
        nested_structs: Dict[str, Dict[str, Any]] = {}        # For nested struct fields.
        bitfield_names: set = set()         # Names of fields declared as bit-fields.
        total_bits: int = 0

        # Replace commas with semicolons for flexibility.
        definition = definition.replace(',', ';')

        # Regex for bit-fields (fields with colon), e.g.:
        #     int item_1: 4;
        bit_field_pattern = re.compile(r'(\w+)\s+(\w+)\s*:\s*(\d+)\s*;')
        # Regex for normal fields (without colon) with optional array, e.g.:
        #     char values[5];
        normal_field_pattern = re.compile(r'(\w+)\s+(\w+)(?!\s*:)\s*(\[[^]]+])?\s*;')

        # Process bit-fields.
        for dtype, name, size_str in bit_field_pattern.findall(definition):
            size = int(size_str)
            field_types[name] = dtype
            field_sizes[name] = size
            field_array_lengths[name] = None  # Bit-fields are not arrays.
            bit_masks[name] = ((1 << size) - 1) << total_bits
            bit_shifts[name] = total_bits
            total_bits += size
            bitfield_names.add(name)

        # Process normal fields.
        for dtype, name, array_part in normal_field_pattern.findall(definition):
            if name in field_types:
                continue  # Already processed as bit-field.
            # Check for nested struct.
            if dtype in self.struct_registry:
                nested_layout = self.struct_registry[dtype]
                nested_structs[name] = nested_layout
                if array_part:
                    array_length = int(array_part.strip("[]").strip())
                    field_array_lengths[name] = array_length
                    total_field_bits = nested_layout["total_bits"] * array_length
                else:
                    field_array_lengths[name] = None
                    total_field_bits = nested_layout["total_bits"]
                # Align total_bits to nested struct's total_bits.
                if total_bits % nested_layout["total_bits"] != 0:
                    padding = nested_layout["total_bits"] - (total_bits % nested_layout["total_bits"])
                    total_bits += padding
                field_types[name] = dtype
                field_sizes[name] = total_field_bits
                bit_shifts[name] = total_bits
                bit_masks[name] = ((1 << total_field_bits) - 1) << total_bits
                total_bits += total_field_bits
            else:
                # Must be a primitive type.
                if dtype not in TYPE_SIZES:
                    raise StructParserError(f"Unknown type '{dtype}' in field '{name}'.")
                base_size = TYPE_SIZES[dtype]
                if array_part:
                    array_length = int(array_part.strip("[]").strip())
                    field_array_lengths[name] = array_length
                    total_field_bits = base_size * array_length
                else:
                    field_array_lengths[name] = None
                    total_field_bits = base_size
                # Align total_bits to base_size.
                if total_bits % base_size != 0:
                    padding = base_size - (total_bits % base_size)
                    total_bits += padding
                field_types[name] = dtype
                field_sizes[name] = base_size
                bit_shifts[name] = total_bits
                bit_masks[name] = ((1 << total_field_bits) - 1) << total_bits
                total_bits += total_field_bits

        layout["struct_name"] = self._extract_struct_name(definition)
        layout["endianness"] = self.endianness
        layout["total_bits"] = total_bits
        layout["total_bytes"] = (total_bits + 7) // 8

        fields = []
        fields_by_name = {}
        for name in field_types:
            field_info: Dict[str, Any] = {
                "name": name,
                "type": field_types[name],
                "bit_offset": bit_shifts[name],
            }
            if name in nested_structs:
                field_info["nested"] = nested_structs[name]
                if field_array_lengths[name] is not None:
                    field_info["array_length"] = field_array_lengths[name]
                    field_info["total_bits"] = field_sizes[name]
                else:
                    field_info["total_bits"] = field_sizes[name]
            elif name in bitfield_names:
                field_info["bit_width"] = field_sizes[name]
                field_info["mask"] = hex(bit_masks[name])
            else:
                if field_array_lengths[name] is not None:
                    field_info["array_length"] = field_array_lengths[name]
                    field_info["element_size"] = field_sizes[name]
                    field_info["total_bits"] = field_sizes[name] * field_array_lengths[name]
                else:
                    field_info["size"] = field_sizes[name]
            # If the overall structure has 64 bits or fewer, add a mask for every field.
            if layout["total_bits"] <= 64:
                field_info["mask"] = hex(bit_masks[name])
            fields.append(field_info)
            fields_by_name[name] = field_info

        layout["fields"] = fields
        layout["fields_by_name"] = fields_by_name
        return layout

    def parse_struct(self, struct_definition: str) -> Dict[str, Any]:
        """
        Parse a C struct definition string.
        The definition may reference preprocessor constants and nested struct types that must have been
        previously defined in this parser.
        Returns a dictionary describing the layout and registers the struct in the instance registry.
        """
        processed = self._preprocess_definition(struct_definition)
        layout = self._parse_struct(processed)
        # Register by typedef name.
        struct_name = layout["struct_name"]
        self.struct_registry[struct_name] = layout
        return layout

    def to_json(self, struct_name: str) -> str:
        """
        Return a JSON string representing the layout of the struct with the given name.
        """
        if struct_name not in self.struct_registry:
            raise StructParserError(f"Struct '{struct_name}' not found in registry.")
        return json.dumps(self.struct_registry[struct_name], indent=4)

    def import_from_json(self, json_str: str) -> None:
        """
        Import a struct layout from a JSON string and register it.
        """
        layout = json.loads(json_str)
        self.struct_registry[layout["struct_name"]] = layout

    def associate_field_symbols(self, struct_name: str, field_name: str, symbols: Dict[int, str]) -> None:
        """Associate a field with symbolic values."""
        key = f"{struct_name}.{field_name}"
        self.field_symbols[key] = symbols

    def get_symbol(self, struct_name: str, field_name: str, value: int) -> str:
        """Return the symbolic name for a given field value."""
        key = f"{struct_name}.{field_name}"
        if key in self.field_symbols and value in self.field_symbols[key]:
            return self.field_symbols[key][value]
        raise StructParserError(f"No symbolic value found for field '{field_name}' in struct '{struct_name}' and value '{value}'.")

    def get_field(self, struct_name: str, field_name: str) -> Dict[str, Any]:
        """
        Retrieve field metadata from a specific struct by field name.
        """
        if struct_name not in self.struct_registry:
            raise StructParserError(f"Struct '{struct_name}' not found in registry.")
        layout = self.struct_registry[struct_name]
        if "fields_by_name" not in layout:
            raise StructParserError(f"Struct '{struct_name}' does not have 'fields_by_name' mapping.")
        if field_name not in layout["fields_by_name"]:
            raise StructParserError(f"Field '{field_name}' not found in struct '{struct_name}'.")
        return layout["fields_by_name"][field_name]

    def get_field_by_path(self, field_path: str) -> Dict[str, Any]:
        """
        Retrieve field metadata using dot notation (e.g., "my_struct.my_field").
        """
        parts = field_path.split('.')
        if len(parts) < 2:
            raise StructParserError(f"Invalid field path '{field_path}'. Must be in the format 'struct_name.field_name'.")
        struct_name = parts[0]
        field_name = parts[1]
        return self.get_field(struct_name, field_name)


# === Test Cases ===
if __name__ == "__main__":
    parser = StructParser()

    # Test 1: Simple struct with bit-fields and an array.
    my_struct = """
    typedef struct {
        int item_1: 4;
        int item_2: 4;
        int item_3: 16;
        char values[5];
    } my_t;
    """
    layout1 = parser.parse_struct(my_struct)
    print("Test 1 - Layout for my_t:")
    print(parser.to_json("my_t"))
    # Expect: bit-fields for item_1, item_2, item_3 with masks; values field with array_length 5.
    # Since total_bits is 64 or less, all fields will have a mask.

    # Test 2: Struct with undefined preprocessor constants.
    my_struct_bad = """
    typedef struct {
        int item_1: 4;
        int item_2: 4;
        int item_3: ITEM_3_BITS;
        char values[MAX_BUFFER_LEN];
    } my_t_bad;
    """
    try:
        parser.parse_struct(my_struct_bad)
    except StructParserError as e:
        print("\nTest 2 - Caught exception for undefined constants (expected):", e)

    # Now update definitions so that ITEM_3_BITS and MAX_BUFFER_LEN are defined.
    parser.update_definitions({"ITEM_3_BITS": 16, "MAX_BUFFER_LEN": 5})
    try:
        layout2 = parser.parse_struct(my_struct_bad)
        print("\nTest 2 - Layout for my_t_bad after updating definitions:")
        print(parser.to_json("my_t_bad"))
    except StructParserError as e:
        print("Test 2 - Unexpected exception:", e)

    # Test 3: Nested struct dependency.
    my_outer = """
    typedef struct {
        my_inner_t item_1;
        my_inner_t item_2;
    } my_outer_t;
    """
    try:
        parser.parse_struct(my_outer)
    except StructParserError as e:
        print("\nTest 3 - Caught exception for undefined nested struct (expected):", e)

    # Now define the nested struct.
    my_inner = """
    typedef struct {
        int x;
        int y;
    } my_inner_t;
    """
    parser.parse_struct(my_inner)
    # Parse outer struct again; should now succeed.
    layout3 = parser.parse_struct(my_outer)
    print("\nTest 3 - Layout for my_outer_t after defining my_inner_t:")
    print(parser.to_json("my_outer_t"))

    # Test 4: Nested struct array.
    my_nested_array = """
    typedef struct {
        my_inner_t a;
        my_inner_t b;
    } my_nested_t;
    """
    parser.parse_struct(my_nested_array)
    my_outer2 = """
    typedef struct {
        my_nested_t arr[3];
        int z;
    } my_outer2_t;
    """
    layout4 = parser.parse_struct(my_outer2)
    print("\nTest 4 - Layout for my_outer2_t (nested struct array):")
    print(parser.to_json("my_outer2_t"))

    # Test 5: Field symbol association and lookup.
    my_struct_with_symbols = """
    typedef struct {
        int status;
        int error_code;
    } my_symbolic_t;
    """
    parser.parse_struct(my_struct_with_symbols)
    parser.associate_field_symbols("my_symbolic_t", "status", {
        0: "OK",
        1: "WARNING",
        2: "ERROR"
    })
    try:
        symbol = parser.get_symbol("my_symbolic_t", "status", 1)
        print("\nTest 5 - Symbolic name for 'status' with value 1:", symbol)
    except StructParserError as e:
        print("Test 5 - Unexpected exception:", e)

    # Test 6: Field lookup by name.
    try:
        status_field = parser.get_field("my_symbolic_t", "status")
        print("\nTest 6 - Field 'status' in 'my_symbolic_t':", status_field)
    except StructParserError as e:
        print("Test 6 - Unexpected exception:", e)

    # Test 7: Field lookup by path.
    try:
        status_field_by_path = parser.get_field_by_path("my_symbolic_t.status")
        print("\nTest 7 - Field 'status' by path in 'my_symbolic_t':", status_field_by_path)
    except StructParserError as e:
        print("Test 7 - Unexpected exception:", e)
