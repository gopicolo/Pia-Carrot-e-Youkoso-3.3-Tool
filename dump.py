# dump.py (Seu script, aprimorado com detecção de duplicatas)
import struct
import os
import codecs
import re

# --- CONFIGURATION ---
rom_filename = "Pia Carrot e Youkoso!! 3.3 (Japan).gba"
output_filename = "dialogue_for_translation.txt"
mode = "scan"  # ou "tables"

pointer_tables = [
    {'start': 0x10F488, 'end': 0x10FE50, 'type': 'standard'},
    {'start': 0x114D50, 'end': 0x1150D4, 'type': 'standard'},
    {'start': 0x11603C, 'end': 0x11625C, 'type': 'alternating'},
    {'start': 0x116AFC, 'end': 0x11707C, 'type': 'alternating'},
    {'start': 0x1179CC, 'end': 0x117B44, 'type': 'alternating'},
    {'start': 0x117CCC, 'end': 0x117DA8, 'type': 'standard'},
]

terminator = b'\x00'
newline_char = b'\x0a'

OFFSET_MIN_VALID = 0x0010C000  # strings abaixo desse offset serão ignoradas

def custom_sjis_error_handler(e):
    if not isinstance(e, UnicodeDecodeError):
        raise e
    bad_bytes = e.object[e.start:e.end]
    hex_representation = bad_bytes.hex().upper()
    return (f"<${hex_representation}$>", e.end)

codecs.register_error("custom_sjis", custom_sjis_error_handler)

def read_string_from(data, offset, terminator_byte):
    if offset >= len(data):
        return None
    end_index = data.find(terminator_byte, offset)
    if end_index == -1:
        return None
    chunk = data[offset:end_index]
    processed_chunk = chunk.replace(newline_char, b'\n')
    try:
        decoded = processed_chunk.decode('shift_jis', errors='custom_sjis')
    except:
        return None
    return decoded

# --- FILTER CONFIG ---
MIN_CHARS = 2
MAX_REPLACEMENT_FRAC = 0.15
MIN_PRINTABLE_FRAC = 0.55
MIN_JP_CHARS_OVERRIDE = 2
MIN_LATIN_DIGITS = 3
MAX_TOTAL_LENGTH = 1024
MAX_CONTROL_CHAR_FRAC = 0.05
MIN_UNIQUE_CHARS = 6
MIN_NON_JP_LENGTH = 5

JAPANESE_RE = re.compile(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]')
PRINTABLE_RE = re.compile(
    r'['
    r'\u0020-\u007E'
    r'\u3000-\u303F'
    r'\u3040-\u309F'
    r'\u30A0-\u30FF'
    r'\u4E00-\u9FFF'
    r'\n\r\t'
    r']'
)
REPLACEMENT_TOKEN_RE = re.compile(r'<\$\w{2,}\$>')
LATIN_DIGIT_RE = re.compile(r'[A-Za-z0-9]')

def is_valid_string(text):
    if not text:
        return False
    if len(text.strip()) < MIN_CHARS:
        return False
    if len(text) > MAX_TOTAL_LENGTH:
        return False

    repl_tokens = REPLACEMENT_TOKEN_RE.findall(text)
    repl_frac = (len(''.join(repl_tokens)) / max(1, len(text)))
    repl_token_count = len(repl_tokens)

    printable_chars = PRINTABLE_RE.findall(text)
    printable_frac = len(printable_chars) / max(1, len(text))

    jp_chars = JAPANESE_RE.findall(text)
    jp_count = len(jp_chars)
    latin_digits_count = len(LATIN_DIGIT_RE.findall(text))

    control_chars = [c for c in text if ord(c) < 0x20 and c not in "\n\r\t"]
    control_frac = len(control_chars) / max(1, len(text))

    unique_chars = set(text)

    def is_repeated_pattern(s):
        if len(set(s)) == 1:
            return True
        for size in range(1, 6):
            if len(s) > size and len(s) % size == 0:
                pattern = s[:size]
                if pattern * (len(s) // size) == s:
                    return True
        return False

    def is_single_japanese_char_repetition(s):
        if len(s) == 0:
            return False
        unique_chars_local = set(s)
        if len(unique_chars_local) == 1:
            c = unique_chars_local.pop()
            return bool(JAPANESE_RE.fullmatch(c))
        return False

    if control_frac > MAX_CONTROL_CHAR_FRAC: return False
    if jp_count < MIN_JP_CHARS_OVERRIDE and latin_digits_count < MIN_LATIN_DIGITS: return False
    if printable_frac < MIN_PRINTABLE_FRAC: return False
    if repl_token_count > 0 and repl_frac > MAX_REPLACEMENT_FRAC: return False
    if jp_count >= MIN_JP_CHARS_OVERRIDE and repl_token_count < (len(text) * 0.5): return True
    if jp_count == 0 and len(printable_chars) < MIN_NON_JP_LENGTH: return False
    if jp_count == 0 and latin_digits_count < 3: return False
    if is_repeated_pattern(text) and not is_single_japanese_char_repetition(text): return False
    start_sample = text[:6]
    if re.match(r'^[\u3040-\u30FF\u4E00-\u9FFF][A-Za-z0-9]', start_sample): return False
    if re.match(r'^[A-Za-z0-9]{1,3}[^A-Za-z0-9]', start_sample) and len(text) < 8: return False

    return True

# ---------------------- main ---------------------- #
if not os.path.exists(rom_filename):
    print(f"ERROR: ROM file '{rom_filename}' not found.")
else:
    with open(rom_filename, 'rb') as f:
        rom_data = f.read()

    print(f"Extracting text from ROM '{rom_filename}' to '{output_filename}' (mode={mode})...")

    with open(output_filename, 'w', encoding='utf-8') as output_file:
        string_id_counter = 0
        # NEW: Dictionary to track already processed text offsets: {text_offset: original_string_id}
        seen_text_offsets = {} 

        if mode == "tables":
            for table_info in pointer_tables:
                start_offset = table_info['start']
                end_offset = table_info['end']
                table_type = table_info['type']

                current_offset = start_offset
                entry_size = 8 if table_type == 'standard' else 16

                while current_offset < end_offset:
                    pointer_bytes = rom_data[current_offset:current_offset+4]
                    if len(pointer_bytes) < 4:
                        break
                    address = struct.unpack('<I', pointer_bytes)[0]

                    if 0x08000000 <= address < 0x09000000:
                        file_offset = address - 0x08000000
                        if file_offset < len(rom_data) and file_offset >= OFFSET_MIN_VALID:
                            text_string = read_string_from(rom_data, file_offset, terminator)
                            if is_valid_string(text_string):
                                # NEW: Check for duplicates
                                if file_offset in seen_text_offsets:
                                    original_id = seen_text_offsets[file_offset]
                                    output_block = f"<STRING {string_id_counter:04}>\nPOINTER_OFFSET: 0x{current_offset:08X}\nTEXT_OFFSET: 0x{file_offset:08X}\n[DUPLICATE OF <STRING {original_id:04}>]\n\n"
                                else:
                                    # NEW: Add new, valid text to our tracking dictionary
                                    seen_text_offsets[file_offset] = string_id_counter
                                    output_block = f"<STRING {string_id_counter:04}>\nPOINTER_OFFSET: 0x{current_offset:08X}\nTEXT_OFFSET: 0x{file_offset:08X}\n{text_string}\n\n"
                                
                                output_file.write(output_block)
                                string_id_counter += 1
                    current_offset += entry_size

        elif mode == "scan":
            rom_size = len(rom_data)
            # NEW: Loop through all potential pointers first to build a list
            all_pointers = []
            for ptr_offset in range(0, rom_size - 4, 4):
                address = struct.unpack('<I', rom_data[ptr_offset:ptr_offset+4])[0]
                if 0x08000000 <= address < 0x09000000:
                    file_offset = address - 0x08000000
                    if 0 <= file_offset < rom_size and file_offset >= OFFSET_MIN_VALID:
                        all_pointers.append({'ptr_offset': ptr_offset, 'file_offset': file_offset})
            
            # NEW: Now process the found pointers
            for pointer_info in all_pointers:
                ptr_offset = pointer_info['ptr_offset']
                file_offset = pointer_info['file_offset']
                
                if file_offset in seen_text_offsets:
                    # This is a duplicate pointer
                    original_id = seen_text_offsets[file_offset]
                    output_block = f"<STRING {string_id_counter:04}>\nPOINTER_OFFSET: 0x{ptr_offset:08X}\nTEXT_OFFSET: 0x{file_offset:08X}\n[DUPLICATE OF <STRING {original_id:04}>]\n\n"
                    output_file.write(output_block)
                    string_id_counter += 1
                else:
                    # This is a new text offset, check if the string is valid
                    text_string = read_string_from(rom_data, file_offset, terminator)
                    if is_valid_string(text_string):
                        seen_text_offsets[file_offset] = string_id_counter
                        output_block = f"<STRING {string_id_counter:04}>\nPOINTER_OFFSET: 0x{ptr_offset:08X}\nTEXT_OFFSET: 0x{file_offset:08X}\n{text_string}\n\n"
                        output_file.write(output_block)
                        string_id_counter += 1

    print(f"Extraction complete! Total entries (including duplicates): {string_id_counter}")