import os
import re
import subprocess
import json
import shutil
import time
# import allure # Keep for potential direct attachments if ever needed
import sys

# --- Configuration ---

# Using the exact .git URL as requested by the user.
NEXTJS_GITHUB_EXAMPLE_URL = "https://github.com/dterenin/weby-nextjs-template"

# --- Helper Functions ( _create_file_with_content, _run_command_util ) ---
def _create_file_with_content(filepath: str, content: str, results_dict: dict, file_description: str):
    """Helper function to create a file with given content."""
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        file_content_to_write = content
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(file_content_to_write)
        print(f"[{time.strftime('%H:%M:%S')}] Successfully wrote: {file_description} ({filepath})")
    except Exception as e:
        error_msg = f"Error creating/writing file {file_description} ({filepath}): {e}"
        print(f"ERROR: {error_msg}")
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
        env["PATH"] = os.path.join(cwd, "node_modules", ".bin") + os.pathsep + env.get("PATH", "")
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
            if stderr_val and stderr_val.strip(): print(f"[{time.strftime('%H:%M:%S')}] {command_val} STDERR:\n{stderr_val.strip()}")

        if check_on_error and process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, cmd_list_or_str, output=stdout_val, stderr=stderr_val)
        
        print(f"[{time.strftime('%H:%M:%S')}] {command_name} completed (Return Code: {process.returncode}).")

    except subprocess.CalledProcessError as e:
        error_msg = f"{command_name} failed with return code {e.returncode}."
        print(f"[{time.strftime('%H:%M:%S')}] ERROR: {error_msg} \nSTDOUT:\n{e.stdout}\nSTDERR:\n{e.stderr}")
        if "error_messages" not in results_dict: results_dict["error_messages"] = []
        results_dict["error_messages"].append(f"{error_msg} (stdout: {e.stdout[:200]}, stderr: {e.stderr[:200]})")
        process_result["success"] = False
    except subprocess.TimeoutExpired as e:
        error_msg = f"{command_name} timed out after {timeout} seconds."
        print(f"[{time.strftime('%H:%M:%S')}] ERROR: {error_msg}\nSTDOUT:\n{e.stdout}\nSTDERR:\n{e.stderr}")
        if "error_messages" not in results_dict: results_dict["error_messages"] = []
        results_dict["error_messages"].append(error_msg)
        process_result["stdout"] = (e.stdout.decode(encoding='utf-8', errors='replace') if isinstance(e.stdout, bytes) else e.stdout) or ""
        process_result["stderr"] = (e.stderr.decode(encoding='utf-8', errors='replace') if isinstance(e.stderr, bytes) else e.stderr) or ""
        process_result["success"] = False
    except FileNotFoundError:
        cmd_to_report_fnf = cmd_list_or_str if isinstance(cmd_list_or_str, str) else cmd_list_or_str[0]
        error_msg = f"'{cmd_to_report_fnf}' command not found for '{command_name}'. Ensure it's in PATH or pnpm is installed correctly."
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
    
    return process_result["success"]

# --- Core Logic Functions ---

def setup_project_environment(base_tmp_dir: str, project_folder_name: str, results: dict) -> str | None:
    """
    Creates a Next.js project by cloning a specified GitHub example template
    and installing its pre-configured dependencies.
    Returns the project path if successful, None otherwise.
    """
    project_path = os.path.join(base_tmp_dir, project_folder_name)
    results["project_setup_stages"] = []

    # Check if the URL is the placeholder or empty, critical for operation.
    if NEXTJS_GITHUB_EXAMPLE_URL == "YOUR_GITHUB_USERNAME/YOUR_NEXTJS_TEMPLATE_REPO_NAME" or \
       not NEXTJS_GITHUB_EXAMPLE_URL or \
       NEXTJS_GITHUB_EXAMPLE_URL == "https://github.com/YOUR_USERNAME/YOUR_REPO.git": # Generic placeholder check
        error_msg = "FATAL: NEXTJS_GITHUB_EXAMPLE_URL is not configured correctly. Please set it to your specific GitHub template .git URL."
        print(f"[{time.strftime('%H:%M:%S')}] {error_msg}")
        if "error_messages" not in results: results["error_messages"] = []
        results["error_messages"].append(error_msg)
        return None

    if os.path.exists(project_path):
        print(f"[{time.strftime('%H:%M:%S')}] Cleaning up existing project directory: {project_path}")
        try:
            shutil.rmtree(project_path)
        except Exception as e:
            error_msg = f"Failed to remove existing directory {project_path}: {e}"
            print(f"ERROR: {error_msg}")
            if "error_messages" not in results: results["error_messages"] = []
            results["error_messages"].append(error_msg)
            return None

    os.makedirs(base_tmp_dir, exist_ok=True)

    stage_name_clone = "Clone Next.js Template from GitHub"
    results["project_setup_stages"].append(stage_name_clone)
    git_clone_cmd = ['git', 'clone', '--depth', '1', NEXTJS_GITHUB_EXAMPLE_URL, project_folder_name]

    clone_success = _run_command_util(
        git_clone_cmd,
        cwd=base_tmp_dir,
        results_dict=results,
        timeout=180,
        command_name="Git Clone Template",
        check_on_error=True
    )
    results["cna_success"] = clone_success # Renamed from cna_success to reflect clone
    if not clone_success:
        results["error_messages"].append(f"Failed to clone project from example '{NEXTJS_GITHUB_EXAMPLE_URL}'. Check git clone logs.")
        return None
    
    if not os.path.isdir(project_path):
        results["error_messages"].append(f"Project directory '{project_path}' not found after git clone command.")
        return None
    
    # Remove .git directory after cloning to prevent issues if a new git repo needs to be initialized later
    git_dir_path = os.path.join(project_path, ".git")
    if os.path.exists(git_dir_path):
        try:
            shutil.rmtree(git_dir_path)
            print(f"[{time.strftime('%H:%M:%S')}] Removed .git directory from cloned template.")
        except Exception as e:
            print(f"WARN: Could not remove .git directory: {e}")

    # Stage: pnpm Install for Template Dependencies (This is the primary install)
    stage_name_pnpm_install = "pnpm Install (Template Dependencies)"
    results["project_setup_stages"].append(stage_name_pnpm_install)
    install_success = _run_command_util(
        ['pnpm', 'install', '--strict-peer-dependencies=false'],
        cwd=project_path,
        results_dict=results,
        timeout=300, # Increased timeout for initial install
        command_name=stage_name_pnpm_install,
        check_on_error=True
    )
    results["pnpm_template_install_success"] = install_success
    if not install_success:
        results["error_messages"].append("pnpm install for template dependencies failed.")
        return None

    # The steps for Shadcn Init and Shadcn Add Components are removed here,
    # as the golden template is assumed to have them pre-configured.

    # Check if components.json exists, as a sanity check for shadcn/ui setup in the template
    if not os.path.exists(os.path.join(project_path, "components.json")):
        warn_msg = "Warning: components.json not found in the cloned template. Ensure your GitHub template includes a complete shadcn/ui setup."
        print(f"[{time.strftime('%H:%M:%S')}] {warn_msg}")
        results["error_messages"].append(warn_msg)
    else:
        print(f"[{time.strftime('%H:%M:%S')}] Found components.json in the cloned template, assuming shadcn/ui is configured.")

    print(f"[{time.strftime('%H:%M:%S')}] Project setup from GitHub example '{NEXTJS_GITHUB_EXAMPLE_URL}' completed at: {project_path}")
    return project_path


def extract_external_packages(code: str) -> set[str]:
    """Extracts potential external package names from import statements in LLM code."""
    pkgs = set()
    for m in re.finditer(r'from\s+["\']((?:@[^/"\']+\/[^/"\']+|[^./"\'][^/"\']*)?)["\']', code):
        spec = m.group(1)
        if spec: 
            pkgs.add(spec)
    return pkgs

def process_generated_site(tesslate_response_content: str, base_tmp_dir: str, site_identifier: str):
    """
    Full process: create project from GitHub template, apply LLM code, 
    install any new deps extracted from LLM code, lint, format, and build.
    """
    results = {
        "site_path": None,
        "error_messages": [],
        "command_outputs_map": {},
        "project_setup_stages": [],
        "cna_success": False, # Retained for compatibility, represents initial project clone success
        "pnpm_template_install_success": False,
        "llm_files_write_success": True,
        "pnpm_install_llm_deps_success": True,
        "eslint_fix_success": False,
        "prettier_success": False,
        "build_success": False,
        "llm_syntax_fixes_applied": 0,
        "prettier_modified_files": 0
    }

    safe_project_name = re.sub(r'[^a-zA-Z0-9_-]', '_', site_identifier) or f"nextjs_app_{int(time.time() * 1000)}"

    project_final_path = setup_project_environment(base_tmp_dir, safe_project_name, results)
    results["site_path"] = project_final_path

    if not project_final_path or not results.get("pnpm_template_install_success"):
        print(f"[{time.strftime('%H:%M:%S')}] Critical project setup failure for {site_identifier}. Aborting subsequent steps.")
        results["llm_files_write_success"] = False
        results["pnpm_install_llm_deps_success"] = False
        results["eslint_fix_success"] = False
        results["prettier_success"] = False
        results["build_success"] = False
        return results

    stage_name_llm_apply = "Apply LLM Code (Syntax Fixes and File Writes)"
    results["project_setup_stages"].append(stage_name_llm_apply)
    replacements = [
       # (r'import\s+\{\s*([\w,\s]+)\s*\}\s*=\s*(".*?");', r'import { \1 } from \2;'),
       # (r'import\s+\*\s*as\s+(\w+)\s*=\s*(".*?");', r'import * as \1 from \2;'),
       # (r'import\s+\{\s*(?:useToast|toast)\s*(?:,\s*[^}]+)?\s*\}\s+from\s+["\']@/components/ui/use-toast["\'];?',
       #  r'import { toast } from "sonner"; /* Patched: useToast from shadcn is for its Toaster, direct toast calls usually from sonner */'),
    ]
    original_llm_content_for_fixes = tesslate_response_content
    for old_pattern, new_string in replacements:
        tesslate_response_content = re.sub(old_pattern, new_string, tesslate_response_content, flags=re.DOTALL)
    if original_llm_content_for_fixes != tesslate_response_content:
        results["llm_syntax_fixes_applied"] += 1

    edit_blocks = re.findall(r'<Edit filename="(.*?)">([\s\S]*?)<\/Edit>', tesslate_response_content)
    if edit_blocks:
        # Initialize auto fix tracking
        auto_fix_script = os.path.join(os.path.dirname(__file__), "auto_fix_imports.py")
        auto_fix_results = []

        for filename, code_content in edit_blocks:
            filename = filename.replace('\\"', '"').strip()
            code_content_unescaped = code_content.replace(r'<', '<').replace(r'>', '>').replace(r'&', '&')
            code_content_unescaped = code_content_unescaped.replace(r'\"', '"').replace(r"\'", "'").replace(r'\\', '\\')
            target_path = os.path.normpath(os.path.join(project_final_path, filename))

            if not target_path.startswith(os.path.abspath(project_final_path)):
                results["error_messages"].append(f"Security risk: LLM write attempt outside project: {filename}")
                results["llm_files_write_success"] = False
                continue

            # Write the file
            _create_file_with_content(target_path, code_content_unescaped, results, f"AI-generated file: {filename}")

            # Check if file write was successful
            if any(err_msg.startswith(f"Error creating/writing file AI-generated file: {filename}") for err_msg in results.get("error_messages", [])):
                results["llm_files_write_success"] = False
                continue

            # Apply auto fix to this specific file
            stage_name_auto_fix = f"Auto Import Fix: {filename}"
            if "project_setup_stages" not in results:
                results["project_setup_stages"] = []
            results["project_setup_stages"].append(stage_name_auto_fix)

            auto_fix_cmd = [sys.executable, auto_fix_script, target_path, "lucide_icons.json"]

            auto_fix_success = _run_command_util(
                auto_fix_cmd,
                cwd=project_final_path,
                results_dict=results,
                timeout=120,
                command_name=stage_name_auto_fix
            )

            auto_fix_results.append({
                "filename": filename,
                "success": auto_fix_success
            })

            # Log individual file auto fix result
            if auto_fix_success:
                print(f"[{time.strftime('%H:%M:%S')}] Auto fix completed successfully for {filename}")
            else:
                print(f"[{time.strftime('%H:%M:%S')}] Auto fix failed for {filename}")

        # Set overall auto fix success based on all individual results
        results["auto_fix_success"] = all(result["success"] for result in auto_fix_results)
        results["auto_fix_results"] = auto_fix_results

        if not results["auto_fix_success"]:
            failed_files = [result["filename"] for result in auto_fix_results if not result["success"]]
            results["error_messages"].append(f"Auto fix failed for files: {', '.join(failed_files)}")

    if not results["llm_files_write_success"]:
        print(f"[{time.strftime('%H:%M:%S')}] Error writing one or more LLM files for {site_identifier}. Aborting build process.")
        return results  # Stop if LLM files couldn't be written

    # Add
    external_pkgs = set()
    for _, code in edit_blocks:
        external_pkgs |= extract_external_packages(code)

    stage_name_eslint_fix = "ESLint Fix"
    results["project_setup_stages"].append(stage_name_eslint_fix)
    eslint_fix_cmd = ['pnpm', 'exec', 'eslint', '.', '--fix'] 
    _run_command_util( # Result stored in results dict by _run_command_util
        eslint_fix_cmd, cwd=project_final_path, results_dict=results, timeout=120, 
        command_name=stage_name_eslint_fix, check_on_error=False
    )
    eslint_command_output = results["command_outputs_map"].get(stage_name_eslint_fix, {})
    if not eslint_command_output.get("success", False) and eslint_command_output.get("returncode", -1) != 0 :
         print(f"[{time.strftime('%H:%M:%S')}] Warning: ESLint --fix command execution failed. RC: {eslint_command_output.get('returncode')}")
         results["eslint_fix_success"] = False # Explicitly mark as failed if command itself failed
    else:
        results["eslint_fix_success"] = True

    stage_name_prettier = "Prettier Format"
    results["project_setup_stages"].append(stage_name_prettier)
    prettier_cmd = ['pnpm', 'exec', 'prettier', '--write', '.', '--plugin', 'prettier-plugin-tailwindcss', '--ignore-unknown', '--no-error-on-unmatched-pattern']
    _run_command_util( # Result stored in results dict
        prettier_cmd, cwd=project_final_path, results_dict=results, timeout=120, 
        command_name=stage_name_prettier, check_on_error=False
    )
    prettier_command_output = results["command_outputs_map"].get(stage_name_prettier, {})
    if not prettier_command_output.get("success", False) and prettier_command_output.get("returncode", -1) !=0:
        print(f"[{time.strftime('%H:%M:%S')}] Warning: Prettier command execution failed. RC: {prettier_command_output.get('returncode')}")
        results["prettier_success"] = False # Explicitly mark as failed
    else:
        results["prettier_success"] = True
        modified_files = 0
        combined_output = (prettier_command_output.get("stdout", "") or "") + (prettier_command_output.get("stderr", "") or "")
        for line in combined_output.splitlines():
            if re.search(r"\S+\.(tsx|ts|js|jsx|json|css|mdx?)\s+\d+(\.\d+)?m?s", line.strip(), re.IGNORECASE):
                if "unchanged" not in line.lower() and not line.lower().startswith("done in"):
                    modified_files += 1
        results["prettier_modified_files"] = modified_files
        print(f"[{time.strftime('%H:%M:%S')}] Prettier formatted {modified_files} file(s).")

    stage_name_build = "pnpm Build"
    results["project_setup_stages"].append(stage_name_build)
    build_success_flag = _run_command_util(
        ['pnpm', 'run', 'build'], cwd=project_final_path, results_dict=results, 
        timeout=240, command_name=stage_name_build, check_on_error=True
    )
    results["build_success"] = build_success_flag

    print(f"[{time.strftime('%H:%M:%S')}] Site processing finished for {site_identifier}. Overall Build Success: {results['build_success']}")
    return results

# --- Main Execution (Example for testing the script directly) ---
if __name__ == "__main__":
    print("Starting standalone test run of gen_site_logic.py...")
    
    if NEXTJS_GITHUB_EXAMPLE_URL == "YOUR_GITHUB_USERNAME/YOUR_NEXTJS_TEMPLATE_REPO_NAME" or \
       not NEXTJS_GITHUB_EXAMPLE_URL or \
       NEXTJS_GITHUB_EXAMPLE_URL == "https://github.com/YOUR_USERNAME/YOUR_REPO.git":
        print("\nERROR: Please set NEXTJS_GITHUB_EXAMPLE_URL correctly at the top of the script to your specific GitHub template .git URL before running a test.\n")
        print(f"Current value is: '{NEXTJS_GITHUB_EXAMPLE_URL}'")
        print("Example: NEXTJS_GITHUB_EXAMPLE_URL = \"https://github.com/dterenin/weby-nextjs-template\"")
        sys.exit(1)
    
    example_llm_output = """
    <Edit filename="src/app/page.tsx">
    // AI Generated Page Content for the template
    import Link from 'next/link';

    export default function AIPage() {
      return (
        <div className="flex flex-col items-center justify-center min-h-screen py-2 bg-gray-900 text-white">
          <main className="flex flex-col items-center justify-center w-full flex-1 px-4 sm:px-20 text-center">
            <h1 className="text-5xl sm:text-6xl font-bold mb-8">
              AI Enhanced <span className="text-purple-400">Next.js</span> Site
            </h1>
            <p className="text-xl sm:text-2xl mb-10 text-gray-300">
              This content is dynamically injected by an LLM into a pre-configured template.
              The template provides the structure, styling, and base dependencies.
            </p>
            <div className="bg-gray-800 p-6 rounded-lg shadow-xl">
                <p className="text-lg text-purple-300">Edit this page at <code className="bg-gray-700 p-1 rounded">src/app/page.tsx</code></p>
            </div>
          </main>
          <footer className="w-full h-24 flex items-center justify-center border-t border-gray-700 mt-12">
            <p className="text-gray-500">Generated by AI & Your Awesome Template</p>
          </footer>
        </div>
      );
    }
    </Edit>
    """
    temp_base_dir = os.path.join(os.getcwd(), "temp_generated_sites_git_url") # Changed dir name for clarity
    os.makedirs(temp_base_dir, exist_ok=True)
    
    site_id = f"llm_site_git_url_{int(time.time())}"

    print(f"\n--- Processing site: {site_id} using template '{NEXTJS_GITHUB_EXAMPLE_URL}' ---")
    generation_results = process_generated_site(
        tesslate_response_content=example_llm_output,
        base_tmp_dir=temp_base_dir,
        site_identifier=site_id
    )

    print(f"\n--- Results for {site_id} ---")
    print(json.dumps(generation_results, indent=2, ensure_ascii=False))

    if generation_results.get("build_success"):
        print(f"\n[SUCCESS] Test site '{site_id}' built successfully at: {generation_results.get('site_path')}")
    else:
        print(f"\n[FAILURE] Test site '{site_id}' failed to build.")
        print("Check error messages and command outputs in the results JSON and console logs.")