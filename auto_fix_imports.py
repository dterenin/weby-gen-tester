#!/usr/bin/env python3
"""
Hybrid Auto-Fix Utility (Orchestrator) - OPTIMIZED

- Reads a list of specific files to process from command-line arguments.
- Pre-processes files with simple text-based fixes (markdown, 'use client').
- Invokes the powerful TypeScript fixer for all complex import-related issues.
"""

import sys
import re
import subprocess
from pathlib import Path
from typing import Tuple, List, Optional

class HybridAutoFixer:
    """
    Handles pre-processing of source files with text-based fixes
    before invoking the more powerful TypeScript AST-based fixer.
    """
    def __init__(self):
        # Indicators that a file likely needs a "use client" directive.
        self.client_indicators = [
            r"\buseState\s*\(", r"\buseEffect\s*\(", r"\bonClick\s*=",
            r"react-hot-toast", r"sonner", r"@dnd-kit", r"embla-carousel-react",
            r"recharts", r"cmdk", r"input-otp", r"react-day-picker",
            r"react-hook-form", r"next-themes", r"vaul",
        ]

    def _strip_markdown_fences(self, content: str) -> Tuple[str, bool]:
        """Removes Markdown code fences (```) from content."""
        lines = content.splitlines()
        if not lines: return content, False
        fence_indices = [i for i, line in enumerate(lines) if line.strip().startswith("```")]
        if len(fence_indices) >= 2 and fence_indices[0] < fence_indices[-1]:
            cleaned_lines = lines[fence_indices[0] + 1 : fence_indices[-1]]
            return "\n".join(cleaned_lines), True
        return content, False

    def _needs_use_client(self, content: str) -> bool:
        """Checks if the content contains client-side hooks or libraries."""
        if re.match(r'^["\']use client["\'];?\s*$', content.strip(), re.M): return False
        return any(re.search(pattern, content) for pattern in self.client_indicators)

    def _add_use_client(self, content: str) -> str:
        """Adds 'use client;' to the top of the file."""
        lines = content.splitlines()
        # Handle shebangs like #!/usr/bin/env node
        start_index = 1 if lines and lines[0].startswith("#!") else 0
        lines.insert(start_index, '"use client";')
        return "\n".join(lines)

    def preprocess_file(self, file_path: Path) -> bool:
        """Runs a series of simple, safe text-based fixes on a single file."""
        try:
            original_content = file_path.read_text(encoding="utf-8")
            content = original_content
            was_changed = False

            # Step 1: Strip Markdown from LLM-generated code.
            content, stripped = self._strip_markdown_fences(content)
            if stripped: 
                print(f"  - Stripped Markdown from {file_path.name}")
                was_changed = True

            # --- REMOVED ---
            # The brute-force regex fix for Header/Footer is no longer needed.
            # The new, intelligent auto_fixer.ts handles default and named imports correctly.

            # Step 2 (was 3): Add "use client" directive if needed.
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

    def process_directory(self, directory_path: str, specific_files: Optional[List[str]] = None):
        """Orchestrates the fixing process for a given directory."""
        target_path = Path(directory_path)
        print(f"🚀 Starting Hybrid Auto-Fix for: {target_path}")

        files_to_process: List[Path] = []
        if specific_files:
            print(f"🎯 Targeted mode: Processing {len(specific_files)} specific file(s).")
            files_to_process = [Path(f) for f in specific_files]
        else:
            print("🔍 Fallback mode: Scanning entire directory for files to process.")
            extensions = ["*.js", "*.jsx", "*.ts", "*.tsx"]
            for ext in extensions:
                files_to_process.extend(f for f in target_path.rglob(ext) if "node_modules" not in f.parts)

        print("\n🐍 [Python] Stage 1: Running text-based pre-processing...")
        preprocessed_count = sum(1 for file_path in files_to_process if self.preprocess_file(file_path))
        print(f"🐍 [Python] Pre-processing complete. {preprocessed_count} files modified.")
        
        if not files_to_process:
            print("✅ No files needed processing. Skipping TypeScript fixer.")
            return

        print("\n🤖 [Python] Stage 2: Invoking TypeScript fixer for deep analysis...")
        
        script_cwd = Path(__file__).parent.resolve()
        ts_fixer_script_path = script_cwd / "auto_fixer.ts"

        command = [
            "pnpm", "exec", "ts-node", str(ts_fixer_script_path),
            directory_path
        ] + [str(p.resolve()) for p in files_to_process]

        try:
            process = subprocess.run(command, capture_output=True, text=True, check=True, encoding='utf-8', cwd=script_cwd)
            print("🤖 [Python] TypeScript fixer output:", process.stdout, sep='\n')
            if process.stderr: print("🤖 [Python] TypeScript fixer warnings:", process.stderr, sep='\n')
            print("✅ Fix process completed successfully!")
        except FileNotFoundError:
            print("❌ Error: `pnpm` command not found.")
        except subprocess.CalledProcessError as e:
            print("❌ Error: The TypeScript fixer script failed.", "--- STDOUT ---", e.stdout, "--- STDERR ---", e.stderr, sep='\n')
            sys.exit(1)
        except Exception as e:
            print(f"❌ An unexpected error occurred: {e}")
            sys.exit(1)

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 auto_fix_imports.py <directory_to_process> [file1.ts] [file2.tsx] ...")
        sys.exit(1)
    
    target_dir = sys.argv[1]
    specific_files = sys.argv[2:] if len(sys.argv) > 2 else None

    if not Path(target_dir).is_dir():
        print(f"❌ Error: Target '{target_dir}' is not a directory.")
        sys.exit(1)
        
    fixer = HybridAutoFixer()
    fixer.process_directory(target_dir, specific_files)

if __name__ == "__main__":
    main()