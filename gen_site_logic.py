import os
import re
import subprocess
import json
import shutil
import time
import sys

# --- Configuration ---
NEXTJS_GITHUB_EXAMPLE_URL = "https://github.com/dterenin/weby-nextjs-template"

# --- Helper Functions ---
def _create_file_with_content(filepath: str, content: str, results_dict: dict, file_description: str):
    """Helper function to create a file with given content."""
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"[{time.strftime('%H:%M:%S')}] Successfully wrote: {file_description} ({filepath})")
    except Exception as e:
        error_msg = f"Error creating/writing file {file_description} ({filepath}): {e}"
        print(f"ERROR: {error_msg}")
        if "error_messages" not in results_dict: results_dict["error_messages"] = []
        results_dict["error_messages"].append(error_msg)

def _run_command_util(cmd_list_or_str, cwd, results_dict, timeout=120, check_on_error=True, command_name="Command", log_output_to_console=False, shell=False, std_input=None):
    """Utility to run a shell command and capture its output."""
    if shell and not isinstance(cmd_list_or_str, str):
        raise ValueError("cmd_list_or_str must be a string if shell=True")
    if not shell and not isinstance(cmd_list_or_str, list):
        raise ValueError("cmd_list_or_str must be a list if shell=False")

    display_cmd = cmd_list_or_str if isinstance(cmd_list_or_str, str) else ' '.join(cmd_list_or_str)
    print(f"[{time.strftime('%H:%M:%S')}] Running: {command_name} ('{display_cmd}') in '{cwd}'")
    
    start_time = time.time()
    process_result = {"stdout": "", "stderr": "", "returncode": -1, "duration": 0, "success": False}

    try:
        env = os.environ.copy()
        env["PATH"] = os.path.join(cwd, "node_modules", ".bin") + os.pathsep + env.get("PATH", "")
        process_input_bytes = std_input.encode() if std_input else None

        process = subprocess.run(
            cmd_list_or_str, cwd=cwd, shell=shell, capture_output=True,
            text=(not process_input_bytes), input=process_input_bytes,
            encoding='utf-8', errors='replace',
            check=False, timeout=timeout, env=env
        )
        
        stdout_val = process.stdout
        stderr_val = process.stderr
        
        process_result["stdout"] = stdout_val or ""
        process_result["stderr"] = stderr_val or ""
        process_result["returncode"] = process.returncode
        process_result["success"] = process.returncode == 0

        if check_on_error and process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, cmd_list_or_str, output=stdout_val, stderr=stderr_val)
        
        print(f"[{time.strftime('%H:%M:%S')}] {command_name} completed (RC: {process.returncode}).")

    except subprocess.CalledProcessError as e:
        error_msg = f"{command_name} failed with return code {e.returncode}."
        print(f"[{time.strftime('%H:%M:%S')}] ERROR: {error_msg}\nSTDOUT:\n{e.output}\nSTDERR:\n{e.stderr}")
        results_dict.setdefault("error_messages", []).append(error_msg)
    except Exception as e:
        error_msg = f"An unexpected error occurred during {command_name}: {e}"
        print(f"[{time.strftime('%H:%M:%S')}] ERROR: {error_msg}")
        results_dict.setdefault("error_messages", []).append(error_msg)
    finally:
        process_result["duration"] = time.time() - start_time
        results_dict.setdefault("command_outputs_map", {})[command_name] = process_result
    
    return process_result["success"]

# --- Core Logic Functions ---

def setup_project_environment(base_tmp_dir: str, project_folder_name: str, results: dict) -> str | None:
    """Clones a GitHub template and installs dependencies."""
    project_path = os.path.join(base_tmp_dir, project_folder_name)
    results["project_setup_stages"] = []

    if not NEXTJS_GITHUB_EXAMPLE_URL or "YOUR_USERNAME" in NEXTJS_GITHUB_EXAMPLE_URL:
        error_msg = "FATAL: NEXTJS_GITHUB_EXAMPLE_URL is not configured correctly."
        print(f"[{time.strftime('%H:%M:%S')}] {error_msg}")
        results.setdefault("error_messages", []).append(error_msg)
        return None

    if os.path.exists(project_path):
        shutil.rmtree(project_path)
    os.makedirs(base_tmp_dir, exist_ok=True)

    stage_name_clone = "Clone Next.js Template"
    results["project_setup_stages"].append(stage_name_clone)
    clone_success = _run_command_util(
        ['git', 'clone', '--depth', '1', NEXTJS_GITHUB_EXAMPLE_URL, project_folder_name],
        cwd=base_tmp_dir, results_dict=results, command_name=stage_name_clone
    )
    if not clone_success: return None
    
    git_dir_path = os.path.join(project_path, ".git")
    if os.path.exists(git_dir_path): shutil.rmtree(git_dir_path)

    stage_name_pnpm_install = "pnpm Install"
    results["project_setup_stages"].append(stage_name_pnpm_install)
    install_success = _run_command_util(
        ['pnpm', 'install', '--strict-peer-dependencies=false'],
        cwd=project_path, results_dict=results, command_name=stage_name_pnpm_install
    )
    if not install_success: return None

    print(f"[{time.strftime('%H:%M:%S')}] Project setup completed at: {project_path}")
    return project_path


def process_generated_site(tesslate_response_content: str, base_tmp_dir: str, site_identifier: str):
    """Full process: create project, apply LLM code, fix, format, and build."""
    results = { "site_path": None, "error_messages": [], "command_outputs_map": {} }
    safe_project_name = re.sub(r'[^a-zA-Z0-9_-]', '_', site_identifier)
    project_final_path = setup_project_environment(base_tmp_dir, safe_project_name, results)
    results["site_path"] = project_final_path

    if not project_final_path:
        print(f"[{time.strftime('%H:%M:%S')}] Critical project setup failure. Aborting.")
        return results

    # --- Write all LLM files to disk first ---
    stage_name_llm_apply = "Apply LLM Code"
    results.setdefault("project_setup_stages", []).append(stage_name_llm_apply)
    results["llm_files_write_success"] = True
    edit_blocks = re.findall(r'<Edit filename="(.*?)">([\s\S]*?)<\/Edit>', tesslate_response_content)

    for filename, code_content in edit_blocks:
        filename = filename.replace('\\"', '"').strip()
        code_content = code_content.replace(r'<', '<').replace(r'>', '>').replace(r'&', '&')
        target_path = os.path.normpath(os.path.join(project_final_path, filename))
        if not target_path.startswith(os.path.abspath(project_final_path)):
            results["error_messages"].append(f"Security risk: LLM write attempt outside project: {filename}")
            results["llm_files_write_success"] = False
            continue
        _create_file_with_content(target_path, code_content, results, f"AI-generated file: {filename}")

    if not results.get("llm_files_write_success", False):
        print(f"[{time.strftime('%H:%M:%S')}] Error writing one or more LLM files. Aborting build.")
        return results

    # --- MODIFICATION START: Call the hybrid auto-fixer ONCE for the whole project ---
    auto_fix_script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "auto_fix_imports.py")
    if os.path.exists(auto_fix_script_path):
        stage_name_auto_fix = "Auto Fix (Project-wide)"
        results.setdefault("project_setup_stages", []).append(stage_name_auto_fix)
        script_parent_dir = os.path.dirname(auto_fix_script_path)
        
        auto_fix_success = _run_command_util(
            [sys.executable, auto_fix_script_path, project_final_path],
            cwd=script_parent_dir,  # Run from script's dir to find its node_modules
            results_dict=results,
            timeout=180,
            command_name=stage_name_auto_fix,
            check_on_error=False # The fixer script handles its own errors
        )
        results["auto_fix_success"] = auto_fix_success
        if not auto_fix_success:
            results["error_messages"].append("Project-wide auto fix script failed.")
    else:
        print(f"[{time.strftime('%H:%M:%S')}] Warning: Auto-fix script not found at {auto_fix_script_path}, skipping step.")
    # --- MODIFICATION END ---
    
    stage_name_eslint_fix = "ESLint Fix"
    results.setdefault("project_setup_stages", []).append(stage_name_eslint_fix)
    _run_command_util(
        ['pnpm', 'exec', 'eslint', '.', '--fix'], cwd=project_final_path, 
        results_dict=results, command_name=stage_name_eslint_fix, check_on_error=False
    )

    stage_name_prettier = "Prettier Format"
    results.setdefault("project_setup_stages", []).append(stage_name_prettier)
    _run_command_util(
        ['pnpm', 'exec', 'prettier', '--write', '.', '--ignore-unknown'],
        cwd=project_final_path, results_dict=results, command_name=stage_name_prettier, check_on_error=False
    )
    
    stage_name_build = "pnpm Build"
    results.setdefault("project_setup_stages", []).append(stage_name_build)
    build_success_flag = _run_command_util(
        ['pnpm', 'run', 'build'], cwd=project_final_path, 
        results_dict=results, timeout=240, command_name=stage_name_build, check_on_error=True
    )
    results["build_success"] = build_success_flag

    print(f"[{time.strftime('%H:%M:%S')}] Site processing finished. Overall Build Success: {results['build_success']}")
    return results

# --- Main Execution (Example for testing) ---
if __name__ == "__main__":
    if "YOUR_USERNAME" in NEXTJS_GITHUB_EXAMPLE_URL:
        print("\nERROR: Please set NEXTJS_GITHUB_EXAMPLE_URL at the top of the script.\n")
        sys.exit(1)
    
    example_llm_output = """
<Edit filename="src/app/page.tsx">
import Link from 'next/link';

// This component is not imported, auto-fixer should add it.
import { Button } from "@/components/ui/button";

export default function AIPage() {
  // This hook is not imported, auto-fixer should add it.
  const [count, setCount] = useState(0);

  return (
    <div className="flex flex-col items-center justify-center min-h-screen py-2">
      <h1 className="text-5xl font-bold">AI Enhanced Page</h1>
      <p className="text-xl mt-4">This content is dynamically injected.</p>
      <Button onClick={() => setCount(c => c + 1)} className="mt-8">
        Click Count: {count}
      </Button>
    </div>
  );
}
</Edit>
"""
    temp_base_dir = os.path.join(os.getcwd(), "temp_generated_sites")
    os.makedirs(temp_base_dir, exist_ok=True)
    site_id = f"llm_site_{int(time.time())}"
    
    generation_results = process_generated_site(
        tesslate_response_content=example_llm_output,
        base_tmp_dir=temp_base_dir,
        site_identifier=site_id
    )

    print(f"\n--- Results for {site_id} ---")
    print(json.dumps(generation_results, indent=2))