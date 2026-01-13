#!/usr/bin/env python3
"""
Compile .po files to .mo files without external dependencies.

This script uses Python's built-in msgfmt module to compile translation files.
"""

import os
import sys
from pathlib import Path

# Add the project root to the path so we can import msgfmt
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Python's tools/msgfmt.py from the standard library
# We'll implement a simple version here

def compile_po_to_mo(po_path: Path, mo_path: Path) -> bool:
    """Compile a .po file to .mo format."""
    try:
        import struct

        # Parse .po file
        messages = {}
        current_msgid = None
        current_msgstr = None
        in_msgid = False
        in_msgstr = False

        with open(po_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        for line in lines:
            line = line.strip()

            if line.startswith('msgid "'):
                if current_msgid is not None and current_msgstr is not None:
                    # Include ALL messages including header (empty msgid has charset info)
                    messages[current_msgid] = current_msgstr
                current_msgid = line[7:-1]  # Remove 'msgid "' and trailing '"'
                current_msgstr = None
                in_msgid = True
                in_msgstr = False
            elif line.startswith('msgstr "'):
                current_msgstr = line[8:-1]  # Remove 'msgstr "' and trailing '"'
                in_msgid = False
                in_msgstr = True
            elif line.startswith('"') and line.endswith('"'):
                # Continuation line
                content = line[1:-1]  # Remove surrounding quotes
                if in_msgid:
                    current_msgid += content
                elif in_msgstr:
                    current_msgstr += content
            elif not line or line.startswith('#'):
                # Empty line or comment - save current message
                if current_msgid is not None and current_msgstr is not None:
                    # Include ALL messages including header (empty msgid has charset info)
                    messages[current_msgid] = current_msgstr
                    current_msgid = None
                    current_msgstr = None
                    in_msgid = False
                    in_msgstr = False

        # Don't forget the last message
        if current_msgid is not None and current_msgstr is not None:
            messages[current_msgid] = current_msgstr

        # Process escape sequences
        def unescape(s):
            return s.replace('\\n', '\n').replace('\\t', '\t').replace('\\"', '"').replace('\\\\', '\\')

        processed_messages = {}
        for msgid, msgstr in messages.items():
            msgid = unescape(msgid)
            msgstr = unescape(msgstr)
            # Only include non-empty translations
            if msgstr:
                processed_messages[msgid] = msgstr

        # Generate .mo file
        # .mo file format (little-endian):
        # - magic number: 0x950412de
        # - version: 0
        # - number of strings
        # - offset of table with original strings
        # - offset of table with translation strings
        # - size of hashing table (0)
        # - offset of hashing table (0)

        # Sort messages by msgid for binary search
        sorted_keys = sorted(processed_messages.keys())

        # Build string data
        originals = []
        translations = []
        for key in sorted_keys:
            originals.append(key.encode('utf-8'))
            translations.append(processed_messages[key].encode('utf-8'))

        # Calculate offsets
        num_strings = len(sorted_keys)
        header_size = 28  # 7 * 4 bytes
        orig_table_offset = header_size
        trans_table_offset = orig_table_offset + num_strings * 8
        string_offset = trans_table_offset + num_strings * 8

        # Build tables and strings
        orig_table = []
        trans_table = []
        string_data = b''

        current_offset = string_offset
        for orig in originals:
            orig_table.append((len(orig), current_offset))
            string_data += orig + b'\x00'
            current_offset += len(orig) + 1

        for trans in translations:
            trans_table.append((len(trans), current_offset))
            string_data += trans + b'\x00'
            current_offset += len(trans) + 1

        # Build the .mo file
        mo_data = struct.pack(
            '<Iiiiiii',
            0x950412de,  # magic
            0,           # version
            num_strings, # number of strings
            orig_table_offset,
            trans_table_offset,
            0,           # hash table size
            0            # hash table offset
        )

        for length, offset in orig_table:
            mo_data += struct.pack('<ii', length, offset)

        for length, offset in trans_table:
            mo_data += struct.pack('<ii', length, offset)

        mo_data += string_data

        # Write .mo file
        with open(mo_path, 'wb') as f:
            f.write(mo_data)

        return True

    except Exception as e:
        print(f"    Error compiling {po_path}: {e}")
        return False


def main():
    """Compile all .po files in the locale directory."""
    locale_dir = PROJECT_ROOT / "locale"
    languages = ["en", "fr", "de", "es", "zh_CN", "ar"]
    domain = "quickwhisper"

    print("Compiling translation files...")
    success_count = 0
    error_count = 0

    for lang in languages:
        po_path = locale_dir / lang / "LC_MESSAGES" / f"{domain}.po"
        mo_path = locale_dir / lang / "LC_MESSAGES" / f"{domain}.mo"

        if not po_path.exists():
            print(f"  Skipping {lang}: .po file not found")
            continue

        print(f"  Compiling {lang}...", end=" ")
        if compile_po_to_mo(po_path, mo_path):
            print("OK")
            success_count += 1
        else:
            print("FAILED")
            error_count += 1

    print(f"\nDone: {success_count} compiled, {error_count} errors")
    return error_count == 0


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
