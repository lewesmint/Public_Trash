# 802.1Q VLAN Header Structure

| **Field**                  | **Bits**   | **Bytes**  | **Value (Example)**      | **Description**                                                                 |
|----------------------------|------------|------------|--------------------------|---------------------------------------------------------------------------------|
| **Tag Protocol Identifier (TPID)** | 16 bits   | 2 bytes   | `0x8100`                 | Indicates the frame is VLAN-tagged.                                             |
| **Priority Code Point (PCP)**      | 3 bits    | 0.375 bytes | `0b100` (Priority 4)     | Frame priority (0 = lowest, 7 = highest).                                       |
| **Drop Eligible Indicator (DEI)**  | 1 bit     | 0.125 bytes | `0b0`                    | Marks the frame as eligible for dropping under congestion.                      |
| **VLAN Identifier (VID)**          | 12 bits   | 1.5 bytes  | `0b000011100010` (114)   | VLAN ID (1–4094, where 0 and 4095 are reserved).                                |

---

# Ethernet Frame With VLAN Header

| **Field**                  | **Size (Bytes)** | **Description**                                                                 |
|----------------------------|------------------|---------------------------------------------------------------------------------|
| **Destination MAC Address**| 6 bytes          | MAC address of the destination device.                                         |
| **Source MAC Address**     | 6 bytes          | MAC address of the source device.                                              |
| **TPID (Tag Protocol Identifier)**| 2 bytes  | Always `0x8100` to indicate a VLAN tag is present.                             |
| **TCI (Tag Control Information)** | 2 bytes  | Contains PCP, DEI, and VLAN ID.                                                |
| **Payload**                | Variable (46–1500 bytes)| Actual data being transmitted.                                                 |
| **Frame Check Sequence (FCS)**| 4 bytes      | CRC value for error checking.                                                  |


# Standard Ethernet Frame Structure (IEEE 802.3)

| **Field**                  | **Bits**   | **Bytes**  | **Description**                                                                 |
|----------------------------|------------|------------|---------------------------------------------------------------------------------|
| **Preamble**               | 56 bits    | 7 bytes    | Synchronisation pattern for the receiver.                                       |
| **Start of Frame Delimiter (SFD)** | 8 bits | 1 byte     | Marks the start of the frame.                                                   |
| **Destination MAC Address**| 48 bits    | 6 bytes    | MAC address of the destination device.                                          |
| **Source MAC Address**     | 48 bits    | 6 bytes    | MAC address of the source device.                                               |
| **EtherType/Length**       | 16 bits    | 2 bytes    | Either the payload length or protocol type (e.g., IPv4, IPv6).                  |
| **Payload**                | Variable   | 46–1500 bytes | Data being transmitted.                                                         |
| **Frame Check Sequence (FCS)** | 32 bits | 4 bytes    | CRC for error checking.                                                         |

---

# Ethernet Frame Overview

| **Field**                  | **Size (Bytes)** | **Description**                                                                 |
|----------------------------|------------------|---------------------------------------------------------------------------------|
| **Preamble**               | 7 bytes          | Synchronisation for the receiver.                                               |
| **SFD**                    | 1 byte           | Marks the start of the frame.                                                   |
| **Destination MAC Address**| 6 bytes          | MAC address of the destination device.                                          |
| **Source MAC Address**     | 6 bytes          | MAC address of the source device.                                               |
| **EtherType/Length**       | 2 bytes          | Protocol identifier (e.g., IPv4, ARP, etc.).                                    |
| **Payload (MTU)**          | 46–1500 bytes    | The actual data being transmitted.                                              |
| **FCS**                    | 4 bytes          | Cyclic redundancy check (CRC) for detecting errors.                             |

---

# Total Frame Size

| **Frame Component**        | **Size (Bytes)**   | **Description**                                                                 |
|----------------------------|--------------------|---------------------------------------------------------------------------------|
| **Minimum Frame Size**     | 64 bytes           | Includes header, minimum payload (46 bytes), and FCS.                          |
| **Maximum Frame Size**     | 1518 bytes         | Includes header, maximum payload (1500 bytes), and FCS.                        |
