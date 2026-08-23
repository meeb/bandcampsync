# Hexagonal architecture cleanup: layering, single-purpose files, domain resource folders

## Context

The bandcampsync rewrite (commit `c0e3802`) restructured the codebase into domain/interface/service layers, but left some things unfinished or inconsistent:

1. `domain/scheduling.py` bundles three unrelated concerns in one file — not single-purpose.
2. `service/sync_collection.py` is a god-function that also imports and constructs the *concrete* `Bandcamp` adapter directly, instead of depending on a domain-defined port the way `download_purchase` already does for the narrower download-file flow. Tests have to monkeypatch a class reference inside the module instead of injecting a fake.
3. `BandcampItem`, `Ignores`, and `LocalMedia` are stateful classes whose methods mix "what this data means" (business rules) with I/O and HTTP-adjacent logic. Some of that logic (`interface/bandcamp/download_resolution.py`, `interface/bandcamp/deduplication.py`) is pure business logic that has *no HTTP in it at all*, yet sits in the `interface` layer today — the wrong side of the boundary.

**Target architecture** (agreed through discussion): the Bandcamp HTTP client stays a class — transport/session mechanics (auth, cookies, request/response, pagination cursors) are not fragmented into functions, that stays in `interface/bandcamp/`. But everything that decides *what the data means* moves to domain, organized **per resource** as a folder of small single-purpose function files around a pure data shape:

```
domain/<resource>/
  model.py    - pydantic BaseModel(s): the shape of the data, no business methods on it
  index.py    - retrieval/shaping: turn raw data (e.g. one page of API JSON) into validated model(s)
  actions.py  - create/modify/destroy: things that change state (write a file, mark something)
  checks.py   - pure predicates/queries about an already-built object (is_x, has_y)
```

Interface layers (today's HTTP trigger server, tomorrow's web UI or a public HTTP API) are meant to end up only importing **service** functions (which call domain's index/actions/checks) plus a handful of exception types — never reaching past service into domain or interface/bandcamp directly. This plan doesn't build a new interface, but every domain/service change here is shaped to make that trivial later.

New dependency: **pydantic** (not currently used anywhere in this repo — add to `[tool.poetry.dependencies]`).

This is a big, multi-phase change. Phases are ordered so each is independently shippable; run the full verification suite (below) after each phase before moving to the next, and commit per phase.

---

## Phase 1 — Split `domain/scheduling.py` into single-purpose files

**Current**: `bandcampsync/domain/scheduling.py` (89 lines) holds `compute_next_run` (pure math), `class SyncState` (thread-safe run-state tracker), and `class LogTail(logging.Handler)` (in-memory log ring buffer) — three unrelated concerns in one file.

**Change**:
- `domain/scheduling.py` → trim to just `compute_next_run`. Drop now-unused `logging`/`threading`/`deque`/`timezone` imports.
- `domain/sync_state.py` (new) → `SyncState`, verbatim body + its own module docstring.
- `domain/log_tail.py` (new) → `LogTail`, verbatim body + its own module docstring.
- `domain/__init__.py` → update the three imports to pull from their new homes, keep re-exporting the same three names under the same `__all__`, so every barrel-import consumer (`interface/http/trigger_server.py`, `interface/service/entrypoint.py`, `service/run_scheduled_sync.py`) needs **no changes**. Update the module docstring (currently claims scheduling.py alone is "the shared surface" — no longer accurate).

**Tests**:
- `tests/domain/test_scheduling.py` → keep only the 3 `test_compute_next_run_*` tests.
- `tests/domain/test_sync_state.py` (new) → move the 3 `test_sync_state_*` tests.
- `tests/domain/test_log_tail.py` (new) → move the 1 `test_log_tail_*` test.
- No changes to `tests/interface/http/test_trigger_server.py` / `tests/service/test_run_scheduled_sync.py` (barrel imports unaffected).

**Status: done** (committed).

---

## Phase 2 — Bandcamp collection port + slim `sync_collection.py`

**Current**: `bandcampsync/service/sync_collection.py` (116 lines) does everything inline, including constructing the concrete `Bandcamp` class directly. Tests monkeypatch `patch.object(_module, "Bandcamp", ...)` for lack of an injection seam.

**Reference pattern to mirror** (already in the codebase): `run_scheduled_sync(...)` delegates to `run_scheduled_sync_with(...)`, which takes the same params plus injectable dependencies as keyword args with real defaults. Tests call `_with` directly and pass fakes.

**New domain port** — `bandcampsync/domain/bandcamp/collection_session.py` (new), styled like the existing `bandcampsync/domain/bandcamp/session.py`:

```python
class BandcampCollectionSession(Protocol):
    purchases: list[BandcampItem]
    collection_items: list[BandcampItem]
    def verify_authentication(self) -> bool: ...
    def load_purchases(self, stop_when: Callable[[BandcampItem], bool] | None = None) -> bool: ...
```

Deliberately separate from `BandcampSession` (interface segregation). The concrete `Bandcamp` class satisfies both structurally. Export from `domain/bandcamp/__init__.py`.

**Two new extracted service functions** (matching the existing single-purpose-file convention: `maybe_save_checkpoint.py`, `maybe_notify.py`, `log_id_file_migration_warning.py`, `log_sync_error_summary.py`, `sync_all_items.py`):
- `bandcampsync/service/prepare_local_media.py` → `prepare_local_media(options, ignores) -> tuple[LocalMedia, str | None, bool]` — the checkpoint-decision + `LocalMedia` construction block, pulled out verbatim. (NOTE: this signature will actually change slightly in Phase 5 once `Ignores`/`LocalMedia` are restructured — see Phase 5. Implement Phase 2 against today's `Ignores`/`LocalMedia` classes as they exist now; Phase 5 will update this function's signature when it gets there.)
- `bandcampsync/service/authenticate_and_load_collection.py` → `authenticate_and_load_collection(bandcamp_factory, options, date_parser, checkpoint_token) -> BandcampCollectionSession` — the auth+paginate block, pulled out verbatim.

**Reworked `sync_collection.py`**: `sync_collection(options)` → one-line delegate to `sync_collection_with(options, bandcamp_factory: Callable[[str], BandcampCollectionSession] = Bandcamp)`. Body composes the extracted pieces plus existing logic (`select_items_to_sync`, `sync_all_items`, the four logging/checkpoint/notify calls) — no behavior change.

**`service/__init__.py`**: add `prepare_local_media`, `authenticate_and_load_collection`, `sync_collection_with` to the barrel, alphabetized.

**Tests**: `tests/service/test_sync_collection.py` → replace `patch.object(_module, "Bandcamp", ...)` + `sync_collection(...)` with `sync_collection_with(options, bandcamp_factory=lambda cookies: bandcamp)`. Keep one plain-`sync_collection(options)` smoke test with the default patched. New `test_prepare_local_media.py` and `test_authenticate_and_load_collection.py`.

**No changes needed** to `do_sync.py`, `run_scheduled_sync.py`, `entrypoint.py`, top-level `bandcampsync/__init__.py` — `bandcamp_factory` stays a same-module default, not threaded through the composition root in this pass.

**Status: done** (committed). Also folded in along the way: `BandcampClientBase.request()` now verifies authentication lazily on first use instead of requiring callers to remember to call `verify_authentication()` themselves (raised while implementing this phase - see commit `44a111f`).

---

## Phase 3 — `domain/bandcamp_item/`: pydantic model + index/checks, pull pure logic out of `interface/bandcamp/`

**Current problem, concretely**: `interface/bandcamp/mixins/fancollection.py::load_purchases()` fuses HTTP pagination (cursor/token bookkeeping — genuinely transport, stays in interface) together with constructing `BandcampItem` from raw JSON, field validation, resolving each item's download URL, and de-duplication (genuinely business logic, currently misplaced in `interface/bandcamp/download_resolution.py` and `interface/bandcamp/deduplication.py` — neither file makes an HTTP call). `interface/bandcamp/item.py`'s `BandcampItem` is itself a raw-dict wrapper with `__getattr__` magic (raises `KeyError` not `AttributeError` on a missing key — this is *why* `getattr(item, "item_type", "")` in `deduplication.py` doesn't actually work as a fallback today, confirmed live).

**New folder** — `bandcampsync/domain/bandcamp_item/`:

- **`model.py`** — pure data shape, pydantic:

  ```python
  class BandcampItem(BaseModel):
      model_config = ConfigDict(validate_assignment=True)  # not frozen: download_url/folder_suffix are set after construction
      item_id: int | None = None
      band_name: str | None = None
      item_title: str | None = None
      item_type: str | None = None
      hidden: bool = False
      token: str | None = None
      download_url: str | None = None
      folder_suffix: str = ""
      sale_item_type: str | None = None
      sale_item_id: int | None = None
      is_preorder: bool = False
      url_hints: dict[str, Any] | None = None
      purchased: str | None = None
      # extra="ignore" (pydantic default): upstream JSON has dozens of fields
      # (currency, price, genre_id, ...) nothing here reads - keep them out
      # of the typed surface instead of smuggling them through.
  ```

  Confirmed complete field list via grep across every `item.`/`purchase.` attribute access and `getattr(item, ...)` call in the codebase.

- **`index.py`** — retrieval/shaping, no HTTP, no loop (pagination stays in interface — see below):

  ```python
  def build_items_from_page(
      raw_items: list[dict[str, Any]], redownload_urls: dict[str, str]
  ) -> list[BandcampItem]:
      """Validates one page of raw collection JSON into BandcampItems,
      skipping (and logging) entries missing band_name/item_title/item_id,
      and resolving each item's download_url. Equivalent to today's
      per-item loop body inside FanCollectionMixin.load_purchases()."""
      ...

  def resolve_download_url(item: BandcampItem, redownload_urls: dict[str, str]) -> str | None:
      ...  # moved verbatim from interface/bandcamp/download_resolution.py

  def deduplicate_purchases(items: list[BandcampItem]) -> None:
      ...  # moved (near-)verbatim from interface/bandcamp/deduplication.py;
      # today's version takes a pre-grouped dict - keep grouping internal to
      # this function instead of making callers build the group map themselves
  ```

- **`checks.py`** — pure predicates on an already-built item:

  ```python
  def is_physical_purchase(item: BandcampItem) -> bool: ...  # moved off the class, same logic
  ```

**Interface changes**:
- `interface/bandcamp/mixins/fancollection.py::load_purchases()` — **keeps** the `while True` loop, `older_than_token` cursor bookkeeping, and the `self.request(...)` calls (this is what "pagination is an interface thing" means — it's Bandcamp's specific transport mechanic, not a business rule). For each page, replaces the current inline per-item loop with `items = build_items_from_page(data["items"], data["redownload_urls"])`, appends to `self.collection_items`/`self.purchases`, and still runs `stop_when` per item (that decision itself — `should_stop_loading_purchase` — is already a domain function, unchanged). After the loop, calls `deduplicate_purchases(self.purchases)` once on the full accumulated list (dedup needs to see all pages, so it can't run per-page).
- `interface/bandcamp/download_resolution.py` and `interface/bandcamp/deduplication.py` — **deleted**, logic now in `domain/bandcamp_item/index.py`.
- `interface/bandcamp/item.py` — **deleted**, replaced by `domain/bandcamp_item/model.py`. `domain/bandcamp/item.py` (today's home) also goes away; update `domain/bandcamp/__init__.py` and everywhere importing `BandcampItem` from `bandcampsync.domain.bandcamp` to import from `bandcampsync.domain.bandcamp_item` instead (mechanical import-path change, no logic change, across ~15 files — grep `from bandcampsync.domain.bandcamp import` for the full list at implementation time).
- **Follow-up, not done yet**: verify `BandcampItem`'s field-level required/optional split against more real captured payloads (or a live authenticated request via `poetry shell` + the real client) rather than guessing. One real bug already found and fixed this way: `hidden` comes back as `"hidden": null` in real payloads, not `false` - `bool = False` would reject that outright at construction, so it's `bool | None = None`. Every other Optional field (`item_id`/`band_name`/`item_title`/`item_type`/`token`/`sale_item_type`/`sale_item_id`/`url_hints`/`purchased`) is backed by an existing defensive check elsewhere in the codebase (e.g. `build_items_from_page` already skips-and-logs a missing `band_name`/`item_title`/`item_id`, tagged "possibly a subscription?") - real evidence they can legitimately be absent, not just defensive guessing. Worth a dedicated pass with more real samples (different item types: subscriptions, gifts, preorders, hidden items) to see whether any of these should tighten further, e.g. whether `band_name`/`item_title`/`item_id` should be required fields that pydantic itself rejects a malformed item on (raising `ValidationError`, caught by `build_items_from_page`) rather than Optional fields checked post-construction.
- `interface/bandcamp/mixins/download.py::get_download_file_url()` — **flagged, not committed to yet**: its pagedata-walking logic (matching `digital_items[].item_id`, extracting `downloads[encoding]["url"]`) is the same *shape* of misplaced business logic (pure JSON-shape-navigation, no HTTP mechanics) as what's moving in this phase. Left as a follow-up candidate for the same treatment rather than folded into this already-large phase — flag for a decision when you get here rather than deciding now.

**Call-site mechanical changes** (same logic, new import path / free-function form):
- `item.is_physical_purchase()` → `is_physical_purchase(item)` (one call site: was in `download_resolution.py`, now co-located in `domain/bandcamp_item/checks.py` alongside its only caller `index.py::resolve_download_url`, or called from `service/` — confirm exact call site when `resolve_download_url` is relocated).
- `BandcampItem(item_data)` / `BandcampItem({...})` construction → `BandcampItem(**item_data)` (pydantic dict-unpacking) at both construction sites (`fancollection.py` via `build_items_from_page`, `media.py`'s synthetic construction of `item_id`/`band_name`/`item_title`).
- The `deduplication.py` `getattr(item, "item_type", "")` `KeyError` bug disappears automatically as a side effect (worth a one-line callout in the commit message, not a separate fix).
- Every other `item.<field>` dot-access (`skip_rules.py`, `purchase_selection.py`, `checkpoint.py`, `media.py`, `place_single_track.py`, etc.) needs no change — same attribute names, now backed by real typed fields. mypy now actually catches typos here (couldn't before, `__getattr__` returns `Any`).

**Tests**:
- `tests/domain/test_bandcamp_item.py` → move under `tests/domain/bandcamp_item/`, update `is_physical_purchase()` calls to free-function form, import path updates.
- `tests/interface/bandcamp/test_download_resolution.py`, `tests/interface/bandcamp/test_deduplication.py` → move to `tests/domain/bandcamp_item/test_index.py` (or split further if that reads better), same test cases, updated import paths. `deduplicate_purchases`'s new signature (`list[BandcampItem]` instead of a pre-grouped dict) needs the test fixtures updated to match.
- `tests/interface/bandcamp/test_load_purchases.py` → still valid as an interface-level integration test of the pagination loop, but its mocked page payloads now flow through the real `build_items_from_page`/`deduplicate_purchases` rather than inline logic — should still pass unchanged in spirit, verify field-by-field.
- `tests/interface/bandcamp/test_verify_authentication.py`, `test_client.py`, `test_get_download_file_url.py`, `test_check_download_stat.py`, `test_fetch_purchase_file.py`, `test_expired_download_page.py` — only need the `BandcampItem` import path updated (`bandcampsync.domain.bandcamp` → `bandcampsync.domain.bandcamp_item`), no logic changes.

**Status: done** (committed), with a few refinements made while implementing, beyond what this phase originally specified:

- `band_name`/`item_title`/`item_id` ended up **required** fields (not `| None`), not just typed-but-optional. Rationale: the app only ever deals with items it's about to download or has already indexed - "we're just downloading purchases," not modelling every hypothetical Bandcamp API shape speculatively - and the original code already treated a missing one of these three as fatal-for-that-item (skip + log, "possibly a subscription?"), so pydantic itself now rejects a malformed raw item outright (`ValidationError`) instead of constructing a half-formed `BandcampItem` and checking for `None` at every downstream call site. `band_name`/`item_title` also got `Field(min_length=1)` to match the original falsy-string check exactly. `build_items_from_page` catches the `ValidationError` and reports the same three distinct log messages as before, in the same priority order.
- `hidden` is `bool | None`, not `bool = False`: checked the two real captured payload fixtures and found `"hidden": null` in both, which `bool = False` would have rejected outright at construction. Every *other* Optional field is backed by an existing defensive check elsewhere in the pre-existing codebase (real evidence of legitimate absence, not guessing) - see the follow-up note below for why those weren't tightened further yet.
- The per-field-missing logging (`log_invalid_item`) lives in a new `actions.py`, not `index.py` - logging is a side effect ("doing something"), not retrieval/shaping, even though it's triggered from within `build_items_from_page` (which stays in `index.py`).
- Knock-on cleanup: the `cast()` calls in `domain/media.py` and `domain/ignores.py` that worked around the old dict-wrapper's untyped `band_name`/`item_id` are gone now that those are real guaranteed-typed fields - this was the concrete "messy casting" this phase was meant to fix.

---

## Phase 3.5 — split `domain/file_transfer/` into domain (local/pure) + `interface/file_transfer/` (HTTP)

Raised mid-session: `domain/file_transfer/` made real HTTP requests (`stream_to_file.py`, `response_body.py`'s `refetch_response_body`) and operated on HTTP response objects (`content_type_check.py`, `write_chunks.py`, `response_status.py`) - genuinely interface-shaped, not domain, and not Bandcamp-specific either (generic URL-to-disk transport). "Unless the file transfer stuff is very specifically bandcamp shaped, it doesn't belong in domain."

**Split**:
- **Stays in `domain/file_transfer/`** (local file / pure operations, no different in kind from what `LocalMedia`/`checkpoint.py` already do directly in domain): `archive.py` (zip extraction), `local_copy.py` (shutil copy/move), `url_masking.py` (pure string masking), `errors.py` (the `Transfer*` exception types - shared vocabulary both layers use).
- **Moves to new `interface/file_transfer/`**: `stream_to_file.py`, `response_body.py`, `content_type_check.py`, `write_chunks.py`, `response_status.py`.

Turned out low-risk: `domain/collection/download_purchase/*` only ever imported the local-file half (`copy_file`, `move_file`, `extract_zip_archive`, `is_zip_archive`, `mask_signed_url`, the `Transfer*` exception types) - none of it touches the HTTP-request-making half, so **no domain code needed to change**. Only `interface/bandcamp/mixins/download.py` (which calls `stream_url_to_file`) needed an import update.

**Status: done** (committed).

---

## Phase 4 — `domain/ignore_entry/`: same convention

**Current**: `bandcampsync/domain/ignores.py` — one class conflating rule data (`ids`, `band_patterns`), the business predicate (`is_ignored`), and file-rewrite bookkeeping (`ign_lines`, `ign_insert_index`, `add()`).

**New folder** — `bandcampsync/domain/ignore_entry/`:
- **`model.py`** — `IgnoreRules` (pydantic, frozen — pure rule data, nothing here is ever mutated in place):

  ```python
  class IgnoreRules(BaseModel):
      model_config = ConfigDict(frozen=True)
      ids: frozenset[int] = frozenset()
      band_patterns: tuple[str, ...] = ()
  ```

  Plus `IgnoreFileLayout` (plain `@dataclass`, not pydantic — it's parse-result bookkeeping for preserving file formatting on rewrite, not validated external data): `lines: list[str]`, `insert_index: int`.
- **`index.py`** — retrieval: `load_ignore_rules(ign_file_path: Path | None, ign_patterns: str) -> tuple[IgnoreRules, IgnoreFileLayout]` (today's `parse_ignores()` body, split to return both pieces; still creates the file from the template if missing, same as today).
- **`actions.py`** — mutation: `record_ignored_item(ign_file_path: Path, layout: IgnoreFileLayout, item: BandcampItem) -> IgnoreFileLayout` (today's `add()` body: computes new lines, `atomic_write_text`, returns the updated layout for the next call).
- **`checks.py`** — pure predicate: `is_ignored(rules: IgnoreRules, item: BandcampItem) -> bool` (today's `Ignores.is_ignored` logic, same log messages). This is the concrete "unwieldy to test" fix: `is_ignored(IgnoreRules(ids={1}), item)` is a one-line test, no filesystem.

**Call-site impact** (widest-reaching part of this plan): `PurchaseDownloadContext.ignores: Ignores` (in `domain/collection/download_purchase/context.py`) splits into `ignore_rules: IgnoreRules` plus something to carry the mutable `IgnoreFileLayout` across a run (see open point below). Consumers to update:
- `service/prepare_local_media.py` (from Phase 2) and `service/sync_collection.py`: `Ignores(...)` construction → `load_ignore_rules(...)`.
- `domain/media.py`/Phase 5's replacement: currently `LocalMedia` reaches into `ignores.is_ignored()`/`.add()` during its own directory walk — this is itself a layering smell (a local-media indexer needing write access to the ignore file). Resolve during Phase 5 implementation; don't presuppose the shape here.
- `domain/collection/download_purchase/skip_rules.py`: `ctx.ignores.is_ignored(purchase)` → `is_ignored(ctx.ignore_rules, purchase)`.
- `domain/collection/download_purchase/local_bookkeeping.py`: `ctx.ignores.add(purchase)` → `record_ignored_item(ctx.ign_file_path, <current layout>, purchase)`, persisting the returned updated layout for the next call.

**Open point to resolve during implementation**: `PurchaseDownloadContext` is currently a frozen dataclass; `IgnoreFileLayout` needs to mutate across many `record_ignored_item` calls within one sync run. Either carry it in a small mutable box passed alongside the frozen `ctx`, or reconsider freezing just that one field. Pick whichever reads cleanest once the surrounding code is in front of you.

**Resolved**: added `IgnoreFileWriter` (plain mutable `@dataclass`, in `actions.py` alongside the pure `record_ignored_item()` it wraps) - holds `ign_file_path` and the current `layout`, and its one method `record(item)` calls the pure action function and reassigns its own `.layout`. `PurchaseDownloadContext.ignore_file_writer: IgnoreFileWriter` is a frozen field pointing at a mutable object - freezing only stops the field itself from being reassigned, not the object it points to, so this works within the existing frozen-dataclass without loosening it. `record_ignored_item()` itself stays pure/directly testable (explicit `layout` in, updated `layout` out, no hidden state).

`domain/media.py`'s `LocalMedia` layering smell (reaching into ignore-file write access during its own directory walk) - not resolved here, left exactly as it was (now calling the renamed `ignore_rules`/`ignore_file_writer` params) since Phase 5 is where `LocalMedia` itself gets restructured.

**Status: done** (committed).

**Tests**: delete `tests/domain/test_ignores.py`, replace with `tests/domain/ignore_entry/test_checks.py` (pure, no filesystem — id match / pattern match / neither), `tests/domain/ignore_entry/test_index.py` and `test_actions.py` (the parsing/rewriting tests, same coverage as today, adapted signatures). Update `tests/domain/test_media.py`, `tests/service/test_sync_collection.py`, `tests/domain/collection/download_purchase/test_skip_rules.py`, `test_local_bookkeeping.py` for the new `ctx` shape.

---

## Phase 5 — `domain/local_media_entry/`: same convention, lighter touch

**Current**: `bandcampsync/domain/media.py` — `LocalMedia` walks the media directory in `__init__`/`index()` (I/O), tracks `media: dict[int, Path]` and `item_names: set[tuple[str, str]]` as mutable state, mixes in pure path-computation methods (`get_path_for_purchase`, `get_path_for_file`, `clean_format` — already `@staticmethod`) with I/O (`is_locally_downloaded` — which also *lazily mutates* `self.media`/`self.item_names` as a side effect of being queried; `write_bandcamp_id`).

**New folder** — `bandcampsync/domain/local_media_entry/`, mirroring Phase 4:
- **`model.py`** — `MediaIndex` (pydantic): `by_item_id: dict[int, Path]`, `item_names: frozenset[tuple[str, str]]`.
- **`index.py`** — `index_local_media(media_dir: Path) -> MediaIndex` (the directory-walk I/O, returns a fresh snapshot instead of mutating an instance).
- **`checks.py`** — `is_locally_downloaded(index: MediaIndex, item: BandcampItem, local_path: Path) -> tuple[bool, MediaIndex]` — restructured to *not* silently mutate: the fallback check of `local_path`'s own id file can discover something the eager walk missed (e.g. `index_on_init=False` runs); return the possibly-updated index instead of hiding the mutation inside a query call, and let the caller decide whether to keep it.
- **`actions.py`** — `write_bandcamp_id(item: BandcampItem, dirpath: Path) -> None` (moved as-is, already pure I/O with no hidden state).
- `clean_format`, `get_path_for_purchase`, `get_path_for_file` stay as free functions — already small and single-purpose as static-method-shaped functions; put them in `index.py` (they're read-only path computation, closest fit) unless implementation reveals a cleaner split.

**Call-site impact**: `PurchaseDownloadContext.local_media: LocalMedia` → replaced by whatever holder reads best once you're looking at the actual `download_purchase/*` call sites (`skip_rules.py`, `download_purchase.py`, `local_bookkeeping.py`, `place_single_track.py`, `place_zip_archive.py` all currently call `ctx.local_media.<method>(...)`) — don't presuppose the exact shape (could be a small `LocalMediaSession` bundling `media_dir` + `MediaIndex`, or separate context fields). `service/prepare_local_media.py` (Phase 2) updates to call `index_local_media(...)` instead of constructing `LocalMedia(...)`.

**Tests**: `tests/domain/test_media.py` splits like Phase 4's — pure index-query tests need no filesystem; directory-walk and file-write tests keep using `tmp_path` as today.

**Resolved differently than sketched above, for a concrete reason**: `sync_all_items.py` runs purchases concurrently via a thread pool, and `is_locally_downloaded`'s lazy-discovery cache (`self.media`/`self.item_names`) is shared and mutated across that whole run. An immutable `MediaIndex` returned fresh on every call (the `tuple[bool, MediaIndex]` idea above) would mean each concurrent call computes its own delta from a possibly-stale base and the caller has nowhere shared to reconcile them - a real lost-update risk, not just a style question. So:

- `MediaIndex` (pydantic, frozen) is used only as the *snapshot* type returned by the one-shot `index_local_media()` walk - not as `LocalMedia`'s live state.
- `checks.py::is_locally_downloaded(media: dict[int, Path], item_names: set[tuple[str, str]], item, local_path) -> bool` takes plain mutable containers and mutates them in place on discovery. This is the same GIL-atomicity safety the original code already relied on (simple dict/set mutation from multiple threads doesn't corrupt state), just made explicit at the call site instead of hidden inside a class method.
- `LocalMedia` (kept, in `domain/media.py`) is now a thin shell: holds `self.media`/`self.item_names` (seeded from one `index_local_media()` snapshot) and delegates every method to the extracted free functions. Its public method signatures are **unchanged**, so none of the 5 `ctx.local_media.<method>(...)` call sites in `download_purchase/*` needed to change at all.
- The ignore-file layering smell flagged in Phase 4 *is* fixed here: `index_local_media(media_dir, on_item_discovered=callback)` takes an optional callback invoked per discovered item, rather than importing `ignore_entry` itself. `LocalMedia.__init__` supplies a closure that does the `is_ignored`/`ignore_file_writer.record` sync - so `local_media_entry/` has zero dependency on `ignore_entry`, and the composition of the two resources happens where `LocalMedia` is constructed, not inside the indexing walk.

**Status: done** (committed).

---

## Dependency change

`pyproject.toml`:

```toml
[tool.poetry.dependencies]
python = "^3.10"
beautifulsoup4 = "^4.14.3"
curl-cffi = "^0.14.0"
pydantic = "^2.x"  # pin to latest 2.x at implementation time
```

Optionally add `plugins = ["pydantic.mypy"]` under `[tool.mypy]` for stricter validate-on-init checking — nice-to-have, not required (plain pydantic + `mypy --strict` already type-checks correctly without it).

---

## Verification (after every phase)

```
pytest -q                              # full suite must pass
mypy                                    # strict mode must pass
ruff check bandcampsync/ tests/         # must pass
ruff format --check bandcampsync/ tests/
```

Pure refactor of internal domain/service/interface code, no user-facing behavior change — the test suite is the source of truth, no manual verification needed. Commit after each phase so a regression in a later phase is easy to bisect.

---

## Deferred follow-ups (noted, not scheduled)

- **`record_error: Callable[[str], None]` threaded through domain functions** (`download_purchase.py`, `skip_rules.py`, `local_bookkeeping.py`, `download_attempt.py`, `place_single_track.py`, `place_zip_archive.py`, `file_placement.py`): each layer should probably have its own exception classes instead, with the service layer deciding whether to catch domain exceptions or let them bubble up to interface, rather than every domain function taking a callback to accumulate error strings. Explicitly deferred - not urgent, and any work here must keep behavior identical to the original bandcampsync (same error messages, same skip-vs-fail decisions), just with better structure.

---

## Discussed and resolved: where does the Bandcamp session contract live?

Raised mid-session: should `BandcampSession`/`BandcampCollectionSession`/`BandcampFullSession` (domain-declared Protocols, satisfied structurally by `interface.bandcamp.Bandcamp`) actually live in domain, or should `interface/bandcamp/` declare its own contract instead (with domain importing the type for annotations)?

**Resolved: keep as-is.** Domain declaring the port is the standard hexagonal/DIP pattern already in the codebase before this session (`BandcampSession` predates Phase 1) - domain has zero dependency on interface, not even for types.
