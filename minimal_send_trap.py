#!/usr/bin/env python3
"""Script to send a coldStart SNMP trap with uptime and system description."""

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any, cast

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from pysnmp.hlapi.v3arch.asyncio import (
    CommunityData,
    ContextData,
    NotificationType,
    ObjectIdentity,
    SnmpEngine,
    UdpTransportTarget,
    send_notification,
)

# OID tuples (numeric)
SYSUPTIME_OID = (1, 3, 6, 1, 2, 1, 1, 3, 0)
SYSDESCR_OID = (1, 3, 6, 1, 2, 1, 1, 1, 0)
COLDSTART_TRAP = ObjectIdentity("SNMPv2-MIB", "coldStart")

# System start time (for demo, assume started 100 seconds ago in centiseconds)
UPTIME_CENTISECONDS = 100 * 100  # 100 seconds


async def send_coldstart_trap(destination: str, port: int) -> None:
    """Send a coldStart SNMP trap with uptime and system description."""
    engine = SnmpEngine()

    try:
        result = await send_notification(
            engine,
            CommunityData("public"),
            await UdpTransportTarget.create((destination, port)),
            ContextData(),
            "trap",
            NotificationType(COLDSTART_TRAP).add_var_binds(
                (SYSUPTIME_OID, UPTIME_CENTISECONDS),
                (SYSDESCR_OID, "SNMP Simulator - Cold Start"),
            ),
        )
        error_indication = cast(
            tuple[Any, int, int, list[tuple[Any, Any]]], result
        )[0]
        if error_indication:
            print(f"Trap send error: {error_indication}", file=sys.stderr)
        else:
            print(f"coldStart trap sent to {destination}:{port}")
    finally:
        engine.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Send a coldStart SNMP trap")
    parser.add_argument("destination", help="Destination IP address or hostname")
    parser.add_argument("port", type=int, help="Destination port")
    args = parser.parse_args()

    asyncio.run(send_coldstart_trap(args.destination, args.port))


if __name__ == "__main__":
    main()
