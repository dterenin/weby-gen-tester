#!/usr/bin/env python3

import os
import re
import json
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional

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
    'Accordion': 'accordion',
    'AccordionContent': 'accordion',
    'AccordionItem': 'accordion',
    'AccordionTrigger': 'accordion',
    'Alert': 'alert',
    'AlertDescription': 'alert',
    'AlertTitle': 'alert',
    'AlertDialog': 'alert-dialog',
    'AlertDialogAction': 'alert-dialog',
    'AlertDialogCancel': 'alert-dialog',
    'AlertDialogContent': 'alert-dialog',
    'AlertDialogDescription': 'alert-dialog',
    'AlertDialogFooter': 'alert-dialog',
    'AlertDialogHeader': 'alert-dialog',
    'AlertDialogTitle': 'alert-dialog',
    'AlertDialogTrigger': 'alert-dialog',
    'AspectRatio': 'aspect-ratio',
    'Avatar': 'avatar',
    'AvatarFallback': 'avatar',
    'AvatarImage': 'avatar',
    'Badge': 'badge',
    'Button': 'button',
    'Calendar': 'calendar',
    'Card': 'card',
    'CardContent': 'card',
    'CardDescription': 'card',
    'CardFooter': 'card',
    'CardHeader': 'card',
    'CardTitle': 'card',
    'Carousel': 'carousel',
    'CarouselContent': 'carousel',
    'CarouselItem': 'carousel',
    'CarouselNext': 'carousel',
    'CarouselPrevious': 'carousel',
    'Checkbox': 'checkbox',
    'Collapsible': 'collapsible',
    'CollapsibleContent': 'collapsible',
    'CollapsibleTrigger': 'collapsible',
    'Command': 'command',
    'CommandDialog': 'command',
    'CommandEmpty': 'command',
    'CommandGroup': 'command',
    'CommandInput': 'command',
    'CommandItem': 'command',
    'CommandList': 'command',
    'CommandSeparator': 'command',
    'CommandShortcut': 'command',
    'ContextMenu': 'context-menu',
    'ContextMenuCheckboxItem': 'context-menu',
    'ContextMenuContent': 'context-menu',
    'ContextMenuItem': 'context-menu',
    'ContextMenuLabel': 'context-menu',
    'ContextMenuRadioGroup': 'context-menu',
    'ContextMenuRadioItem': 'context-menu',
    'ContextMenuSeparator': 'context-menu',
    'ContextMenuShortcut': 'context-menu',
    'ContextMenuSub': 'context-menu',
    'ContextMenuSubContent': 'context-menu',
    'ContextMenuSubTrigger': 'context-menu',
    'ContextMenuTrigger': 'context-menu',
    'Dialog': 'dialog',
    'DialogContent': 'dialog',
    'DialogDescription': 'dialog',
    'DialogFooter': 'dialog',
    'DialogHeader': 'dialog',
    'DialogTitle': 'dialog',
    'DialogTrigger': 'dialog',
    'Drawer': 'drawer',
    'DrawerClose': 'drawer',
    'DrawerContent': 'drawer',
    'DrawerDescription': 'drawer',
    'DrawerFooter': 'drawer',
    'DrawerHeader': 'drawer',
    'DrawerTitle': 'drawer',
    'DrawerTrigger': 'drawer',
    'DropdownMenu': 'dropdown-menu',
    'DropdownMenuCheckboxItem': 'dropdown-menu',
    'DropdownMenuContent': 'dropdown-menu',
    'DropdownMenuGroup': 'dropdown-menu',
    'DropdownMenuItem': 'dropdown-menu',
    'DropdownMenuLabel': 'dropdown-menu',
    'DropdownMenuPortal': 'dropdown-menu',
    'DropdownMenuRadioGroup': 'dropdown-menu',
    'DropdownMenuRadioItem': 'dropdown-menu',
    'DropdownMenuSeparator': 'dropdown-menu',
    'DropdownMenuShortcut': 'dropdown-menu',
    'DropdownMenuSub': 'dropdown-menu',
    'DropdownMenuSubContent': 'dropdown-menu',
    'DropdownMenuSubTrigger': 'dropdown-menu',
    'DropdownMenuTrigger': 'dropdown-menu',
    'Form': 'form',
    'FormControl': 'form',
    'FormDescription': 'form',
    'FormField': 'form',
    'FormItem': 'form',
    'FormLabel': 'form',
    'FormMessage': 'form',
    'HoverCard': 'hover-card',
    'HoverCardContent': 'hover-card',
    'HoverCardTrigger': 'hover-card',
    'Input': 'input',
    'Label': 'label',
    'Menubar': 'menubar',
    'MenubarCheckboxItem': 'menubar',
    'MenubarContent': 'menubar',
    'MenubarItem': 'menubar',
    'MenubarLabel': 'menubar',
    'MenubarMenu': 'menubar',
    'MenubarRadioGroup': 'menubar',
    'MenubarRadioItem': 'menubar',
    'MenubarSeparator': 'menubar',
    'MenubarShortcut': 'menubar',
    'MenubarSub': 'menubar',
    'MenubarSubContent': 'menubar',
    'MenubarSubTrigger': 'menubar',
    'MenubarTrigger': 'menubar',
    'NavigationMenu': 'navigation-menu',
    'NavigationMenuContent': 'navigation-menu',
    'NavigationMenuIndicator': 'navigation-menu',
    'NavigationMenuItem': 'navigation-menu',
    'NavigationMenuLink': 'navigation-menu',
    'NavigationMenuList': 'navigation-menu',
    'NavigationMenuTrigger': 'navigation-menu',
    'NavigationMenuViewport': 'navigation-menu',
    'Pagination': 'pagination',
    'PaginationContent': 'pagination',
    'PaginationEllipsis': 'pagination',
    'PaginationItem': 'pagination',
    'PaginationLink': 'pagination',
    'PaginationNext': 'pagination',
    'PaginationPrevious': 'pagination',
    'Popover': 'popover',
    'PopoverContent': 'popover',
    'PopoverTrigger': 'popover',
    'Progress': 'progress',
    'RadioGroup': 'radio-group',
    'RadioGroupItem': 'radio-group',
    'ScrollArea': 'scroll-area',
    'ScrollBar': 'scroll-area',
    'Select': 'select',
    'SelectContent': 'select',
    'SelectGroup': 'select',
    'SelectItem': 'select',
    'SelectLabel': 'select',
    'SelectSeparator': 'select',
    'SelectTrigger': 'select',
    'SelectValue': 'select',
    'Separator': 'separator',
    'Sheet': 'sheet',
    'SheetClose': 'sheet',
    'SheetContent': 'sheet',
    'SheetDescription': 'sheet',
    'SheetFooter': 'sheet',
    'SheetHeader': 'sheet',
    'SheetTitle': 'sheet',
    'SheetTrigger': 'sheet',
    'Skeleton': 'skeleton',
    'Slider': 'slider',
    'Switch': 'switch',
    'Table': 'table',
    'TableBody': 'table',
    'TableCaption': 'table',
    'TableCell': 'table',
    'TableFooter': 'table',
    'TableHead': 'table',
    'TableHeader': 'table',
    'TableRow': 'table',
    'Tabs': 'tabs',
    'TabsContent': 'tabs',
    'TabsList': 'tabs',
    'TabsTrigger': 'tabs',
    'Textarea': 'textarea',
    'Toast': 'toast',
    'ToastAction': 'toast',
    'ToastClose': 'toast',
    'ToastDescription': 'toast',
    'ToastProvider': 'toast',
    'ToastTitle': 'toast',
    'ToastViewport': 'toast',
    'Toggle': 'toggle',
    'ToggleGroup': 'toggle-group',
    'ToggleGroupItem': 'toggle-group',
    'Tooltip': 'tooltip',
    'TooltipContent': 'tooltip',
    'TooltipProvider': 'tooltip',
    'TooltipTrigger': 'tooltip'
}

# Next.js patterns
NEXTJS_IMPORTS = {
    'next/router': ['useRouter', 'withRouter', 'Router'],
    'next/head': ['Head'],
    'next/image': ['Image'],
    'next/link': ['Link'],
    'next/script': ['Script'],
    'next/navigation': ['usePathname', 'useRouter', 'useSearchParams', 'redirect'],
    'next/server': ['NextRequest', 'NextResponse'],
}

def load_lucide_icons() -> List[str]:
    """Load Lucide icons from JSON file."""
    try:
        icons_path = HERE / 'lucide_icons.json'
        if icons_path.exists():
            with open(icons_path, 'r') as f:
                return json.load(f)
        else:
            print('⚠️  lucide_icons.json not found. Using fallback icons.')
            # A larger fallback list for better coverage in testing
            return ['Sun', 'Moon', 'Star', 'Heart', 'User', 'Search', 'Menu', 'X', 'Camera', 'Bell', 'Check', 'AlertCircle']
    except Exception as e:
        print(f'❌ Error loading lucide_icons.json: {e}')
        # A larger fallback list for better coverage in testing
        return ['Sun', 'Moon', 'Star', 'Heart', 'User', 'Search', 'Menu', 'X', 'Camera', 'Bell', 'Check', 'AlertCircle']

# Load Lucide icons
LUCIDE_ICONS = load_lucide_icons()

def detect_import_source(component_name: str) -> Optional[str]:
    """Detect the import source for a component."""
    # Check for cn utility
    if component_name == 'cn':
        return '@/lib/utils'
    
    # Check shadcn/ui components
    if component_name in SHADCN_COMPONENTS:
        return f'@/components/ui/{SHADCN_COMPONENTS[component_name]}'
    
    # Check Lucide React
    if component_name in LUCIDE_ICONS:
        return 'lucide-react'
    
    # Check React
    if component_name in REACT_COMPONENTS:
        return 'react'
    
    # Check Next.js
    for source, exports in NEXTJS_IMPORTS.items():
        if component_name in exports:
            return source
    
    return None

def find_used_components(content: str) -> List[str]:
    """Find all components used in the content."""
    components = set()
    
    # Find cn utility usage: cn(...)
    if re.search(r'\bcn\s*\(', content):
        components.add('cn')
    
    # Find JSX components: <ComponentName or <ComponentName.Subcomponent
    # This pattern is refined to capture the top-level component,
    # e.g., for <Accordion.Item>, it will capture 'Accordion'.
    # If the intent is to capture 'AccordionItem' then the SHADCN_COMPONENTS map
    # already has 'AccordionItem' as a key, so `detect_import_source` will handle it.
    # The regex `([A-Z][a-zA-Z0-9]*)` gets `Accordion` from `<Accordion.Item`.
    # It also gets `AccordionItem` from `<AccordionItem`. This is fine.
    jsx_pattern = r'<([A-Z][a-zA-Z0-9]*)' 
    for match in re.finditer(jsx_pattern, content):
        components.add(match.group(1))
    
    # Find hook usage: useComponentName
    hook_pattern = r'\b(use[A-Z][a-zA-Z0-9]*)\b'
    for match in re.finditer(hook_pattern, content):
        components.add(match.group(1))
    
    # Find direct component usage (e.g., ComponentName.prop or ComponentName() or memo(ComponentName))
    # This tries to catch things like `React.Fragment`, `memo(MyComponent)`, `Children.map`, `Router.push`
    # It might over-match, but `detect_import_source` will filter unknowns.
    # `([A-Z][a-zA-Z0-9]*)` for the component name
    # `(?:[.(])` non-capturing group for dot or opening parenthesis.
    # `|\(\s*[A-Z]` to catch `memo(Component)` where `Component` is capitalized.
    component_pattern = r'\b([A-Z][a-zA-Z0-9]*)(?:[.(]|\(\s*[A-Z])' 
    for match in re.finditer(component_pattern, content):
        components.add(match.group(1))
    
    return list(components)

def group_components_by_source(components: List[str]) -> Dict[str, List[str]]:
    """Group components by their import source."""
    grouped: Dict[str, Set[str]] = {} # Use Set to avoid duplicates
    
    for component in components:
        source = detect_import_source(component)
        if source:
            grouped.setdefault(source, set()).add(component)
    
    # Convert sets back to sorted lists for consistent output
    return {source: sorted(list(comps)) for source, comps in grouped.items()}

def parse_existing_imports(content: str) -> Tuple[Dict[str, Set[str]], List[Tuple[int, int]]]:
    """
    Parse existing imports and return:
    1. A dict of source -> set of components found in existing imports.
    2. A list of (start_line, end_line) tuples for each recognized import block.
       This is used to remove existing imports before generating new ones.
       Malformed nested imports (like `import { Button }` inside another `import { ... }` block)
       will not be recognized as separate import blocks by this parser. They will be ignored
       as part of the outer block's content when extracting components.
       This strategy effectively fixes such malformations by removing them and re-adding
       correctly formatted imports for any used components.
    """
    existing_imports_map: Dict[str, Set[str]] = {}
    import_block_ranges: List[Tuple[int, int]] = []
    lines = content.split('\n')
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # 1. Match single-line named imports: `import { comp1, comp2 } from 'source';`
        # Using non-greedy `[^}]+?` for component list and optional semicolon.
        match_single = re.match(r'^import\s*{\s*([^}]+?)\s*}\s*from\s*[\'"]([^\'"]+)[\'"];?$', line)
        if match_single:
            components_str, source = match_single.groups()
            components = {c.strip() for c in components_str.split(',') if c.strip()}
            existing_imports_map.setdefault(source, set()).update(components)
            import_block_ranges.append((i, i)) # Store line range for removal
            i += 1
            continue
        
        # 2. Match start of multi-line named imports: `import {`
        match_multi_start = re.match(r'^import\s*{\s*$', line)
        if match_multi_start:
            start_block_line = i
            j = i + 1 # Start searching from the next line for the closing brace
            
            # Look for the matching closing brace and 'from' statement
            while j < len(lines):
                sub_line = lines[j].strip()
                # Check for the closing brace and source on this line.
                # `(?:[^}]+)?` allows for non-component content on the last line (e.g. comments or whitespace)
                # before `from '...'`.
                match_multi_end = re.match(r'^\s*}(?:[^}]+)?\s*from\s*[\'"]([^\'"]+)[\'"];?$', sub_line)
                
                if match_multi_end:
                    source = match_multi_end.group(1)
                    
                    # Extract components from lines *between* start_block_line and j
                    components_in_block = set()
                    # Iterate from line after '{' to line before '}'
                    for k in range(start_block_line + 1, j):
                        comp_line_content = lines[k].strip()
                        # Filter out lines that look like a complete import statement themselves.
                        # This addresses the malformed nested import.
                        # It also filters out other types of imports like default or namespace imports.
                        if not (re.match(r'^import\s*{\s*[^}]+?\s*}\s*from\s*[\'"]', comp_line_content) or # Named import
                                re.match(r'^import\s+\S+\s+from\s*[\'"]', comp_line_content) or          # Default/Namespace import
                                re.match(r'^import\s*[\'"].*[\'"]', comp_line_content)):                   # Side-effect import
                            
                            # Split by comma, remove whitespace, and add to set
                            # Use regex to split to handle various whitespace and commas
                            for comp_name in re.split(r'[,\s]+', comp_line_content):
                                if comp_name.strip():
                                    components_in_block.add(comp_name.strip())
                    
                    if source: # Ensure a valid source was found
                        existing_imports_map.setdefault(source, set()).update(components_in_block)
                        import_block_ranges.append((start_block_line, j))
                    
                    i = j + 1 # Move past this multi-line import block
                    break # Break inner while loop, continue outer loop from new 'i'
                
                j += 1
            else: # Inner loop completed without finding closing '}'
                # This indicates an unclosed multi-line import block (malformed).
                # We skip it and don't add its content to existing_imports_map.
                i += 1
            continue # Continue outer loop
        
        # 3. Catch general import statements not covered by named imports.
        # These are usually default imports, namespace imports, or side-effect imports.
        # We don't extract components for these, but we mark the line for removal
        # to ensure they are preserved by the "remove all and regenerate" strategy.
        # This regex covers:
        # - `import 'styles.css';`
        # - `import Default from 'module';`
        # - `import * as Module from 'module';`
        match_general_import = re.match(r'^\s*import\s+(?:[\'"][^\'"]+[\'"]|[^;]+?\s+from\s*[\'"][^\'"]+[\'"]|\*\s+as\s+\S+\s+from\s*[\'"][^\'"]+[\'"]);?$', line)
        if match_general_import:
            import_block_ranges.append((i, i))
            i += 1
            continue
            
        i += 1
            
    return existing_imports_map, import_block_ranges

def update_imports(content: str, new_imports: Dict[str, List[str]]) -> str:
    """
    Update imports in the content using a 'remove all and regenerate' strategy.
    
    1. Parse existing imports and identify their line ranges.
    2. Identify and extract special top-level lines (shebang, 'use client').
    3. Collect all lines that are NOT part of any identified import block or special top-level line.
    4. Generate new, correctly formatted import statements from scratch based on
       all used components (from `find_used_components`) and previously identified
       components (from `parse_existing_imports`).
    5. Reconstruct the file by inserting the special lines first, then new imports,
       followed by the remaining code.
    """
    lines = content.split('\n')
    
    # Step 1: Parse existing imports and identify their line ranges for removal
    existing_imports_map, import_block_ranges = parse_existing_imports(content)
    
    # Convert `new_imports` (Dict[str, List[str]]) to Dict[str, Set[str]] for easier merging.
    # `new_imports` represents the components *detected as used in the code*.
    desired_imports_map: Dict[str, Set[str]] = {
        source: set(components) for source, components in new_imports.items()
    }

    # Merge all components that should be imported:
    # 1. Components previously identified in *valid* import statements.
    # 2. Components detected as *used* in the file.
    all_final_imports: Dict[str, Set[str]] = {}
    
    for source, components_set in existing_imports_map.items():
        all_final_imports.setdefault(source, set()).update(components_set)
    
    for source, components_set in desired_imports_map.items():
        all_final_imports.setdefault(source, set()).update(components_set)

    # Step 2: Identify and extract special top-level lines (shebang, 'use client')
    # and collect non-import lines for the main content.
    
    shebang_line = ""
    use_client_directive_line = ""
    initial_special_lines_indices: Set[int] = set() # Indices of lines for shebang, use client, and leading blank/comments
    
    current_idx = 0
    
    # Handle shebang (must be the very first line)
    if current_idx < len(lines) and lines[current_idx].startswith("#!"):
        shebang_line = lines[current_idx]
        initial_special_lines_indices.add(current_idx)
        current_idx += 1
        
    # Handle 'use client' directive and preceding blank/comment lines
    # It must be before any actual JS expressions, usually directly after shebang/comments.
    while current_idx < len(lines):
        line = lines[current_idx]
        stripped_line = line.strip()
        
        # Check for "use client" directive
        if re.match(r'^(?:"use client"|\'use client\');?$', stripped_line):
            use_client_directive_line = line # Keep original formatting (indentation, semicolon)
            initial_special_lines_indices.add(current_idx)
            current_idx += 1
            break # Found 'use client', no more directives should follow
        
        # Allow comments and blank lines before 'use client' at the very top
        if stripped_line == '' or stripped_line.startswith('//') or stripped_line.startswith('/*'):
            initial_special_lines_indices.add(current_idx)
            current_idx += 1
            continue # Keep scanning for 'use client'
        
        # If we hit an import statement or any other JavaScript expression,
        # it means "use client" (if present) is not at its valid top position.
        # So we stop scanning for it.
        if stripped_line.startswith('import ') or \
           re.match(r'^(const|let|var|function|class|export|enum|type|interface)\s', stripped_line) or \
           re.match(r'^[\w\s]+=[\s\(]', stripped_line) or \
           re.match(r'^\s*<[A-Z]', stripped_line): # Basic check for JSX/Component definition start
            break # Stop looking for 'use client'
            
        # If it's none of the above, it's an unhandled top-level line that's not a directive.
        # This implies 'use client' won't be found in a valid position.
        break 

    # Filter out lines that are part of import blocks OR the special top-level lines
    lines_to_keep_indices = set(range(len(lines)))
    for start, end in import_block_ranges:
        for i in range(start, end + 1):
            lines_to_keep_indices.discard(i)
    
    for idx in initial_special_lines_indices:
        lines_to_keep_indices.discard(idx)

    # Build the main content lines (non-import, non-special-top-level lines)
    non_import_lines = []
    for i in range(len(lines)): # Iterate through original lines
        if i not in lines_to_keep_indices: # If this line was marked for removal, skip it
            continue
        non_import_lines.append(lines[i]) # Otherwise, keep it
        
    # Step 3: Generate new, correctly formatted import statements
    generated_import_lines: List[str] = []
    
    # Sort sources and components for consistent output order
    sorted_sources = sorted(all_final_imports.keys())

    for source in sorted_sources:
        components = sorted(list(all_final_imports[source]))
        if not components: # Should not happen if logic is correct, but defensive
            continue

        if len(components) <= 3: # Keep small imports on a single line
            generated_import_lines.append(f"import {{ {', '.join(components)} }} from '{source}';")
        else: # Format larger imports as multi-line
            generated_import_lines.append(f"import {{")
            for comp in components:
                generated_import_lines.append(f"  {comp},")
            # Remove trailing comma from the last component
            generated_import_lines[-1] = generated_import_lines[-1].rstrip(',') 
            generated_import_lines.append(f"}} from '{source}';")
    
    # Step 4: Reconstruct the file content in the correct order
    reconstructed_lines = []
    
    # Add shebang first
    if shebang_line:
        reconstructed_lines.append(shebang_line)
    
    # Add 'use client' directive next, after shebang (if present)
    if use_client_directive_line:
        # A blank line after shebang and before 'use client' is usually not needed/desired.
        reconstructed_lines.append(use_client_directive_line)

    # Add new imports only if there are any
    if generated_import_lines:
        # Add a blank line before imports if there's content before it (shebang or 'use client')
        # AND the last added line wasn't already blank (not just whitespace).
        if reconstructed_lines and reconstructed_lines[-1].strip() != '':
            reconstructed_lines.append('')
             
        reconstructed_lines.extend(generated_import_lines)
        
        # Add a blank line after imports, before other code, only if there's actual code following
        # AND the last added line wasn't already blank (not just whitespace).
        if non_import_lines and reconstructed_lines[-1].strip() != '':
            reconstructed_lines.append('')
    
    # Add the remaining code/non-import lines
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
    
    # Find all components actually used in the file's code (excluding import statements)
    used_components = find_used_components(content)
    
    # Group them by their determined import source
    grouped_components_by_source = group_components_by_source(used_components)
    
    if not grouped_components_by_source:
        print("ℹ️  No known components detected in code. Checking existing imports for reformatting.")

    # print(f"📦 Found components: {', '.join(used_components)}") # Too verbose if many
    print("📥 Components to ensure imported (found in code or existing valid imports):")
    if grouped_components_by_source:
        for source, components in grouped_components_by_source.items():
            print(f"   {source}: {', '.join(components)}")
    else:
        print("   (None new/known detected in code directly.)") # Will rely on parsed_existing_imports
    
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