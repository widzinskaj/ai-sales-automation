import os
from pathlib import Path


def get_stage0_attachments_from_env() -> list[Path]:
    paths: list[Path] = []
    for var in ("STAGE0_PDF_1", "STAGE0_PDF_2", "STAGE0_PDF_3"):
        value = os.environ.get(var, "").strip()
        if not value:
            raise ValueError(f"Environment variable {var} is not set or empty")
        p = Path(value)
        if not p.exists():
            raise ValueError(f"File not found for {var}: {p}")
        paths.append(p)
    return paths
