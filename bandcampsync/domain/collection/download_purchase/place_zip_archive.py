import logging
from collections.abc import Callable
from pathlib import Path
from tempfile import TemporaryDirectory

from bandcampsync.domain.collection.download_purchase.context import PurchaseDownloadContext
from bandcampsync.domain.collection.download_purchase.placement_outcome import PlacementOutcome
from bandcampsync.domain.file_transfer import extract_zip_archive, move_file

log = logging.getLogger("sync")


def place_zip_archive(
    ctx: PurchaseDownloadContext,
    temp_file_path: Path,
    local_path: Path,
    record_error: Callable[[str], None],
) -> PlacementOutcome:
    with TemporaryDirectory(dir=ctx.temp_dir_root) as temp_dir:
        log.info(f'Decompressing downloaded zip "{temp_file_path}" to "{temp_dir}"')
        extract_zip_archive(temp_file_path, Path(temp_dir))
        try:
            local_path.mkdir(parents=True, exist_ok=True)
        except OSError as mkdir_error:
            record_error(
                f"Failed to create directory: {local_path} "
                f"({mkdir_error}), skipping file extraction"
            )
            return PlacementOutcome.RETRY_ATTEMPT
        for extracted_file in Path(temp_dir).iterdir():
            file_dest = ctx.local_media.get_path_for_file(local_path, extracted_file.name)
            log.info(f'Moving extracted file: "{extracted_file}" to "{file_dest}"')
            try:
                move_file(extracted_file, file_dest)
            except OSError as move_error:
                record_error(f"Failed to move {extracted_file} to {file_dest}: {move_error}")
    return PlacementOutcome.PLACED
