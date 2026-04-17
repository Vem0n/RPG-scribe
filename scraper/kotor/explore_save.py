"""
KOTOR save file explorer.
Parses GFF3 format files (GLOBALVARS.res, PARTYTABLE.res, savenfo.res).

GFF3 spec: https://wiki.neverwintervault.org/pages/viewpage.action?pageId=327727
"""
import struct
from pathlib import Path


def parse_gff3(data: bytes) -> dict:
    """Parse a GFF3 file and return a nested dict."""
    # Header (56 bytes)
    file_type = data[0:4].decode('ascii', errors='replace').strip()
    file_version = data[4:8].decode('ascii', errors='replace').strip()

    (struct_offset, struct_count,
     field_offset, field_count,
     label_offset, label_count,
     field_data_offset, field_data_size,
     field_indices_offset, field_indices_size,
     list_indices_offset, list_indices_size) = struct.unpack_from('<12I', data, 8)

    # Read labels
    labels = []
    for i in range(label_count):
        lbl = data[label_offset + i*16 : label_offset + i*16 + 16]
        labels.append(lbl.rstrip(b'\x00').decode('ascii', errors='replace'))

    # Read fields
    fields = []
    for i in range(field_count):
        off = field_offset + i * 12
        ftype, label_idx, data_or_offset = struct.unpack_from('<III', data, off)
        fields.append((ftype, label_idx, data_or_offset))

    # Read structs
    structs = []
    for i in range(struct_count):
        off = struct_offset + i * 12
        stype, data_or_offset, field_cnt = struct.unpack_from('<III', data, off)
        structs.append((stype, data_or_offset, field_cnt))

    def read_field_data(ftype, data_or_offset):
        """Read field value based on type."""
        if ftype == 0:  # BYTE
            return data_or_offset & 0xFF
        elif ftype == 1:  # CHAR
            return struct.pack('<I', data_or_offset)[0]
        elif ftype == 2:  # WORD (uint16)
            return data_or_offset & 0xFFFF
        elif ftype == 3:  # SHORT (int16)
            return struct.unpack('<h', struct.pack('<H', data_or_offset & 0xFFFF))[0]
        elif ftype == 4:  # DWORD (uint32)
            return data_or_offset
        elif ftype == 5:  # INT (int32)
            return struct.unpack('<i', struct.pack('<I', data_or_offset))[0]
        elif ftype == 6:  # DWORD64
            return struct.unpack_from('<Q', data, field_data_offset + data_or_offset)[0]
        elif ftype == 7:  # INT64
            return struct.unpack_from('<q', data, field_data_offset + data_or_offset)[0]
        elif ftype == 8:  # FLOAT
            return struct.unpack('<f', struct.pack('<I', data_or_offset))[0]
        elif ftype == 9:  # DOUBLE
            return struct.unpack_from('<d', data, field_data_offset + data_or_offset)[0]
        elif ftype == 10:  # CExoString
            off = field_data_offset + data_or_offset
            slen = struct.unpack_from('<I', data, off)[0]
            return data[off+4:off+4+slen].decode('utf-8', errors='replace')
        elif ftype == 11:  # CResRef
            off = field_data_offset + data_or_offset
            slen = data[off]
            return data[off+1:off+1+slen].decode('ascii', errors='replace')
        elif ftype == 12:  # CExoLocString
            off = field_data_offset + data_or_offset
            total_size = struct.unpack_from('<I', data, off)[0]
            str_ref = struct.unpack_from('<i', data, off+4)[0]
            str_count = struct.unpack_from('<I', data, off+8)[0]
            if str_count > 0:
                lang_id = struct.unpack_from('<I', data, off+12)[0]
                slen = struct.unpack_from('<I', data, off+16)[0]
                text = data[off+20:off+20+slen].decode('utf-8', errors='replace')
                return {"str_ref": str_ref, "text": text}
            return {"str_ref": str_ref}
        elif ftype == 13:  # VOID (raw bytes)
            off = field_data_offset + data_or_offset
            size = struct.unpack_from('<I', data, off)[0]
            return data[off+4:off+4+size]
        elif ftype == 14:  # Struct
            return read_struct(data_or_offset)
        elif ftype == 15:  # List
            off = list_indices_offset + data_or_offset
            count = struct.unpack_from('<I', data, off)[0]
            result = []
            for j in range(count):
                sidx = struct.unpack_from('<I', data, off + 4 + j*4)[0]
                result.append(read_struct(sidx))
            return result
        return f"<unknown type {ftype}>"

    def read_struct(struct_idx):
        stype, data_or_offset, field_cnt = structs[struct_idx]
        result = {"__type": stype}

        if field_cnt == 1:
            field_indices = [data_or_offset]
        else:
            field_indices = []
            for j in range(field_cnt):
                fidx = struct.unpack_from('<I', data, field_indices_offset + data_or_offset + j*4)[0]
                field_indices.append(fidx)

        for fidx in field_indices:
            ftype, label_idx, data_val = fields[fidx]
            label = labels[label_idx] if label_idx < len(labels) else f"_{label_idx}"
            value = read_field_data(ftype, data_val)
            result[label] = value

        return result

    root = read_struct(0)
    root["__file_type"] = file_type
    return root


def extract_globals(save_dir: Path) -> dict:
    """Extract global variables (booleans + numbers) from GLOBALVARS.res."""
    gv_path = save_dir / "GLOBALVARS.res"
    gff = parse_gff3(gv_path.read_bytes())

    booleans = {}
    numbers = {}

    # CatBoolean = list of {Name, ValBoolean}
    for entry in gff.get("CatBoolean", []):
        name = entry.get("Name", "")
        val = entry.get("ValBoolean", 0)
        booleans[name] = bool(val)

    # CatNumber = list of {Name, ValNumber}
    for entry in gff.get("CatNumber", []):
        name = entry.get("Name", "")
        val = entry.get("ValNumber", 0)
        numbers[name] = val

    return {"booleans": booleans, "numbers": numbers}


def extract_save_info(save_dir: Path) -> dict:
    """Extract save metadata from savenfo.res."""
    nfo_path = save_dir / "savenfo.res"
    gff = parse_gff3(nfo_path.read_bytes())

    return {
        "save_name": gff.get("SAVEGAMENAME", ""),
        "area_name": gff.get("AREANAME", ""),
        "last_module": gff.get("LASTMODULE", ""),
        "time_played": gff.get("TIMEPLAYED", 0),
        "cheat_used": gff.get("CHEATUSED", 0),
        "portrait": gff.get("PORTRAIT0", ""),
    }


def main():
    save_dir = Path(r"C:\Program Files (x86)\Steam\steamapps\common\swkotor\Saves\000003 - Game2")

    # Parse save info
    info = extract_save_info(save_dir)
    print("=== SAVE INFO ===")
    for k, v in info.items():
        print(f"  {k}: {v}")

    # Parse global variables
    globals_data = extract_globals(save_dir)
    booleans = globals_data["booleans"]
    numbers = globals_data["numbers"]

    print("\n=== GLOBAL VARIABLES ===")
    print(f"  Booleans: {len(booleans)}")
    print(f"  Numbers: {len(numbers)}")

    # Show quest-related globals (journal entries use specific variable names)
    print("\n=== QUEST-RELATED BOOLEANS (non-zero) ===")
    quest_bools = {k: v for k, v in sorted(booleans.items()) if v}
    for name, val in sorted(quest_bools.items()):
        print(f"  {name} = {val}")

    print("\n=== QUEST-RELATED NUMBERS (non-zero) ===")
    quest_nums = {k: v for k, v in sorted(numbers.items()) if v != 0}
    for name, val in sorted(quest_nums.items()):
        print(f"  {name} = {val}")


if __name__ == "__main__":
    main()
