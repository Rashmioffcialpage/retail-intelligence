from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
steps = [
    "prepare_data.py",
    "build_database.py",
    "validate_pipeline.py",
    "build_warehouse.py",
    "warehouse_analysis.py",
    "analyze_sales.py",
    "customer_analysis.py",
    "forecast_sales.py",
     "build_warehouse.py",
    "validate_warehouse.py",
    "warehouse_analysis.py",
]
started = time.perf_counter()

for step in steps:
    print(f"\nRunning {step}...", flush=True)

    result = subprocess.run(
        [sys.executable, str(ROOT / step)],
        cwd=ROOT,
    )

    if result.returncode != 0:
        raise SystemExit(
            f"\nPipeline stopped: {step} failed "
            f"with exit code {result.returncode}."
        )

elapsed = time.perf_counter() - started
print(f"\nPipeline completed successfully in {elapsed:.1f} seconds.")