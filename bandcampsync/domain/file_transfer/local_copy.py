import shutil
from pathlib import Path


def move_file(src: Path, dst: Path) -> Path | str:
    return shutil.move(src, dst)


def copy_file(src: Path, dst: Path) -> Path | str:
    return shutil.copyfile(src, dst)
