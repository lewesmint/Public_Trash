import asyncio

from pysnmp.hlapi.asyncio import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    set_cmd,
)
from pysnmp.proto.rfc1902 import OctetString

TARGET = ("127.0.0.1", 161)
COMMUNITY = "private"  # often "private" for write access


async def send_set() -> None:
    engine = SnmpEngine()
    transport = await UdpTransportTarget.create(TARGET)

    error_indication, error_status, error_index, var_binds = await set_cmd(
        engine,
        CommunityData(COMMUNITY, mpModel=1),  # SNMP v2c
        transport,
        ContextData(),
        ObjectType(
            ObjectIdentity("1.3.6.1.2.1.1.4.0"),  # sysContact.0
            OctetString("New contact via pysnmp"),
        ),
    )

    if error_indication:
        print("SET error:", error_indication)
        return

    if error_status:
        bad_oid = "?"
        if error_index:
            idx = int(error_index) - 1  # 1-based
            if 0 <= idx < len(var_binds):
                bad_oid = str(var_binds[idx][0])

        print(f"SET {error_status} at {bad_oid}")
        return

    for oid, val in var_binds:
        print("SET result:", oid.prettyPrint(), "=", val.prettyPrint())


if __name__ == "__main__":
    asyncio.run(send_set())