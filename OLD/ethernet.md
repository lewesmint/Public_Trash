# VLAN-Tagged Ethernet Frame Structure (802.1Q)

| **Start Bit** | **Field Name**            | **Abbreviation** | **Bytes** | **Bits** | **Example Value**  | **Description**                                                                 |
|---------------|---------------------------|------------------|-----------|----------|---------------------|---------------------------------------------------------------------------------|
| 0             | Destination MAC Address  | Dest MAC         | 6         | 48       | `FF:FF:FF:FF:FF:FF` | MAC address of the destination device.                                         |
| 48            | Source MAC Address       | Src MAC          | 6         | 48       | `00:11:22:33:44:55` | MAC address of the source device.                                              |
| 96            | Tag Protocol Identifier  | TPID             | 2         | 16       | `0x8100`            | Indicates the frame is VLAN-tagged.                                            |
| 112           | Tag Control Information  | TCI              | 2         | 16       | `0x0064` (VLAN 100) | Contains priority (PCP), DEI, and VLAN ID.                                     |
| 128           | EtherType/Length         | EtherType        | 2         | 16       | `0x0800`            | Specifies the protocol type (e.g., IPv4 = 0x0800, ARP = 0x0806).               |
| 144           | Payload/Data             | Data             | 46–1500   | 368–12000| `...`               | The actual data being transmitted.                                             |
| Variable      | Frame Check Sequence     | FCS              | 4         | 32       | `0x12345678`        | CRC for error checking to ensure frame integrity.                              |

---

# Preamble and SFD

| **Field Name**                | **Bytes** | **Bits** | **Example Value** | **Description**                                                                 |
|--------------------------------|-----------|----------|--------------------|---------------------------------------------------------------------------------|
| Preamble                      | 7         | 56       | `10101010` (repeated)| Synchronisation pattern for receiver alignment.                                 |
| Start Frame Delimiter (SFD)    | 1         | 8        | `10101011`         | Marks the start of the Ethernet frame.                                         |


# Standard Ethernet Frame Structure

| **Start Bit** | **Field Name**            | **Abbreviation** | **Bytes** | **Bits** | **Example Value**  | **Description**                                                                 |
|---------------|---------------------------|------------------|-----------|----------|---------------------|---------------------------------------------------------------------------------|
| 0             | Destination MAC Address  | Dest MAC         | 6         | 48       | `FF:FF:FF:FF:FF:FF` | MAC address of the destination device.                                         |
| 48            | Source MAC Address       | Src MAC          | 6         | 48       | `00:11:22:33:44:55` | MAC address of the source device.                                              |
| 96            | EtherType/Length         | EtherType        | 2         | 16       | `0x0800`            | Specifies the protocol type (e.g., IPv4 = 0x0800, ARP = 0x0806).               |
| 112           | Payload/Data             | Data             | 46–1500   | 368–12000| `...`               | The actual data being transmitted.                                             |
| Variable      | Frame Check Sequence     | FCS              | 4         | 32       | `0x12345678`        | CRC for error checking to ensure frame integrity.                              |

---

# Preamble and SFD

| **Field Name**                | **Bytes** | **Bits** | **Example Value** | **Description**                                                                 |
|--------------------------------|-----------|----------|--------------------|---------------------------------------------------------------------------------|
| Preamble                      | 7         | 56       | `10101010` (repeated)| Synchronisation pattern for receiver alignment.                                 |
| Start Frame Delimiter (SFD)    | 1         | 8        | `10101011`         | Marks the start of the Ethernet frame.                                         |
