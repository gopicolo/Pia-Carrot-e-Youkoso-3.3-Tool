# repack_pia_carrot.py
import struct
import os
import re

# --- CONFIGURATION ---
rom_filename = "Pia Carrot e Youkoso!! 3.3 (Japan).gba"
translated_text_filename = "dialogue_for_translation.txt"
new_rom_filename = "pia_carrot_translated.gba"

# --- OFFSETS ---
# The location in the ROM where we will write our new, longer text strings
free_space_start_offset = 0x79D6D8
ROM_END_OFFSET = 0x7FFFFF # The absolute end of the usable ROM space

# --- GAME-SPECIFIC BYTES ---
terminator = b'\x00'
newline_char = b'\x0a'

# This dictionary will map our text tags back to their original bytes
TAG_MAP = {
    # Add any special named tags here if you find them, e.g.,
    # '[PLAYER_NAME]': b'\x02\x01'
}
# ---------------------------------

def parse_text_file(filename):
    """Reads the formatted text file and parses it into a list of entries."""
    print(f"Reading and parsing '{filename}'...")
    entries = []
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Regex to find each block, capturing ID, POINTER_OFFSET, TEXT_OFFSET and the text content
    pattern = re.compile(
        r"<STRING (\d+?)>\n"
        r"POINTER_OFFSET: 0x([0-9A-F]+)\n"
        r"TEXT_OFFSET: 0x([0-9A-F]+)\n"
        r"([\s\S]*?)\n\n",
        re.MULTILINE
    )
    # Regex for duplicate entries
    duplicate_pattern = re.compile(r"\[DUPLICATE OF <STRING (\d+)>\]")

    for match in pattern.finditer(content):
        entry_id = int(match.group(1))
        pointer_offset = int(match.group(2), 16)
        text_offset = int(match.group(3), 16)
        text = match.group(4)

        duplicate_match = duplicate_pattern.match(text)
        if duplicate_match:
            original_id = int(duplicate_match.group(1))
            entries.append({
                "id": entry_id,
                "pointer_offset": pointer_offset,
                "is_duplicate": True,
                "original_id": original_id
            })
        else:
            entries.append({
                "id": entry_id,
                "pointer_offset": pointer_offset,
                "original_text_offset": text_offset,
                "is_duplicate": False,
                "text": text
            })
            
    print(f"Found {len(entries)} total entries in the source file.")
    return entries

def encode_string(text_string):
    """Encodes a string, converting tags into bytes."""
    # This regex will find both custom <$HEX$> tags and named [TAG] tags
    hex_tag_pattern = r"<\$\s*([0-9A-F\s]+)\s*\$>"
    named_tag_pattern = '|'.join(re.escape(k) for k in TAG_MAP.keys())
    combined_pattern = re.compile(f"({hex_tag_pattern}|{named_tag_pattern})")

    # Replace text newlines with the game's newline byte
    processed_text = text_string.replace('\n', chr(newline_char[0]))
    
    parts = combined_pattern.split(processed_text)
    encoded_bytes = b''

    for i, part in enumerate(parts):
        if not part: continue

        if part in TAG_MAP:
            encoded_bytes += TAG_MAP[part]
        elif part.startswith('<$') and part.endswith('$>'):
            hex_string = part[2:-2].strip().replace(" ", "")
            encoded_bytes += bytes.fromhex(hex_string)
        else:
            try:
                encoded_bytes += part.encode('shift_jis', errors='replace')
            except Exception as e:
                print(f"WARNING: Could not encode part '{part[:20]}...': {e}")
    
    return encoded_bytes + terminator

# --- MAIN SCRIPT ---
if not all(os.path.exists(f) for f in [rom_filename, translated_text_filename]):
    print("ERROR: One or more required files (ROM or text file) are missing.")
else:
    print("Reading original ROM into memory...")
    with open(rom_filename, 'rb') as f:
        rom_data = bytearray(f.read())
        
    entries = parse_text_file(translated_text_filename)

    print(f"\nRepacking text...")
    
    current_free_space_offset = free_space_start_offset
    # This will store the new location of every unique string
    repointed_locations = {}

    # --- First Pass: Insert text and decide new locations ---
    for entry in entries:
        if entry["is_duplicate"]:
            continue

        original_offset = entry["original_text_offset"]
        
        # Get original text length
        original_end = rom_data.find(terminator, original_offset)
        original_length = (original_end - original_offset) + 1 if original_end != -1 else 0

        # Encode new text to get its length
        new_text_bytes = encode_string(entry["text"])
        new_length = len(new_text_bytes)

        if new_length <= original_length:
            # If it fits, it stays in the original location
            rom_data[original_offset : original_offset + new_length] = new_text_bytes
            # Fill the rest of the original space with terminators to prevent garbage data
            for i in range(new_length, original_length):
                rom_data[original_offset + i] = terminator[0]
            
            repointed_locations[entry["id"]] = original_offset
        else:
            # If it doesn't fit, move it to free space
            if current_free_space_offset + new_length > ROM_END_OFFSET:
                print(f"FATAL ERROR: Ran out of free space! Aborting.")
                exit()
            
            rom_data[current_free_space_offset : current_free_space_offset + new_length] = new_text_bytes
            repointed_locations[entry["id"]] = current_free_space_offset
            current_free_space_offset += new_length

    print(f"Finished writing new text blocks. Last byte written at {hex(current_free_space_offset)}.")

    # --- Second Pass: Update all pointers ---
    print("\nUpdating pointer table...")
    for entry in entries:
        pointer_offset = entry["pointer_offset"]
        
        target_id = entry["id"]
        if entry["is_duplicate"]:
            target_id = entry["original_id"]

        if target_id in repointed_locations:
            new_text_location = repointed_locations[target_id]
            new_pointer_value = 0x08000000 + new_text_location
            new_pointer_bytes = struct.pack('<I', new_pointer_value)
            rom_data[pointer_offset : pointer_offset + 4] = new_pointer_bytes
        else:
            print(f"WARNING: Could not find original string for duplicate <STRING {entry['id']:04}>. Pointer not updated.")

    # --- Final Step: Write the new ROM file ---
    print(f"Writing all changes to new ROM file: '{new_rom_filename}'...")
    with open(new_rom_filename, 'wb') as f:
        f.write(rom_data)

    print("\nRepack finished successfully! 🎉")