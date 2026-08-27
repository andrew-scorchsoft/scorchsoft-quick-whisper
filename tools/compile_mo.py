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

def _unescape(text):
    """Turn the escape sequences a .po file uses back into real characters."""
    return (text.replace('\\n', '\n').replace('\\t', '\t')
                .replace('\\"', '"').replace('\\\\', '\\'))


def parse_po(po_path: Path):
    """Read a .po file into {msgid: msgstr} ready for the .mo tables.

    Plural entries are stored the way the .mo format expects them: the key is
    "singular\\x00plural" and the value is every plural form joined by NULs.
    Without this a catalogue compiled here silently loses every _n() string and
    the application falls back to English for them.

    A "#, fuzzy" flag means msgmerge guessed this translation from a similar
    string and a human has not confirmed it. The guesses are frequently wrong -
    msgmerge paired "Save Failed" with the French for "Retry failed" - so
    gettext's own msgfmt excludes them by default and falls back to the English
    source. This compiler does the same.
    """
    messages = {}
    fuzzy_skipped = 0

    # Current entry being accumulated.
    msgid = msgid_plural = None
    msgstr = None            # singular translation
    plurals = {}             # index -> translation, for plural entries
    target = None            # which field continuation lines belong to
    is_fuzzy = pending_fuzzy = False

    def flush():
        nonlocal msgid, msgid_plural, msgstr, plurals, target, is_fuzzy, fuzzy_skipped
        if msgid is None:
            return
        if is_fuzzy and msgid:
            fuzzy_skipped += 1
        elif msgid_plural is not None:
            forms = [plurals[i] for i in sorted(plurals)]
            if any(forms):
                key = _unescape(msgid) + "\x00" + _unescape(msgid_plural)
                messages[key] = "\x00".join(_unescape(f) for f in forms)
        elif msgstr is not None:
            # The header (empty msgid) carries the charset and plural rules and
            # has to be kept.
            messages[_unescape(msgid)] = _unescape(msgstr)
        msgid = msgid_plural = msgstr = None
        plurals = {}
        target = None
        is_fuzzy = False

    with open(po_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    for raw in lines:
        line = raw.strip()

        if line.startswith('msgid_plural "'):
            msgid_plural = line[14:-1]
            target = 'msgid_plural'
        elif line.startswith('msgid "'):
            flush()
            msgid = line[7:-1]
            target = 'msgid'
            is_fuzzy = pending_fuzzy
            pending_fuzzy = False
        elif line.startswith('msgstr["') or line.startswith('msgstr['):
            index = int(line[line.index('[') + 1:line.index(']')])
            msgstr_start = line.index('"')
            plurals[index] = line[msgstr_start + 1:-1]
            target = ('plural', index)
        elif line.startswith('msgstr "'):
            msgstr = line[8:-1]
            target = 'msgstr'
        elif line.startswith('"') and line.endswith('"'):
            # Continuation of whichever field we are in.
            content = line[1:-1]
            if target == 'msgid':
                msgid += content
            elif target == 'msgid_plural':
                msgid_plural += content
            elif target == 'msgstr':
                msgstr += content
            elif isinstance(target, tuple):
                plurals[target[1]] += content
        elif not line or line.startswith('#'):
            if line.startswith('#,') and 'fuzzy' in line:
                pending_fuzzy = True
            if not line:
                flush()

    flush()

    if fuzzy_skipped:
        print(f"    ({fuzzy_skipped} fuzzy entries skipped - need translator review)")

    # Only non-empty translations belong in the catalogue; an empty msgstr
    # means "not translated" and must fall back to the source string.
    return {msgid: msgstr for msgid, msgstr in messages.items() if msgstr}


def compile_po_to_mo(po_path: Path, mo_path: Path) -> bool:
    """Compile a .po file to .mo format."""
    try:
        import struct

        processed_messages = parse_po(po_path)

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
    languages = ["en", "fr", "de", "es", "zh_CN", "ar", "ja", "ko", "ru", "pt"]
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
