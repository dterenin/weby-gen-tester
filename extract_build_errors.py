#!/usr/bin/env python3
import json
import os
import glob
from pathlib import Path

def extract_build_stderr(json_file_path):
    """Extract pnpm Build stderr from a single JSON file."""
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Check if command_outputs_map exists and has pnpm Build
        command_outputs = data.get('command_outputs_map', {})
        build_output = command_outputs.get('pnpm Build', {})
        stderr = build_output.get('stderr', '')
        
        if stderr:
            return {
                'file': json_file_path,
                'site_path': data.get('site_path', 'Unknown'),
                'stderr': stderr,
                'returncode': build_output.get('returncode', 'Unknown'),
                'success': build_output.get('success', False),
                'Prompt': build_output.get('Prompt', 'Unknown'),
                'LLM Response': build_output.get('LLM Response', 'Unknown'),
            }
    except (json.JSONDecodeError, FileNotFoundError, KeyError) as e:
        print(f"Error processing {json_file_path}: {e}")
    
    return None

def main():
    """Main function to process all JSON files and extract build errors."""
    # Directory containing JSON files
    base_dir = '/Users/machine/GVstudio/nextjs-web-tester/weby_eval_run_generated_772013ed'
    
    # Find all JSON files in the directory
    json_pattern = os.path.join(base_dir, '*.json')
    json_files = glob.glob(json_pattern)
    
    print(f"Found {len(json_files)} JSON files to process...\n")
    
    build_errors = []
    
    for json_file in json_files:
        result = extract_build_stderr(json_file)
        if result:
            build_errors.append(result)
    
    # Output results
    if build_errors:
        print(f"Found {len(build_errors)} files with pnpm Build stderr:\n")
        
        for i, error in enumerate(build_errors, 1):
            print(f"=== Error {i} ===")
            print(f"File: {Path(error['file']).name}")
            print(f"Site Path: {error['site_path']}")
            print(f"Return Code: {error['returncode']}")
            print(f"Success: {error['success']}")
            print(f"STDERR:")
            print(error['stderr'])
            print("\n" + "="*80 + "\n")
        
        # Save to output file
        output_file = 'build_errors_summary.txt'
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"pnpm Build STDERR Summary\n")
            f.write(f"Generated from {len(json_files)} JSON files\n")
            f.write(f"Found {len(build_errors)} files with build errors\n\n")
            
            for i, error in enumerate(build_errors, 1):
                f.write(f"=== Error {i} ===\n")
                f.write(f"File: {Path(error['file']).name}\n")
                f.write(f"Site Path: {error['site_path']}\n")
                f.write(f"Return Code: {error['returncode']}\n")
                f.write(f"Success: {error['success']}\n")
                f.write(f"STDERR:\n")
                f.write(error['stderr'])
                f.write("\n" + "="*80 + "\n\n")
        
        print(f"Results saved to: {output_file}")
    else:
        print("No pnpm Build stderr found in any JSON files.")

if __name__ == '__main__':
    main()