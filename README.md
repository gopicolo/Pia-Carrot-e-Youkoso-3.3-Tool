# Pia Carrot e Youkoso!! 3.3 Text Extraction & Repacking Tools

This repository contains two Python scripts for extracting and repacking the in-game text from the GBA visual novel *Pia Carrot e Youkoso!! 3.3 (Japan)*.

---

## Features

- **dump.py**  
  Scans the game ROM for pointers and extracts Japanese text strings for translation.  
  - Supports pointer table scanning and full ROM scanning modes.  
  - Detects and marks duplicate text pointers to avoid redundant entries.  
  - Filters out invalid or garbage text with custom heuristics.  
  - Handles Shift-JIS decoding with custom error handling.

- **repack.py**  
  Re-inserts translated text back into the ROM, managing free space when text length changes.  
  - Parses translation text files with clear markers for each string and duplicate references.  
  - Encodes Shift-JIS text including custom hex tags for special bytes.  
  - Updates all pointers to point to the correct locations after repacking.  
  - Prevents pointer corruption and out-of-space errors with checks.

---
- **Warning** -
The font of this game for ascii letters is almost illegible, it will be necessary to change the font for a translation
