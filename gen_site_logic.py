# gen_site_logic.py
import os
import re
import subprocess
import json
import shutil
import time
import allure # Keep for potential direct attachments if ever needed, though primary control is in test script

# --- Start of gen_site_logic.py ---

# Dependencies to add or ensure specific versions for, on top of what create-next-app installs.
ADDITIONAL_DEPENDENCIES: dict[str, str] = {
    "@dnd-kit/core": "^6.3.1",
    "@dnd-kit/modifiers": "^9.0.0",
    "@dnd-kit/sortable": "^10.0.0",
    "@dnd-kit/utilities": "^3.2.2",
    "@hello-pangea/dnd": "^18.0.1",
    "@hookform/resolvers": "^5.0.1",
    "@radix-ui/react-accordion": "^1.2.4",
    "@radix-ui/react-alert-dialog": "^1.1.7",
    "@radix-ui/react-aspect-ratio": "^1.1.3",
    "@radix-ui/react-avatar": "^1.1.4",
    "@radix-ui/react-checkbox": "^1.1.5",
    "@radix-ui/react-collapsible": "^1.1.4",
    "@radix-ui/react-context-menu": "^2.2.7",
    "@radix-ui/react-dialog": "^1.1.7",
    "@radix-ui/react-dropdown-menu": "^2.1.7",
    "@radix-ui/react-hover-card": "^1.1.7",
    "@radix-ui/react-label": "^2.1.3",
    "@radix-ui/react-menubar": "^1.1.7",
    "@radix-ui/react-navigation-menu": "^1.2.6",
    "@radix-ui/react-popover": "^1.1.7",
    "@radix-ui/react-progress": "^1.1.3",
    "@radix-ui/react-radio-group": "^1.2.4",
    "@radix-ui/react-scroll-area": "^1.2.4",
    "@radix-ui/react-select": "^2.1.7",
    "@radix-ui/react-separator": "^1.1.3",
    "@radix-ui/react-slider": "^1.2.4",
    "@radix-ui/react-slot": "^1.2.0",
    "@radix-ui/react-switch": "^1.1.4",
    "@radix-ui/react-tabs": "^1.1.4",
    "@radix-ui/react-toast": "^1.2.10",
    "@radix-ui/react-toggle": "^1.1.3",
    "@radix-ui/react-toggle-group": "^1.1.3",
    "@radix-ui/react-tooltip": "^1.2.0",
    "body-parser": "^2.2.0",
    "class-variance-authority": "^0.7.1",
    "clsx": "^2.1.1",
    "cmdk": "^1.1.1",
    "date-fns": "^3.6.0",
    "embla-carousel-react": "^8.6.0",
    "express": "^5.1.0",
    "input-otp": "^1.4.2",
    "lucide-react": "^0.488.0",
    "motion": "^12.6.5",
    "next": "15.3.0",
    "next-themes": "^0.4.6",
    "puppeteer": "^24.8.2",
    "react": "^19.0.0",
    "react-day-picker": "^8.10.1",
    "react-dnd": "^16.0.1",
    "react-dnd-html5-backend": "^16.0.1",
    "react-dom": "^19.0.0",
    "react-hook-form": "^7.55.0",
    "react-resizable-panels": "^2.1.7",
    "recharts": "^2.15.2",
    "sonner": "^2.0.3",
    "tailwind-merge": "^3.2.0",
    "three": "^0.176.0",
    "tw-animate-css": "^1.2.5",
    "vaul": "^1.1.2",
    "zod": "^3.24.2"
}


ADDITIONAL_DEV_DEPENDENCIES: dict[str, str] = {
    "@babel/eslint-parser": "^7.27.0",
    "@eslint/eslintrc": "^3",
    "@tailwindcss/postcss": "^4",
    "@types/node": "^20",
    "@types/react": "^19",
    "@types/react-dom": "^19",
    "eslint": "^9.25.1",
    "eslint-config-next": "15.3.0",
    "eslint-plugin-import": "^2.31.0",
    "eslint-plugin-react": "^7.37.5",
    "eslint-plugin-react-hooks": "^5.2.0",
    "tailwindcss": "^4",
    "typescript": "^5",
    "prettier": "latest",
    "prettier-plugin-tailwindcss": "latest",
    "tailwindcss-animate": "latest"
}

# --- Templates for essential configuration and placeholder files ---
APP_LAYOUT_TSX_TEMPLATE = """
import './globals.css';
import { Inter as FontSans } from 'next/font/google';
import { cn } from '@/lib/utils';
import { Toaster } from '@/components/ui/sonner';
import { ThemeProvider } from '@/components/theme-provider';

const fontSans = FontSans({
  subsets: ['latin'],
  variable: '--font-sans',
});

export const metadata = {
  title: 'Generated Next.js Site',
  description: 'A site generated by AI.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body
        className={cn(
          'min-h-screen bg-background font-sans antialiased',
          fontSans.variable
        )}
      >
        <ThemeProvider
          attribute="class"
          defaultTheme="system"
          enableSystem
          disableTransitionOnChange
        >
          {children}
        </ThemeProvider>
        <Toaster />
      </body>
    </html>
  );
}
"""

APP_PAGE_TSX_TEMPLATE = """
export default function HomePage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center">
      <main className="flex flex-1 flex-col items-center justify-center p-4 text-center">
        <h1 className="text-4xl font-bold">Welcome!</h1>
        <p className="mt-2 text-lg text-muted-foreground">
          LLM content for page.tsx will be placed here.
        </p>
      </main>
    </div>
  );
}
"""

LIB_UTILS_TS_TEMPLATE = """
import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
"""

COMPONENTS_THEME_PROVIDER_TEMPLATE = """
"use client"
import * as React from "react"
import { ThemeProvider as NextThemesProvider, type ThemeProviderProps } from "next-themes";

export function ThemeProvider({ children, ...props }: ThemeProviderProps) {
  return <NextThemesProvider {...props}>{children}</NextThemesProvider>
}
"""

MODE_TOGGLE_TEMPLATE = """
"use client"
import * as React from "react"
import { Moon, Sun } from "lucide-react"
import { useTheme } from "next-themes"
import { Button } from "@/components/ui/button"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"

export function ModeToggle() {
  const { setTheme } = useTheme()
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon">
          <Sun className="h-[1.2rem] w-[1.2rem] rotate-0 scale-100 transition-all dark:-rotate-90 dark:scale-0" />
          <Moon className="absolute h-[1.2rem] w-[1.2rem] rotate-90 scale-0 transition-all dark:rotate-0 dark:scale-100" />
          <span className="sr-only">Toggle theme</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem onClick={() => setTheme("light")}>Light</DropdownMenuItem>
        <DropdownMenuItem onClick={() => setTheme("dark")}>Dark</DropdownMenuItem>
        <DropdownMenuItem onClick={() => setTheme("system")}>System</DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
"""

HEADER_PLACEHOLDER_TEMPLATE = """
"use client";
import Link from "next/link";
import { ModeToggle } from "@/components/mode-toggle";
import { Building2 } from "lucide-react";

export function Header() {
  return (
    <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container flex h-14 items-center justify-between">
        <Link href="/" className="flex items-center gap-2">
           <Building2 className="h-6 w-6 text-primary" />
          <span className="text-xl font-bold tracking-wide text-primary">SiteName</span>
        </Link>
        <nav className="flex items-center gap-4">
          <ModeToggle />
        </nav>
      </div>
    </header>
  );
}
"""

FOOTER_PLACEHOLDER_TEMPLATE = """
"use client";

export function Footer() {
  return (
    <footer className="p-4 border-t text-center text-sm text-muted-foreground">
      © {new Date().getFullYear()} SiteName. All rights reserved.
    </footer>
  );
}
"""

USE_KEY_PRESS_TEMPLATE = """
import { useEffect, useCallback } from 'react';

export function useKeyPress(targetKey: string, handler: () => void) {
  const handleKeyPress = useCallback((event: KeyboardEvent) => {
    if (event.key === targetKey) {
      handler();
    }
  }, [handler, targetKey]);

  useEffect(() => {
    window.addEventListener('keydown', handleKeyPress);
    return () => {
      window.removeEventListener('keydown', handleKeyPress);
    };
  }, [handleKeyPress]);
}
"""

def _create_file_with_content(filepath: str, content: str, results_dict: dict, file_description: str):
    """Helper function to create a file with given content."""
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        file_content_to_write = content if file_description.startswith("AI-generated file") else content.strip()
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(file_content_to_write + ('\n' if not file_description.startswith("AI-generated file") else ''))
    except Exception as e:
        error_msg = f"Error creating/writing file {file_description} ({filepath}): {e}"
        print(f"ERROR: {error_msg}") # Keep console print for immediate feedback during script dev
        if "error_messages" not in results_dict: results_dict["error_messages"] = []
        results_dict["error_messages"].append(error_msg)

def _run_command_util(cmd_list_or_str, cwd, results_dict, timeout=120, check_on_error=True, command_name="Command", log_output_to_console=False, shell=False, std_input=None):
    """
    Utility to run a shell command and capture its output.
    Outputs are stored in results_dict["command_outputs_map"][command_name].
    """
    if shell and not isinstance(cmd_list_or_str, str):
        raise ValueError("cmd_list_or_str must be a string if shell=True")
    if not shell and not isinstance(cmd_list_or_str, list):
        raise ValueError("cmd_list_or_str must be a list if shell=False")

    display_cmd = cmd_list_or_str if isinstance(cmd_list_or_str, str) else ' '.join(cmd_list_or_str)
    print(f"[{time.strftime('%H:%M:%S')}] Running: {command_name} ('{display_cmd}') (timeout: {timeout}s) in '{cwd}' (shell={shell})")
    
    start_time = time.time()
    process_result = {"stdout": "", "stderr": "", "returncode": -1, "duration": 0, "success": False}

    try:
        env = os.environ.copy()
        process_input_bytes = std_input.encode() if std_input else None

        process = subprocess.run(
            cmd_list_or_str, cwd=cwd, shell=shell, capture_output=True,
            text=(not process_input_bytes), input=process_input_bytes,
            encoding='utf-8' if not process_input_bytes else None,
            errors='replace' if not process_input_bytes else None,
            check=False, timeout=timeout, env=env
        )
        
        stdout_val = process.stdout.decode(encoding='utf-8', errors='replace') if isinstance(process.stdout, bytes) else process.stdout
        stderr_val = process.stderr.decode(encoding='utf-8', errors='replace') if isinstance(process.stderr, bytes) else process.stderr
        
        process_result["stdout"] = stdout_val or ""
        process_result["stderr"] = stderr_val or ""
        process_result["returncode"] = process.returncode
        process_result["success"] = process.returncode == 0

        if log_output_to_console:
            if stdout_val and stdout_val.strip(): print(f"[{time.strftime('%H:%M:%S')}] {command_name} STDOUT:\n{stdout_val.strip()}")
            if stderr_val and stderr_val.strip(): print(f"[{time.strftime('%H:%M:%S')}] {command_name} STDERR:\n{stderr_val.strip()}")

        if check_on_error and process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, cmd_list_or_str, output=stdout_val, stderr=stderr_val)
        
        print(f"[{time.strftime('%H:%M:%S')}] {command_name} completed (Return Code: {process.returncode}).")

    except subprocess.CalledProcessError as e:
        error_msg = f"{command_name} failed with return code {e.returncode}."
        print(f"[{time.strftime('%H:%M:%S')}] ERROR: {error_msg}")
        if "error_messages" not in results_dict: results_dict["error_messages"] = []
        results_dict["error_messages"].append(f"{error_msg} (See logs for {command_name})")
        process_result["success"] = False # Already set by returncode
    except subprocess.TimeoutExpired as e:
        error_msg = f"{command_name} timed out after {timeout} seconds."
        print(f"[{time.strftime('%H:%M:%S')}] ERROR: {error_msg}")
        if "error_messages" not in results_dict: results_dict["error_messages"] = []
        results_dict["error_messages"].append(error_msg)
        process_result["stdout"] = (e.stdout.decode(encoding='utf-8', errors='replace') if isinstance(e.stdout, bytes) else e.stdout) or ""
        process_result["stderr"] = (e.stderr.decode(encoding='utf-8', errors='replace') if isinstance(e.stderr, bytes) else e.stderr) or ""
        process_result["success"] = False
    except FileNotFoundError:
        cmd_to_report_fnf = cmd_list_or_str if isinstance(cmd_list_or_str, str) else cmd_list_or_str[0]
        error_msg = f"'{cmd_to_report_fnf}' command not found for '{command_name}'. Ensure it's in PATH."
        print(f"[{time.strftime('%H:%M:%S')}] ERROR: {error_msg}")
        if "error_messages" not in results_dict: results_dict["error_messages"] = []
        results_dict["error_messages"].append(error_msg)
        process_result["success"] = False
    except Exception as e:
        error_msg = f"An unexpected error occurred during {command_name}: {type(e).__name__} - {str(e)}"
        print(f"[{time.strftime('%H:%M:%S')}] ERROR: {error_msg}")
        if "error_messages" not in results_dict: results_dict["error_messages"] = []
        results_dict["error_messages"].append(error_msg)
        process_result["success"] = False
    finally:
        process_result["duration"] = time.time() - start_time
        if "command_outputs_map" not in results_dict: results_dict["command_outputs_map"] = {}
        results_dict["command_outputs_map"][command_name] = process_result
    
    return process_result["success"] # Return simple success status


def setup_project_environment(base_tmp_dir: str, project_folder_name: str, results: dict) -> str | None:
    """
    Creates a Next.js project using create-next-app and configures it.
    Returns the project path if successful, None otherwise.
    Populates results with success flags for each sub-step.
    """
    project_path = os.path.join(base_tmp_dir, project_folder_name)
    results["project_setup_stages"] = [] # To store stage names for iteration in test script

    if os.path.exists(project_path):
        shutil.rmtree(project_path)

    # Stage: Create Next App
    stage_name_cna = "Create Next App (CNA)"
    results["project_setup_stages"].append(stage_name_cna)
    cna_flags = [
    project_folder_name, '--ts', '--tailwind', '--eslint', '--app', '--src-dir',
    '--import-alias', '@/*', '--package-manager', 'pnpm', '--skip-git',
    '--no-install', '--no-turbopack'
    ]
    cna_cmd_list = ['pnpm', 'dlx', 'create-next-app@latest'] + cna_flags
    cna_success = _run_command_util(cna_cmd_list, cwd=base_tmp_dir, results_dict=results, timeout=180, command_name=stage_name_cna)
    results["cna_success"] = cna_success
    if not cna_success: return None
    
    # Stage: Configure Next.js (eslint.ignoreDuringBuilds)
    stage_name_next_config = "Configure Next.js (ESLint)"
    results["project_setup_stages"].append(stage_name_next_config)
    next_config_success = True # Assume success unless an error occurs
    next_config_filenames = ['next.config.mjs', 'next.config.js', 'next.config.ts']
    actual_next_config_path = None
    for filename_iter_nc in next_config_filenames:
        temp_path_nc = os.path.join(project_path, filename_iter_nc)
        if os.path.exists(temp_path_nc): actual_next_config_path = temp_path_nc; break
    
    if actual_next_config_path:
        try:
            with open(actual_next_config_path, 'r+', encoding='utf-8') as f_nc:
                content_nc = f_nc.read(); modified_nc = False
                ignore_builds_true_pattern = re.compile(r"eslint\s*:\s*{\s*[^}]*?\bignoreDuringBuilds\s*:\s*true\b")
                if not ignore_builds_true_pattern.search(content_nc):
                    # Simplified logic: if not found, try to add it. More robust parsing would be better.
                    config_object_pattern = re.compile(r"((?:const|let|var)\s+\w+\s*(?::\s*\S+)?\s*=\s*{\s*|module\.exports\s*=\s*{\s*|export\s+default\s*(?:function\s*\w*\s*\(\s*\)\s*{[^}]*return\s*)?{\s*)")
                    match = config_object_pattern.search(content_nc)
                    if match:
                        insert_pos = match.end(1)
                        eslint_config_text = "\n  eslint: {\n    ignoreDuringBuilds: true,\n  },"
                        content_nc = content_nc[:insert_pos] + eslint_config_text + content_nc[insert_pos:]
                        modified_nc = True
                    else: # Fallback if main config object pattern not found
                        content_nc += "\nmodule.exports = { ...module.exports, eslint: { ignoreDuringBuilds: true } };" # Less ideal
                        modified_nc = True
                        results["error_messages"].append(f"Fallback used for next.config.js ESLint setting for {actual_next_config_path}")
                
                if modified_nc:
                    f_nc.seek(0); f_nc.write(content_nc); f_nc.truncate()
                    f_nc.seek(0); final_content_check = f_nc.read()
                    if not ignore_builds_true_pattern.search(final_content_check):
                        results["error_messages"].append(f"Failed to verify eslint.ignoreDuringBuilds in {actual_next_config_path}")
                        next_config_success = False
        except Exception as e_nc_update:
            results["error_messages"].append(f"Error updating {actual_next_config_path} for ESLint: {e_nc_update}")
            next_config_success = False
    else:
        results["error_messages"].append(f"next.config.* not found in {project_path}")
        next_config_success = False
    results["next_config_success"] = next_config_success
    if not next_config_success:
        print(f"[{time.strftime('%H:%M:%S')}] Warning: Failed to configure Next.js for ESLint.")
        # Decide if this is critical enough to stop. For now, let's continue but log it.

    # Stage: Update package.json
    stage_name_pkg_json = "Update package.json"
    results["project_setup_stages"].append(stage_name_pkg_json)
    pkg_json_success = True
    pkg_json_path = os.path.join(project_path, 'package.json')
    if not os.path.exists(pkg_json_path):
        results["error_messages"].append(f"package.json not found at {pkg_json_path}"); pkg_json_success = False
    else:
        try:
            with open(pkg_json_path, 'r+') as f:
                pkg_data = json.load(f)
                pkg_data.setdefault('dependencies', {}).update(ADDITIONAL_DEPENDENCIES)
                pkg_data['dependencies']['react'] = "^18.2.0"; pkg_data['dependencies']['react-dom'] = "^18.2.0"
                pkg_data.setdefault('devDependencies', {}).update(ADDITIONAL_DEV_DEPENDENCIES)
                pkg_data['devDependencies']['@types/react'] = "^18.2.0"; pkg_data['devDependencies']['@types/react-dom'] = "^18.2.0"
                pkg_data.setdefault('scripts', {}).update({"dev": "next dev", "build": "next build", "start": "next start", "lint": "next lint"})
                f.seek(0); json.dump(pkg_data, f, indent=2); f.truncate()
        except Exception as e: results["error_messages"].append(f"Failed to update package.json: {e}"); pkg_json_success = False
    results["pkg_json_success"] = pkg_json_success
    if not pkg_json_success: return None

    # Stage: pnpm Install
    stage_name_pnpm_install = "pnpm Install"
    results["project_setup_stages"].append(stage_name_pnpm_install)
    install_success = _run_command_util(['pnpm', 'install', '--strict-peer-dependencies'], cwd=project_path, results_dict=results, timeout=180, command_name=stage_name_pnpm_install)
    results["npm_install_success"] = install_success # Keep old key for compatibility if test script uses it
    results["pnpm_install_success"] = install_success
    if not install_success: return None

    # Stage: Shadcn Init
    stage_name_shadcn_init = "Shadcn Init"
    results["project_setup_stages"].append(stage_name_shadcn_init)
    shadcn_init_shell_cmd = 'yes "" | pnpm dlx shadcn@latest init --yes'
    init_success = _run_command_util(shadcn_init_shell_cmd, cwd=project_path, results_dict=results, timeout=120, command_name=stage_name_shadcn_init, shell=True, check_on_error=True)
    results["shadcn_init_success"] = init_success and os.path.exists(os.path.join(project_path, "components.json"))
    if not results["shadcn_init_success"]:
        if not os.path.exists(os.path.join(project_path, "components.json")):
             results["error_messages"].append("components.json not created by shadcn init.")
        # Continue even if init has issues, add might still work or reveal more
        print(f"[{time.strftime('%H:%M:%S')}] Warning: Shadcn init may have had issues.")


    # Stage: Shadcn Add Components
    stage_name_shadcn_add = "Shadcn Add Components"
    results["project_setup_stages"].append(stage_name_shadcn_add)
    if results.get("shadcn_init_success"): # Only run add if init was somewhat successful (components.json exists)
        shadcn_add_cmd_list = ['pnpm', 'dlx', 'shadcn@latest', 'add', '--all', '--yes']
        add_success = _run_command_util(shadcn_add_cmd_list, cwd=project_path, results_dict=results, timeout=120, command_name=stage_name_shadcn_add)
        results["shadcn_add_success"] = add_success
        if add_success:
            shadcn_ui_dir = os.path.join(project_path, 'src', 'components', 'ui')
            if not os.path.isdir(shadcn_ui_dir) or not os.listdir(shadcn_ui_dir):
                results["error_messages"].append(f"Shadcn UI dir empty after add.")
                results["shadcn_add_success"] = False
    else:
        results["shadcn_add_success"] = False
        results["error_messages"].append("Skipped shadcn add due to init failure.")


    # Create/Overwrite standard template files
    _create_file_with_content(os.path.join(project_path, 'src', 'app', 'layout.tsx'), APP_LAYOUT_TSX_TEMPLATE, results, "Template: src/app/layout.tsx")
    _create_file_with_content(os.path.join(project_path, 'src', 'app', 'page.tsx'), APP_PAGE_TSX_TEMPLATE, results, "Template: src/app/page.tsx")
    utils_path = os.path.join(project_path, 'src', 'lib', 'utils.ts')
    if not os.path.exists(utils_path): # shadcn init should create this
        os.makedirs(os.path.join(project_path, 'src', 'lib'), exist_ok=True)
        _create_file_with_content(utils_path, LIB_UTILS_TS_TEMPLATE, results, "Template: src/lib/utils.ts")
    
    placeholder_dirs = [os.path.join(project_path, 'src', 'components'), os.path.join(project_path, 'src', 'hooks')]
    for p_dir in placeholder_dirs: os.makedirs(p_dir, exist_ok=True)
    placeholder_files = {
        os.path.join(project_path, 'src', 'components', 'theme-provider.tsx'): COMPONENTS_THEME_PROVIDER_TEMPLATE,
        os.path.join(project_path, 'src', 'components', 'Header.tsx'): HEADER_PLACEHOLDER_TEMPLATE,
        os.path.join(project_path, 'src', 'components', 'Footer.tsx'): FOOTER_PLACEHOLDER_TEMPLATE,
        os.path.join(project_path, 'src', 'components', 'mode-toggle.tsx'): MODE_TOGGLE_TEMPLATE,
        os.path.join(project_path, 'src', 'hooks', 'use-key-press.ts'): USE_KEY_PRESS_TEMPLATE,
    }
    for path, template_content in placeholder_files.items():
        _create_file_with_content(path, template_content, results, f"Template: {os.path.relpath(path, project_path)}")
            
    return project_path

def extract_external_packages(code: str) -> set[str]:
    pkgs = set()
    for m in re.finditer(r'from\s+["\']([^"\']+)["\']', code):
        spec = m.group(1)
        if spec.startswith((".", "/")) or spec.startswith("@/"):
            continue
        root = "/".join(spec.split("/")[:2]) if spec.startswith("@") else spec.split("/")[0]
        pkgs.add(root)
    return pkgs

def process_generated_site(tesslate_response_content: str, base_tmp_dir: str, site_identifier: str):
    """Full process: create project, apply LLM code, build."""
    results = {
        "site_path": None,
        "error_messages": [],
        "command_outputs_map": {}, # Stores {"command_name": {"stdout": ..., "stderr": ..., "success": ..., "duration": ...}}
        "project_setup_stages": [], # Will be populated by setup_project_environment
        # Individual success flags for major operations
        "cna_success": False, "next_config_success": False, "pkg_json_success": False,
        "pnpm_install_success": False, "shadcn_init_success": False, "shadcn_add_success": False,
        "llm_files_write_success": True, # Assume true unless a file write fails
        "eslint_fix_success": False, "prettier_success": False, "build_success": False,
        # Counts
        "llm_syntax_fixes_applied": 0, "prettier_modified_files": 0
    }

    safe_project_name = re.sub(r'[^a-zA-Z0-9_-]', '_', site_identifier) or f"nextjs_app_{int(time.time() * 1000)}"

    project_final_path = setup_project_environment(base_tmp_dir, safe_project_name, results)
    results["site_path"] = project_final_path

    if not project_final_path or not results.get("pnpm_install_success"): # If dir not created or pnpm install failed
        print(f"[{time.strftime('%H:%M:%S')}] Critical project setup failure for {site_identifier}. Aborting.")
        # Ensure all setup stage flags reflect failure if we abort early
        for stage_key in ["cna_success", "next_config_success", "pkg_json_success", "pnpm_install_success", "shadcn_init_success", "shadcn_add_success"]:
            if stage_key not in results: results[stage_key] = False
        return results

    # --- LLM Code Application ---
    # Stage: Apply LLM Code (Syntax Fixes and File Writes)
    stage_name_llm_apply = "Apply LLM Code"
    results["project_setup_stages"].append(stage_name_llm_apply) # Add this as a conceptual stage

    replacements = [
        (r'import\s+\{\s*([\w,\s]+)\s*\}\s*=\s*(".*?");', r'import { \1 } from \2;'),
        (r'import\s+\*\s*as\s+(\w+)\s*=\s*(".*?");', r'import * as \1 from \2;'),
        (r"(>)([^<]*?)'([^<]*?)(<)", r"\1\2'\3\4"),
        (r'import\s+\{\s*(?:useToast|toast)\s*(?:,\s*[^}]+)?\s*\}\s+from\s+["\']@/components/ui/use-toast["\'];?',
         r'import { toast } from "sonner"; /* Patched for sonner */'),
    ]
    original_llm_content_for_fixes = tesslate_response_content
    for old_pattern, new_string in replacements:
        tesslate_response_content = re.sub(old_pattern, new_string, tesslate_response_content, flags=re.DOTALL)
    if original_llm_content_for_fixes != tesslate_response_content:
        results["llm_syntax_fixes_applied"] += 1
    
    edit_blocks = re.findall(r'<Edit filename="(.*?)">([\s\S]*?)<\/Edit>', tesslate_response_content)
    if edit_blocks:
        for filename, code_content in edit_blocks:
            filename = filename.replace('\\"', '"').strip()
            code_content_unescaped = code_content.replace(r'<', '<').replace(r'>', '>').replace(r'&', '&')
            code_content_unescaped = code_content_unescaped.replace(r'\"', '"').replace(r"\'", "'").replace(r'\\', '\\')
            target_path = os.path.normpath(os.path.join(project_final_path, filename))
            if not target_path.startswith(os.path.abspath(project_final_path)):
                results["error_messages"].append(f"Security risk: LLM write attempt outside project: {filename}")
                results["llm_files_write_success"] = False; continue
            _create_file_with_content(target_path, code_content_unescaped, results, f"AI-generated file: {filename}")
            if any(err_msg.startswith(f"Error creating/writing file AI-generated file: {filename}") for err_msg in results.get("error_messages", [])):
                 results["llm_files_write_success"] = False
    if not results["llm_files_write_success"]:
        print(f"[{time.strftime('%H:%M:%S')}] Error writing one or more LLM files for {site_identifier}. Aborting build process.")
        return results # Stop if LLM files couldn't be written

    # Add
    external_pkgs = set()
    for _, code in edit_blocks:
        external_pkgs |= extract_external_packages(code)

    if external_pkgs:
        pkg_json_path = os.path.join(project_final_path, "package.json")
        newly_added = False
        with open(pkg_json_path, "r+") as f:
            pkg = json.load(f)
            deps = pkg.setdefault("dependencies", {})
            for pkg_name in external_pkgs:
                if pkg_name not in deps:
                    deps[pkg_name] = "latest"
                    newly_added = True
            if newly_added:
                f.seek(0); json.dump(pkg, f, indent=2); f.truncate()

        if newly_added:
          stage_name_extra = "pnpm Install (extra)"
          results["project_setup_stages"].append(stage_name_extra)

          extra_ok = _run_command_util(
              ['pnpm', 'install', '--strict-peer-dependencies'],
              cwd=project_final_path,
              results_dict=results,
              timeout=120,
              command_name=stage_name_extra
          )
          results["pnpm_install_extra_success"] = extra_ok

    # --- ESLint --fix step ---
    stage_name_eslint_fix = "ESLint Fix"
    results["project_setup_stages"].append(stage_name_eslint_fix)
    eslint_fix_cmd = ['pnpm', 'eslint', '.', '--fix']
    eslint_fix_success = _run_command_util(eslint_fix_cmd, cwd=project_final_path, results_dict=results, timeout=120, command_name=stage_name_eslint_fix, check_on_error=False)
    results["eslint_fix_success"] = eslint_fix_success # True if command ran, even if it exited > 0 (meaning issues remain)
    if not eslint_fix_success and results["command_outputs_map"].get(stage_name_eslint_fix, {}).get("returncode", -1) !=0 :
         print(f"[{time.strftime('%H:%M:%S')}] Warning: ESLint --fix command itself failed or had issues for {site_identifier}.")
         # Not necessarily a fatal error for the whole process, build will show final state.

    # --- Prettier step ---
    stage_name_prettier = "Prettier Format"
    results["project_setup_stages"].append(stage_name_prettier)
    prettier_cmd = ['pnpm', 'prettier', '--write', '.', '--plugin', 'prettier-plugin-tailwindcss', '--ignore-unknown', '--no-error-on-unmatched-pattern']
    prettier_success_run = _run_command_util(prettier_cmd, cwd=project_final_path, results_dict=results, timeout=120, command_name=stage_name_prettier, check_on_error=False)
    results["prettier_success"] = prettier_success_run # True if command ran
    if prettier_success_run:
        prettier_output = results["command_outputs_map"].get(stage_name_prettier, {})
        modified_files = 0
        combined_output = (prettier_output.get("stdout", "") or "") + (prettier_output.get("stderr", "") or "")
        for line in combined_output.splitlines():
            if re.search(r"\S+\.(tsx|ts|js|jsx|json|css|mdx?)\s+\d+(\.\d+)?ms", line.strip(), re.IGNORECASE):
                if "unchanged" not in line.lower() and not line.startswith("Done in"):
                    modified_files += 1
        results["prettier_modified_files"] = modified_files

    # --- Build step ---
    stage_name_build = "pnpm Build"
    results["project_setup_stages"].append(stage_name_build)
    build_success = _run_command_util(['pnpm', 'build'], cwd=project_final_path, results_dict=results, timeout=120, command_name=stage_name_build)
    results["build_success"] = build_success

    print(f"[{time.strftime('%H:%M:%S')}] Site processing finished for {site_identifier}. Overall Build Success: {results['build_success']}")
    return results

# --- End of gen_site_logic.py ---