import os
import re
import subprocess
import json
import shutil
import time

# --- Templates for minimal Next.js and shadcn/ui structure ---

SHADCN_COMPONENTS_TO_ADD = [
    "accordion", "alert-dialog", "aspect-ratio", "avatar", "badge", "button",
    "calendar", "card", "checkbox", "collapsible", "command", "context-menu",
    "dialog", "dropdown-menu", "form", "input", "label", "menubar",
    "navigation-menu", "popover", "progress", "radio-group", "scroll-area",
    "select", "separator", "sheet", "skeleton", "slider", "sonner", "switch",
    "table", "tabs", "textarea", "toast", "toggle", "tooltip"
]

PACKAGE_JSON_TEMPLATE = """
{
  "name": "nextjs-site",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "next lint"
  },
  "dependencies": {
    "next": "latest",
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "lucide-react": "latest",
    "framer-motion": "latest",
    "react-hook-form": "latest",
    "class-variance-authority": "latest",
    "clsx": "latest",
    "tailwind-merge": "latest",
    "tailwindcss-animate": "latest",
    "react-intersection-observer": "latest",
    "sonner": "latest",
    "date-fns": "latest",
    "@dnd-kit/core": "latest",
    "@dnd-kit/sortable": "latest",
    "@dnd-kit/modifiers": "latest",
    "next-themes": "latest",
    "recharts": "latest"
  },
  "devDependencies": {
    "typescript": "latest",
    "@types/node": "latest",
    "@types/react": "latest",
    "@types/react-dom": "latest",
    "autoprefixer": "latest",
    "postcss": "latest",
    "tailwindcss": "3.4.3",
    "eslint": "latest",
    "eslint-config-next": "latest",
    "eslint-plugin-prettier": "latest",
    "eslint-config-prettier": "latest",
    "prettier": "latest",
    "prettier-plugin-tailwindcss": "latest",
    "@next/codemod": "latest"
  }
}
"""

TSCONFIG_JSON_TEMPLATE = """
{
  "compilerOptions": {
    "target": "es2017",
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": true,
    "skipLibCheck": true,
    "strict": true,
    "forceConsistentCasingInFileNames": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [
      {
        "name": "next"
      }
    ],
    "paths": {
      "@/*": ["./src/*"],
      "@/components/*": ["./src/components/*"],
      "@/lib/*": ["./src/lib/*"],
      "@/app/*": ["./src/app/*"],
      "@/hooks/*": ["./src/hooks/*"]
    }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
"""

NEXT_CONFIG_JS_TEMPLATE = """
/** @type {import('next').NextConfig} */
const nextConfig = {
    images: {
        remotePatterns: [
            { protocol: 'https', hostname: 'images.unsplash.com', port: '', pathname: '**' },
            { protocol: 'https', hostname: 'plus.unsplash.com', port: '', pathname: '**' },
            { protocol: 'https', hostname: 'tailwindui.com', port: '', pathname: '**' }
        ],
    },
    eslint: {
        ignoreDuringBuilds: true,
    },
    typescript: {
        ignoreBuildErrors: true,
    }
};
module.exports = nextConfig;
"""

POSTCSS_CONFIG_JS_TEMPLATE = """
module.exports = {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
"""

TAILWIND_CONFIG_JS_TEMPLATE = """
const { fontFamily } = require("tailwindcss/defaultTheme");

/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: ["class"],
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    container: {
      center: true,
      padding: "2rem",
      screens: { "2xl": "1400px" },
    },
    extend: {
      colors: {
        border: "hsl(var(--border))", input: "hsl(var(--input))", ring: "hsl(var(--ring))",
        background: "hsl(var(--background))", foreground: "hsl(var(--foreground))",
        primary: { DEFAULT: "hsl(var(--primary))", foreground: "hsl(var(--primary-foreground))" },
        secondary: { DEFAULT: "hsl(var(--secondary))", foreground: "hsl(var(--secondary-foreground))" },
        destructive: { DEFAULT: "hsl(var(--destructive))", foreground: "hsl(var(--destructive-foreground))" },
        muted: { DEFAULT: "hsl(var(--muted))", foreground: "hsl(var(--muted-foreground))" },
        accent: { DEFAULT: "hsl(var(--accent))", foreground: "hsl(var(--accent-foreground))" },
        popover: { DEFAULT: "hsl(var(--popover))", foreground: "hsl(var(--popover-foreground))" },
        card: { DEFAULT: "hsl(var(--card))", foreground: "hsl(var(--card-foreground))" },
      },
      borderRadius: { lg: "var(--radius)", md: "calc(var(--radius) - 2px)", sm: "calc(var(--radius) - 4px)" },
      keyframes: {
        "accordion-down": { from: { height: "0" }, to: { height: "var(--radix-accordion-content-height)" } },
        "accordion-up": { from: { height: "var(--radix-accordion-content-height)" }, to: { height: "0" } },
      },
      animation: { "accordion-down": "accordion-down 0.2s ease-out", "accordion-up": "accordion-up 0.2s ease-out" },
      fontFamily: { sans: ["var(--font-sans)", ...fontFamily.sans] },
    },
  },
  plugins: [require("tailwindcss-animate")],
};
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

COMPONENTS_JSON_TEMPLATE = """
{
  "$schema": "https://ui.shadcn.com/schema.json",
  "style": "default",
  "rsc": true,
  "tsx": true,
  "tailwind": {
    "config": "tailwind.config.js",
    "css": "src/app/globals.css",
    "baseColor": "slate",
    "cssVariables": true
  },
  "aliases": {
    "components": "@/components",
    "utils": "@/lib/utils"
  }
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


APP_GLOBALS_CSS_TEMPLATE = """
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  :root {
    --background: 0 0% 100%;
    --foreground: 222.2 84% 4.9%;
    --card: 0 0% 100%;
    --card-foreground: 222.2 84% 4.9%;
    --popover: 0 0% 100%;
    --popover-foreground: 222.2 84% 4.9%;
    --primary: 222.2 47.4% 11.2%;
    --primary-foreground: 210 40% 98%;
    --secondary: 210 40% 96.1%;
    --secondary-foreground: 222.2 47.4% 11.2%;
    --muted: 210 40% 96.1%;
    --muted-foreground: 215.4 16.3% 46.9%;
    --accent: 210 40% 96.1%;
    --accent-foreground: 222.2 47.4% 11.2%;
    --destructive: 0 84.2% 60.2%;
    --destructive-foreground: 210 40% 98%;
    --border: 214.3 31.8% 91.4%;
    --input: 214.3 31.8% 91.4%;
    --ring: 222.2 84% 4.9%;
    --radius: 0.5rem;
  }
  .dark {
    --background: 222.2 84% 4.9%;
    --foreground: 210 40% 98%;
    --card: 222.2 84% 4.9%;
    --card-foreground: 210 40% 98%;
    --popover: 222.2 84% 4.9%;
    --popover-foreground: 210 40% 98%;
    --primary: 210 40% 98%;
    --primary-foreground: 222.2 47.4% 11.2%;
    --secondary: 217.2 32.6% 17.5%;
    --secondary-foreground: 210 40% 98%;
    --muted: 217.2 32.6% 17.5%;
    --muted-foreground: 215 20.2% 65.1%;
    --accent: 217.2 32.6% 17.5%;
    --accent-foreground: 210 40% 98%;
    --destructive: 0 62.8% 30.6%;
    --destructive-foreground: 210 40% 98%;
    --border: 217.2 32.6% 17.5%;
    --input: 217.2 32.6% 17.5%;
    --ring: 212.7 26.8% 83.9%;
  }
}
@layer base {
  * { @apply border-border; }
  body { @apply bg-background text-foreground; }
}
"""

LIB_UTILS_TS_TEMPLATE = """
import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
"""

ESLINTRC_JSON_TEMPLATE = """
{
  "root": true,
  "extends": ["next/core-web-vitals", "prettier"],
  "rules": {
    "react/no-unescaped-entities": "off"
  }
}
"""

COMPONENTS_THEME_PROVIDER_TEMPLATE = """
"use client"

import * as React from "react"
import { ThemeProvider as NextThemesProvider, type ThemeProviderProps } from "next-themes"

export function ThemeProvider({ children, ...props }: ThemeProviderProps) {
  return <NextThemesProvider {...props}>{children}</NextThemesProvider>
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

MODE_TOGGLE_TEMPLATE = """
"use client"

import * as React from "react"
import { Moon, Sun } from "lucide-react"
import { useTheme } from "next-themes"

import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"

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
        <DropdownMenuItem onClick={() => setTheme("light")}>
          Light
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => setTheme("dark")}>
          Dark
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => setTheme("system")}>
          System
        </DropdownMenuItem>
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


def _create_file_with_content(filepath: str, content: str, results_dict: dict, file_description: str):
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        file_content_to_write = content.strip() if not file_description.startswith("AI-generated file") else content
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(file_content_to_write)
    except Exception as e:
        error_msg = f"Error creating/writing file {file_description} ({filepath}): {e}"
        print(f"ERROR: {error_msg}")
        if "error_messages" in results_dict:
            results_dict["error_messages"].append(error_msg)


def create_nextjs_boilerplate(site_dir, results):
    print(f"[{time.strftime('%H:%M:%S')}] Creating Next.js boilerplate in {site_dir}...")
    os.makedirs(os.path.join(site_dir, 'src', 'app'), exist_ok=True)
    os.makedirs(os.path.join(site_dir, 'src', 'lib'), exist_ok=True)
    os.makedirs(os.path.join(site_dir, 'src', 'components', 'ui'), exist_ok=True) 
    os.makedirs(os.path.join(site_dir, 'src', 'components'), exist_ok=True)     
    os.makedirs(os.path.join(site_dir, 'src', 'hooks'), exist_ok=True)

    _create_file_with_content(
        os.path.join(site_dir, 'next-env.d.ts'),
        '/// <reference types="next" />\n/// <reference types="next/image-types/global" />\n\n',
        results, "next-env.d.ts"
    )

    files_to_create_root = {
        'package.json': PACKAGE_JSON_TEMPLATE,
        'tsconfig.json': TSCONFIG_JSON_TEMPLATE,
        'next.config.js': NEXT_CONFIG_JS_TEMPLATE,
        'postcss.config.js': POSTCSS_CONFIG_JS_TEMPLATE,
        'tailwind.config.js': TAILWIND_CONFIG_JS_TEMPLATE,
        '.eslintrc.json': ESLINTRC_JSON_TEMPLATE,
        'components.json': COMPONENTS_JSON_TEMPLATE,
    } # Disabled the rule for apostrophes
    for filename, content in files_to_create_root.items():
        _create_file_with_content(os.path.join(site_dir, filename), content, results, filename)

    app_files_to_create = {
        'layout.tsx': APP_LAYOUT_TSX_TEMPLATE,
        'globals.css': APP_GLOBALS_CSS_TEMPLATE,
        'page.tsx': APP_PAGE_TSX_TEMPLATE,
    }
    for filename, content in app_files_to_create.items():
        _create_file_with_content(os.path.join(site_dir, 'src', 'app', filename), content, results, f"src/app/{filename}")

    _create_file_with_content(os.path.join(site_dir, 'src', 'lib', 'utils.ts'), LIB_UTILS_TS_TEMPLATE, results, "src/lib/utils.ts")
    
    placeholders = {
        os.path.join(site_dir, 'src', 'components', 'theme-provider.tsx'): COMPONENTS_THEME_PROVIDER_TEMPLATE,
        os.path.join(site_dir, 'src', 'hooks', 'use-key-press.ts'): USE_KEY_PRESS_TEMPLATE,
        os.path.join(site_dir, 'src', 'components', 'Header.tsx'): HEADER_PLACEHOLDER_TEMPLATE,
        os.path.join(site_dir, 'src', 'components', 'Footer.tsx'): FOOTER_PLACEHOLDER_TEMPLATE,
        os.path.join(site_dir, 'src', 'components', 'mode-toggle.tsx'): MODE_TOGGLE_TEMPLATE, # Added placeholder
    }
    for filepath, template in placeholders.items():
        _create_file_with_content(filepath, template, results, f"placeholder: {os.path.relpath(filepath, site_dir)}")
    print(f"[{time.strftime('%H:%M:%S')}] Boilerplate creation finished.")


def process_generated_site(tesslate_response_content: str, site_dir: str):
    results = {
        "build_success": False,
        "npm_install_success": False,
        "shadcn_add_success": False, 
        "prettier_modified_files": 0,
        "llm_syntax_fixes_applied": 0,
        "error_messages": [],
        "site_path": site_dir,
        "command_outputs": []
    }

    def _run_command(cmd_list, cwd, timeout=120, check_on_error=True, command_name="Command", log_output=True):
        print(f"[{time.strftime('%H:%M:%S')}] Running: {' '.join(cmd_list)} (timeout: {timeout}s)")
        try:
            process = subprocess.run(
                cmd_list, cwd=cwd, capture_output=True, text=True, encoding='utf-8',
                errors='replace', check=False, timeout=timeout
            )
            results["command_outputs"].append((command_name, process.stdout, process.stderr))

            if log_output and process.stdout: print(f"[{time.strftime('%H:%M:%S')}] {command_name} STDOUT:\n{process.stdout}")
            if log_output and process.stderr: print(f"[{time.strftime('%H:%M:%S')}] {command_name} STDERR:\n{process.stderr}")
            
            if check_on_error and process.returncode != 0:
                raise subprocess.CalledProcessError(process.returncode, cmd_list, output=process.stdout, stderr=process.stderr)
            print(f"[{time.strftime('%H:%M:%S')}] {command_name} completed (Return Code: {process.returncode}).")
            return process
        except subprocess.CalledProcessError as e:
            error_msg = f"{command_name} failed with return code {e.returncode}."
            print(f"[{time.strftime('%H:%M:%S')}] ERROR: {error_msg}")
            results["error_messages"].append(f"{error_msg} (stdout/stderr in 'All Command Outputs')")
            return None
        except subprocess.TimeoutExpired as e:
            error_msg = f"{command_name} timed out after {timeout} seconds."
            print(f"[{time.strftime('%H:%M:%S')}] ERROR: {error_msg}")
            partial_stdout = e.stdout.decode(encoding='utf-8', errors='replace') if isinstance(e.stdout, bytes) else e.stdout
            partial_stderr = e.stderr.decode(encoding='utf-8', errors='replace') if isinstance(e.stderr, bytes) else e.stderr
            found_cmd_log = False
            for i, (cmd, _, _) in enumerate(results["command_outputs"]):
                if cmd == command_name:
                    results["command_outputs"][i] = (command_name, partial_stdout or "", partial_stderr or "")
                    found_cmd_log = True
                    break
            if not found_cmd_log:
                 results["command_outputs"].append((command_name, partial_stdout or "", partial_stderr or ""))
            if log_output and partial_stdout: print(f"[{time.strftime('%H:%M:%S')}] {command_name} Partial STDOUT (Timeout):\n{partial_stdout}")
            if log_output and partial_stderr: print(f"[{time.strftime('%H:%M:%S')}] {command_name} Partial STDERR (Timeout):\n{partial_stderr}")
            results["error_messages"].append(f"{error_msg} (partial stdout/stderr in 'All Command Outputs')")
            return None
        except FileNotFoundError:
            error_msg = f"'{cmd_list[0]}' command not found."
            print(f"[{time.strftime('%H:%M:%S')}] ERROR: {error_msg}")
            results["error_messages"].append(error_msg)
            return None
        except Exception as e:
            error_msg = f"An unexpected error occurred during {command_name}: {str(e)}"
            print(f"[{time.strftime('%H:%M:%S')}] ERROR: {error_msg}")
            results["error_messages"].append(error_msg)
            return None

    if os.path.exists(site_dir): shutil.rmtree(site_dir)
    os.makedirs(site_dir, exist_ok=True)

    create_nextjs_boilerplate(site_dir, results)
    if results["error_messages"]: return results

    replacements = [
        # General LLM import syntax fixes
        (r'import\s+\{\s*([\w,\s]+)\s*\}\s*=\s*(".*?");', r'import { \1 } from \2;'),
        (r'import\s+\*\s*as\s+(\w+)\s*=\s*(".*?");', r'import * as \1 from \2;'),
        # Fix for unescaped apostrophes in JSX text (caution, may be too aggressive)
        (r"(>)([^<]*?)'([^<]*?)(<)", r"\1\2'\3\4"), # Basic version
        # Fix for old toast/useToast import
        (r'import\s+\{\s*(?:useToast|toast)\s*(?:,\s*[^}]+)?\s*\}\s+from\s+["\']@/components/ui/use-toast["\'];?',
         r'import { toast } from "sonner"; /* Patched by script */'),
    ]
    for old_pattern, new_string in replacements:
        content_before_replace = tesslate_response_content
        tesslate_response_content = re.sub(old_pattern, new_string, tesslate_response_content, flags=re.DOTALL)
        if content_before_replace != tesslate_response_content:
            results["llm_syntax_fixes_applied"] += 1
    if results["llm_syntax_fixes_applied"] > 0:
        print(f"[{time.strftime('%H:%M:%S')}] Applied {results['llm_syntax_fixes_applied']} LLM syntax fixes.")

    edit_blocks = re.findall(r'<Edit filename="(.*?)">([\s\S]*?)<\/Edit>', tesslate_response_content)
    if not edit_blocks:
        print(f"[{time.strftime('%H:%M:%S')}] No <Edit> blocks found in LLM response.")
    else:
        print(f"[{time.strftime('%H:%M:%S')}] Found {len(edit_blocks)} <Edit> blocks. Writing AI-generated files...")
        for filename, code_content in edit_blocks:
            filename = filename.replace('\\"', '"').strip()
            code_content_unescaped = code_content.replace(r'\"', '"').replace(r"\'", "'").replace(r'\\', '\\')
            _create_file_with_content(os.path.join(site_dir, filename), code_content_unescaped, results, f"AI-generated file: {filename}")
            if any(f"Error creating/writing file AI-generated file: {filename}" in msg for msg in results["error_messages"]):
                 return results

    npm_install_cmd_list = ['npm', 'install']
    # npm_install_cmd_list.append('--legacy-peer-deps') # Uncomment if issues with React 19
    npm_install_process = _run_command(npm_install_cmd_list, site_dir, timeout=300, command_name="npm install")
    if not npm_install_process:
        results["npm_install_success"] = False
        return results
    results["npm_install_success"] = True
    
    if SHADCN_COMPONENTS_TO_ADD:
        shadcn_add_cmd = ['npx', 'shadcn@latest', 'add'] + SHADCN_COMPONENTS_TO_ADD
        num_components = len(SHADCN_COMPONENTS_TO_ADD)
        shadcn_timeout = 120 + (num_components * 45)
        
        shadcn_add_process = _run_command(shadcn_add_cmd, site_dir, timeout=shadcn_timeout, command_name="shadcn add components")
        if not shadcn_add_process:
            results["shadcn_add_success"] = False
        else:
            results["shadcn_add_success"] = True
            print(f"[{time.strftime('%H:%M:%S')}] Verifying shadcn components installation...")
            missing_shadcn_components = []
            shadcn_ui_dir = os.path.join(site_dir, 'src', 'components', 'ui')
            if not os.path.isdir(shadcn_ui_dir):
                results["error_messages"].append(f"Shadcn UI directory missing after add: {shadcn_ui_dir}")
                results["shadcn_add_success"] = False
            else:
                for comp_name in SHADCN_COMPONENTS_TO_ADD:

                    if comp_name == "toast": # Special case for toast
                        if not os.path.exists(os.path.join(site_dir, 'src', 'hooks', 'use-toast.ts')):
                            missing_shadcn_components.append(f"{comp_name} (missing src/hooks/use-toast.ts)")
                        if not os.path.exists(os.path.join(shadcn_ui_dir, "toaster.tsx")):
                             missing_shadcn_components.append(f"{comp_name} (missing ui/toaster.tsx)")
                        if not os.path.exists(os.path.join(shadcn_ui_dir, "toast.tsx")): # The toast component itself
                             missing_shadcn_components.append(f"{comp_name} (missing ui/toast.tsx)")
                    elif not os.path.exists(os.path.join(shadcn_ui_dir, f"{comp_name}.tsx")):
                        missing_shadcn_components.append(comp_name)
                if missing_shadcn_components:
                    msg = f"Missing shadcn components after add: {', '.join(missing_shadcn_components)}"
                    results["error_messages"].append(msg)
                    results["shadcn_add_success"] = False
                    print(f"[{time.strftime('%H:%M:%S')}] Verification FAILED: {msg}")
                else:
                    print(f"[{time.strftime('%H:%M:%S')}] Verification PASSED: All expected shadcn components found.")
    else:
        results["shadcn_add_success"] = True
    
    if results["shadcn_add_success"]: 
        toaster_path = os.path.join(site_dir, 'src', 'components', 'ui', 'toaster.tsx')
        if os.path.exists(toaster_path):
            try:
                with open(toaster_path, 'r', encoding='utf-8') as f: content = f.read()
                old_import_pattern = r'import\s+\{\s*useToast\s*\}\s+from\s+["\']@/components/hooks/use-toast["\'];?'
                new_import = 'import { useToast } from "@/hooks/use-toast";'
                if re.search(old_import_pattern, content):
                    content = re.sub(old_import_pattern, new_import, content)
                    with open(toaster_path, 'w', encoding='utf-8') as f: f.write(content)
                    print(f"[{time.strftime('%H:%M:%S')}] Patched import in {toaster_path}")
                    results["llm_syntax_fixes_applied"] += 1 
            except Exception as e_patch:
                results["error_messages"].append(f"Failed to patch {toaster_path}: {e_patch}")
        
        # Patch for EventForm.tsx, if it exists (specific to site_4)
        event_form_path = os.path.join(site_dir, 'src', 'components', 'EventForm.tsx')
        if os.path.exists(event_form_path):
            try:
                with open(event_form_path, 'r', encoding='utf-8') as f: content = f.read()
                # Fix toast import to sonner if it's from the old path
                old_toast_import_pattern = r'import\s+\{\s*toast\s*\}\s+from\s+["\']@/components/ui/use-toast["\'];?'

                new_sonner_import = 'import { toast } from "sonner";'
                if re.search(old_toast_import_pattern, content):
                    content = re.sub(old_toast_import_pattern, new_sonner_import, content)
                    with open(event_form_path, 'w', encoding='utf-8') as f: f.write(content)
                    print(f"[{time.strftime('%H:%M:%S')}] Patched toast import in {event_form_path} to sonner.")
                    results["llm_syntax_fixes_applied"] += 1
            except Exception as e_patch_eventform:
                 results["error_messages"].append(f"Failed to patch {event_form_path}: {e_patch_eventform}")


    components_dir_path = os.path.join(site_dir, 'src', 'components')
    if os.path.exists(components_dir_path):
        print(f"[{time.strftime('%H:%M:%S')}] DEBUG: Files in {components_dir_path}: {os.listdir(components_dir_path)}")
        # Ожидаемые компоненты могут меняться от сайта к сайту, этот список для общего случая или fallback
        expected_components_debug = ["Header.tsx", "Footer.tsx", "theme-provider.tsx", "mode-toggle.tsx"]
        for comp_to_check in expected_components_debug : 
            comp_path = os.path.join(components_dir_path, comp_to_check)
            print(f"[{time.strftime('%H:%M:%S')}] DEBUG: Check for {comp_path}: {'Exists' if os.path.exists(comp_path) else 'MISSING'}")
        hook_path = os.path.join(site_dir, 'src', 'hooks', 'use-key-press.ts')
        print(f"[{time.strftime('%H:%M:%S')}] DEBUG: Check for {hook_path}: {'Exists' if os.path.exists(hook_path) else 'MISSING'}")
    else:
        print(f"[{time.strftime('%H:%M:%S')}] DEBUG: Components directory {components_dir_path} does NOT exist.")


    prettier_process = _run_command(['npx', 'prettier', '--write', '.', '--plugin', 'prettier-plugin-tailwindcss'], site_dir, timeout=120, command_name="prettier", check_on_error=False)
    if prettier_process:
        modified_files = 0
        combined_output = (prettier_process.stdout or "") + (prettier_process.stderr or "")
        for line in combined_output.splitlines():
            if re.search(r"\.(tsx|ts|js|jsx|json|css|md)\s+\d+ms", line, re.IGNORECASE) and "(changed)" in line.lower():
                modified_files += 1
        summary_match = re.search(r"(\d+)\s+files?\s+changed", combined_output, re.IGNORECASE)
        if summary_match: modified_files = int(summary_match.group(1))
        results["prettier_modified_files"] = modified_files
        print(f"[{time.strftime('%H:%M:%S')}] Prettier modified {modified_files} files.")
        if prettier_process.returncode != 0:
            print(f"[{time.strftime('%H:%M:%S')}] Warning: Prettier exited with code {prettier_process.returncode}.")

    build_process = _run_command(['npm', 'run', 'build'], site_dir, timeout=360, command_name="npm build")
    if not build_process:
        results["build_success"] = False
        return results
    results["build_success"] = True
    
    print(f"[{time.strftime('%H:%M:%S')}] Site processing finished. Build success: {results['build_success']}")
    return results