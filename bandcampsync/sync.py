import asyncio
import time
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from .logger import get_logger
from .bandcamp import Bandcamp, BandcampError, BandcampDownloadUnavailable
from .ignores import Ignores
from .media import LocalMedia
from .notify import NotifyURL
from .download import (
    download_file,
    unzip_file,
    move_file,
    copy_file,
    mask_sig,
    is_zip_file,
    DownloadInvalidContentType,
    DownloadBadStatusCode,
    DownloadExpired,
)


log = get_logger("sync")


class Syncer:
    def __init__(
        self,
        cookies,
        dir_path,
        media_format,
        temp_dir_root,
        ign_file_path,
        ign_patterns,
        notify_url,
        concurrency=1,
        max_retries=3,
        retry_wait=5,
        skip_item_index=False,
        sync_ignore_file=False,
    ):
        self.ignores = Ignores(ign_file_path=ign_file_path, ign_patterns=ign_patterns)
        self.sync_ignore_file = sync_ignore_file
        self.local_media = LocalMedia(
            media_dir=dir_path,
            ignores=self.ignores,
            skip_item_index=skip_item_index,
            sync_ignore_file=sync_ignore_file,
        )
        self.media_format = media_format
        self.temp_dir_root = temp_dir_root
        self.ign_file_path = ign_file_path
        self.notify_url = notify_url
        self.concurrency = max(1, concurrency)
        self.max_retries = max(1, max_retries)
        self.retry_wait = max(0, retry_wait)

        self.show_id_file_warning = False
        self.new_items_downloaded = False

        self.bandcamp = Bandcamp(cookies=cookies)
        self.bandcamp.verify_authentication()
        self.bandcamp.load_purchases()

        asyncio.run(self.sync_items())
        self.notify()

    def sync_item(
        self,
        item,
    ) -> bool:
        """Syncs a single item (purchase).

        Returns:
            bool: indicating new media was downloaded
        """

        local_path = self.local_media.get_path_for_purchase(item)

        # Check if any ignore pattern matches the band name
        if self.ignores.is_ignored(item):
            if not self.show_id_file_warning and self.local_media.is_locally_downloaded(
                item, local_path
            ):
                self.show_id_file_warning = True
            return False

        if item.is_preorder:
            log.info(
                f'Item is a preorder, skipping: "{item.band_name} / {item.item_title}" '
                f"(id:{item.item_id})"
            )
            return False

        elif self.local_media.is_locally_downloaded(item, local_path):
            log.info(
                f'Already locally downloaded, skipping: "{item.band_name} / {item.item_title}" '
                f"(id:{item.item_id})"
            )
            return False

        else:
            log.info(
                f'New media item, will download: "{item.band_name} / {item.item_title}" '
                f'(id:{item.item_id}) in "{self.media_format}"'
            )

            for attempt in range(self.max_retries):
                try:
                    initial_download_url = self.bandcamp.get_download_file_url(
                        item, encoding=self.media_format
                    )
                    download_file_url = self.bandcamp.check_download_stat(
                        item, initial_download_url
                    )

                    with NamedTemporaryFile(
                        mode="w+b", delete=True, dir=self.temp_dir_root
                    ) as temp_file:
                        log.info(
                            f'Downloading item "{item.band_name} / {item.item_title}" (id:{item.item_id}) '
                            f"from {mask_sig(download_file_url)} to {temp_file.name}"
                        )
                        download_file(download_file_url, temp_file)
                        temp_file.seek(0)
                        temp_file_path = Path(temp_file.name)
                        if is_zip_file(temp_file_path):
                            with TemporaryDirectory(dir=self.temp_dir_root) as temp_dir:
                                log.info(
                                    f'Decompressing downloaded zip "{temp_file.name}" to "{temp_dir}"'
                                )
                                unzip_file(temp_file.name, temp_dir)
                                temp_path = Path(temp_dir)
                                try:
                                    local_path.mkdir(parents=True, exist_ok=True)
                                except OSError as e:
                                    log.error(
                                        f"Failed to create directory: {local_path} ({e}), skipping file extraction"
                                    )
                                    continue
                                for file_path in temp_path.iterdir():
                                    file_dest = self.local_media.get_path_for_file(
                                        local_path, file_path.name
                                    )
                                    log.info(
                                        f'Moving extracted file: "{file_path}" to "{file_dest}"'
                                    )
                                    try:
                                        move_file(file_path, file_dest)
                                    except OSError as e:
                                        log.error(
                                            f"Failed to move {file_path} to {file_dest}: {e}"
                                        )
                        elif item.item_type == "track":
                            slug = item.item_title
                            if item.url_hints and isinstance(item.url_hints, dict):
                                slug = item.url_hints.get("slug", item.item_title)
                            format_extension = self.local_media.clean_format(
                                self.media_format
                            )
                            try:
                                local_path.mkdir(parents=True, exist_ok=True)
                            except OSError as e:
                                log.error(
                                    f"Failed to create directory: {local_path} ({e}), skipping file write"
                                )
                                continue
                            file_dest = self.local_media.get_path_for_file(
                                local_path, f"{slug}.{format_extension}"
                            )
                            log.info(
                                f'Copying single track: "{temp_file_path}" to "{file_dest}"'
                            )
                            try:
                                copy_file(temp_file_path, file_dest)
                            except OSError as e:
                                log.error(
                                    f"Failed to copy {temp_file_path} to {file_dest}: {e}"
                                )
                        else:
                            log.error(
                                f'Downloaded file for "{item.band_name} / {item.item_title}" (id:{item.item_id}) '
                                f'at "{temp_file_path}" is not a zip archive or a single track, skipping'
                            )
                            return False

                        if self.ign_file_path:
                            # We assume that if you use an ignore file once, you'll
                            # keep using it forever (e.g. Docker).
                            # In case you don't, you'll get warnings for missing id file
                            # on the items downloaded in the current session.
                            self.ignores.add(item)
                        else:
                            self.local_media.write_bandcamp_id(item, local_path)

                        self.new_items_downloaded = True
                        return True

                except (
                    BandcampError,
                    DownloadBadStatusCode,
                    DownloadInvalidContentType,
                ) as e:
                    if attempt < self.max_retries - 1:
                        log.warning(
                            f"Attempt {attempt + 1} failed for {item.band_name} / {item.item_title}: {e}. "
                            f"Retrying in {self.retry_wait} seconds..."
                        )
                        time.sleep(self.retry_wait)
                        continue
                    else:
                        log.error(
                            f"All {self.max_retries} attempts failed for {item.band_name} / {item.item_title}: {e}. Skipping."
                        )
                        return False
                except DownloadExpired:
                    log.error(
                        f'Download expired and requires email confirmation on Bandcamp for "{item.band_name} / {item.item_title}" '
                        f"(id:{item.item_id}), skipping"
                    )
                    return False

    async def sync_items(self):
        """Syncs all items with optional concurrency."""
        if self.concurrency == 1:
            # Sequential processing
            for item in self.bandcamp.purchases:
                self.sync_item(item)
        else:
            # Concurrent processing with semaphore to limit concurrency
            semaphore = asyncio.Semaphore(self.concurrency)

            async def sync_with_semaphore(item):
                async with semaphore:
                    # Run sync_item in executor since it's blocking I/O
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(None, self.sync_item, item)

            # Create tasks for all items
            tasks = [sync_with_semaphore(item) for item in self.bandcamp.purchases]

            # Wait for all tasks to complete
            await asyncio.gather(*tasks)

        # We don't need to show this warning if we're running the ignorefile sync script
        if self.show_id_file_warning and not self.sync_ignore_file:
            log.warning(
                f"The {self.ign_file_path} file is tracking already downloaded items, "
                f"but some directories are using bandcamp_item_id.txt files. "
                f"If you want to get migrate from ID files to using the {self.ign_file_path} file, "
                f"pass the '--sync-ignore-file' flag, or"
                f"run the following script inside the downloads directory, then append the "
                f"content of the new ignores.txt file to the ignores file in your "
                f"config directory:\n"
                '  find . -name "bandcamp_item_id.txt" \\\n'
                "    | while read -r id_file\n"
                "      do \\\n"
                '        comment="$(echo "$id_file" \\\n'
                '            | sed -r -e "s%./([^/]+)/([^/]+)/bandcamp_item_id.txt%\\1 / \\2%")"\n'
                '        echo "$(cat "$id_file")  # $comment"\n'
                '        rm "$id_file"\n'
                "      done >> ignores.txt\n"
            )

    def notify(self):
        if self.new_items_downloaded and self.notify_url is not None:
            notify = NotifyURL(self.notify_url)
            notify.notify()
