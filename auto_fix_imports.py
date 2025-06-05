#!/usr/bin/env python3
"""
Enhanced Auto Import Utility
Automatically adds missing imports for:
- "use client" directive
- React hooks and components
- Lucide icons
- shadcn/ui components
- cn utility function
"""

import sys
import re
import json
from pathlib import Path
from typing import List, Set, Dict, Tuple
from collections import defaultdict


class AutoImporter:
    def __init__(self, lucide_icons_path: str = None):
        self.lucide_icons = self._load_lucide_icons(lucide_icons_path)

        # Client-side indicators for "use client"
        self.client_indicators = [
            r"\buseState\s*\(",
            r"\buseEffect\s*\(",
            r"\buseContext\s*\(",
            r"\buseReducer\s*\(",
            r"\buseRef\s*\(",
            r"\buseCallback\s*\(",
            r"\buseMemo\s*\(",
            r"\buseLayoutEffect\s*\(",
            r"\buseImperativeHandle\s*\(",
            r"\buseDebugValue\s*\(",
            r"\buseTransition\s*\(",
            r"\buseDeferredValue\s*\(",
            r"\buseId\s*\(",
            r"\buseSyncExternalStore\s*\(",
            r"\buseActionState\s*\(",
            r"\buseFormStatus\s*\(",
            r"\buseOptimistic\s*\(",
            r"\bonClick\s*=",
            r"\bonChange\s*=",
            r"\bonSubmit\s*=",
            r"\bonBlur\s*=",
            r"\bonFocus\s*=",
            r"\bonMouseEnter\s*=",
            r"\bonMouseLeave\s*=",
            r"\bonKeyDown\s*=",
            r"\bonKeyUp\s*=",
            r"\bwindow\.",
            r"\bdocument\.",
            r"\blocalStorage\.",
            r"\bsessionStorage\.",
            r"\bnavigator\.",
            # Libraries that require client-side
            r"react-hot-toast",
            r"sonner",
            r"@dnd-kit",
            r"embla-carousel-react",
            r"recharts",
            r"cmdk",
            r"input-otp",
            r"react-day-picker",
            r"react-hook-form",
            r"next-themes",
            r"vaul",
        ]

        # React hooks mapping
        self.react_hooks = {
            r"\buseState\s*\(": "useState",
            r"\buseEffect\s*\(": "useEffect",
            r"\buseContext\s*\(": "useContext",
            r"\buseReducer\s*\(": "useReducer",
            r"\buseCallback\s*\(": "useCallback",
            r"\buseMemo\s*\(": "useMemo",
            r"\buseRef\s*\(": "useRef",
            r"\buseLayoutEffect\s*\(": "useLayoutEffect",
            r"\buseImperativeHandle\s*\(": "useImperativeHandle",
            r"\buseDebugValue\s*\(": "useDebugValue",
            r"\buseTransition\s*\(": "useTransition",
            r"\buseDeferredValue\s*\(": "useDeferredValue",
            r"\buseId\s*\(": "useId",
            r"\buseSyncExternalStore\s*\(": "useSyncExternalStore",
            r"\buseActionState\s*\(": "useActionState",
            r"\buseFormStatus\s*\(": "useFormStatus",
            r"\buseOptimistic\s*\(": "useOptimistic",
        }

        # React components and types
        self.react_components = {
            r"\bReact\.Fragment\b": "Fragment",
            r"\bReact\.Suspense\b": "Suspense",
            r"\bReact\.lazy\b": "lazy",
            r"\bReact\.memo\b": "memo",
            r"\bReact\.forwardRef\b": "forwardRef",
            r"\bReact\.createContext\b": "createContext",
            r"\bReact\.FC\b": "FC",
            r"\bReact\.ReactNode\b": "ReactNode",
            r"\bReact\.ReactElement\b": "ReactElement",
            r"\bReact\.ComponentProps\b": "ComponentProps",
        }

        # Common shadcn/ui components
        self.shadcn_components = {
            r"\bButton\b(?!\.|\w)": ("Button", "@/components/ui/button"),
            r"\bCard\b(?!\.|\w)": ("Card", "@/components/ui/card"),
            r"\bCardHeader\b": ("CardHeader", "@/components/ui/card"),
            r"\bCardContent\b": ("CardContent", "@/components/ui/card"),
            r"\bCardFooter\b": ("CardFooter", "@/components/ui/card"),
            r"\bCardTitle\b": ("CardTitle", "@/components/ui/card"),
            r"\bCardDescription\b": ("CardDescription", "@/components/ui/card"),
            r"\bInput\b(?!\.|\w)": ("Input", "@/components/ui/input"),
            r"\bLabel\b(?!\.|\w)": ("Label", "@/components/ui/label"),
            r"\bSelect\b(?!\.|\w)": ("Select", "@/components/ui/select"),
            r"\bSelectContent\b": ("SelectContent", "@/components/ui/select"),
            r"\bSelectItem\b": ("SelectItem", "@/components/ui/select"),
            r"\bSelectTrigger\b": ("SelectTrigger", "@/components/ui/select"),
            r"\bSelectValue\b": ("SelectValue", "@/components/ui/select"),
            r"\bDialog\b(?!\.|\w)": ("Dialog", "@/components/ui/dialog"),
            r"\bDialogContent\b": ("DialogContent", "@/components/ui/dialog"),
            r"\bDialogHeader\b": ("DialogHeader", "@/components/ui/dialog"),
            r"\bDialogTitle\b": ("DialogTitle", "@/components/ui/dialog"),
            r"\bDialogTrigger\b": ("DialogTrigger", "@/components/ui/dialog"),
            r"\bDialogFooter\b": ("DialogFooter", "@/components/ui/dialog"),
            r"\bDialogDescription\b": ("DialogDescription", "@/components/ui/dialog"),
            r"\bDropdownMenu\b": ("DropdownMenu", "@/components/ui/dropdown-menu"),
            r"\bDropdownMenuContent\b": (
                "DropdownMenuContent",
                "@/components/ui/dropdown-menu",
            ),
            r"\bDropdownMenuItem\b": (
                "DropdownMenuItem",
                "@/components/ui/dropdown-menu",
            ),
            r"\bDropdownMenuTrigger\b": (
                "DropdownMenuTrigger",
                "@/components/ui/dropdown-menu",
            ),
            r"\bDropdownMenuSeparator\b": (
                "DropdownMenuSeparator",
                "@/components/ui/dropdown-menu",
            ),
            r"\bToast\b(?!\.|\w)": ("Toast", "@/components/ui/toast"),
            r"\buseToast\b": ("useToast", "@/components/ui/use-toast"),
            r"\bTooltip\b(?!\.|\w)": ("Tooltip", "@/components/ui/tooltip"),
            r"\bTooltipContent\b": ("TooltipContent", "@/components/ui/tooltip"),
            r"\bTooltipProvider\b": ("TooltipProvider", "@/components/ui/tooltip"),
            r"\bTooltipTrigger\b": ("TooltipTrigger", "@/components/ui/tooltip"),
            r"\bAlert\b(?!\.|\w)": ("Alert", "@/components/ui/alert"),
            r"\bAlertDescription\b": ("AlertDescription", "@/components/ui/alert"),
            r"\bAlertTitle\b": ("AlertTitle", "@/components/ui/alert"),
            r"\bBadge\b(?!\.|\w)": ("Badge", "@/components/ui/badge"),
            r"\bCheckbox\b(?!\.|\w)": ("Checkbox", "@/components/ui/checkbox"),
            r"\bRadioGroup\b": ("RadioGroup", "@/components/ui/radio-group"),
            r"\bRadioGroupItem\b": ("RadioGroupItem", "@/components/ui/radio-group"),
            r"\bSwitch\b(?!\.|\w)": ("Switch", "@/components/ui/switch"),
            r"\bTextarea\b(?!\.|\w)": ("Textarea", "@/components/ui/textarea"),
            r"\bTabs\b(?!\.|\w)": ("Tabs", "@/components/ui/tabs"),
            r"\bTabsContent\b": ("TabsContent", "@/components/ui/tabs"),
            r"\bTabsList\b": ("TabsList", "@/components/ui/tabs"),
            r"\bTabsTrigger\b": ("TabsTrigger", "@/components/ui/tabs"),
            r"\bAvatar\b(?!\.|\w)": ("Avatar", "@/components/ui/avatar"),
            r"\bAvatarFallback\b": ("AvatarFallback", "@/components/ui/avatar"),
            r"\bAvatarImage\b": ("AvatarImage", "@/components/ui/avatar"),
            r"\bSkeleton\b(?!\.|\w)": ("Skeleton", "@/components/ui/skeleton"),
            r"\bAccordion\b(?!\.|\w)": ("Accordion", "@/components/ui/accordion"),
            r"\bAccordionContent\b": ("AccordionContent", "@/components/ui/accordion"),
            r"\bAccordionItem\b": ("AccordionItem", "@/components/ui/accordion"),
            r"\bAccordionTrigger\b": ("AccordionTrigger", "@/components/ui/accordion"),
            r"\bScrollArea\b": ("ScrollArea", "@/components/ui/scroll-area"),
            r"\bSeparator\b(?!\.|\w)": ("Separator", "@/components/ui/separator"),
            r"\bSheet\b(?!\.|\w)": ("Sheet", "@/components/ui/sheet"),
            r"\bSheetContent\b": ("SheetContent", "@/components/ui/sheet"),
            r"\bSheetDescription\b": ("SheetDescription", "@/components/ui/sheet"),
            r"\bSheetHeader\b": ("SheetHeader", "@/components/ui/sheet"),
            r"\bSheetTitle\b": ("SheetTitle", "@/components/ui/sheet"),
            r"\bSheetTrigger\b": ("SheetTrigger", "@/components/ui/sheet"),
            r"\bSheetFooter\b": ("SheetFooter", "@/components/ui/sheet"),
            r"\bForm\b(?!\.|\w)": ("Form", "@/components/ui/form"),
            r"\bFormControl\b": ("FormControl", "@/components/ui/form"),
            r"\bFormDescription\b": ("FormDescription", "@/components/ui/form"),
            r"\bFormField\b": ("FormField", "@/components/ui/form"),
            r"\bFormItem\b": ("FormItem", "@/components/ui/form"),
            r"\bFormLabel\b": ("FormLabel", "@/components/ui/form"),
            r"\bFormMessage\b": ("FormMessage", "@/components/ui/form"),
            r"\bPopover\b(?!\.|\w)": ("Popover", "@/components/ui/popover"),
            r"\bPopoverContent\b": ("PopoverContent", "@/components/ui/popover"),
            r"\bPopoverTrigger\b": ("PopoverTrigger", "@/components/ui/popover"),
            r"\bCommand\b(?!\.|\w)": ("Command", "@/components/ui/command"),
            r"\bCommandDialog\b": ("CommandDialog", "@/components/ui/command"),
            r"\bCommandEmpty\b": ("CommandEmpty", "@/components/ui/command"),
            r"\bCommandGroup\b": ("CommandGroup", "@/components/ui/command"),
            r"\bCommandInput\b": ("CommandInput", "@/components/ui/command"),
            r"\bCommandItem\b": ("CommandItem", "@/components/ui/command"),
            r"\bCommandList\b": ("CommandList", "@/components/ui/command"),
            r"\bCommandSeparator\b": ("CommandSeparator", "@/components/ui/command"),
            r"\bCommandShortcut\b": ("CommandShortcut", "@/components/ui/command"),
        }

    def _load_lucide_icons(self, path: str) -> Set[str]:
        """Load Lucide icons from JSON file."""
        if not path or not Path(path).exists():
            return set()

        try:
            with open(path, "r") as f:
                icons = json.load(f)
                return set(icons) if isinstance(icons, list) else set()
        except Exception as e:
            print(f"⚠️  Warning: Could not load lucide icons from {path}: {e}")
            return set()

    def needs_use_client(self, content: str) -> bool:
        """Check if the file needs 'use client' directive."""
        # Skip if already has use client
        if re.match(r'^["\']use client["\'];?\s*$', content.strip(), re.MULTILINE):
            return False

        # Check for client-side indicators
        for pattern in self.client_indicators:
            if re.search(pattern, content):
                return True

        return False

    def find_missing_react_imports(self, content: str) -> Set[str]:
        """Find missing React imports."""
        missing = set()

        # Check for React hooks
        for pattern, hook in self.react_hooks.items():
            if re.search(pattern, content) and not self._has_import(
                content, hook, "react"
            ):
                missing.add(hook)

        # Check for React components/utilities
        for pattern, component in self.react_components.items():
            if re.search(pattern, content) and not self._has_import(
                content, component, "react"
            ):
                missing.add(component)

        return missing

    def find_missing_lucide_icons(self, content: str) -> Set[str]:
        """Find missing Lucide icon imports."""
        if not self.lucide_icons:
            return set()

        missing = set()

        # Look for icon usage patterns
        for icon in self.lucide_icons:
            # Check for <IconName /> or <IconName ... />
            pattern = rf"<{icon}\s*(?:/?>|\s+[^>]*>)"
            if re.search(pattern, content) and not self._has_import(
                content, icon, "lucide-react"
            ):
                missing.add(icon)

        return missing

    def find_missing_shadcn_imports(self, content: str) -> Dict[str, Set[str]]:
        """Find missing shadcn/ui component imports."""
        missing = defaultdict(set)

        for pattern, (component, module) in self.shadcn_components.items():
            # Check if component is used but not imported
            if re.search(pattern, content):
                # Check in JSX tags
                jsx_pattern = rf"<{component}(?:\s|>|/)"
                # Check as type/prop
                type_pattern = rf":\s*{component}(?:\s|>|\[|$)"

                if re.search(jsx_pattern, content) or re.search(type_pattern, content):
                    if not self._has_import(content, component, module):
                        missing[module].add(component)

        return missing

    def has_cn_usage(self, content: str) -> bool:
        """Check if the file contains cn(...) usage."""
        pattern = r"\bcn\s*\("
        return bool(re.search(pattern, content))

    def _has_import(self, content: str, item: str, module: str) -> bool:
        """Check if an import already exists."""
        # Check for named imports
        patterns = [
            rf'import\s*{{[^}}]*\b{re.escape(item)}\b[^}}]*}}\s*from\s*["\'{re.escape(module)}["\']',
            rf'import\s+{re.escape(item)}\s+from\s*["\'{re.escape(module)}["\']',
            rf'const\s*{{[^}}]*\b{re.escape(item)}\b[^}}]*}}\s*=\s*require\s*\(["\'{re.escape(module)}["\']\)',
        ]

        for pattern in patterns:
            if re.search(pattern, content):
                return True

        return False

    def find_import_insertion_point(self, lines: List[str]) -> Tuple[int, bool]:
        """
        Find the appropriate line to insert imports.
        Returns (line_number, has_use_client)
        """
        has_use_client = False
        last_import_line = -1
        use_client_line = -1

        for i, line in enumerate(lines):
            stripped = line.strip()

            # Check for "use client"
            if re.match(r'^["\']use client["\'];?\s*$', stripped):
                has_use_client = True
                use_client_line = i
                continue

            # Skip empty lines and comments
            if not stripped or stripped.startswith("//") or stripped.startswith("/*"):
                continue

            # Check if this line is an import statement
            if stripped.startswith("import ") or (
                stripped.startswith("const ") and " = require(" in stripped
            ):
                last_import_line = i
            # If we hit a non-import statement after finding imports, stop
            elif last_import_line >= 0 and not stripped.startswith("import"):
                break

        # Determine insertion point
        if last_import_line >= 0:
            return last_import_line + 1, has_use_client
        elif use_client_line >= 0:
            return use_client_line + 1, has_use_client
        else:
            # Find first non-comment line
            for i, line in enumerate(lines):
                stripped = line.strip()
                if (
                    stripped
                    and not stripped.startswith("//")
                    and not stripped.startswith("/*")
                ):
                    return i, has_use_client
            return 0, has_use_client

    def add_imports_to_content(self, content: str, imports_to_add: List[str]) -> str:
        """Add multiple imports to the content."""
        lines = content.splitlines()
        insertion_point, _ = self.find_import_insertion_point(lines)

        # Insert imports in reverse order to maintain the insertion point
        for import_statement in reversed(imports_to_add):
            lines.insert(insertion_point, import_statement)

        return "\n".join(lines)

    def add_use_client(self, content: str) -> str:
        """Add 'use client' directive at the top of the file."""
        lines = content.splitlines()

        # Skip shebang if present
        start_index = 0
        if lines and lines[0].startswith("#!"):
            start_index = 1

        # Insert use client
        lines.insert(start_index, '"use client";')

        return "\n".join(lines)

    def process_file(self, file_path: str) -> Dict[str, int]:
        """Process a single file and add missing imports."""
        path = Path(file_path)
        stats = {"use_client": 0, "react": 0, "lucide": 0, "shadcn": 0, "cn": 0}

        # Only process JavaScript/TypeScript files
        if path.suffix not in [".js", ".jsx", ".ts", ".tsx"]:
            return stats

        try:
            # Read the file
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

            original_content = content
            imports_to_add = []

            # Check for "use client"
            if self.needs_use_client(content):
                content = self.add_use_client(content)
                stats["use_client"] = 1
                print(f"  ➕ Added 'use client' directive")

            # Check for React imports
            missing_react = self.find_missing_react_imports(content)
            if missing_react:
                import_items = ", ".join(sorted(missing_react))
                imports_to_add.append(f'import {{ {import_items} }} from "react";')
                stats["react"] = len(missing_react)
                print(f"  ➕ Added React imports: {import_items}")

            # Check for Lucide icons
            missing_lucide = self.find_missing_lucide_icons(content)
            if missing_lucide:
                import_items = ", ".join(sorted(missing_lucide))
                imports_to_add.append(
                    f'import {{ {import_items} }} from "lucide-react";'
                )
                stats["lucide"] = len(missing_lucide)
                print(f"  ➕ Added Lucide icons: {import_items}")

            # Check for shadcn components
            missing_shadcn = self.find_missing_shadcn_imports(content)
            for module, components in missing_shadcn.items():
                if components:
                    import_items = ", ".join(sorted(components))
                    imports_to_add.append(
                        f'import {{ {import_items} }} from "{module}";'
                    )
                    stats["shadcn"] += len(components)
                    print(f"  ➕ Added shadcn imports from {module}: {import_items}")

            # Check for cn utility
            if self.has_cn_usage(content) and not self._has_import(
                content, "cn", "@/lib/utils"
            ):
                imports_to_add.append('import { cn } from "@/lib/utils";')
                stats["cn"] = 1
                print(f"  ➕ Added cn import")

            # Add all imports if any
            if imports_to_add:
                content = self.add_imports_to_content(content, imports_to_add)

            # Write back if changed
            if content != original_content:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
                print(f"✅ Updated: {file_path}")
            else:
                print(f"✨ No changes needed: {file_path}")

            return stats

        except Exception as e:
            print(f"❌ Error processing {file_path}: {e}")
            return stats

    def process_directory(self, directory_path: str) -> None:
        """Recursively process all JS/TS files in a directory."""
        path = Path(directory_path)

        # Find all JS/TS files
        extensions = ["*.js", "*.jsx", "*.ts", "*.tsx"]
        total_stats = defaultdict(int)
        files_processed = 0
        files_modified = 0

        for ext in extensions:
            for file_path in path.rglob(ext):
                # Skip node_modules and other common directories
                if any(
                    part in str(file_path)
                    for part in ["node_modules", ".next", "dist", "build", ".git"]
                ):
                    continue

                files_processed += 1
                print(f"\n🔍 Processing: {file_path}")

                stats = self.process_file(str(file_path))

                # Update totals
                for key, value in stats.items():
                    total_stats[key] += value

                if any(stats.values()):
                    files_modified += 1

        # Print summary
        print("\n" + "=" * 60)
        print("📊 Summary:")
        print(f"  Files processed: {files_processed}")
        print(f"  Files modified: {files_modified}")
        print(f"  'use client' added: {total_stats['use_client']}")
        print(f"  React imports added: {total_stats['react']}")
        print(f"  Lucide icons added: {total_stats['lucide']}")
        print(f"  Shadcn components added: {total_stats['shadcn']}")
        print(f"  cn imports added: {total_stats['cn']}")
        print("=" * 60)


def main():
    """Main CLI interface."""
    if len(sys.argv) < 2:
        print("Usage: python auto_import.py <file_or_directory> [lucide_icons.json]")
        print("\nOptions:")
        print("  <file_or_directory>  File or directory to process")
        print("  [lucide_icons.json]  Optional path to Lucide icons JSON file")
        sys.exit(1)

    target = sys.argv[1]
    lucide_path = sys.argv[2] if len(sys.argv) > 2 else None

    target_path = Path(target)

    if not target_path.exists():
        print(f"❌ Target not found: {target}")
        sys.exit(1)

    # Initialize the auto importer
    importer = AutoImporter(lucide_path)

    if target_path.is_file():
        print(f"🔄 Processing file: {target}")
        importer.process_file(target)
    elif target_path.is_dir():
        print(f"🔄 Processing directory: {target}")
        importer.process_directory(target)
    else:
        print(f"❌ Invalid target: {target}")
        sys.exit(1)


if __name__ == "__main__":
    main()
