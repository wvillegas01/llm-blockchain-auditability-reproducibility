from __future__ import annotations

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parents[1]
ZIP_PATH = ROOT.parent / f"{ROOT.name}_v1.zip"


def include(path: Path) -> bool:
    if not path.is_file():
        return False
    if ".git" in path.parts:
        return False
    if "__pycache__" in path.parts:
        return False
    if path.suffix == ".pyc":
        return False
    return True


def main() -> None:
    files = [path for path in sorted(ROOT.rglob("*")) if include(path)]
    with ZipFile(ZIP_PATH, "w", ZIP_DEFLATED) as zf:
        for path in files:
            zf.write(path, path.relative_to(ROOT).as_posix())
    print(f"Wrote {ZIP_PATH} with {len(files)} files.")


if __name__ == "__main__":
    main()
