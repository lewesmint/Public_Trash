from pysnmp.hlapi.asyncio import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    get_cmd,
)


async def send_get(target: tuple[str, int], community: str) -> None:
    engine = SnmpEngine()
    transport = await UdpTransportTarget.create(target)

    error_indication, error_status, error_index, var_binds = await get_cmd(
        engine,
        CommunityData(community, mpModel=1),  # SNMP v2c
        transport,
        ContextData(),
        ObjectType(ObjectIdentity("1.3.6.1.2.1.1.1.0")),  # sysDescr.0
    )

    if error_indication:
        print("GET error:", error_indication)
        return

    if error_status:
        # error_index is 1-based, and points at the varbind that failed
        bad_oid = "?"
        if error_index:
            bad_oid = str(var_binds[int(error_index) - 1][0])

        # Some type checkers complain about prettyPrint(), so str() is simplest
        print(f"GET {error_status} at {bad_oid}")
        return

    for oid, val in var_binds:
        print("GET result:", oid.prettyPrint(), "=", val.prettyPrint())