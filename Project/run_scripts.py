#!/usr/bin/env python3
"""
Automated Script Runner for Trading Project
This script runs all Python files in the current directory automatically without user interaction.
"""

import os
import sys
import subprocess
import time
from pathlib import Path 
import importlib.util

# Resolve everything relative to THIS file so the runner works no matter which
# directory it is launched from.
PROJECT_DIR = Path(__file__).resolve().parent

def get_python_files():
    """Return the trading scripts to run, in dependency order.

    The pipeline is order-sensitive because each step reads the table the
    previous step wrote:
      Fees_Script -> reduced_fees
      1 -> skins lists -> 2 -> weekly volumes -> 3 -> mwv -> 4 -> indicators
      -> 5 -> offers -> 6 -> items on hold / portfolio -> 7 -> create targets
    """
    scripts_dir = PROJECT_DIR / 'scripts'

    ordered = [
        PROJECT_DIR / 'Fees_Script.py',
        PROJECT_DIR / 'delete_targets.py',
        scripts_dir / '1_Skins.py',
        scripts_dir / '2_skins_weekly_history.py',
        scripts_dir / '3_Skins_mwv.py',
        scripts_dir / '4_skins_history_indicators.py',
        scripts_dir / '5_skins_offers.py',
        scripts_dir / '6_history_records.py',
        scripts_dir / '7_target_creation.py',
    ]

    # Only include scripts that actually exist on disk.
    return [path for path in ordered if path.exists()]

def run_script(script_path, output_folder, use_subprocess=True):
    """Run a Python script using either subprocess or import method."""
    try:
        print(f"\n{'='*60}")
        print(f"Running: {script_path.name}")
        print(f"{'='*60}")
        
        if use_subprocess:
            # Set environment variable for output folder (relative to scripts directory)
            env = os.environ.copy()
            env['OUTPUT_FOLDER'] = str(Path('../trading_results'))
            
            # Weekly history paginates DMarket last-sales per skin; 20 minutes
            # is not enough for a full rebuild of the skins list.
            script_timeout = 3600 if script_path.name == "2_skins_weekly_history.py" else 1200

            # Run using subprocess (isolated execution) from scripts directory
            result = subprocess.run([sys.executable, script_path.name], 
                                  capture_output=True, 
                                  text=True, 
                                  timeout=script_timeout,
                                  env=env,
                                  cwd=script_path.parent)
            
            if result.returncode == 0:
                print(f"[SUCCESS] {script_path.name} completed successfully!")
                if result.stdout:
                    print("Output:")
                    print(result.stdout)
                return True
            else:
                print(f"[ERROR] {script_path.name} failed with return code {result.returncode}")
                if result.stderr:
                    print("Error output:")
                    print(result.stderr)
                if result.stdout:
                    print("Standard output:")
                    print(result.stdout)
                return False
                
        else:
            # Set environment variable for output folder
            os.environ['OUTPUT_FOLDER'] = str(output_folder)
            
            # Run using import method (faster but may have conflicts)
            spec = importlib.util.spec_from_file_location(script_path.stem, script_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            print(f"[SUCCESS] {script_path.name} completed successfully!")
            return True
            
    except subprocess.TimeoutExpired as e:
        limit = getattr(e, "timeout", None) or 1200
        print(f"[TIMEOUT] {script_path.name} timed out after {int(limit)} seconds")
        return False
    except Exception as e:
        print(f"[ERROR] Error running {script_path.name}: {str(e)}")
        return False

def main():
    """Main function to run all Python scripts automatically."""
    print("[START] Starting Automated Trading Project Script Runner")
    print(f"[INFO] Project directory: {PROJECT_DIR}")
    
    # Use a single consistent output folder (next to this file)
    output_folder = PROJECT_DIR / "trading_results"
    output_folder.mkdir(exist_ok=True)
    
    print(f"[INFO] Using output folder: {output_folder}")
    
    # Get all Python files
    python_files = get_python_files()
    
    if not python_files:
        print(f"[ERROR] No trading scripts found under {PROJECT_DIR / 'scripts'}")
        return
    
    print(f"\n[INFO] Found {len(python_files)} Python files to run:")
    for i, file in enumerate(python_files, 1):
        print(f"  {i}. {file.name}")
    
    # Configuration - you can modify these settings
    USE_SUBPROCESS = True  # Set to False to use import method
    DELAY_BETWEEN_SCRIPTS = 2  # seconds
    
    print(f"\n[CONFIG] Configuration:")
    print(f"   - Execution method: {'Subprocess' if USE_SUBPROCESS else 'Import'}")
    print(f"   - Delay between scripts: {DELAY_BETWEEN_SCRIPTS} seconds")
    
    # Run all scripts
    successful_runs = 0
    failed_runs = 0
    
    start_time = time.time()
    
    for i, script_file in enumerate(python_files, 1):
        print(f"\n[PROGRESS] Progress: {i}/{len(python_files)}")
        
        success = run_script(script_file, output_folder, USE_SUBPROCESS)
        
        if success:
            successful_runs += 1
        else:
            failed_runs += 1
        
        # Delay between scripts
        if i < len(python_files):
            print(f"[WAIT] Waiting {DELAY_BETWEEN_SCRIPTS} seconds before next script...")
            time.sleep(DELAY_BETWEEN_SCRIPTS)
    
    # Summary
    end_time = time.time()
    total_time = end_time - start_time
    
    print(f"\n{'='*60}")
    print("[SUMMARY] EXECUTION SUMMARY")
    print(f"{'='*60}")
    print(f"[SUCCESS] Successful runs: {successful_runs}")
    print(f"[ERROR] Failed runs: {failed_runs}")
    print(f"[INFO] Success rate: {(successful_runs/len(python_files)*100):.1f}%")
    print(f"[INFO] Total execution time: {total_time:.2f} seconds")
    
    if failed_runs > 0:
        print(f"\n[WARNING] {failed_runs} script(s) failed. Check the error messages above.")
        sys.exit(1)  # Exit with error code
    else:
        print(f"\n[SUCCESS] All scripts completed successfully!")
    
    print(f"\n[INFO] All results are stored in the SQL database: {output_folder / 'trading.db'}")
    print(f"[INFO] Excel mirrors (if enabled) are also refreshed in: {output_folder}")

if __name__ == "__main__":
    main() 