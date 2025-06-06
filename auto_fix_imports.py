#!/usr/bin/env python3
"""
Hybrid Auto-Fix Utility (Orchestrator)

This script performs simple, text-based pre-processing and then invokes a
powerful TypeScript-based script (auto_fixer.ts) to handle complex,
AST-aware code modifications like fixing and organizing imports.

- Step 1 (Python): Strips Markdown code fences.
- Step 2 (Python): Adds "use client" directive where needed.
- Step 3 (TypeScript): Fixes missing imports, merges duplicates, and removes unused imports.
"""

import sys
import re
import subprocess
from pathlib import Path
from typing import Tuple, List

class HybridAutoFixer:
    def __init__(self):
        self.client_indicators = [
            r"\buseState\s*\(", r"\buseEffect\s*\(", r"\bonClick\s*=",
            r"react-hot-toast", r"sonner", r"@dnd-kit", r"embla-carousel-react",
            r"recharts", r"cmdk", r"input-otp", r"react-day-picker",
            r"react-hook-form", r"next-themes", r"vaul",
        ]

    def _strip_markdown_fences(self, content: str) -> Tuple[str, bool]:
        """Strips Markdown code fences. Returns (new_content, was_changed)."""
        lines = content.splitlines()
        if not lines:
            return content, False
        fence_indices = [i for i, line in enumerate(lines) if line.strip().startswith("```")]
        if len(fence_indices) >= 2 and fence_indices[0] < fence_indices[-1]:
            cleaned_lines = lines[fence_indices[0] + 1 : fence_indices[-1]]
            return "\n".join(cleaned_lines), True
        return content, False

    def _needs_use_client(self, content: str) -> bool:
        """Checks if 'use client' is needed and not already present."""
        if re.match(r'^["\']use client["\'];?\s*$', content.strip(), re.M):
            return False
        for pattern in self.client_indicators:
            if re.search(pattern, content):
                return True
        return False

    def _add_use_client(self, content: str) -> str:
        """Adds 'use client' to the top of the content."""
        lines = content.splitlines()
        start_index = 1 if lines and lines[0].startswith("#!") else 0
        lines.insert(start_index, '"use client";')
        return "\n".join(lines)

    def preprocess_file(self, file_path: Path) -> bool:
        """Runs only text-based preprocessing on a single file."""
        try:
            original_content = file_path.read_text(encoding="utf-8")
            content = original_content
            was_changed = False

            # Step 1: Strip Markdown
            content, stripped = self._strip_markdown_fences(content)
            if stripped:
                print(f"  - Stripped Markdown from {file_path.name}")
                was_changed = True

            # Step 2: Add "use client"
            if self._needs_use_client(content):
                content = self._add_use_client(content)
                print(f"  - Added 'use client' to {file_path.name}")
                was_changed = True

            if was_changed:
                file_path.write_text(content, encoding="utf-8")
            
            return was_changed
        except Exception as e:
            print(f"  - ❌ Error preprocessing {file_path.name}: {e}")
            return False

    def process_directory(self, directory_path: str) -> None:
        """Main workflow to fix a project directory."""
        target_path = Path(directory_path)
        print(f"🚀 Starting Hybrid Auto-Fix for: {target_path}")

        # --- STAGE 1: Pre-processing with Python ---
        print("\n🐍 [Python] Stage 1: Running text-based pre-processing...")
        extensions = ["*.js", "*.jsx", "*.ts", "*.tsx"]
        files_to_process: List[Path] = []
        for ext in extensions:
            files_to_process.extend(target_path.rglob(ext))

        preprocessed_count = 0
        for file_path in files_to_process:
            if any(part in file_path.parts for part in ["node_modules", ".next", "dist", "build"]):
                continue
            if self.preprocess_file(file_path):
                preprocessed_count += 1
        
        print(f"🐍 [Python] Pre-processing complete. {preprocessed_count} files modified.")

        # --- STAGE 2: Code-aware fixing with TypeScript ---
        print("\n🤖 [Python] Stage 2: Invoking TypeScript fixer for deep analysis...")
        
        # We assume `auto_fixer.ts` is in the current working directory.
        ts_fixer_script = "auto_fixer.ts"
        command = ["npx", "ts-node", ts_fixer_script, directory_path]
        
        try:
            # We use `check=True` to raise an exception if the TS script fails.
            process = subprocess.run(
                command, 
                capture_output=True, 
                text=True, 
                check=True,
                encoding='utf-8'
            )
            print("🤖 [Python] TypeScript fixer output:")
            print(process.stdout)
            if process.stderr:
                print("🤖 [Python] TypeScript fixer warnings:")
                print(process.stderr)
            print("✅ Fix process completed successfully!")

        except FileNotFoundError:
            print("❌ Error: `npx` command not found. Is Node.js installed and in your PATH?")
        except subprocess.CalledProcessError as e:
            print("❌ Error: The TypeScript fixer script failed.")
            print("--- STDOUT ---")
            print(e.stdout)
            print("--- STDERR ---")
            print(e.stderr)
        except Exception as e:
            print(f"❌ An unexpected error occurred while running the subprocess: {e}")

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 auto_fix_imports.py <directory_to_process>")
        sys.exit(1)

    target_dir = sys.argv[1]
    if not Path(target_dir).is_dir():
        print(f"❌ Error: Target '{target_dir}' is not a directory.")
        sys.exit(1)

    fixer = HybridAutoFixer()
    fixer.process_directory(target_dir)

if __name__ == "__main__":
    main()