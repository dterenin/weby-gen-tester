import pytest
import os
import time
import requests
from playwright.sync_api import Playwright # If used
import subprocess
import glob
import csv
import allure
import json
import shutil

from gen_site_logic import process_generated_site # Ensure this import is correct

# Fallback LLM response (can be simplified or removed if CSV is always present)
LLM_TEST_RESPONSE_FALLBACK = """
<Edit filename="src/app/page.tsx">
export default function HomePage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center">
      <main className="flex flex-1 flex-col items-center justify-center p-4 text-center">
        <h1 className="text-4xl font-bold">Fallback Page!</h1>
        <p className="mt-2 text-lg text-muted-foreground">
          This is a fallback page content because no CSV data was found or valid.
        </p>
      </main>
    </div>
  );
}
</Edit>
"""

def load_test_data(csv_filepath="Weby Unified.csv"):
    """Loads test data from a CSV file or uses fallback data."""
    test_cases = []
    # Access pytest config for command-line options
    config = getattr(pytest, 'global_test_context', {}).get('config', None)
    
    # Get field names from pytest options, with defaults
    output_response_field = "output_response"
    framework_field = "metadata_framework"
    input_question_field = "input_question"

    if config and hasattr(config, "option"):
        output_response_field = getattr(config.option, "csv_output_field", output_response_field)
        framework_field = getattr(config.option, "csv_framework_field", framework_field)
        input_question_field = getattr(config.option, "csv_input_field", input_question_field)
    
    if not os.path.exists(csv_filepath):
        print(f"WARNING: CSV file not found: {csv_filepath}. Using fallback for one test.")
        return [("fallback_site_0", LLM_TEST_RESPONSE_FALLBACK, "Fallback: CSV not found")]

    with open(csv_filepath, 'r', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        if not reader.fieldnames:
            print(f"WARNING: CSV {csv_filepath} is empty or headerless. Using fallback.")
            return [("fallback_site_1", LLM_TEST_RESPONSE_FALLBACK, "Fallback: CSV empty/headerless")]
        
        required_fields_map = {
            "tesslate_response": output_response_field,
            "framework": framework_field,
            "input_question": input_question_field
        }
        
        actual_field_names = {}
        missing_fields = []

        for key, default_name in required_fields_map.items():
            if default_name in reader.fieldnames:
                actual_field_names[key] = default_name
            else:
                # Try generic names if custom ones are missing
                generic_names = {"output_response": "output_tesslate_response", "metadata_framework": "framework", "input_question": "input_question"}
                if key in generic_names and generic_names[key] in reader.fieldnames:
                    actual_field_names[key] = generic_names[key]
                    print(f"Warning: Custom field '{default_name}' not found for '{key}'. Using generic '{actual_field_names[key]}'.")
                else:
                    missing_fields.append(default_name)
        
        if missing_fields:
            raise ValueError(f"Missing required CSV fields: {', '.join(missing_fields)}. Available: {', '.join(reader.fieldnames or [])}")

        for i, row in enumerate(reader):
            tesslate_response = row.get(actual_field_names["tesslate_response"], '')
            framework = row.get(actual_field_names["framework"], '')
            input_question = row.get(actual_field_names["input_question"], f"CSV row {i+1}: No input question")

            if framework == 'Nextjs' and '<Edit filename="' in tesslate_response:
                test_cases.append((f"site_{i}", tesslate_response, input_question))
    
    if not test_cases and os.path.exists(csv_filepath): # Only skip if CSV exists but no valid cases
        pytest.skip(f"No valid Next.js test cases with <Edit> blocks found in {csv_filepath}. Skipping tests.")
    elif not test_cases and not os.path.exists(csv_filepath): # If CSV doesn't exist, we already returned a fallback
        pass # Fallback case handled above
        
    return test_cases

@pytest.fixture(scope="function", params=load_test_data())
def site_data_and_tmp_dir(tmp_path_factory, request):
    """Pytest fixture to provide test data and a base temporary directory for each test."""
    site_identifier, tesslate_response_content, input_question = request.param
    # Create a base temporary directory. process_generated_site will create the project folder inside this.
    timestamp = str(int(time.time() * 1000))
    base_tmp_dir_name = f"cna_base_{site_identifier.replace('/', '_')}_{timestamp}"
    base_tmp_dir = tmp_path_factory.mktemp(base_tmp_dir_name)
    yield str(base_tmp_dir), tesslate_response_content, input_question, site_identifier

def wait_for_nextjs_server(url, timeout=180, poll_interval=3): # Increased timeout
    """Waits for the Next.js development server to become ready."""
    print(f"Waiting for Next.js server at {url} (timeout: {timeout}s)...")
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            response = requests.get(url, timeout=poll_interval)
            response.raise_for_status() # Will raise HTTPError for 4xx/5xx
            if response.status_code == 200:
                print(f"Server at {url} is ready.")
                return True
        except requests.exceptions.ConnectionError:
            # print(f"Connection error to {url}, retrying...")
            time.sleep(poll_interval)
        except requests.exceptions.Timeout:
            print(f"Timeout connecting to {url}, retrying...")
            time.sleep(poll_interval)
        except requests.exceptions.HTTPError as e:
            print(f"Server at {url} returned HTTP {e.response.status_code}. Retrying...")
            time.sleep(poll_interval) 
    raise TimeoutError(f"Next.js server at {url} did not become ready within {timeout} seconds.")

def convert_webm_to_gif(webm_path, gif_path):
    """Converts a WEBM video file to GIF using FFmpeg."""
    try:
        ffmpeg_check = subprocess.run(['ffmpeg', '-version'], check=True, capture_output=True, text=True)
        if ffmpeg_check.returncode != 0:
            print(f"Warning: FFmpeg check failed. Skipping GIF conversion. STDERR: {ffmpeg_check.stderr}")
            return False
    except (FileNotFoundError, subprocess.CalledProcessError) as e:
        print(f"Warning: FFmpeg not found or not working ({e}). Skipping GIF conversion.")
        return False
    
    palette_path = os.path.join(os.path.dirname(gif_path), "palette.png")
    try:
        print(f"Generating palette for GIF: {webm_path} -> {palette_path}")
        palette_gen_cmd = ['ffmpeg', '-i', webm_path, '-vf', 'fps=10,scale=640:-1:flags=lanczos,palettegen', '-y', palette_path]
        subprocess.run(palette_gen_cmd, check=True, capture_output=True, text=True)
        
        print(f"Converting WEBM to GIF: {webm_path} -> {gif_path}")
        gif_convert_cmd = ['ffmpeg', '-i', webm_path, '-i', palette_path, '-lavfi', 'fps=10,scale=640:-1:flags=lanczos[x];[x][1:v]paletteuse', '-loop', '0', '-y', gif_path]
        subprocess.run(gif_convert_cmd, check=True, capture_output=True, text=True)
        
        if os.path.exists(palette_path): os.remove(palette_path)
        print(f"GIF conversion successful: {gif_path}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"FFmpeg conversion failed. CMD: {' '.join(e.cmd)}\nStderr: {e.stderr}\nStdout: {e.stdout}")
        if os.path.exists(palette_path): os.remove(palette_path)
        return False
    except Exception as e_conv:
        print(f"Unexpected error during GIF conversion: {e_conv}")
        if os.path.exists(palette_path): os.remove(palette_path)
        return False

def test_generated_nextjs_site(site_data_and_tmp_dir, playwright: Playwright):
    """
    Main test function to process a generated Next.js site, build it, and perform UI checks.
    """
    base_tmp_dir, tesslate_response_content, input_question, site_identifier = site_data_and_tmp_dir
    
    allure.dynamic.title(f"Test Next.js Site (CNA) Build & UI: {site_identifier}")
    allure.dynamic.description(f"Input Question: {input_question}\nBase Temp Dir for CNA: {base_tmp_dir}")

    with allure.step(f"Process & Build Next.js site (CNA approach): {site_identifier}"):
        results = process_generated_site(tesslate_response_content, base_tmp_dir, site_identifier)
        
        actual_site_directory = results.get("site_path")
        if actual_site_directory:
            allure.dynamic.description(f"Input Question: {input_question}\nSite Directory: {actual_site_directory}")
        else:
             allure.dynamic.description(f"Input Question: {input_question}\nSite Directory: Not created (project setup failed)")

        allure.attach(json.dumps(results, indent=2), name="Build Process Summary", attachment_type=allure.attachment_type.JSON)
        
        all_command_logs_str = []
        for cmd_name, stdout_val, stderr_val in results.get("command_outputs", []):
            log_entry = f"--- Command: {cmd_name} ---\n"
            if stdout_val: log_entry += "STDOUT:\n" + stdout_val + "\n"
            if stderr_val: log_entry += "STDERR:\n" + stderr_val + "\n"
            log_entry += "--------------------------\n\n"
            all_command_logs_str.append(log_entry)
        if all_command_logs_str:
            allure.attach("".join(all_command_logs_str), name="All Command Outputs", attachment_type=allure.attachment_type.TEXT)
        
        logged_errors = results.get("error_messages", [])
        if logged_errors:
             allure.attach("\n".join(logged_errors), name="Logged Errors During Processing", attachment_type=allure.attachment_type.TEXT)

        print(f"Processing {site_identifier} (CNA): CNA={results.get('cna_success', False)}, Yarn Install={results.get('npm_install_success', False)}, Shadcn={results.get('shadcn_add_success', False)}, Build={results.get('build_success', False)}")

        assert results.get("cna_success", False), f"create-next-app scaffolding failed for {site_identifier}. Errors: {logged_errors}"
        assert results.get("npm_install_success", False), f"Yarn install (after CNA/merge) failed for {site_identifier}. Errors: {logged_errors}"
        assert results.get("shadcn_add_success", False), f"Shadcn add/init components failed for {site_identifier}. Errors: {logged_errors}"
        assert results.get("build_success", False), f"Build failed for {site_identifier}. Errors: {logged_errors}"


    if results.get("build_success") and actual_site_directory:
        with allure.step(f"Verify UI for {site_identifier} (from CNA project at {actual_site_directory})"):
            dev_server_process = None
            output_media_dir = os.path.join(actual_site_directory, "test_output_media")
            os.makedirs(output_media_dir, exist_ok=True)
            server_url = "http://localhost:3000"
            page = None # Initialize page to None for error handling
            browser = None # Initialize browser to None
            context = None # Initialize context to None
            try:
                print(f"[{time.strftime('%H:%M:%S')}] Starting dev server for {site_identifier} in {actual_site_directory}...")
                dev_server_process = subprocess.Popen(
                    ["yarn", "dev"], 
                    cwd=actual_site_directory, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE, 
                    text=True, 
                    bufsize=1, 
                    creationflags=0 
                )
                
                wait_for_nextjs_server(server_url, timeout=180) # Increased timeout
                
                browser = playwright.chromium.launch(headless=True) 
                context = browser.new_context(
                    viewport={'width': 1280, 'height': 720},
                    record_video_dir=output_media_dir, # Re-enable video recording
                    record_video_size={'width': 1280, 'height': 720}
                )
                page = context.new_page()
                
                print(f"Attempting to navigate to {server_url} for {site_identifier}")
                
                # --- Robust Event Handlers ---
                def _on_console(msg):
                    try:
                        # Ensure msg, msg.type, and msg.text() are safe to access
                        msg_type = getattr(msg, 'type', 'unknown_type') 
                        msg_text = msg.text() if hasattr(msg, 'text') and callable(msg.text) else str(msg) 
                        print(f"BROWSER CONSOLE ({site_identifier} {msg_type}): {msg_text}")
                    except Exception as e_console:
                        print(f"!! ERROR IN CONSOLE HANDLER ({site_identifier}): {type(e_console).__name__} - {e_console}")
                
                def _on_page_error(exc):
                    try:
                        print(f"BROWSER PAGE ERROR ({site_identifier}): {exc}") 
                    except Exception as e_pageerror:
                        print(f"!! ERROR IN PAGEERROR HANDLER ({site_identifier}): {type(e_pageerror).__name__} - {e_pageerror}")

                page.on("console", _on_console)
                page.on("pageerror", _on_page_error)
                # --- End Robust Event Handlers ---

                page.goto(server_url, wait_until="domcontentloaded", timeout=90000) 
                print(f"Page {server_url} loaded for {site_identifier}. Waiting for 5s for hydration/JS...")
                page.wait_for_timeout(5000) 
                
                screenshot_filename = os.path.join(output_media_dir, f"{site_identifier}_debug_page.png")
                page.screenshot(path=screenshot_filename, full_page=True)
                allure.attach.file(screenshot_filename, name=f"{site_identifier}_debug_screenshot", attachment_type=allure.attachment_type.PNG)
                print(f"Screenshot taken for {site_identifier}")

                page_content_lower = page.content().lower()

                # --- MODIFIED/IMPROVED ERROR CHECKING ---
                critical_error_substrings = [
                    "cannot resolve",       # For module resolution issues
                    "module not found",     # For module resolution issues (re-enable this)
                    "typeerror:",           # Common JavaScript error type
                    "referenceerror:",      # Common JavaScript error type
                    "syntaxerror:",         # Common JavaScript error type
                    "unhandled runtime error", # Next.js specific
                    "application error: a client-side exception has occurred", # Next.js specific
                    "server error",         # Often displayed by frameworks for 500 errors
                    "compilation failed",   # Next.js dev server error
                    "failed to compile",    # Next.js dev server error
                ]

                found_errors = []
                for substring in critical_error_substrings:
                    if substring in page_content_lower:
                        found_errors.append(substring)
                
                assert not found_errors, \
                    f"Found critical error indicators in page content for {site_identifier}: {', '.join(found_errors)}"
                # --- END MODIFIED ERROR CHECKING ---

                print(f"[{time.strftime('%H:%M:%S')}] Playwright UI check completed for {site_identifier}.")

            except Exception as e_ui:
                error_msg = f"Playwright/Browser automation error for {site_identifier}: {type(e_ui).__name__} - {str(e_ui)}"
                allure.attach(error_msg, name="Playwright Error", attachment_type=allure.attachment_type.TEXT)
                if page and not page.is_closed():
                    error_screenshot_path = os.path.join(output_media_dir, f"{site_identifier}_error_page.png")
                    try:
                        page.screenshot(path=error_screenshot_path, full_page=True)
                        allure.attach.file(error_screenshot_path, name=f"{site_identifier}_error_screenshot", attachment_type=allure.attachment_type.PNG)
                    except Exception as e_shot:
                        print(f"Could not take error screenshot: {e_shot}")
                pytest.fail(error_msg)
            finally:
                if context: context.close() 
                if browser: browser.close()
                if dev_server_process and dev_server_process.poll() is None:
                    print(f"[{time.strftime('%H:%M:%S')}] Terminating dev server for {site_identifier} (PID: {dev_server_process.pid})...")
                    dev_server_process.terminate()
                    try:
                        stdout, stderr = dev_server_process.communicate(timeout=15)
                        if stdout: allure.attach(stdout, name=f"Dev Server STDOUT on exit ({site_identifier})", attachment_type=allure.attachment_type.TEXT)
                        if stderr: allure.attach(stderr, name=f"Dev Server STDERR on exit ({site_identifier})", attachment_type=allure.attachment_type.TEXT)
                    except subprocess.TimeoutExpired:
                        print(f"[{time.strftime('%H:%M:%S')}] Dev server for {site_identifier} did not terminate gracefully, killing...")
                        dev_server_process.kill()
                        stdout_k, stderr_k = dev_server_process.communicate() # Wait for kill to complete
                        if stdout_k: allure.attach(stdout_k, name=f"Server STDOUT (killed) ({site_identifier})", attachment_type=allure.attachment_type.TEXT)
                        if stderr_k: allure.attach(stderr_k, name=f"Server STDERR (killed) ({site_identifier})", attachment_type=allure.attachment_type.TEXT)
                    except Exception as e_cleanup:
                        allure.attach(str(e_cleanup), name=f"Server Cleanup Error ({site_identifier})", attachment_type=allure.attachment_type.TEXT)
                    print(f"[{time.strftime('%H:%M:%S')}] Dev server for {site_identifier} terminated.")
                
                # Video and GIF processing moved to outside the try/except/finally for browser operations
                # Ensure this runs even if browser part fails, as long as actual_site_directory and output_media_dir are valid
                if actual_site_directory and os.path.isdir(output_media_dir):
                    recorded_videos_list = glob.glob(os.path.join(output_media_dir, "*.webm"))
                    if recorded_videos_list:
                        recorded_video_path = recorded_videos_list[0]
                        allure.attach.file(recorded_video_path, name=f"{site_identifier}_video_raw", attachment_type=allure.attachment_type.WEBM)
                        gif_output_path = os.path.join(output_media_dir, f"{site_identifier}_animation.gif")
                        if convert_webm_to_gif(recorded_video_path, gif_output_path):
                            allure.attach.file(gif_output_path, name=f"{site_identifier}_animation_gif", attachment_type=allure.attachment_type.GIF)
                        # Clean up the raw webm after processing or attempting to process
                        # os.remove(recorded_video_path) # Optional: remove webm to save space
                    else:
                        print(f"Warning: No video file found for {site_identifier} in {output_media_dir}")


    elif not actual_site_directory:
        pytest.fail(f"Site directory for {site_identifier} was not created due to errors in project setup.")