import os
import re
import subprocess
import json
import shutil
import time
import allure # For attaching files to Allure reports

# Dependencies to add or ensure specific versions for, on top of what create-next-app installs.
# Using React 18 for stability with the ecosystem.
ADDITIONAL_DEPENDENCIES = {
    "lucide-react": "latest",
    "framer-motion": "latest",
    "class-variance-authority": "latest", 
    "clsx": "latest", 
    "tailwind-merge": "latest", 
    "react-intersection-observer": "latest",
    "sonner": "latest", 
    "date-fns": "latest", 
    "@dnd-kit/core": "latest", 
    "@dnd-kit/sortable": "latest",
    "@dnd-kit/modifiers": "latest",
    "next-themes": "latest", 
    "recharts": "latest", 
    "react": "^18.2.0", 
    "react-dom": "^18.2.0", 
    "cmdk": "^1.0.0", 
    "embla-carousel-react": "^8.0.0", 
    "@radix-ui/react-slot": "^1.0.2", 
    "zod": "^3.23.0", 
    "@hookform/resolvers": "^3.0.0", 
    "react-hook-form": "latest", 
}

ADDITIONAL_DEV_DEPENDENCIES = {
    "@types/react": "^18.2.0",
    "@types/react-dom": "^18.2.0",
    "prettier": "latest",
    "prettier-plugin-tailwindcss": "latest",
    "tailwindcss-animate": "latest", 
}

# --- Templates for essential configuration and placeholder files ---

# components.json is NOT created by us before shadcn init. shadcn init will create it.

# This TAILWIND_CONFIG_TS_TEMPLATE is now primarily for reference, 
# as we will rely on shadcn init/add to generate/update the actual tailwind.config.ts.
# If issues persist, we might revert to overwriting with this, but only as a last resort.
TAILWIND_CONFIG_TS_REFERENCE_TEMPLATE = """ 
import type { Config } from 'tailwindcss'

const config: Config = {
  darkMode: ["class"],
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  prefix: "",
  theme: {
    container: {
      center: true,
      padding: "2rem",
      screens: {
        "2xl": "1400px",
      },
    },
    extend: {
      colors: { 
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
      },
      borderRadius: { 
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      keyframes: {
        "accordion-down": {
          from: { height: "0" },
          to: { height: "var(--radix-accordion-content-height)" },
        },
        "accordion-up": {
          from: { height: "var(--radix-accordion-content-height)" },
          to: { height: "0" },
        },
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
}
export default config
"""

# This APP_GLOBALS_CSS_TEMPLATE is also for reference.
# We will rely on shadcn init/add to correctly populate globals.css.
# If that fails, we might need to overwrite with this.
APP_GLOBALS_CSS_REFERENCE_TEMPLATE = """
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  :root {
    --background: 0 0% 100%;
    --foreground: 222.2 84% 4.9%;
    /* ... all other css variables ... */
    --border: 214.3 31.8% 91.4%;
    --input: 214.3 31.8% 91.4%;
    --ring: 222.2 84% 4.9%;
    --radius: 0.5rem;
  }
 
  .dark {
    --background: 222.2 84% 4.9%;
    --foreground: 210 40% 98%;
    /* ... all other dark mode css variables ... */
    --border: 217.2 32.6% 17.5%;
    --input: 217.2 32.6% 17.5%;
    --ring: 212.7 26.8% 83.9%;
  }
}
 
@layer base {
  * {
    @apply border-border;
  }
  body {
    @apply bg-background text-foreground;
    font-feature-settings: "rlig" 1, "calt" 1; 
  }
}
"""

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
        print(f"ERROR: {error_msg}")
        if "error_messages" not in results_dict: results_dict["error_messages"] = []
        results_dict["error_messages"].append(error_msg)

def _run_command_util(cmd_list_or_str, cwd, results_dict, timeout=120, check_on_error=True, command_name="Command", log_output=True, shell=False, std_input=None):
    """Utility to run a shell command and capture its output. Can take a list or a string (if shell=True)."""
    if shell and not isinstance(cmd_list_or_str, str):
        raise ValueError("cmd_list_or_str must be a string if shell=True")
    if not shell and not isinstance(cmd_list_or_str, list):
        raise ValueError("cmd_list_or_str must be a list if shell=False")

    display_cmd = cmd_list_or_str if isinstance(cmd_list_or_str, str) else ' '.join(cmd_list_or_str)
    print(f"[{time.strftime('%H:%M:%S')}] Running: {display_cmd} (timeout: {timeout}s) in '{cwd}' (shell={shell})")
    
    try:
        env = os.environ.copy()
        process_input_bytes = std_input.encode() if std_input else None

        process = subprocess.run(
            cmd_list_or_str, 
            cwd=cwd, 
            shell=shell,
            capture_output=True, 
            text=(not process_input_bytes), 
            input=process_input_bytes,
            encoding='utf-8' if not process_input_bytes else None,
            errors='replace' if not process_input_bytes else None,
            check=False, 
            timeout=timeout, 
            env=env
        )
        
        stdout_val = process.stdout
        stderr_val = process.stderr

        if process_input_bytes: 
            stdout_val = stdout_val.decode(encoding='utf-8', errors='replace') if stdout_val else ""
            stderr_val = stderr_val.decode(encoding='utf-8', errors='replace') if stderr_val else ""
        
        if "command_outputs" not in results_dict: results_dict["command_outputs"] = []
        results_dict["command_outputs"].append((command_name, stdout_val, stderr_val))

        stdout_strip = stdout_val.strip() if stdout_val else ""
        stderr_strip = stderr_val.strip() if stderr_val else ""

        if log_output and stdout_strip: print(f"[{time.strftime('%H:%M:%S')}] {command_name} STDOUT:\n{stdout_strip}")
        if log_output and stderr_strip: print(f"[{time.strftime('%H:%M:%S')}] {command_name} STDERR:\n{stderr_strip}")

        if check_on_error and process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, cmd_list_or_str, output=stdout_val, stderr=stderr_val)
        print(f"[{time.strftime('%H:%M:%S')}] {command_name} completed (Return Code: {process.returncode}).")
        return process
    except subprocess.CalledProcessError as e:
        error_msg = f"{command_name} failed with return code {e.returncode}."
        print(f"[{time.strftime('%H:%M:%S')}] ERROR: {error_msg}")
        if "error_messages" not in results_dict: results_dict["error_messages"] = []
        results_dict["error_messages"].append(f"{error_msg} (See 'All Command Outputs')")
        return None
    except subprocess.TimeoutExpired as e:
        error_msg = f"{command_name} timed out after {timeout} seconds."
        print(f"[{time.strftime('%H:%M:%S')}] ERROR: {error_msg}")
        if "error_messages" not in results_dict: results_dict["error_messages"] = []
        results_dict["error_messages"].append(error_msg)
        partial_stdout_timeout = e.stdout.decode(encoding='utf-8', errors='replace') if isinstance(e.stdout, bytes) else e.stdout
        partial_stderr_timeout = e.stderr.decode(encoding='utf-8', errors='replace') if isinstance(e.stderr, bytes) else e.stderr
        if "command_outputs" not in results_dict: results_dict["command_outputs"] = []
        results_dict["command_outputs"].append((f"{command_name} (Timeout)", partial_stdout_timeout or "", partial_stderr_timeout or ""))
        return None
    except FileNotFoundError:
        cmd_to_report_fnf = cmd_list_or_str if isinstance(cmd_list_or_str, str) else cmd_list_or_str[0]
        error_msg = f"'{cmd_to_report_fnf}' command not found. Ensure it's in PATH. Current PATH: {os.environ.get('PATH', 'Not set')}"
        print(f"[{time.strftime('%H:%M:%S')}] ERROR: {error_msg}")
        if "error_messages" not in results_dict: results_dict["error_messages"] = []
        results_dict["error_messages"].append(error_msg)
        return None
    except Exception as e:
        error_msg = f"An unexpected error occurred during {command_name}: {type(e).__name__} - {str(e)}"
        print(f"[{time.strftime('%H:%M:%S')}] ERROR: {error_msg}")
        if "error_messages" not in results_dict: results_dict["error_messages"] = []
        results_dict["error_messages"].append(error_msg)
        return None

def setup_project_environment(base_tmp_dir: str, project_folder_name: str, results: dict) -> str | None:
    """
    Creates a Next.js project using create-next-app and configures it.
    """
    project_path = os.path.join(base_tmp_dir, project_folder_name)

    if os.path.exists(project_path):
        shutil.rmtree(project_path)

    cna_flags = [
        project_folder_name, '--ts', '--tailwind', '--eslint', '--app', '--src-dir',
        '--import-alias', '@/*', '--use-yarn', '--skip-git', 
        '--no-install', # We run yarn install after modifying package.json
        '--no-turbopack'
    ]
    cna_cmd_list = ['npx', '-y', 'create-next-app@latest'] + cna_flags
    
    print(f"[{time.strftime('%H:%M:%S')}] Running create-next-app to scaffold '{project_folder_name}'...")
    cna_process = _run_command_util(cna_cmd_list, cwd=base_tmp_dir, results_dict=results, timeout=300, command_name="create-next-app scaffolding")

    if not cna_process or cna_process.returncode != 0:
        results["cna_success"] = False
        return None
    results["cna_success"] = True
    print(f"[{time.strftime('%H:%M:%S')}] create-next-app scaffolding completed. Project path: {project_path}")
    
    # Ensure eslint.ignoreDuringBuilds in next.config file
    next_config_filenames = ['next.config.mjs', 'next.config.js', 'next.config.ts']
    actual_next_config_path = None
    actual_next_config_filename = None
    for filename_iter_nc in next_config_filenames:
        temp_path_nc = os.path.join(project_path, filename_iter_nc)
        if os.path.exists(temp_path_nc):
            actual_next_config_path = temp_path_nc
            actual_next_config_filename = filename_iter_nc
            break
    
    if actual_next_config_path:
        print(f"[{time.strftime('%H:%M:%S')}] Found Next.js config file: {actual_next_config_filename}")
        try:
            with open(actual_next_config_path, 'r+', encoding='utf-8') as f_nc:
                content_nc = f_nc.read()
                original_content_nc = str(content_nc)
                
                if not re.search(r"eslint\s*:\s*{\s*[^}]*?\bignoreDuringBuilds\s*:\s*true\b[^}]*}", content_nc, re.DOTALL):
                    eslint_block_text = "eslint: {\n    ignoreDuringBuilds: true,\n  },"
                    if "eslint:" in content_nc:
                        content_nc, num_replacements_nc = re.subn(r"(\beslint\s*:\s*{)([^}]*?)(\bignoreDuringBuilds\s*:\s*)false([^}]*})", r"\1\2\3true\4", content_nc, flags=re.DOTALL)
                        if num_replacements_nc == 0 and "ignoreDuringBuilds: true" not in content_nc:
                             content_nc = re.sub(r"(\beslint\s*:\s*{)", r"\1\n    ignoreDuringBuilds: true,", content_nc, flags=re.DOTALL)
                    else: 
                        config_patterns_nc = [
                            (r"(const\s+\w+\s*:\s*(?:import\([^)]+\)\.)?Config\s*=\s*{)", r"\1\n  {eslint_block}"),
                            (r"(const\s+\w+\s*=\s*{)", r"\1\n  {eslint_block}"),
                            (r"(export\s+default\s*{)", r"\1\n  {eslint_block}"),
                            (r"(module\.exports\s*=\s*{)", r"\1\n  {eslint_block}")
                        ]; added_eslint_block_nc = False
                        for p_nc, rep_nc in config_patterns_nc:
                            new_content_nc, n_s_nc = re.subn(p_nc, rep_nc.format(eslint_block=eslint_block_text), content_nc, 1)
                            if n_s_nc > 0: content_nc = new_content_nc; added_eslint_block_nc = True; break
                        if not added_eslint_block_nc: results["error_messages"].append(f"Could not reliably add eslint.ignoreDuringBuilds to {actual_next_config_filename}")
                    
                    if content_nc != original_content_nc:
                        f_nc.seek(0); f_nc.write(content_nc); f_nc.truncate()
                        if "ignoreDuringBuilds: true" in content_nc: print(f"[{time.strftime('%H:%M:%S')}] Ensured eslint.ignoreDuringBuilds = true in {actual_next_config_filename}")
                        else: print(f"[{time.strftime('%H:%M:%S')}] Attempted to modify {actual_next_config_filename} for ESLint, but 'ignoreDuringBuilds: true' not confirmed present.")
                    elif "ignoreDuringBuilds: true" in content_nc:
                         print(f"[{time.strftime('%H:%M:%S')}] eslint.ignoreDuringBuilds = true already set in {actual_next_config_filename}")
                    else:
                         print(f"[{time.strftime('%H:%M:%S')}] No changes made to {actual_next_config_filename} for ESLint (or 'ignoreDuringBuilds: true' already effectively set).")
        except Exception as e_nc_update: results["error_messages"].append(f"Failed to update {actual_next_config_filename} for ESLint: {e_nc_update}")
    else: print(f"WARNING: next.config.(mjs|js|ts) not found at {project_path}. Cannot ensure eslint.ignoreDuringBuilds.")

    # Update package.json
    pkg_json_path = os.path.join(project_path, 'package.json')
    if not os.path.exists(pkg_json_path): results["error_messages"].append(f"package.json not found at {pkg_json_path}"); return None
    try:
        with open(pkg_json_path, 'r+') as f:
            pkg_data = json.load(f)
            if 'dependencies' not in pkg_data: pkg_data['dependencies'] = {}
            pkg_data['dependencies'].update(ADDITIONAL_DEPENDENCIES); pkg_data['dependencies']['react'] = "^18.2.0"; pkg_data['dependencies']['react-dom'] = "^18.2.0"
            if 'devDependencies' not in pkg_data: pkg_data['devDependencies'] = {}
            pkg_data['devDependencies'].update(ADDITIONAL_DEV_DEPENDENCIES); pkg_data['devDependencies']['@types/react'] = "^18.2.0"; pkg_data['devDependencies']['@types/react-dom'] = "^18.2.0"
            if "tailwindcss-animate" not in pkg_data['devDependencies']: pkg_data['devDependencies']["tailwindcss-animate"] = "latest"
            standard_scripts = {"dev": "next dev", "build": "next build", "start": "next start", "lint": "next lint"}
            if 'scripts' not in pkg_data: pkg_data['scripts'] = {}
            pkg_data['scripts'].update(standard_scripts)
            f.seek(0); json.dump(pkg_data, f, indent=2); f.truncate()
        print(f"[{time.strftime('%H:%M:%S')}] Updated package.json.")
    except Exception as e: results["error_messages"].append(f"Failed to update package.json: {e}"); return None

    # Run yarn install
    print(f"[{time.strftime('%H:%M:%S')}] Running yarn install in {project_path}...")
    install_process = _run_command_util(['yarn', 'install'], cwd=project_path, results_dict=results, timeout=600, command_name="yarn install (all)")
    results["npm_install_success"] = bool(install_process and install_process.returncode == 0)
    if not results["npm_install_success"]:
        print(f"[{time.strftime('%H:%M:%S')}] Yarn install failed. Aborting setup for {project_folder_name}.")
        return None

    # Initialize shadcn/ui using `yes "" | ...` to handle interactive prompts
    print(f"[{time.strftime('%H:%M:%S')}] Initializing shadcn/ui in {project_path} using shell for pipeline...")
    shadcn_init_shell_cmd = 'yes "" | npx -y shadcn@latest init --yes' 
    init_timeout = 400 
    init_completed_successfully = False
    try:
        env = os.environ.copy()
        init_process = subprocess.run(
            shadcn_init_shell_cmd, cwd=project_path, shell=True, capture_output=True, 
            text=True, encoding='utf-8', errors='replace', timeout=init_timeout, env=env
        )
        if "command_outputs" not in results: results["command_outputs"] = []
        results["command_outputs"].append(("shadcn init (shell)", init_process.stdout, init_process.stderr))
        if init_process.stdout and init_process.stdout.strip(): print(f"[{time.strftime('%H:%M:%S')}] shadcn init (shell) STDOUT:\n{init_process.stdout.strip()}")
        if init_process.stderr and init_process.stderr.strip(): print(f"[{time.strftime('%H:%M:%S')}] shadcn init (shell) STDERR:\n{init_process.stderr.strip()}")
        
        if init_process.returncode == 0:
            print(f"[{time.strftime('%H:%M:%S')}] shadcn init (shell) completed (Return Code: 0).")
            init_completed_successfully = True
        else:
            raise subprocess.CalledProcessError(init_process.returncode, shadcn_init_shell_cmd, output=init_process.stdout, stderr=init_process.stderr)
    except Exception as e_init:
        results["error_messages"].append(f"Error during 'shadcn init (shell)': {str(e_init)}")
        init_completed_successfully = False

    if not init_completed_successfully or not os.path.exists(os.path.join(project_path, "components.json")):
        results["error_messages"].append("shadcn init failed to create components.json or completed with errors.")
        results["shadcn_add_success"] = False
    else:
        print(f"[{time.strftime('%H:%M:%S')}] components.json found after shadcn init.")
        print(f"[{time.strftime('%H:%M:%S')}] Adding all shadcn/ui components in {project_path}...")
        shadcn_add_cmd_list = ['npx', '-y', 'shadcn@latest', 'add', '--all', '--yes']
        shadcn_timeout = 120 + (50 * 10) 
        shadcn_add_process = _run_command_util(shadcn_add_cmd_list, cwd=project_path, results_dict=results, timeout=shadcn_timeout, command_name="shadcn add components")
        
        if not shadcn_add_process or shadcn_add_process.returncode != 0:
            results["shadcn_add_success"] = False
        else:
            results["shadcn_add_success"] = True
            shadcn_ui_dir = os.path.join(project_path, 'src', 'components', 'ui')
            if not os.path.isdir(shadcn_ui_dir) or not os.listdir(shadcn_ui_dir):
                results["error_messages"].append(f"Shadcn UI directory ({shadcn_ui_dir}) is missing or empty after 'add --all --yes'.")
                results["shadcn_add_success"] = False
    
    # Crucial step: Overwrite tailwind.config.ts and globals.css with our definitive templates
    # This happens AFTER shadcn init and add, to ensure our config takes precedence if shadcn's updates were incomplete or problematic.
    #_create_file_with_content(os.path.join(project_path, 'tailwind.config.ts'), TAILWIND_CONFIG_TS_TEMPLATE, results, "tailwind.config.ts (FINAL OVERWRITE)")
    #print(f"[{time.strftime('%H:%M:%S')}] Overwrote tailwind.config.ts with FINAL custom template.")
    _create_file_with_content(os.path.join(project_path, 'src', 'app', 'globals.css'), APP_GLOBALS_CSS_TEMPLATE, results, "src/app/globals.css (FINAL OVERWRITE)")
    print(f"[{time.strftime('%H:%M:%S')}] Overwrote globals.css with FINAL custom template.")

    # Create/Overwrite other standard files
    _create_file_with_content(os.path.join(project_path, 'src', 'app', 'layout.tsx'), APP_LAYOUT_TSX_TEMPLATE, results, "src/app/layout.tsx (custom)")
    _create_file_with_content(os.path.join(project_path, 'src', 'app', 'page.tsx'), APP_PAGE_TSX_TEMPLATE, results, "src/app/page.tsx (custom)")
    
    # utils.ts: shadcn init should create this. If not, our template provides it.
    utils_path = os.path.join(project_path, 'src', 'lib', 'utils.ts')
    if not os.path.exists(utils_path):
        os.makedirs(os.path.join(project_path, 'src', 'lib'), exist_ok=True)
        _create_file_with_content(utils_path, LIB_UTILS_TS_TEMPLATE, results, "src/lib/utils.ts (fallback creation)")
    else: # If shadcn created it, we might still want to ensure our version for consistency
        _create_file_with_content(utils_path, LIB_UTILS_TS_TEMPLATE, results, "src/lib/utils.ts (ensuring custom version)")

    
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
        _create_file_with_content(path, template_content, results, f"Placeholder: {os.path.relpath(path, project_path)}")
            
    return project_path


def process_generated_site(tesslate_response_content: str, base_tmp_dir: str, site_identifier: str):
    """Full process: create project, apply LLM code, build."""
    results = {
        "build_success": False, "npm_install_success": False, "cna_success": False,
        "shadcn_add_success": False, "prettier_modified_files": 0, "llm_syntax_fixes_applied": 0,
        "error_messages": [], "site_path": None, "command_outputs": []
    }

    safe_project_name = re.sub(r'[^a-zA-Z0-9_-]', '_', site_identifier)
    if not safe_project_name: 
        timestamp = str(int(time.time() * 1000))
        safe_project_name = f"nextjs_app_{timestamp}"

    project_final_path = setup_project_environment(base_tmp_dir, safe_project_name, results)

    if not project_final_path:
        print(f"[{time.strftime('%H:%M:%S')}] Project environment setup failed for {site_identifier}.")
        return results
    results["site_path"] = project_final_path

    if not results.get("cna_success", False) or not results.get("npm_install_success", False):
        print(f"[{time.strftime('%H:%M:%S')}] Critical: CNA or Yarn install failed. Aborting further steps for {site_identifier}.")
        return results

    # LLM code processing (syntax fixes, writing files)
    replacements = [
        (r'import\s+\{\s*([\w,\s]+)\s*\}\s*=\s*(".*?");', r'import { \1 } from \2;'),
        (r'import\s+\*\s*as\s+(\w+)\s*=\s*(".*?");', r'import * as \1 from \2;'),
        (r"(>)([^<]*?)'([^<]*?)(<)", r"\1\2'\3\4"),
        (r'import\s+\{\s*(?:useToast|toast)\s*(?:,\s*[^}]+)?\s*\}\s+from\s+["\']@/components/ui/use-toast["\'];?',
         r'import { toast } from "sonner"; /* Patched for sonner */'),
    ]
    # ... (LLM replacements logic) ...
    for old_pattern, new_string in replacements:
        content_before_replace = tesslate_response_content
        tesslate_response_content = re.sub(old_pattern, new_string, tesslate_response_content, flags=re.DOTALL)
        if content_before_replace != tesslate_response_content:
            results["llm_syntax_fixes_applied"] += 1
    if results["llm_syntax_fixes_applied"] > 0:
        print(f"[{time.strftime('%H:%M:%S')}] Applied {results['llm_syntax_fixes_applied']} LLM syntax fixes.")


    edit_blocks = re.findall(r'<Edit filename="(.*?)">([\s\S]*?)<\/Edit>', tesslate_response_content)
    if not edit_blocks:
        print(f"[{time.strftime('%H:%M:%S')}] No <Edit> blocks in LLM response for {site_identifier}.")
    else:
        # ... (Writing LLM files logic) ...
        print(f"[{time.strftime('%H:%M:%S')}] Found {len(edit_blocks)} <Edit> blocks for {site_identifier}. Writing AI-generated files...")
        for filename, code_content in edit_blocks:
            filename = filename.replace('\\"', '"').strip()
            code_content_unescaped = code_content.replace(r'\"', '"').replace(r"\'", "'").replace(r'\\', '\\')
            target_path = os.path.normpath(os.path.join(project_final_path, filename))
            if not target_path.startswith(os.path.abspath(project_final_path)):
                results["error_messages"].append(f"Security risk: LLM tried to write outside project dir: {filename} -> {target_path}")
                continue
            _create_file_with_content(target_path, code_content_unescaped, results, f"AI-generated file: {filename}")
            if any(err_msg.startswith(f"Error creating/writing file AI-generated file: {filename}") for err_msg in results.get("error_messages", [])):
                 print(f"[{time.strftime('%H:%M:%S')}] Critical error writing LLM file {filename}. Aborting for {site_identifier}.")
                 results["build_success"] = False
                 return results
    
    if not results.get("shadcn_add_success", False): 
        print(f"[{time.strftime('%H:%M:%S')}] Warning: shadcn components might be missing or incorrectly configured for {site_identifier}. Build will likely fail.")

    # Optional: Code to remove unused 'cn' imports from LLM-generated files
    if edit_blocks:
        print(f"[{time.strftime('%H:%M:%S')}] Attempting to remove unused 'cn' imports from LLM files...")
        for filename_rel_llm, _ in edit_blocks: 
            filepath_abs_llm = os.path.join(project_final_path, filename_rel_llm)
            if os.path.exists(filepath_abs_llm) and filepath_abs_llm.endswith((".tsx", ".jsx")):
                try:
                    with open(filepath_abs_llm, 'r+', encoding='utf-8') as f_llm:
                        content_llm = f_llm.read()
                        # Regex to find `import { cn } from "@/lib/utils";` or `import { cn, type ClassValue } from "@/lib/utils";`
                        cn_import_pattern = r"import\s+\{\s*(?:type\s+)?cn(?:\s*,\s*type\s+ClassValue)?\s*\}\s+from\s+['\"]@/lib/utils['\"];?\s*\n?"
                        # Simple check for `cn(` usage
                        cn_usage_pattern = r"(?:cn\s*\(|className=\{cn\(|className=\{[^}]*cn\([^}]*\)\}|=\s*cn\()"
                        
                        if re.search(cn_import_pattern, content_llm) and not re.search(cn_usage_pattern, content_llm):
                            new_content_llm = re.sub(cn_import_pattern, "", content_llm)
                            if new_content_llm != content_llm:
                                f_llm.seek(0)
                                f_llm.write(new_content_llm)
                                f_llm.truncate()
                                print(f"INFO: Removed unused 'cn' import from LLM file: {filename_rel_llm}")
                                results["llm_syntax_fixes_applied"] += 1 
                except Exception as e_cn_fix_llm:
                    print(f"WARN: Could not process LLM file {filename_rel_llm} for 'cn' fix: {e_cn_fix_llm}")

    # Patch for sidebar.tsx if it exists (common shadcn component that might have this import issue)
    sidebar_tsx_path = os.path.join(project_final_path, "src", "components", "ui", "sidebar.tsx")
    if os.path.exists(sidebar_tsx_path):
        print(f"[{time.strftime('%H:%M:%S')}] Checking/Patching sidebar.tsx for imports...")
        try:
            with open(sidebar_tsx_path, 'r+', encoding='utf-8') as f_sidebar:
                content_sidebar = f_sidebar.read()
                original_sidebar_content = content_sidebar 
                modified_sidebar = False

                # Patch for useIsMobile
                wrong_import_pattern_use_mobile = r"(import\s+{[^}]*?\buseIsMobile\b[^}]*?}\s+from\s+)(?:['\"]@/components/hooks/use-mobile['\"]);?"
                correct_import_use_mobile_text = r"\1'@/hooks/use-mobile';"
                if re.search(wrong_import_pattern_use_mobile, content_sidebar):
                    content_sidebar = re.sub(wrong_import_pattern_use_mobile, correct_import_use_mobile_text, content_sidebar)
                    print(f"INFO: Patched 'useIsMobile' import in {sidebar_tsx_path}")
                    results["llm_syntax_fixes_applied"] +=1 
                    modified_sidebar = True
                
                # Patch for cn
                wrong_import_pattern_cn = r"(import\s+{[^}]*?\bcn\b[^}]*?}\s+from\s+)(?:['\"]@/components/lib/utils['\"]);?"
                correct_import_cn_text = r"\1'@/lib/utils';"
                if re.search(wrong_import_pattern_cn, content_sidebar):
                    content_sidebar = re.sub(wrong_import_pattern_cn, correct_import_cn_text, content_sidebar)
                    print(f"INFO: Patched 'cn' import in {sidebar_tsx_path}")
                    results["llm_syntax_fixes_applied"] +=1
                    modified_sidebar = True
                
                if modified_sidebar:
                    f_sidebar.seek(0)
                    f_sidebar.write(content_sidebar)
                    f_sidebar.truncate()
                    print(f"INFO: sidebar.tsx was modified by patches.")
                else:
                    print(f"INFO: No import patches applied to sidebar.tsx (paths might already be correct or patterns didn't match).")
        except Exception as e_sidebar_patch:
            print(f"WARN: Could not patch sidebar.tsx: {e_sidebar_patch}")
            results["error_messages"].append(f"Failed to patch sidebar.tsx: {e_sidebar_patch}")

    # Attach final config files for debugging
    tailwind_config_file = os.path.join(project_final_path, "tailwind.config.ts")
    if os.path.exists(tailwind_config_file):
        with open(tailwind_config_file, "r", encoding='utf-8') as f:
            allure.attach(f.read(), name="tailwind.config.ts (final)", attachment_type=allure.attachment_type.TEXT)
    
    globals_css_file = os.path.join(project_final_path, "src", "app", "globals.css")
    if os.path.exists(globals_css_file):
        with open(globals_css_file, "r", encoding='utf-8') as f:
            allure.attach(f.read(), name="globals.css (final)", attachment_type=allure.attachment_type.TEXT)

    print(f"[{time.strftime('%H:%M:%S')}] Running prettier in {project_final_path}...")
    prettier_cmd = ['yarn', 'prettier', '--write', '.', '--plugin', 'prettier-plugin-tailwindcss', '--ignore-unknown', '--no-error-on-unmatched-pattern']
    prettier_process = _run_command_util(prettier_cmd, cwd=project_final_path, results_dict=results, timeout=180, command_name="prettier", check_on_error=False)
    if prettier_process:
        modified_files = 0
        combined_output = (prettier_process.stdout or "") + (prettier_process.stderr or "")
        for line in combined_output.splitlines():
            if re.search(r"\S+\.(tsx|ts|js|jsx|json|css|mdx?)\s+\d+(\.\d+)?ms", line.strip(), re.IGNORECASE):
                if "unchanged" not in line.lower() and not line.startswith("Done in"):
                    modified_files += 1
        results["prettier_modified_files"] = modified_files
        print(f"[{time.strftime('%H:%M:%S')}] Prettier potentially modified {modified_files} files (heuristic for yarn).")
        if prettier_process.returncode != 0 :
             print(f"[{time.strftime('%H:%M:%S')}] Warning: Prettier (via yarn) exited with code {prettier_process.returncode}.")

    print(f"[{time.strftime('%H:%M:%S')}] Running yarn build in {project_final_path}...")
    build_process = _run_command_util(['yarn', 'build'], cwd=project_final_path, results_dict=results, timeout=400, command_name="yarn build")
    
    if not build_process or build_process.returncode != 0:
        results["build_success"] = False
    else:
        results["build_success"] = True

    print(f"[{time.strftime('%H:%M:%S')}] Site processing finished for {site_identifier}. Build success: {results['build_success']}")
    return results