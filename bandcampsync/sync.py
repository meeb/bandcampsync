import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from .options import BandcampSyncOptions
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
    STATE_FILENAME = ".bandcampsync-state.json"
    STATE_VERSION = 1

    def __init__(self, options: BandcampSyncOptions, auto_run: bool = True):
        self.ignores = Ignores(
            ign_file_path=options.ign_file_path, ign_patterns=options.ign_patterns
        )
        self.sync_ignore_file = options.sync_ignore_file
        self.media_dir = options.dir_path
        self.media_format = options.media_format
        self.temp_dir_root = options.temp_dir_root
        self.ign_file_path = options.ign_file_path
        self.notify_url = options.notify_url
        self.until_date = options.until_date
        self.dry_run = bool(options.dry_run)
        self.concurrency = max(1, options.concurrency)
        self.max_retries = max(1, options.max_retries)
        self.retry_wait = max(0, options.retry_wait)
        self.skip_hidden = options.skip_hidden

        self.show_id_file_warning = False
        self.new_items_downloaded = False
        self.had_sync_errors = False
        self.sync_errors = []
        self._warned_missing_purchase_date = False

        self.use_collection_checkpoint = not self.until_date
        self.collection_checkpoint_token = self._load_collection_checkpoint()
        index_local_media = not self.collection_checkpoint_token
        if not index_local_media:
            log.info("Collection checkpoint loaded; skipping initial local media index")
        self.local_media = LocalMedia(
            media_dir=options.dir_path,
            ignores=self.ignores,
            skip_item_index=options.skip_item_index,
            sync_ignore_file=options.sync_ignore_file,
            index_on_init=index_local_media,
        )

        self.bandcamp = Bandcamp(cookies=options.cookies)
        self.bandcamp.verify_authentication()
        self.bandcamp.load_purchases(stop_when=self._should_stop_loading_purchase)

        if self.until_date:
            log.info(
                "Will stop after processing purchases on or after: "
                f"{self.until_date.isoformat()} (purchase date GMT)"
            )
        if self.dry_run:
            log.info("Dry run enabled: will not download or write files")

        if auto_run:
            asyncio.run(self.sync_items())
            self.notify()

    @property
    def state_file_path(self):
        return self.media_dir / self.STATE_FILENAME

    @staticmethod
    def _item_token(item):
        token = getattr(item, "token", None)
        if isinstance(token, str) and token:
            return token
        return None

    def _load_collection_checkpoint(self):
        if not self.use_collection_checkpoint:
            return None
        state_file = self.state_file_path
        if not state_file.is_file():
            return None
        try:
            with open(state_file, "rt", encoding="utf-8") as f:
                state = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            log.warning(f'Failed to parse state file "{state_file}": {e}')
            return None
        if not isinstance(state, dict):
            log.warning(
                f'Ignoring invalid state file "{state_file}": expected JSON object'
            )
            return None
        token = state.get("last_seen_token")
        if not isinstance(token, str) or not token:
            return None
        log.info(f'Loaded collection checkpoint from "{state_file}"')
        return token

    def _save_collection_checkpoint(self):
        if not self.use_collection_checkpoint:
            return
        if self.dry_run:
            log.info("Dry run enabled: not updating collection checkpoint")
            return
        if self.had_sync_errors:
            log.warning("Sync had errors; not advancing collection checkpoint")
            return
        collection_items = getattr(self.bandcamp, "collection_items", None)
        if not collection_items:
            collection_items = self.bandcamp.purchases
        if not collection_items:
            return
        newest_item = collection_items[0]
        newest_token = self._item_token(newest_item)
        if not newest_token:
            return
        state = {
            "version": self.STATE_VERSION,
            "last_seen_token": newest_token,
            "last_seen_item_id": getattr(newest_item, "item_id", None),
            "last_seen_purchased": getattr(newest_item, "purchased", None),
            "updated_at_utc": datetime.now(timezone.utc).isoformat(),
        }
        state_file = self.state_file_path
        temp_state_file = Path(f"{state_file}.tmp")
        try:
            with open(temp_state_file, "wt", encoding="utf-8") as f:
                json.dump(state, f, indent=2, sort_keys=True)
                f.write("\n")
            temp_state_file.replace(state_file)
            log.info(f'Updated collection checkpoint: "{state_file}"')
        except OSError as e:
            log.error(f'Failed to write collection checkpoint "{state_file}": {e}')
            if temp_state_file.exists():
                try:
                    temp_state_file.unlink()
                except OSError:
                    pass

    def _record_sync_error(self, message):
        self.had_sync_errors = True
        self.sync_errors.append(message)
        log.error(message)

    def _log_sync_error_summary(self):
        if not self.sync_errors:
            return
        log.warning(f"Sync completed with {len(self.sync_errors)} error(s):")
        for error in self.sync_errors:
            log.warning(f"  - {error}")

    def _should_stop_loading_purchase(self, item):
        if self.until_date:
            purchase_dt = self._parse_purchase_datetime(item)
            if purchase_dt is not None and purchase_dt.date() < self.until_date:
                return True
        if self.collection_checkpoint_token:
            token = self._item_token(item)
            if token and token == self.collection_checkpoint_token:
                log.info(
                    "Reached last known collection checkpoint, stopping pagination"
                )
                return True
        return False

    def _parse_purchase_datetime(self, item):
        purchased = getattr(item, "purchased", None)
        if not purchased or not isinstance(purchased, str):
            return None
        if purchased.endswith(" GMT"):
            try:
                dt = datetime.strptime(purchased, "%d %b %Y %H:%M:%S GMT")
                return dt.replace(tzinfo=timezone.utc)
            except ValueError:
                pass
        try:
            dt = datetime.strptime(purchased, "%d %b %Y %H:%M:%S %Z")
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            if not self._warned_missing_purchase_date:
                log.warning(
                    f'Unable to parse purchase date "{purchased}". '
                    "Date cutoffs may not behave as expected."
                )
                self._warned_missing_purchase_date = True
        return None

    def _ordered_purchases(self):
        items = list(self.bandcamp.purchases)
        if not items:
            return []
        indexed = []
        any_dates = False
        for idx, item in enumerate(items):
            purchase_dt = self._parse_purchase_datetime(item)
            if purchase_dt is not None:
                any_dates = True
            indexed.append((idx, item, purchase_dt))

        if not any_dates:
            return [item for _, item, _ in indexed]

        def sort_key(entry):
            _, _, purchase_datetime = entry
            if purchase_datetime is None:
                return 0, datetime.min.replace(tzinfo=timezone.utc)
            return 1, purchase_datetime

        indexed.sort(key=sort_key, reverse=True)
        return [item for _, item, _ in indexed]

    def _select_items_to_sync(self):
        items = self._ordered_purchases()
        if not items:
            return []

        selected = []
        for item in items:
            token = self._item_token(item)
            if (
                self.collection_checkpoint_token
                and token
                and token == self.collection_checkpoint_token
            ):
                log.info("Stopping at collection checkpoint item")
                break

            if self.until_date:
                purchase_dt = self._parse_purchase_datetime(item)
                if purchase_dt is not None and purchase_dt.date() < self.until_date:
                    log.info(
                        f"Stopping before items older than {self.until_date.isoformat()}"
                    )
                    break

            selected.append(item)
        return selected

    def sync_item(
        self,
        item,
        encoding=None,
    ) -> bool:
        """Syncs a single item (purchase).

        Returns:
            bool: indicating new media was downloaded
        """
        media_format = encoding or self.media_format

        local_path = self.local_media.get_path_for_purchase(item)

        # Check if any "ignore" pattern matches the band name
        if self.skip_hidden and item.hidden:
            log.info(
                f'Item is hidden, skipping: "{item.band_name} / {item.item_title}" '
                f"(id:{item.item_id})"
            )
            return False

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
                f'(id:{item.item_id}) in "{media_format}"'
            )
            if self.dry_run:
                log.info(
                    f'DRY RUN: would download "{item.band_name} / {item.item_title}" '
                    f"(id:{item.item_id})"
                )
                return False
            for attempt in range(self.max_retries):
                try:
                    initial_download_url = self.bandcamp.get_download_file_url(
                        item, encoding=media_format
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
                        download_content_type = download_file(
                            download_file_url, temp_file
                        )
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
                                    self._record_sync_error(
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
                                        self._record_sync_error(
                                            f"Failed to move {file_path} to {file_dest}: {e}"
                                        )
                        elif (
                            item.item_type == "track"
                            or download_content_type.startswith("audio/")
                            # Bandcamp may serve Ogg Vorbis as application/ogg.
                            or download_content_type == "application/ogg"
                        ):
                            slug = item.item_title
                            if item.url_hints and isinstance(item.url_hints, dict):
                                slug = item.url_hints.get("slug", item.item_title)
                            format_extension = self.local_media.clean_format(
                                media_format
                            )
                            try:
                                local_path.mkdir(parents=True, exist_ok=True)
                            except OSError as e:
                                self._record_sync_error(
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
                                self._record_sync_error(
                                    f"Failed to copy {temp_file_path} to {file_dest}: {e}"
                                )
                        else:
                            self._record_sync_error(
                                f'Downloaded file for "{item.band_name} / {item.item_title}" (id:{item.item_id}) '
                                f'at "{temp_file_path}" is not a zip archive or a single track, skipping'
                            )
                            return False

                        if self.ign_file_path:
                            # We assume that if you use an "ignore" file once, you'll
                            # keep using it forever (e.g. Docker).
                            # If you don't, you'll get a warning for the missing ID file
                            # on the items downloaded in the current session.
                            self.ignores.add(item)
                        else:
                            try:
                                self.local_media.write_bandcamp_id(item, local_path)
                            except (OSError, ValueError) as e:
                                self._record_sync_error(
                                    f'Failed to write bandcamp item id for "{item.band_name} / {item.item_title}" '
                                    f'(id:{item.item_id}) to "{local_path}": {e}'
                                )

                        self.new_items_downloaded = True
                        return True

                except BandcampDownloadUnavailable as e:
                    log.info(
                        f'No download available for "{item.band_name} / {item.item_title}" '
                        f"(id:{item.item_id}): {e}. Skipping."
                    )
                    return False
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
                        self._record_sync_error(
                            f"All {self.max_retries} attempts failed for {item.band_name} / {item.item_title}: {e}. Skipping."
                        )
                        return False
                except DownloadExpired:
                    self._record_sync_error(
                        f'Download expired and requires email confirmation on Bandcamp for "{item.band_name} / {item.item_title}" '
                        f"(id:{item.item_id}), skipping"
                    )
                    return False
        return False

    async def sync_items(self):
        """Syncs all items with optional concurrency."""
        items = self._select_items_to_sync()
        total_items = len(items)
        if not items:
            log.info("No purchases to sync after applying filters")
        else:
            if self.concurrency == 1:
                # Sequential processing
                for i, item in enumerate(items, 1):
                    percent = (i / total_items) * 100 if total_items else 0
                    log.info(f"Syncing item {i} of {total_items} ({percent:.1f}%)")
                    self.sync_item(item)
            else:
                # Concurrent processing with semaphore to limit concurrency
                semaphore = asyncio.Semaphore(self.concurrency)

                async def sync_with_semaphore(_item):
                    async with semaphore:
                        # Run sync_item in executor since it's blocking I/O
                        loop = asyncio.get_event_loop()
                        await loop.run_in_executor(None, self.sync_item, _item)

                # Create tasks for all items
                tasks = [sync_with_semaphore(item) for item in items]
                log.info(
                    f"Syncing {total_items} items with concurrency {self.concurrency}"
                )

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

        self._log_sync_error_summary()
        self._save_collection_checkpoint()

    def notify(self):
        if self.dry_run:
            log.info("Dry run enabled: skipping notify")
            return
        if self.new_items_downloaded and self.notify_url is not None:
            notify = NotifyURL(self.notify_url)
            notify.notify()
