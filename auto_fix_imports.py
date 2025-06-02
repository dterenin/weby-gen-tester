#!/usr/bin/env python3
"""
Auto Import CN Utility
Automatically adds missing `import { cn } from "@/lib/utils";`
when cn(...) is used in JavaScript/TypeScript files.
"""

import sys
import re
from pathlib import Path
from typing import List


def has_cn_usage(content: str) -> bool:
    """Check if the file contains cn(...) usage."""
    # Look for cn( with optional whitespace
    pattern = r"\bcn\s*\("
    return bool(re.search(pattern, content))


def has_cn_import(content: str) -> bool:
    """Check if the file already has the cn import."""
    # Look for various forms of cn import
    patterns = [
        r'import\s*{[^}]*\bcn\b[^}]*}\s*from\s*["\']@/lib/utils["\']',
        r'import\s*{[^}]*\bcn\b[^}]*}\s*from\s*["\']@/lib/utils["\']',
    ]

    for pattern in patterns:
        if re.search(pattern, content, re.MULTILINE):
            return True
    return False


def find_import_insertion_point(lines: List[str]) -> int:
    """Find the appropriate line to insert the cn import (after other imports)."""
    last_import_line = -1

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Skip empty lines and comments at the top
        if not stripped or stripped.startswith("//") or stripped.startswith("/*"):
            continue

        # Check if this line is an import statement
        if (
            stripped.startswith("import ")
            or stripped.startswith("const ")
            and " = require(" in stripped
        ):
            last_import_line = i
        # If we hit a non-import statement after finding imports, stop
        elif last_import_line >= 0 and not stripped.startswith("import"):
            break

    # If we found imports, insert after the last one
    if last_import_line >= 0:
        return last_import_line + 1

    # If no imports found, insert at the beginning (after any initial comments)
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped and not stripped.startswith("//") and not stripped.startswith("/*"):
            return i

    return 0


def add_cn_import(content: str) -> str:
    """Add the cn import to the file content."""
    lines = content.splitlines()
    insertion_point = find_import_insertion_point(lines)

    # Create the import statement
    import_statement = 'import { cn } from "@/lib/utils";'

    # Insert the import
    lines.insert(insertion_point, import_statement)

    return "\n".join(lines)


def process_file(file_path: str) -> bool:
    """Process a single file and add cn import if needed."""
    path = Path(file_path)

    # Only process JavaScript/TypeScript files
    if path.suffix not in [".js", ".jsx", ".ts", ".tsx"]:
        return False

    try:
        # Read the file
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        # Check if file uses cn but doesn't have the import
        if has_cn_usage(content) and not has_cn_import(content):
            print(f"📝 Adding cn import to: {file_path}")

            # Add the import
            updated_content = add_cn_import(content)

            # Write back to file
            with open(path, "w", encoding="utf-8") as f:
                f.write(updated_content)

            return True
        else:
            print(f"✅ {file_path} - OK (no changes needed)")
            return False

    except Exception as e:
        print(f"❌ Error processing {file_path}: {e}")
        return False


def process_directory(directory_path: str) -> None:
    """Recursively process all JS/TS files in a directory."""
    path = Path(directory_path)

    # Find all JS/TS files
    extensions = ["*.js", "*.jsx", "*.ts", "*.tsx"]
    files_processed = 0
    files_modified = 0

    for ext in extensions:
        for file_path in path.rglob(ext):
            # Skip node_modules and other common directories
            if any(
                part in str(file_path)
                for part in ["node_modules", ".next", "dist", "build"]
            ):
                continue

            files_processed += 1
            if process_file(str(file_path)):
                files_modified += 1

    print(f"📊 Processed {files_processed} files, modified {files_modified} files")


def main():
    """Main CLI interface."""
    if len(sys.argv) < 2:
        print("Usage: python auto_import.py <file_or_directory>")
        sys.exit(1)

    target = sys.argv[1]
    target_path = Path(target)

    if not target_path.exists():
        print(f"❌ Target not found: {target}")
        sys.exit(1)

    if target_path.is_file():
        process_file(target)
    elif target_path.is_dir():
        print(f"🔄 Processing directory: {target}")
        process_directory(target)
        print("✅ Done processing directory")
    else:
        print(f"❌ Invalid target: {target}")
        sys.exit(1)


if __name__ == "__main__":
    main()
