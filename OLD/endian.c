endian.c

#include <stdio.h>
#include <arpa/inet.h>

struct BitFields {
    unsigned char msg_type     :  4;   
    unsigned char msg_source   :  4;  
    unsigned char counter;     // 8 bits   
    unsigned short length;     // 16 bits
} __attribute__((packed));

void print_struct_details(struct BitFields bf, const char* test_name) {
    union {
        struct BitFields bf;
        uint32_t value;
        unsigned char bytes[4];
    } converter;

    converter.bf = bf;
    
    printf("=== %s ===\n", test_name);
    printf("32-bit value: 0x%08X\n", converter.value);
    printf("Bytes in memory (left to right, low to high address):\n");
    for(int i = 0; i < 4; i++) {
        printf("Byte %d: 0x%02X\n", i, converter.bytes[i]);
    }
    
    // Convert to network byte order (big endian)
    uint32_t network_value = htonl(converter.value);
    printf("Network byte order (big endian): 0x%08X\n", network_value);
    printf("\n");
}

int main() {
    // Test 1: All fields set

    struct BitFields bf1;
    bf1.msg_type   = 0x03;   // ....0011 ........ ........ ........
    bf1.msg_source = 0x06;   // 0110.... ........ ........ ........
    bf1.counter    = 0x78;   // ........ 01111000 ........ ........
    bf1.length     = 0xABCD; // ........ ........ 11001101 10101011
    
    print_struct_details(bf1, "Test 1: All fields set");

    /* Expected output:
        === Test 1: All fields set ===
        32-bit value: 0xABCD7863
        Bytes in memory (left to right, low to high address):
        Byte 0: 0x63
        Byte 1: 0x78
        Byte 2: 0xCD
        Byte 3: 0xAB

        Network byte order (big endian): 0x6378CDAB
    */
    
    // Test 2: Only msg_type set to F
    struct BitFields bf2 = {0};
    bf2.msg_type = 0xF;
    
    print_struct_details(bf2, "Test 2: Only msg_type=0xF");
    /* Expected output:
    === Test 2: Only msg_type=0xF ===
        32-bit value: 0x0000000F
        Bytes in memory (left to right, low to high address):
        Byte 0: 0x0F
        Byte 1: 0x00
        Byte 2: 0x00
        Byte 3: 0x00

        Network byte order (big endian): 0x0F000000
    */
    
    return 0;
}
