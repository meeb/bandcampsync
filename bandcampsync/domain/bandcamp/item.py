import json
from typing import Any, cast


class BandcampItem:
    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data
        self._data.setdefault("folder_suffix", "")

    @property
    def band_name(self) -> str | None:
        return cast("str | None", self._data.get("band_name"))

    @property
    def item_title(self) -> str | None:
        return cast("str | None", self._data.get("item_title"))

    @property
    def item_id(self) -> int | None:
        return cast("int | None", self._data.get("item_id"))

    @property
    def sale_item_type(self) -> str | None:
        return cast("str | None", self._data.get("sale_item_type"))

    @property
    def hidden(self) -> bool:
        return bool(self._data.get("hidden", False))

    @property
    def token(self) -> str | None:
        return cast("str | None", self._data.get("token"))

    @property
    def download_url(self) -> str | None:
        return cast("str | None", self._data.get("download_url"))

    @download_url.setter
    def download_url(self, value: str) -> None:
        self._data["download_url"] = value

    @property
    def folder_suffix(self) -> str:
        return cast(str, self._data["folder_suffix"])

    @folder_suffix.setter
    def folder_suffix(self, value: str) -> None:
        self._data["folder_suffix"] = value

    def is_physical_purchase(self) -> bool:
        # Note that this only tells us that this is a physical purchase, not if
        # there's also a digital download
        item_type = self._data.get("item_type")
        if item_type:
            return bool(item_type == "package")
        return bool(self._data.get("sale_item_type") == "p")

    def __repr__(self) -> str:
        return json.dumps(self._data, indent=4, sort_keys=True)

    def __getattr__(self, key: str) -> Any:
        try:
            return self._data[key]
        except KeyError as e:
            raise KeyError(f'BandcampItem value "{key}" does not exist') from e
