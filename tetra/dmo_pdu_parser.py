#!/usr/bin/env python3
"""TETRA DMO MAC PDU parser — krok 3.

Parses the type-1 bits produced by dmo_l1_chain.py into structured fields:
  SCH/S (60 bits, BLK1 path): DMAC-SYNC or DPRES-SYNC short header
  SCH/H (124 bits, BLK2 path): the same PDU's long header + message-type-specific SDU

Reference: ETSI EN 300 396-3 §9.5.1 and §9.5.3, plus osmo-tetra-dmo
rx_dm_{dmacsync,dpressync}_sch_{s,h} in tetra_upper_mac.c.

Two SYNC PDU subtypes share bits[0:6]:
  system_code (4 bits)  — DMO = 0xD
  sync_pdu_type (2 bits) — 0 = DMAC-SYNC, 1 = DPRES-SYNC
"""

# DMO message types (5-bit message_type field in DMAC-SYNC SCH/H)
DM_MESSAGE_TYPES = {
    0: "DM-RESERVED", 1: "DM-SDS OCCUPIED", 2: "DM-TIMING REQUEST", 3: "DM-TIMING ACK",
    8: "DM-SETUP", 9: "DM-SETUP PRES", 10: "DM-CONNECT", 11: "DM-DISCONNECT",
    12: "DM-CONNECT ACK", 13: "DM-OCCUPIED", 14: "DM-RELEASE", 15: "DM-TX CEASED",
    16: "DM-TX REQUEST", 17: "DM-TX ACCEPT", 18: "DM-PREEMPT", 19: "DM-PRE ACCEPT",
    20: "DM-REJECT", 21: "DM-INFO", 22: "DM-SDS UDATA", 23: "DM-SDS DATA",
    24: "DM-SDS ACK", 25: "GATEWAY SPECIFIC MSG",
}

COMMUNICATION_TYPES = {0: "MS-MS", 1: "via repeater", 2: "via gateway", 3: "via rep+gw"}
ADDRESS_TYPES = {0: "SSI", 1: "Event label", 2: "Usage marker", 3: "SMI+event label"}
ENCRYPTION_STATES = {0: "clear", 1: "TEA", 2: "SCK", 3: "static"}
AB_CHANNEL_USAGE = {0: "reserved", 1: "free", 2: "occupied", 3: "reserved"}
CHANNEL_USAGE = {0: "unallocated", 1: "free", 2: "occupied", 3: "reserved"}
CHANNEL_STATES = {0: "free", 1: "reserved", 2: "occupied (no rep)", 3: "occupied (rep)"}


def _bits_to_uint(bits, off, n):
    """Read n-bit unsigned big-endian integer from bit array starting at off."""
    v = 0
    for i in range(n):
        v = (v << 1) | int(bits[off + i])
    return v


def parse_sch_s(bits):
    """Parse 60-bit SCH/S (short header). Returns dict with sync_pdu_type and either
    DMAC-SYNC or DPRES-SYNC short fields. Always check `sync_pdu_type` to know which."""
    out = {
        "system_code": _bits_to_uint(bits, 0, 4),
        "sync_pdu_type": _bits_to_uint(bits, 4, 2),
        "communication_type": _bits_to_uint(bits, 6, 2),
    }
    if out["sync_pdu_type"] == 0:
        # DMAC-SYNC SCH/S
        ct = out["communication_type"]
        if ct in (1, 3):
            out["masterslave_link_flag"] = _bits_to_uint(bits, 8, 1)
        if ct in (2, 3):
            out["gateway_message_flag"] = _bits_to_uint(bits, 9, 1)
        out["ab_channel_usage"] = _bits_to_uint(bits, 10, 2)
        out["slot_number"] = _bits_to_uint(bits, 12, 2) + 1
        out["frame_number"] = _bits_to_uint(bits, 14, 5)
        out["airint_encryption_state"] = _bits_to_uint(bits, 19, 2)
        if out["airint_encryption_state"] > 0:
            out["time_variant_parameter"] = _bits_to_uint(bits, 21, 29)
            out["ksg_number"] = _bits_to_uint(bits, 51, 4)
            out["encryption_key_number"] = _bits_to_uint(bits, 55, 5)
    else:
        # DPRES-SYNC SCH/S
        out["m_dmo_flag"] = _bits_to_uint(bits, 8, 1)
        out["twofreq_repeater_flag"] = _bits_to_uint(bits, 11, 1)
        out["repeater_operating_modes"] = _bits_to_uint(bits, 12, 2)
        out["spacing_of_uplink"] = _bits_to_uint(bits, 14, 6)
        out["masterslave_link_flag"] = _bits_to_uint(bits, 20, 1)
        out["channel_usage"] = _bits_to_uint(bits, 21, 2)
        out["channel_state"] = _bits_to_uint(bits, 23, 2)
        out["slot_number"] = _bits_to_uint(bits, 25, 2) + 1
        out["frame_number"] = _bits_to_uint(bits, 27, 5)
        out["power_class"] = _bits_to_uint(bits, 32, 3)
        out["power_control_flag"] = _bits_to_uint(bits, 36, 1)
        out["frame_countdown"] = _bits_to_uint(bits, 37, 2)
        out["priority_level"] = _bits_to_uint(bits, 39, 2)
        out["dn232_dn233"] = _bits_to_uint(bits, 47, 4)
        out["dt254"] = _bits_to_uint(bits, 51, 3)
        out["dualwatch_sync_flag"] = _bits_to_uint(bits, 54, 1)
    return out


def parse_sch_h(bits, sch_s):
    """Parse 124-bit SCH/H given the already-parsed SCH/S (so we know which subtype
    and which optional fields are present). Returns dict of additional fields,
    merged into the SCH/S record by the caller."""
    out = {}
    if sch_s["sync_pdu_type"] == 0:
        # DMAC-SYNC SCH/H
        p = 0
        if sch_s["communication_type"] > 0:
            out["repgw_address"] = _bits_to_uint(bits, p, 10)
        else:
            out["repgw_address"] = 0
        p = 10
        out["fillbit_indication"] = _bits_to_uint(bits, p, 1); p += 1
        out["fragmentation_flag"] = _bits_to_uint(bits, p, 1); p += 1
        if out["fragmentation_flag"]:
            out["number_of_sch_f_slots"] = _bits_to_uint(bits, p, 4); p += 4
        out["frame_countdown"] = _bits_to_uint(bits, p, 2); p += 2
        out["dest_address_type"] = _bits_to_uint(bits, p, 2); p += 2
        if out["dest_address_type"] != 2:
            out["dest_address"] = _bits_to_uint(bits, p, 24); p += 24
        out["src_address_type"] = _bits_to_uint(bits, p, 2); p += 2
        if out["src_address_type"] != 2:
            out["src_address"] = _bits_to_uint(bits, p, 24); p += 24
        if sch_s["communication_type"] < 2:
            mni = _bits_to_uint(bits, p, 24); p += 24
            out["mni"] = mni
            out["mcc"] = (mni >> 14) & 0x3FF
            out["mnc"] = mni & 0x3FFF
        out["message_type"] = _bits_to_uint(bits, p, 5); p += 5
        out["message_type_name"] = DM_MESSAGE_TYPES.get(out["message_type"], f"unknown({out['message_type']})")
        # Per-message-type SDU layout (lengths per osmo-tetra-dmo):
        layout = {
            8: (21, 5), 9: (21, 5), 10: (8, 4), 11: (0, 4), 12: (21, 5),
            13: (21, 5), 14: (0, 9), 15: (32, 4),
        }
        if out["message_type"] in layout:
            mf_len, sdu_len = layout[out["message_type"]]
            if mf_len:
                out["message_fields_bits"] = [int(b) for b in bits[p:p + mf_len]]
            out["dm_sdu_bits"] = [int(b) for b in bits[p + mf_len:p + mf_len + sdu_len]]
            out["sdu_offset"] = p + mf_len
        out["_consumed_bits"] = p
    else:
        # DPRES-SYNC SCH/H
        out["repgw_address"] = _bits_to_uint(bits, 0, 10)
        out["mni"] = _bits_to_uint(bits, 10, 24)
        out["mcc"] = (out["mni"] >> 14) & 0x3FF
        out["mnc"] = out["mni"] & 0x3FFF
        out["validity_time_unit"] = _bits_to_uint(bits, 34, 2)
        out["number_of_validity_time_units"] = _bits_to_uint(bits, 36, 6)
        out["max_dmms_power_class"] = _bits_to_uint(bits, 42, 3)
        out["usage_restriction_type"] = _bits_to_uint(bits, 46, 4)
        if out["usage_restriction_type"] >= 8:
            out["sckn"] = _bits_to_uint(bits, 50, 5)
            out["edsi_urtc_initialization_value"] = _bits_to_uint(bits, 55, 19)
    return out


def parse_sync_pdu(sch_s_bits, sch_h_bits=None):
    """Parse a full SYNC PDU. sch_h_bits optional — if absent, only SCH/S returned."""
    rec = parse_sch_s(sch_s_bits)
    if sch_h_bits is not None:
        rec.update(parse_sch_h(sch_h_bits, rec))
    rec["sync_pdu_type_name"] = "DMAC-SYNC" if rec["sync_pdu_type"] == 0 else "DPRES-SYNC"
    rec["communication_type_name"] = COMMUNICATION_TYPES.get(rec["communication_type"], "?")
    return rec


def format_sync_pdu(rec):
    """Human-readable single-line description of a parsed SYNC PDU."""
    head = f"[{rec['sync_pdu_type_name']}] sys=0x{rec['system_code']:x} comm={rec['communication_type_name']}"
    if rec["sync_pdu_type"] == 0:
        tn = rec.get("slot_number", "?")
        fn = rec.get("frame_number", "?")
        enc = ENCRYPTION_STATES.get(rec.get("airint_encryption_state", 0), "?")
        body = f"TN={tn} FN={fn} enc={enc}"
        if "message_type_name" in rec:
            body += f" msg={rec['message_type_name']}"
        if "src_address" in rec:
            body += f" src={rec['src_address']}"
        if "dest_address" in rec:
            body += f" dst={rec['dest_address']}"
        if "mcc" in rec:
            body += f" MNI={rec['mcc']}-{rec['mnc']}"
    else:
        tn = rec.get("slot_number", "?")
        fn = rec.get("frame_number", "?")
        cs = CHANNEL_STATES.get(rec.get("channel_state", 0), "?")
        body = f"TN={tn} FN={fn} ch_state={cs}"
        if "mcc" in rec:
            body += f" MNI={rec['mcc']}-{rec['mnc']}"
    return f"{head}  {body}"


# ---------- Self-test ----------
def _selftest():
    """Build a synthetic DMAC-SYNC PDU, parse it, verify fields."""
    sch_s = [0] * 60
    # system_code = 0xD = 1101
    sch_s[0:4] = [1, 1, 0, 1]
    # sync_pdu_type = 0 (DMAC-SYNC)
    sch_s[4:6] = [0, 0]
    # communication_type = 0 (MS-MS)
    sch_s[6:8] = [0, 0]
    # ab_channel_usage = 2 (occupied) → bits 10:12
    sch_s[10:12] = [1, 0]
    # slot_number raw = 0 → +1 = 1, bits 12:14
    sch_s[12:14] = [0, 0]
    # frame_number = 5 → bits 14:19 = 00101
    sch_s[14:19] = [0, 0, 1, 0, 1]
    # encryption_state = 0
    sch_s[19:21] = [0, 0]

    rec = parse_sch_s(sch_s)
    assert rec["system_code"] == 0xD, rec
    assert rec["sync_pdu_type"] == 0
    assert rec["communication_type"] == 0
    assert rec["ab_channel_usage"] == 2
    assert rec["slot_number"] == 1
    assert rec["frame_number"] == 5
    assert rec["airint_encryption_state"] == 0
    print("DMAC-SYNC SCH/S parse: OK")

    # Build a minimal SCH/H for DM-SETUP (msg_type=8, MS-MS so no repgw)
    sch_h = [0] * 124
    # bits 0..10: repgw_address (= 0 because comm_type=0, but spec puts it always; osmo sets 0)
    # bits 10: fillbit_indication = 0
    # bits 11: fragmentation_flag = 0
    # bits 12..14: frame_countdown = 2 → 10
    sch_h[12:14] = [1, 0]
    # bits 14..16: dest_address_type = 0 (SSI)
    sch_h[14:16] = [0, 0]
    # bits 16..40: dest_address = 1234567 (24-bit big-endian)
    dst = 1234567
    for i in range(24):
        sch_h[16 + i] = (dst >> (23 - i)) & 1
    # bits 40..42: src_address_type = 0 (SSI)
    sch_h[40:42] = [0, 0]
    # bits 42..66: src_address = 7654321
    src = 7654321
    for i in range(24):
        sch_h[42 + i] = (src >> (23 - i)) & 1
    # bits 66..90: MNI = (260 << 14) | 9999 = 4259223
    mni = (260 << 14) | 9999
    for i in range(24):
        sch_h[66 + i] = (mni >> (23 - i)) & 1
    # bits 90..95: message_type = 8 (DM-SETUP) → 01000
    sch_h[90:95] = [0, 1, 0, 0, 0]
    rec2 = parse_sync_pdu(sch_s, sch_h)
    assert rec2["frame_countdown"] == 2
    assert rec2["dest_address"] == 1234567, rec2["dest_address"]
    assert rec2["src_address"] == 7654321, rec2["src_address"]
    assert rec2["mcc"] == 260
    assert rec2["mnc"] == 9999
    assert rec2["message_type_name"] == "DM-SETUP"
    print("DMAC-SYNC SCH/H parse: OK")
    print("  →", format_sync_pdu(rec2))


if __name__ == "__main__":
    _selftest()
