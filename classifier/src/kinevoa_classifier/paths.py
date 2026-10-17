"""Runtime paths are configurable and independent of the iOS source tree."""
import os
from pathlib import Path
PROJECT_ROOT = Path(os.getenv("KINEVOA_PROJECT_ROOT", str(Path.cwd()))).resolve()
CACHE_ROOT = Path(os.getenv("KINEVOA_CACHE_DIR", str(PROJECT_ROOT / ".cache"))).resolve()
ENV_FILE = Path(os.getenv("KINEVOA_ENV_FILE", str(PROJECT_ROOT / ".env.local"))).resolve()
