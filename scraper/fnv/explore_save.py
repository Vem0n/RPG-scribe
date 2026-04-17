"""
Exploration script for Fallout: New Vegas .fos save file format.
Parses header, plugin list, file location table, and change form records
to extract quest stage data.
"""
import struct


def read_uint8(data: bytes, offset: int) -> tuple[int, int]:
    return struct.unpack_from("<B", data, offset)[0], offset + 1


def read_uint16(data: bytes, offset: int) -> tuple[int, int]:
    return struct.unpack_from("<H", data, offset)[0], offset + 2


def read_uint32(data: bytes, offset: int) -> tuple[int, int]:
    return struct.unpack_from("<I", data, offset)[0], offset + 4


def expect_pipe(data: bytes, offset: int) -> int:
    b = data[offset]
    assert b == 0x7C, f"Expected pipe (0x7C) at 0x{offset:X}, got 0x{b:02X}"
    return offset + 1


def dump_raw(data: bytes, offset: int, length: int = 64, label: str = ""):
    if label:
        print(f"\n--- {label} (0x{offset:X}) ---")
    end = min(offset + length, len(data))
    for i in range(offset, end, 16):
        chunk = data[i : min(i + 16, end)]
        hex_part = " ".join(f"{b:02X}" for b in chunk)
        ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        print(f"  0x{i:08X}: {hex_part:<48s}  {ascii_part}")


# =====================================================================
# Header
# =====================================================================
def parse_header(data: bytes):
    magic = data[0:11].decode("ascii")
    assert magic == "FO3SAVEGAME", f"Bad magic: {magic}"
    offset = 11
    header_size, offset = read_uint32(data, offset)
    header_start = offset
    header_end = offset + header_size

    version, offset = read_uint32(data, offset)
    offset = expect_pipe(data, offset)

    language = data[offset : offset + 64].split(b"\x00")[0].decode("ascii", errors="replace")
    offset += 64
    offset = expect_pipe(data, offset)

    screenshot_width, offset = read_uint32(data, offset)
    offset = expect_pipe(data, offset)
    screenshot_height, offset = read_uint32(data, offset)
    offset = expect_pipe(data, offset)
    save_number, offset = read_uint32(data, offset)
    offset = expect_pipe(data, offset)

    # pipe-delimited strings: uint16 len | pipe | chars
    def read_pipe_string():
        nonlocal offset
        slen, offset = read_uint16(data, offset)
        offset = expect_pipe(data, offset)
        s = data[offset : offset + slen].decode("utf-8", errors="replace")
        offset += slen
        return s

    player_name = read_pipe_string()
    offset = expect_pipe(data, offset)
    karma_title = read_pipe_string()
    offset = expect_pipe(data, offset)

    player_level, offset = read_uint32(data, offset)
    offset = expect_pipe(data, offset)

    player_location = read_pipe_string()
    offset = expect_pipe(data, offset)
    playtime = read_pipe_string()

    # Trailing pipe if present
    if offset < header_end and data[offset] == 0x7C:
        offset += 1

    screenshot_size = screenshot_width * screenshot_height * 3
    after_screenshot = header_start + header_size + screenshot_size

    header = {
        "player_name": player_name,
        "karma_title": karma_title,
        "player_level": player_level,
        "player_location": player_location,
        "playtime": playtime,
        "save_number": save_number,
        "screenshot": f"{screenshot_width}x{screenshot_height}",
    }
    return header, after_screenshot


# =====================================================================
# Plugins
# =====================================================================
def parse_plugins(data: bytes, offset: int):
    form_version, offset = read_uint8(data, offset)
    section_size, offset = read_uint32(data, offset)
    section_end = offset + section_size
    marker, offset = read_uint8(data, offset)

    plugin_count = marker  # 0xFF byte is actually the plugin count
    plugins = []
    for _ in range(plugin_count):
        if offset >= section_end or data[offset] != 0x7C:
            break
        offset += 1  # skip pipe
        name_len, offset = read_uint16(data, offset)
        if offset < section_end and data[offset] == 0x7C:
            offset += 1  # skip pipe between len and name
        name = data[offset : offset + name_len].decode("utf-8", errors="replace")
        offset += name_len
        plugins.append(name)

    offset = section_end
    return plugins, form_version, offset


# =====================================================================
# File Location Table
# =====================================================================
def parse_file_location_table(data: bytes, offset: int):
    """
    FO3/FNV file location table (8 uint32 fields + padding).
    Fields:
      [0] formIDArrayCountOffset — absolute offset to formID array count
      [1] unknownTable3Offset — offset to end-of-file section
      [2] globalDataTable1Offset — offset to global data table 1
      [3] globalDataTable2Offset — offset to global data table 2
      [4] changeFormsEndOffset — offset where change forms end
      [5] globalDataTable1Count — number of entries in global data table 1
      [6] globalDataTable2Count — number of entries in global data table 2
      [7] changeFormCount — number of change form records
    """
    fields = {}
    names = [
        "formIDArrayCountOffset", "unknownTable3Offset",
        "globalDataTable1Offset", "changeFormsOffset",
        "changeFormsEndOffset", "globalDataTable1Count",
        "unknown1", "changeFormCount",
    ]
    for i, name in enumerate(names):
        val, _ = read_uint32(data, offset + i * 4)
        fields[name] = val

    return fields


# =====================================================================
# Global Data
# =====================================================================
def skip_global_data(data: bytes, offset: int, count: int):
    """
    Skip global data entries. Each entry: uint32 type, uint32 size, byte[size] data.
    Returns offset after all entries.
    """
    for i in range(count):
        gd_type, offset = read_uint32(data, offset)
        gd_size, offset = read_uint32(data, offset)
        offset += gd_size  # skip data
    return offset


# =====================================================================
# Change Forms
# =====================================================================
def parse_change_form(data: bytes, pos: int, num_plugins: int):
    start = pos

    # RefID — 3 bytes
    b0 = data[pos]; pos += 1
    b1 = data[pos]; pos += 1
    b2 = data[pos]; pos += 1

    ref_type = (b0 >> 6) & 0x03
    if ref_type == 0:
        ref_index = ((b0 & 0x3F) << 16) | (b1 << 8) | b2
        form_id_str = f"formIDArr[{ref_index}]"
        plugin_idx = None
    elif ref_type == 1:
        form_id = 0xFF000000 | ((b0 & 0x3F) << 16) | (b1 << 8) | b2
        form_id_str = f"0x{form_id:08X}(created)"
        plugin_idx = 0xFF
    elif ref_type == 2:
        plugin_idx = b0 & 0x3F
        object_id = (b1 << 8) | b2
        form_id_str = f"plugin[0x{plugin_idx:02X}]:0x{object_id:04X}"
    else:  # 3 = default (FalloutNV.esm = plugin 0)
        object_id = ((b0 & 0x3F) << 16) | (b1 << 8) | b2
        form_id_str = f"0x00{object_id:06X}(FalloutNV)"
        plugin_idx = 0

    # changeFlags (uint32)
    change_flags = struct.unpack_from("<I", data, pos)[0]; pos += 4

    # type byte: lower 6 bits = record type, upper 2 bits = length field encoding
    type_byte = data[pos]; pos += 1
    record_type = type_byte & 0x3F
    length_encoding = (type_byte >> 6) & 0x03

    # version (uint8)
    version = data[pos]; pos += 1

    # Data length — size determined by type byte's upper 2 bits
    # FO3/FNV has ONE length field (no decompressed_length unlike Skyrim)
    if length_encoding == 0:
        data_length = data[pos]; pos += 1
    elif length_encoding == 1:
        data_length = struct.unpack_from("<H", data, pos)[0]; pos += 2
    else:  # 2 or 3
        data_length = struct.unpack_from("<I", data, pos)[0]; pos += 4

    record_data = data[pos : pos + data_length]
    pos += data_length

    return {
        "form_id_str": form_id_str,
        "plugin_idx": plugin_idx,
        "change_flags": change_flags,
        "record_type": record_type,
        "version": version,
        "data_length": data_length,
        "data": record_data,
        "offset": start,
    }, pos


# =====================================================================
# Quest Stage Parsing
# =====================================================================
def try_parse_stages_at(d: bytes, offset: int) -> list | None:
    if offset >= len(d):
        return None
    num_stages = d[offset]; offset += 1
    if num_stages == 0 or num_stages > 200:
        return None

    stages = []
    for _ in range(num_stages):
        if offset + 3 > len(d):
            return None
        stage_index = d[offset]; offset += 1
        stage_flag = d[offset]; offset += 1
        num_entries = d[offset]; offset += 1
        if num_entries > 50:
            return None
        for _ in range(num_entries):
            if offset + 5 > len(d):
                return None
            offset += 5  # skip entry_num(1) + day(2) + year(2)
        stages.append({
            "index": stage_index,
            "flag": stage_flag,
            "completed": bool(stage_flag & 0x01),
        })
    return stages


def parse_quest_stages(record: dict):
    d = record["data"]
    flags = record["change_flags"]
    if len(d) < 1:
        return None

    offset = 0
    result = {"flags_byte": None, "stages": []}

    # Bit 1 (0x02) — CHANGE_QUEST_FLAGS
    if flags & 0x02:
        if offset < len(d):
            result["flags_byte"] = d[offset]
            offset += 1

    # Bit 26 (0x04000000) — CHANGE_QUEST_SCRIPT_DELAY
    if flags & 0x04000000:
        if offset + 4 <= len(d):
            offset += 4

    # Bit 27 (0x08000000) — CHANGE_QUEST_SCRIPT
    if flags & 0x08000000:
        if offset + 3 <= len(d):
            num_scripts = struct.unpack_from("<H", d, offset)[0]; offset += 2
            unknown = d[offset]; offset += 1
            # Variable-length script data — try to skip
            # Each script ref is typically: uint32 refID + variable data
            # For now try brute-force finding stages after script data
            if flags & 0x10000000:
                for try_off in range(offset, min(len(d), offset + 500)):
                    stages = try_parse_stages_at(d, try_off)
                    if stages is not None:
                        result["stages"] = stages
                        return result
                return result

    # Bit 28 (0x10000000) — CHANGE_QUEST_STAGES
    if flags & 0x10000000:
        stages = try_parse_stages_at(d, offset)
        if stages is not None:
            result["stages"] = stages
        else:
            # Brute force scan
            for try_off in range(offset, min(len(d), offset + 200)):
                stages = try_parse_stages_at(d, try_off)
                if stages is not None:
                    result["stages"] = stages
                    break
    return result


# =====================================================================
# FormID Array
# =====================================================================
def parse_formid_array(data: bytes, offset: int):
    count = struct.unpack_from("<I", data, offset)[0]
    offset += 4
    formids = []
    for _ in range(count):
        fid = struct.unpack_from("<I", data, offset)[0]
        offset += 4
        formids.append(fid)
    return formids, offset


