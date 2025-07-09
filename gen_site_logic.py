# gen_site_logic.py
import os
import re
import subprocess
import json
import shutil
import time
import sys


def _create_file_with_content(filepath: str, content: str, results_dict: dict, file_description: str):
    """Helper function to create a file with given content."""
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
    except Exception as e:
        error_msg = f"Error creating/writing file {file_description} ({filepath}): {e}"
        print(f"ERROR: {error_msg}")
        results_dict.setdefault("error_messages", []).append(error_msg)

def _run_command_util(cmd_list, cwd, results_dict, timeout=120, check_on_error=True, command_name="Command"):
    """Utility to run a shell command and capture its output."""
    display_cmd = ' '.join(cmd_list)
    print(f"[{time.strftime('%H:%M:%S')}] Running: {command_name} ('{display_cmd[:150]}...') in '{cwd}'")
    
    start_time = time.time()
    process_result = {"stdout": "", "stderr": "", "returncode": -1, "duration": 0, "success": False}

    try:
        env = os.environ.copy()
        # Ensure local node_modules/.bin is in the PATH
        env["PATH"] = os.path.join(cwd, "node_modules", ".bin") + os.pathsep + env.get("PATH", "")
        
        # Set a longer timeout for the initial, full pnpm install
        effective_timeout = 360 if "pnpm Install" in command_name else timeout

        process = subprocess.run(
            cmd_list, cwd=cwd, capture_output=True,
            text=True, encoding='utf-8', errors='replace',
            check=False, timeout=effective_timeout, env=env
        )
        
        process_result.update({
            "stdout": process.stdout or "", "stderr": process.stderr or "",
            "returncode": process.returncode, "success": process.returncode == 0
        })

        if check_on_error and process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, cmd_list, output=process.stdout, stderr=process.stderr)
        
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

def create_golden_template(base_tmp_dir: str, repo_url: str) -> str | None:
    """
    PERFORMANCE: Clones the template and installs dependencies ONCE per session.
    IMPORTANT: It leaves the .git directory intact to enable fast local clones.
    """
    project_folder_name = "nextjs_golden_template"
    project_path = os.path.join(base_tmp_dir, project_folder_name)
    results = {}

    if not repo_url:
        print(f"FATAL: Repository URL is not configured.")
        return None

    if os.path.exists(project_path):
        shutil.rmtree(project_path)
    os.makedirs(base_tmp_dir, exist_ok=True)

    # Clone the repository from the remote URL. We do a full clone (no --depth)
    # as this is generally better for subsequent local cloning.
    clone_success = _run_command_util(
        ['git', 'clone', repo_url, project_path],
        cwd=base_tmp_dir, results_dict=results, command_name="Clone Remote Template"
    )
    if not clone_success: return None
    
    # --- KEY CHANGE: DO NOT REMOVE the .git directory ---
    # The .git directory is required for fast local cloning.
    # git_dir_path = os.path.join(project_path, ".git")
    # if os.path.exists(git_dir_path):
    #     shutil.rmtree(git_dir_path)

    # Install dependencies using pnpm, which will create a link-based node_modules
    install_success = _run_command_util(
        ['pnpm', 'install', '--strict-peer-dependencies=false'],
        cwd=project_path, results_dict=results, command_name="pnpm Install (template)"
    )
    if not install_success: return None

    return project_path


def process_generated_site(tesslate_response_content: str, project_final_path: str, site_identifier: str):
    """
    Full process: apply LLM code, fix, format, and build on a pre-built project directory.
    """
    results = {
        "site_path": project_final_path,
        "error_messages": [],
        "command_outputs_map": {},
        "project_setup_stages": []
    }

    # --- Step 1: Write all LLM files to disk and collect their paths ---
    stage_name_llm_apply = "Apply LLM Code"
    results["project_setup_stages"].append(stage_name_llm_apply)
    results["llm_files_write_success"] = True
    edit_blocks = re.findall(r'<Edit filename="(.*?)">([\s\S]*?)<\/Edit>', tesslate_response_content)

    
    llm_modified_files = [] # PERFORMANCE: Collect paths of modified files

    for filename, code_content in edit_blocks:
        filename = filename.replace('\\"', '"').strip()
        # Basic sanitization of common XML/HTML entities
        code_content = code_content.replace(r'<', '<').replace(r'>', '>').replace(r'&', '&')
        target_path = os.path.normpath(os.path.join(project_final_path, filename))
        
        # Security check to prevent path traversal attacks
        if not target_path.startswith(os.path.abspath(project_final_path)):
            results["error_messages"].append(f"Security risk: LLM write attempt outside project: {filename}")
            results["llm_files_write_success"] = False
            continue
        
        _create_file_with_content(target_path, code_content, results, f"AI-generated file: {filename}")
        llm_modified_files.append(target_path) # Add to list for targeted fixing

    if not results.get("llm_files_write_success", False):
        print(f"[{time.strftime('%H:%M:%S')}] Error writing one or more LLM files. Aborting build.")
        return results
    if not llm_modified_files:
        print(f"[{time.strftime('%H:%M:%S')}] No <Edit> blocks found to apply. Proceeding to build.")

    # --- Step 2: CRITICAL TEST: Install new dependencies specified by LLM ---
    # This step is essential to validate if the LLM correctly managed package.json
    stage_name_pnpm_install = "pnpm Install"
    results["project_setup_stages"].append(stage_name_pnpm_install)
    pnpm_install_success = _run_command_util(
        ['pnpm', 'install', '--strict-peer-dependencies=false'],
        cwd=project_final_path,
        results_dict=results,
        command_name=stage_name_pnpm_install,
        check_on_error=True # This is a critical step
    )
    results["pnpm_install_success"] = pnpm_install_success
    if not pnpm_install_success:
        # No point in continuing if dependencies are broken
        return results

    # --- Step 3: PERFORMANCE: Call the hybrid auto-fixer ONLY on modified files ---
    auto_fix_script_path = os.path.join(project_final_path, "ts-morph-fixer.ts")
    if os.path.exists(auto_fix_script_path) and llm_modified_files:
        stage_name_auto_fix = "Auto Fix (Project-wide)"
        results["project_setup_stages"].append(stage_name_auto_fix)
        
        # Pass the project path and the list of specific files to the TypeScript script
        command_to_run = ["pnpm", "run", "fix"]#, project_final_path] + llm_modified_files
        
        auto_fix_success = _run_command_util(
            command_to_run,
            cwd=project_final_path,  # Run from project directory, not script parent dir
            results_dict=results,
            timeout=180,
            command_name=stage_name_auto_fix,
            check_on_error=False # The fixer script handles its own errors and exits non-zero
        )
        results["auto_fix_success"] = auto_fix_success
        if not auto_fix_success:
            results["error_messages"].append("Targeted auto fix script failed.")
    elif not os.path.exists(auto_fix_script_path):
        print(f"[{time.strftime('%H:%M:%S')}] Warning: Auto-fix script not found, skipping step.")

    # --- Step 4: Run linters and formatters ---
    stage_name_eslint_fix = "ESLint Fix"
    results["project_setup_stages"].append(stage_name_eslint_fix)
    _run_command_util(
        ['pnpm', 'exec', 'eslint', '.', '--fix'], cwd=project_final_path, 
        results_dict=results, command_name=stage_name_eslint_fix, check_on_error=False
    )

    stage_name_prettier = "Prettier Format"
    results["project_setup_stages"].append(stage_name_prettier)
    _run_command_util(
        ['pnpm', 'exec', 'prettier', '--write', '.', '--ignore-unknown'],
        cwd=project_final_path, results_dict=results, command_name=stage_name_prettier, check_on_error=False
    )
    
    # --- Step 5: The final build ---
    stage_name_build = "pnpm Build"
    results["project_setup_stages"].append(stage_name_build)
    build_success_flag = _run_command_util(
        ['pnpm', 'run', 'build'], cwd=project_final_path, 
        results_dict=results, timeout=240, command_name=stage_name_build, check_on_error=True
    )
    results["build_success"] = build_success_flag

    print(f"[{time.strftime('%H:%M:%S')}] Site processing finished. Overall Build Success: {results['build_success']}")
    return results