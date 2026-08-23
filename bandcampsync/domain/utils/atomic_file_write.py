import contextlib
from pathlib import Path


def atomic_write_text(target_path: Path, content: str, encoding: str = "utf-8") -> None:
    """Writes to a sibling .tmp file then replaces target_path with it, so a
    reader never sees a partially-written file.
    """
    tmp_path = target_path.with_name(target_path.name + ".tmp")
    try:
        with tmp_path.open("w", encoding=encoding) as tmp_file:
            tmp_file.write(content)
        tmp_path.replace(target_path)
    except Exception:
        if tmp_path.exists():
            with contextlib.suppress(OSError):
                tmp_path.unlink()
        raise
