from pathlib import Path
from zipfile import ZipFile


def is_zip_archive(file_path: Path) -> bool:
    try:
        with ZipFile(file_path) as z:
            z.infolist()
    except Exception:
        return False
    else:
        return True


def extract_zip_archive(decompress_from: Path, decompress_to: Path) -> bool:
    with ZipFile(decompress_from) as z:
        z.extractall(decompress_to)
    return True
