from pathlib import Path
import runpy

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "scripts" / "_project_generator.py"

namespace = runpy.run_path(str(GENERATOR))
namespace["generate_data"](ROOT)
print("Synthetic data regenerated.")
