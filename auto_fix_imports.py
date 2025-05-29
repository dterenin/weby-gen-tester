#!/usr/bin/env python3

import os
import re
import json
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional, TypedDict

# --- Global Component/Import Mappings ---
HERE = Path(__file__).resolve().parent
# React component patterns
REACT_COMPONENTS = [
    'Fragment', 'Component', 'PureComponent', 'memo', 'forwardRef',
    'createContext', 'useContext', 'useState', 'useEffect', 'useReducer',
    'useCallback', 'useMemo', 'useRef', 'useImperativeHandle', 'useLayoutEffect',
    'useDebugValue', 'createRef', 'isValidElement', 'Children', 'cloneElement',
    'createElement', 'createFactory', 'lazy', 'Suspense', 'StrictMode'
]

# shadcn/ui components with their kebab-case names
SHADCN_COMPONENTS = {
    'Accordion': 'accordion', 'AccordionContent': 'accordion', 'AccordionItem': 'accordion', 'AccordionTrigger': 'accordion',
    'Alert': 'alert', 'AlertDescription': 'alert', 'AlertTitle': 'alert',
    'AlertDialog': 'alert-dialog', 'AlertDialogAction': 'alert-dialog', 'AlertDialogCancel': 'alert-dialog', 'AlertDialogContent': 'alert-dialog', 'AlertDialogDescription': 'alert-dialog', 'AlertDialogFooter': 'alert-dialog', 'AlertDialogHeader': 'alert-dialog', 'AlertDialogTitle': 'alert-dialog', 'AlertDialogTrigger': 'alert-dialog',
    'AspectRatio': 'aspect-ratio',
    'Avatar': 'avatar', 'AvatarFallback': 'avatar', 'AvatarImage': 'avatar',
    'Badge': 'badge',
    'Button': 'button',
    'Calendar': 'calendar',
    'Card': 'card', 'CardContent': 'card', 'CardDescription': 'card', 'CardFooter': 'card', 'CardHeader': 'card', 'CardTitle': 'card',
    'Carousel': 'carousel', 'CarouselContent': 'carousel', 'CarouselItem': 'carousel', 'CarouselNext': 'carousel', 'CarouselPrevious': 'carousel',
    'Checkbox': 'checkbox',
    'Collapsible': 'collapsible', 'CollapsibleContent': 'collapsible', 'CollapsibleTrigger': 'collapsible',
    'Command': 'command', 'CommandDialog': 'command', 'CommandEmpty': 'command', 'CommandGroup': 'command', 'CommandInput': 'command', 'CommandItem': 'command', 'CommandList': 'command', 'CommandSeparator': 'command', 'CommandShortcut': 'command',
    'ContextMenu': 'context-menu', 'ContextMenuCheckboxItem': 'context-menu', 'ContextMenuContent': 'context-menu', 'ContextMenuItem': 'context-menu', 'ContextMenuLabel': 'context-menu', 'ContextMenuRadioGroup': 'context-menu', 'ContextMenuRadioItem': 'context-menu', 'ContextMenuSeparator': 'context-menu', 'ContextMenuShortcut': 'context-menu', 'ContextMenuSub': 'context-menu', 'ContextMenuSubContent': 'context-menu', 'ContextMenuSubTrigger': 'context-menu', 'ContextMenuTrigger': 'context-menu',
    'Dialog': 'dialog', 'DialogContent': 'dialog', 'DialogDescription': 'dialog', 'DialogFooter': 'dialog', 'DialogHeader': 'dialog', 'DialogTitle': 'dialog', 'DialogTrigger': 'dialog',
    'Drawer': 'drawer', 'DrawerClose': 'drawer', 'DrawerContent': 'drawer', 'DrawerDescription': 'drawer', 'DrawerFooter': 'drawer', 'DrawerHeader': 'drawer', 'DrawerTitle': 'drawer', 'DrawerTrigger': 'drawer',
    'DropdownMenu': 'dropdown-menu', 'DropdownMenuCheckboxItem': 'dropdown-menu', 'DropdownMenuContent': 'dropdown-menu', 'DropdownMenuGroup': 'dropdown-menu', 'DropdownMenuItem': 'dropdown-menu', 'DropdownMenuLabel': 'dropdown-menu', 'DropdownMenuPortal': 'dropdown-menu', 'DropdownMenuRadioGroup': 'dropdown-menu', 'DropdownMenuRadioItem': 'dropdown-menu', 'DropdownMenuSeparator': 'dropdown-menu', 'DropdownMenuShortcut': 'dropdown-menu', 'DropdownMenuSub': 'dropdown-menu', 'DropdownMenuSubContent': 'dropdown-menu', 'DropdownMenuSubTrigger': 'dropdown-menu', 'DropdownMenuTrigger': 'dropdown-menu',
    'Form': 'form', 'FormControl': 'form', 'FormDescription': 'form', 'FormField': 'form', 'FormItem': 'form', 'FormLabel': 'form', 'FormMessage': 'form',
    'HoverCard': 'hover-card', 'HoverCardContent': 'hover-card', 'HoverCardTrigger': 'hover-card',
    'Input': 'input',
    'Label': 'label',
    'Menubar': 'menubar', 'MenubarCheckboxItem': 'menubar', 'MenubarContent': 'menubar', 'MenubarItem': 'menubar', 'MenubarLabel': 'menubar', 'MenubarMenu': 'menubar', 'MenubarRadioGroup': 'menubar', 'MenubarRadioItem': 'menubar', 'MenubarSeparator': 'menubar', 'MenubarShortcut': 'menubar', 'MenubarSub': 'menubar', 'MenubarSubContent': 'menubar', 'MenubarSubTrigger': 'menubar', 'MenubarTrigger': 'menubar',
    'NavigationMenu': 'navigation-menu', 'NavigationMenuContent': 'navigation-menu', 'NavigationMenuIndicator': 'navigation-menu', 'NavigationMenuItem': 'navigation-menu', 'NavigationMenuLink': 'navigation-menu', 'NavigationMenuList': 'navigation-menu', 'NavigationMenuTrigger': 'navigation-menu', 'NavigationMenuViewport': 'navigation-menu',
    'Pagination': 'pagination', 'PaginationContent': 'pagination', 'PaginationEllipsis': 'pagination', 'PaginationItem': 'pagination', 'PaginationLink': 'pagination', 'PaginationNext': 'pagination', 'PaginationPrevious': 'pagination',
    'Popover': 'popover', 'PopoverContent': 'popover', 'PopoverTrigger': 'popover',
    'Progress': 'progress',
    'RadioGroup': 'radio-group', 'RadioGroupItem': 'radio-group',
    'ScrollArea': 'scroll-area', 'ScrollBar': 'scroll-area',
    'Select': 'select', 'SelectContent': 'select', 'SelectGroup': 'select', 'SelectItem': 'select', 'SelectLabel': 'select', 'SelectSeparator': 'select', 'SelectTrigger': 'select', 'SelectValue': 'select',
    'Separator': 'separator',
    'Sheet': 'sheet', 'SheetClose': 'sheet', 'SheetContent': 'sheet', 'SheetDescription': 'sheet', 'SheetFooter': 'sheet', 'SheetHeader': 'sheet', 'SheetTitle': 'sheet', 'SheetTrigger': 'sheet',
    'Skeleton': 'skeleton',
    'Slider': 'slider',
    'Switch': 'switch',
    'Table': 'table', 'TableBody': 'table', 'TableCaption': 'table', 'TableCell': 'table', 'TableFooter': 'table', 'TableHead': 'table', 'TableHeader': 'table', 'TableRow': 'table',
    'Tabs': 'tabs', 'TabsContent': 'tabs', 'TabsList': 'tabs', 'TabsTrigger': 'tabs',
    'Textarea': 'textarea',
    'Toast': 'toast', 'ToastAction': 'toast', 'ToastClose': 'toast', 'ToastDescription': 'toast', 'ToastProvider': 'toast', 'ToastTitle': 'toast', 'ToastViewport': 'toast',
    'Toggle': 'toggle', 'ToggleGroup': 'toggle-group', 'ToggleGroupItem': 'toggle-group',
    'Tooltip': 'tooltip', 'TooltipContent': 'tooltip', 'TooltipProvider': 'tooltip', 'TooltipTrigger': 'tooltip'
}

def load_lucide_icons() -> List[str]:
    """Load Lucide icons from JSON file."""
    try:
        icons_path = HERE / 'lucide_icons.json'
        if icons_path.exists():
            with open(icons_path, 'r') as f:
                return json.load(f)
        else:
            # print('⚠️  lucide_icons.json not found. Using fallback icons.')
            return ['Sun', 'Moon', 'Star', 'Heart', 'User', 'Search', 'Menu', 'X', 'Camera', 'Bell', 'Check', 'AlertCircle', 'Banknote'] # Added Banknote for test case
    except Exception as e:
        # print(f'❌ Error loading lucide_icons.json: {e}')
        return ['Sun', 'Moon', 'Star', 'Heart', 'User', 'Search', 'Menu', 'X', 'Camera', 'Bell', 'Check', 'AlertCircle', 'Banknote'] # Added Banknote for test case

# Load Lucide icons
LUCIDE_ICONS_LIST = load_lucide_icons()

# --- Consolidated Component/Export Mapping for `detect_import_source` ---
# This dictionary maps a component name to its (import_source, import_type).
# The order of population here defines priority for name conflicts.
COMMON_EXPORTS_MAP: Dict[str, Tuple[str, str]] = {}

# 1. Next.js components (highest priority due to potential conflicts like 'Link')
NEXTJS_DEFINITIONS = {
    'Link': ('next/link', 'default'),
    'Image': ('next/image', 'default'),
    'Head': ('next/head', 'default'),
    'Script': ('next/script', 'default'),
    'useRouter': ('next/router', 'named'), # next/router's useRouter hook
    'withRouter': ('next/router', 'named'),
    'Router': ('next/router', 'named'), # For Router.push etc., can be namespace or default
    'usePathname': ('next/navigation', 'named'),
    'useSearchParams': ('next/navigation', 'named'),
    'redirect': ('next/navigation', 'named'),
    'NextRequest': ('next/server', 'named'),
    'NextResponse': ('next/server', 'named'),
}
for comp, info in NEXTJS_DEFINITIONS.items():
    COMMON_EXPORTS_MAP[comp] = info

# 2. React components (all named from 'react')
for comp in REACT_COMPONENTS:
    COMMON_EXPORTS_MAP[comp] = ('react', 'named')

# 3. Shadcn/ui components (all named)
for comp, kebab_name in SHADCN_COMPONENTS.items():
    COMMON_EXPORTS_MAP[comp] = (f'@/components/ui/{kebab_name}', 'named')

# 4. Lucide icons (all named from 'lucide-react')
# Only add if the name hasn't been mapped by a higher priority (e.g., 'Link' by Next.js)
for icon in LUCIDE_ICONS_LIST:
    if icon not in COMMON_EXPORTS_MAP:
        COMMON_EXPORTS_MAP[icon] = ('lucide-react', 'named')

# 5. Special utility 'cn'
COMMON_EXPORTS_MAP['cn'] = ('@/lib/utils', 'named')

# --- Core Logic Functions ---

def detect_import_source(component_name: str) -> Optional[Tuple[str, str]]:
    """
    Detect the import source and type ('named', 'default', 'namespace') for a component.
    Uses the pre-built COMMON_EXPORTS_MAP for efficient lookup and conflict resolution.
    """
    return COMMON_EXPORTS_MAP.get(component_name)

def find_used_components(content: str) -> List[str]:
    """Find all potential component/hook names used in the content."""
    components = set()
    
    # Find 'cn' utility usage: cn(...)
    if re.search(r'\bcn\s*\(', content):
        components.add('cn')
    
    # Find JSX components: <ComponentName or <ComponentName.Subcomponent
    # Captures `Accordion` from `<Accordion.Item>` and `AccordionItem` from `<AccordionItem>`
    jsx_pattern = r'<([A-Z][a-zA-Z0-9]*)' 
    for match in re.finditer(jsx_pattern, content):
        components.add(match.group(1))
    
    # Find hook usage: useComponentName
    hook_pattern = r'\b(use[A-Z][a-zA-Z0-9]*)\b'
    for match in re.finditer(hook_pattern, content):
        components.add(match.group(1))
    
    # Find direct component usage (e.g., ComponentName.prop or ComponentName() or memo(ComponentName))
    # Catches things like `React.Fragment`, `memo(MyComponent)`, `Children.map`, `Router.push`
    # The regex ensures it's a capitalized word followed by `.` or `(` or `( <capital letter>`.
    component_pattern = r'\b([A-Z][a-zA-Z0-9]*)(?:[.(]|\(\s*[A-Z])' 
    for match in re.finditer(component_pattern, content):
        components.add(match.group(1))
    
    return list(components)

def group_components_by_source(components: List[str]) -> Dict[Tuple[str, str], Set[str]]:
    """Group components by their import source and type."""
    grouped: Dict[Tuple[str, str], Set[str]] = {}
    
    for component in components:
        source_info = detect_import_source(component)
        if source_info:
            source, import_type = source_info
            key = (source, import_type)
            # For default/namespace imports, the component name itself is the "export" name
            # For named imports, it's a set of named components.
            grouped.setdefault(key, set()).add(component)
    
    return grouped

class ParsedImports(TypedDict):
    named: Dict[str, Set[str]]
    default: Dict[str, str]
    namespace: Dict[str, str]
    side_effect: List[str]
    ranges: List[Tuple[int, int]]

def parse_existing_imports(content: str) -> ParsedImports:
    """
    Parses existing imports into structured dictionaries based on type.
    Also returns line ranges for removal.
    """
    existing_named_imports_map: Dict[str, Set[str]] = {}
    existing_default_imports_map: Dict[str, str] = {}
    existing_namespace_imports_map: Dict[str, str] = {}
    existing_side_effect_lines: List[str] = []
    import_block_ranges: List[Tuple[int, int]] = []
    lines = content.split('\n')
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # 1. Match single-line named imports: `import { comp1, comp2 } from 'source';`
        match_single_named = re.match(r'^import\s*{\s*([^}]+?)\s*}\s*from\s*[\'"]([^\'"]+)[\'"];?$', line)
        if match_single_named:
            components_str, source = match_single_named.groups()
            components = {c.strip() for c in components_str.split(',') if c.strip()}
            existing_named_imports_map.setdefault(source, set()).update(components)
            import_block_ranges.append((i, i))
            i += 1
            continue
        
        # 2. Match start of multi-line named imports: `import {`
        match_multi_start = re.match(r'^import\s*{\s*$', line)
        if match_multi_start:
            start_block_line = i
            j = i + 1
            while j < len(lines):
                sub_line = lines[j].strip()
                match_multi_end = re.match(r'^\s*}(?:[^}]+)?\s*from\s*[\'"]([^\'"]+)[\'"];?$', sub_line)
                
                if match_multi_end:
                    source = match_multi_end.group(1)
                    components_in_block = set()
                    # Extract components from lines between '{' and '}'
                    for k in range(start_block_line + 1, j):
                        comp_line_content = lines[k].strip()
                        # Filter out lines that look like complete import statements themselves (malformed nested imports)
                        if not (re.match(r'^import\s*{[^}]+}\s*from\s*[\'"]', comp_line_content) or # Named import
                                re.match(r'^import\s+\S+\s+from\s*[\'"]', comp_line_content) or          # Default/Namespace import
                                re.match(r'^import\s*[\'"].*[\'"]', comp_line_content)):                   # Side-effect import
                            for comp_name in re.split(r'[,\s]+', comp_line_content):
                                if comp_name.strip():
                                    components_in_block.add(comp_name.strip())
                    
                    if source:
                        existing_named_imports_map.setdefault(source, set()).update(components_in_block)
                        import_block_ranges.append((start_block_line, j))
                    
                    i = j + 1
                    break
                j += 1
            else: # Inner loop completed without finding closing '}', malformed block
                i += 1
            continue
        
        # 3. Match default imports: `import Default from 'module';`
        match_default = re.match(r'^import\s+([A-Z_][a-zA-Z0-9_]*)\s+from\s*[\'"]([^\'"]+)[\'"];?$', line)
        if match_default:
            component_name, source = match_default.groups()
            existing_default_imports_map[source] = component_name
            import_block_ranges.append((i, i))
            i += 1
            continue

        # 4. Match namespace imports: `import * as Module from 'module';`
        match_namespace = re.match(r'^import\s+\*\s+as\s+([A-Z_][a-zA-Z0-9_]*)\s+from\s*[\'"]([^\'"]+)[\'"];?$', line)
        if match_namespace:
            alias, source = match_namespace.groups()
            existing_namespace_imports_map[source] = alias
            import_block_ranges.append((i, i))
            i += 1
            continue
        
        # 5. Match side-effect imports: `import 'styles.css';`
        match_side_effect = re.match(r'^(import\s*[\'"][^\'"]+[\'"];?)$', line)
        if match_side_effect:
            existing_side_effect_lines.append(match_side_effect.group(1))
            import_block_ranges.append((i, i))
            i += 1
            continue
            
        i += 1
            
    return ParsedImports(
        named=existing_named_imports_map,
        default=existing_default_imports_map,
        namespace=existing_namespace_imports_map,
        side_effect=existing_side_effect_lines,
        ranges=import_block_ranges
    )

def get_source_sort_key(source: str) -> Tuple[int, str]:
    """Custom sort key for import sources to ensure consistent ordering."""
    if source.startswith('@/components/ui/'): return (0, source) # Shadcn UI
    if source.startswith('@/lib/'): return (1, source) # Internal utils
    if source.startswith('next/'): return (2, source) # Next.js
    if source == 'react': return (3, source) # React
    if source == 'lucide-react': return (4, source) # Lucide React
    return (5, source) # Other npm packages or relative imports

def update_imports(content: str, desired_imports_grouped: Dict[Tuple[str, str], Set[str]]) -> str:
    """
    Updates imports in the content using a 'remove all and regenerate' strategy
    while preserving non-component-related imports and correctly handling types.
    """
    lines = content.split('\n')
    
    # 1. Parse existing imports from the content
    parsed_existing_imports = parse_existing_imports(content)
    import_block_ranges = parsed_existing_imports['ranges']

    # Initialize final import structures by copying *only* non-named existing imports.
    # Named imports will be determined solely by `desired_imports_grouped` (i.e., detected usage).
    final_named_imports: Dict[str, Set[str]] = {}
    final_default_imports: Dict[str, str] = dict(parsed_existing_imports['default'])
    final_namespace_imports: Dict[str, str] = dict(parsed_existing_imports['namespace'])
    final_side_effect_imports: List[str] = list(parsed_existing_imports['side_effect'])

    # 2. Populate final import structures based on `desired_imports_grouped` (components detected as used)
    for (source, import_type), components_set in desired_imports_grouped.items():
        if import_type == 'named':
            final_named_imports.setdefault(source, set()).update(components_set)
        elif import_type == 'default':
            if components_set:
                comp_name = list(components_set)[0]
                final_default_imports[source] = comp_name
                # If a component is now default imported, ensure it's not also named imported from this source
                if source in final_named_imports and comp_name in final_named_imports[source]:
                    final_named_imports[source].discard(comp_name)
                    if not final_named_imports[source]:
                        del final_named_imports[source]
        elif import_type == 'namespace':
            if components_set:
                alias = list(components_set)[0]
                final_namespace_imports[source] = alias
                # Similar cleanup for namespace imports
                if source in final_named_imports and alias in final_named_imports[source]:
                    final_named_imports[source].discard(alias)
                    if not final_named_imports[source]:
                        del final_named_imports[source]
    
    # 3. Identify and extract special top-level lines (shebang, 'use client')
    shebang_line = ""
    use_client_directive_line = ""
    initial_special_lines_indices: Set[int] = set()
    
    current_idx = 0
    if current_idx < len(lines) and lines[current_idx].startswith("#!"):
        shebang_line = lines[current_idx]
        initial_special_lines_indices.add(current_idx)
        current_idx += 1
        
    while current_idx < len(lines):
        line = lines[current_idx]
        stripped_line = line.strip()
        if re.match(r'^(?:"use client"|\'use client\');?$', stripped_line):
            use_client_directive_line = line
            initial_special_lines_indices.add(current_idx)
            current_idx += 1
            break
        if stripped_line == '' or stripped_line.startswith('//') or stripped_line.startswith('/*'):
            initial_special_lines_indices.add(current_idx)
            current_idx += 1
            continue
        break # Stop if any other code is encountered

    # Filter out lines that are part of import blocks OR the special top-level lines
    lines_to_keep_indices = set(range(len(lines)))
    for start, end in import_block_ranges:
        for i in range(start, end + 1):
            lines_to_keep_indices.discard(i)
    for idx in initial_special_lines_indices:
        lines_to_keep_indices.discard(idx)

    non_import_lines = []
    for i in range(len(lines)):
        if i not in lines_to_keep_indices:
            continue
        non_import_lines.append(lines[i])
        
    # 4. Generate new, correctly formatted import statements
    generated_import_lines: List[str] = []
    
    # Order: Side-effect, Namespace, Default, Named (grouped by custom sort key)
    
    # Side-effect imports
    if final_side_effect_imports:
        generated_import_lines.extend(sorted(final_side_effect_imports))

    # Namespace imports
    namespace_sources = sorted(final_namespace_imports.keys(), key=get_source_sort_key)
    if namespace_sources:
        if generated_import_lines and generated_import_lines[-1].strip() != '':
            generated_import_lines.append('')
        for source in namespace_sources:
            alias = final_namespace_imports[source]
            generated_import_lines.append(f"import * as {alias} from '{source}';")

    # Default imports
    default_sources = sorted(final_default_imports.keys(), key=get_source_sort_key)
    if default_sources:
        if generated_import_lines and generated_import_lines[-1].strip() != '':
            generated_import_lines.append('')
        for source in default_sources:
            comp_name = final_default_imports[source]
            generated_import_lines.append(f"import {comp_name} from '{source}';")

    # Named imports
    named_sources = sorted(final_named_imports.keys(), key=get_source_sort_key)
    if named_sources:
        if generated_import_lines and generated_import_lines[-1].strip() != '':
            generated_import_lines.append('')
        for source in named_sources:
            components = sorted(list(final_named_imports[source]))
            if not components: # Should not happen after cleanup
                continue

            if len(components) <= 3:
                generated_import_lines.append(f"import {{ {', '.join(components)} }} from '{source}';")
            else:
                generated_import_lines.append(f"import {{")
                for comp in components:
                    generated_import_lines.append(f"  {comp},")
                generated_import_lines[-1] = generated_import_lines[-1].rstrip(',') # Remove trailing comma from last component
                generated_import_lines.append(f"}} from '{source}';")

    # 5. Reconstruct the file content
    reconstructed_lines = []
    if shebang_line:
        reconstructed_lines.append(shebang_line)
    if use_client_directive_line:
        reconstructed_lines.append(use_client_directive_line)

    if generated_import_lines:
        if reconstructed_lines and reconstructed_lines[-1].strip() != '':
            reconstructed_lines.append('') # Add blank line before imports if content precedes
        reconstructed_lines.extend(generated_import_lines)
        if non_import_lines:
            reconstructed_lines.append('') # Add blank line after imports if code follows

    reconstructed_lines.extend(non_import_lines)

    # Final cleanup: ensure no excessive blank lines at the end of the file
    while reconstructed_lines and reconstructed_lines[-1].strip() == '':
        reconstructed_lines.pop()

    return '\n'.join(reconstructed_lines)

def process_file(file_path: str) -> None:
    """Process a single file."""
    path = Path(file_path)
    if not path.exists():
        print(f"❌ File not found: {file_path}")
        return
    
    print(f"🔍 Processing: {file_path}")
    
    content = path.read_text(encoding='utf-8')
    
    used_components = find_used_components(content)
    grouped_components_by_source = group_components_by_source(used_components)
    
    # print("📥 Components to ensure imported (found in code or existing valid imports):")
    # if grouped_components_by_source:
    #     for (source, import_type), components in grouped_components_by_source.items():
    #         print(f"   {source} ({import_type}): {', '.join(components)}")
    # else:
    #     print("   (None new/known detected in code directly.)")
    
    updated_content = update_imports(content, grouped_components_by_source)
    
    if updated_content != content:
        path.write_text(updated_content, encoding='utf-8')
        print(f"✨ Updated {file_path}")
    else:
        print("ℹ️  No changes needed")

def process_directory(dir_path: str) -> None:
    """Process all TypeScript/JavaScript files in a directory."""
    path = Path(dir_path)
    exclude_dirs = {'node_modules', '.git', '.next', 'dist', 'build'}
    
    for item in path.iterdir():
        if item.is_dir() and item.name not in exclude_dirs:
            process_directory(str(item))
        elif item.is_file() and item.suffix in {'.ts', '.tsx', '.js', '.jsx'}:
            process_file(str(item))

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