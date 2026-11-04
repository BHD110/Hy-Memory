"""ZCode CLI auto-memory Markdown and its session database.

ZCode keeps user and project memory as Markdown under
``cli/memories/projects/*/memory/`` and conversations in the SQLite store at
``cli/db/db.sqlite``. Both live under ``~/.zcode``. Markdown references remain
text; this reader never resolves a link from a memory file, and the session
database is read through the same read-only snapshot helper the other SQLite
sources use.
"""

import asyncio
import hashlib
import json
import os
import re
import sqlite3
import stat
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

from pydantic import JsonValue

from one_memory.imports.access import (
    AuthorizedSourceFile,
    AuthorizedSourceRoot,
    SourceAccessError,
    SourceAccessErrorCode,
    safe_project_label,
)
from one_memory.imports.adapters import (
    ScanCursorTouch,
    ScanEvent,
    ScanFailure,
    ScanIssueCode,
    ScannedEvidence,
    ScanOptions,
    ScanPhase,
    ScanProgressEvent,
    SourceCapabilities,
    SourceCursor,
    SourceDescriptor,
    StorageKind,
)
from one_memory.imports.async_bridge import iterate_in_worker
from one_memory.imports.models import EvidenceContentKind, WrittenBy
from one_memory.imports.sources.common import (
    ParsedMessage,
    SourceInstallState,
    is_unchanged,
    source_cursor,
    to_evidence,
)
from one_memory.imports.sqlite_access import open_sqlite_readonly

ZCODE_DESCRIPTOR = SourceDescriptor(
    source_id="zcode",
    display_name="ZCode",
    storage_kinds=frozenset({StorageKind.MARKDOWN, StorageKind.SQLITE}),
    capabilities=SourceCapabilities(
        can_append=True,
        can_observe_edits=False,
        can_observe_deletes=False,
        can_reconcile_complete_set=False,
    ),
)

_MAX_MEMORY_BYTES = 2 * 1024 * 1024
_MEMORY_INDEX = "memory.md"
#: ZCode's memory files start with YAML metadata (`name`, `description`,
#: `metadata.type`). It describes the file, not the memory, so it is removed
#: before the body is stored as memory content.
_FRONTMATTER = re.compile(r"\A---[ \t]*\r?\n.*?\r?\n---[ \t]*(?:\r?\n|\Z)", re.DOTALL)
_DB_RELATIVE = Path("cli/db/db.sqlite")
_DB_SOURCE_VERSION = "zcode-session-db-v1"


def _memory_files(
    grant: AuthorizedSourceRoot, *, max_targets: int
) -> Iterator[AuthorizedSourceFile]:
    """List only ZCode's documented memory directories, rejecting links."""
    grant.check_root()
    projects = grant.root / "cli" / "memories" / "projects"
    directories: list[Path] = []
    if projects.is_dir() and not projects.is_symlink():
        directories.extend(
            project / "memory"
            for project in sorted(projects.iterdir())
            if project.is_dir() and not project.is_symlink()
        )
    count = 0
    for directory in directories:
        if not directory.is_dir() or directory.is_symlink():
            continue
        for path in sorted(directory.iterdir()):
            if path.suffix.lower() != ".md" or path.is_symlink():
                continue
            # `MEMORY.md` is the index of the other files, not a memory itself;
            # importing it would add a link list beside every entry it names.
            if path.name.casefold() == _MEMORY_INDEX:
                continue
            if count >= max_targets:
                raise SourceAccessError(SourceAccessErrorCode.BUDGET_EXCEEDED)
            count += 1
            yield grant.listed_file(path)


def _database_file(grant: AuthorizedSourceRoot) -> AuthorizedSourceFile | None:
    """The session store as an authorized file, or None when absent.

    The store is far larger than the per-file import ceiling, so its own size
    is used as the ceiling: SQLite reads it through a read-only snapshot and
    never loads the whole file into this process.
    """
    grant.check_root()
    for directory in (grant.root / "cli", grant.root / "cli" / "db"):
        if directory.is_symlink():
            return None
    path = grant.root / _DB_RELATIVE
    try:
        details = os.lstat(path)
    except OSError:
        return None
    if stat.S_ISLNK(details.st_mode) or not stat.S_ISREG(details.st_mode):
        return None
    return AuthorizedSourceFile(
        source_id=ZCODE_DESCRIPTOR.source_id,
        root=grant.root,
        path=path,
        relative_path=_DB_RELATIVE,
        # The live host grows the store while an import is running. The size
        # gate exists to stop unbounded reads, not to reject the host's own
        # next write; allow headroom without opening the file through it.
        max_bytes=details.st_size + 512 * 1024 * 1024,
        file_identity=f"{details.st_dev}:{details.st_ino}",
        size=details.st_size,
        modified_ns=details.st_mtime_ns,
        changed_ns=0,
        root_identity=grant.root_identity,
        requested_root=grant.requested_root,
        access_check=grant.access_check,
    )


def _database_token(source_file: AuthorizedSourceFile) -> tuple[int, int]:
    """A change token that includes the WAL, where the host writes first."""
    size, modified = source_file.size, source_file.modified_ns
    try:
        wal = os.lstat(source_file.path.with_name(source_file.path.name + "-wal"))
    except OSError:
        return size, modified
    if stat.S_ISREG(wal.st_mode):
        return size + wal.st_size, max(modified, wal.st_mtime_ns)
    return size, modified


def _database_unchanged(
    source_file: AuthorizedSourceFile,
    previous: SourceCursor | None,
) -> bool:
    if previous is None or not previous.read_to_end:
        return False
    size, modified = _database_token(source_file)
    return (
        previous.file_identity == source_file.file_identity
        and previous.observed_size == size
        and previous.observed_modified_ns == modified
    )


def _database_cursor(
    source_file: AuthorizedSourceFile,
    checkpoint: str,
    *,
    read_to_end: bool,
) -> SourceCursor:
    size, modified = _database_token(source_file)
    return SourceCursor(
        file_key=source_file.safe_id,
        file_identity=source_file.file_identity,
        checkpoint=checkpoint,
        observed_size=size,
        observed_modified_ns=modified,
        read_to_end=read_to_end,
    )


def _row_checkpoint(checkpoint: str) -> int:
    if not checkpoint.startswith("row:"):
        return 0
    try:
        return max(0, int(checkpoint[4:]))
    except ValueError:
        return 0


def _count_database_sessions(path: Path) -> int:
    """A cheap count for source discovery; does not copy a live WAL."""
    try:
        encoded = quote(path.as_posix(), safe="/:")
        connection = sqlite3.connect(f"file:{encoded}?mode=ro", uri=True, timeout=2.0)
    except sqlite3.Error:
        return 0
    try:
        connection.execute("PRAGMA query_only = ON")
        row = connection.execute("SELECT count(*) FROM session").fetchone()
        return int(row[0]) if row is not None else 0
    except sqlite3.Error:
        return 0
    finally:
        connection.close()


def _message_rows(
    source_file: AuthorizedSourceFile,
    after_rowid: int,
    *,
    max_messages: int | None,
) -> Iterator[SourceCursor | ScannedEvidence]:
    """Read user and assistant text out of ZCode's session store.

    Yields the cursor for each message before its evidence so an interrupted
    scan resumes at the next row rather than replaying the whole store.
    """
    emitted = 0
    with open_sqlite_readonly(source_file, mirror_wal=False) as connection:
        connection.row_factory = sqlite3.Row
        sessions = {
            str(row["id"]): str(row["directory"] or "")
            for row in connection.execute("SELECT id, directory FROM session").fetchall()
        }
        rows = connection.execute(
            """
            SELECT m.rowid AS rowid, m.id AS id, m.session_id AS session_id,
                   m.time_created AS created, m.data AS data,
                   p.sequence AS part_sequence, p.data AS part_data
            FROM message m
            JOIN part p ON p.message_id = m.id
            JOIN session s ON s.id = m.session_id
            WHERE m.rowid > ?
              AND s.task_type = 'interactive'
              AND json_extract(p.data, '$.type') = 'text'
            ORDER BY m.rowid, p.sequence
            """,
            (after_rowid,),
        )
        current: int | None = None
        last_rowid = after_rowid
        record: dict[str, JsonValue] = {}
        texts: list[str] = []
        created = 0
        message_id = ""
        session_id = ""

        def finished() -> ScannedEvidence | None:
            if current is None or not texts:
                return None
            role = record.get("role")
            if role not in {"user", "assistant"}:
                return None
            semantics = record.get("semantics")
            semantics = semantics if isinstance(semantics, dict) else {}
            if record.get("synthetic") is True:
                return None
            if semantics.get("uiVisibility") not in (None, "visible"):
                return None
            if role == "user" and semantics.get("origin") not in (None, "real_user"):
                return None
            verbatim = "\n\n".join(text for text in texts if text.strip()).strip()
            if not verbatim:
                return None
            workspace = sessions.get(session_id, "")
            parsed = ParsedMessage(
                conversation_id=session_id,
                message_id=message_id,
                role=str(role),
                written_by=(WrittenBy.PERSON if role == "user" else WrittenBy.AGENT),
                verbatim=verbatim,
                created_at=datetime.fromtimestamp(created / 1000, UTC),
                workspace=workspace or None,
                project=safe_project_label(workspace) or None,
                record_type=f"session.message.{role}",
            )
            return ScannedEvidence(
                evidence=to_evidence(
                    source_id=ZCODE_DESCRIPTOR.source_id,
                    source_file=source_file,
                    parsed=parsed,
                    ordinal=f"{source_file.safe_id}:{current}",
                    source_version=_DB_SOURCE_VERSION,
                ),
                cursor=_database_cursor(source_file, f"row:{current}", read_to_end=False),
            )

        try:
            for row in rows:
                rowid = int(row["rowid"])
                last_rowid = max(last_rowid, rowid)
                if current is not None and rowid != current:
                    event = finished()
                    if event is not None:
                        emitted += 1
                        yield event
                        if max_messages is not None and emitted >= max_messages:
                            return
                    current = None
                if current is None:
                    current = rowid
                    message_id = str(row["id"])
                    session_id = str(row["session_id"])
                    created = int(row["created"])
                    try:
                        decoded = json.loads(str(row["data"]))
                    except ValueError:
                        decoded = {}
                    record = decoded if isinstance(decoded, dict) else {}
                    texts = []
                part = row["part_data"]
                try:
                    decoded_part = json.loads(str(part))
                except ValueError:
                    continue
                if isinstance(decoded_part, dict):
                    text = decoded_part.get("text")
                    if isinstance(text, str):
                        texts.append(text)
        finally:
            rows.close()
        event = finished()
        if event is not None:
            yield event
        yield ScanCursorTouch(
            cursor=_database_cursor(source_file, f"row:{last_rowid}", read_to_end=True)
        )


class ZCodeAdapter:
    def __init__(self, grant: AuthorizedSourceRoot) -> None:
        if grant.source_id != ZCODE_DESCRIPTOR.source_id:
            raise ValueError("Descriptor and authorized root source IDs must match")
        self.grant = grant
        self.descriptor = ZCODE_DESCRIPTOR

    async def detect(self) -> bool:
        return (await self.install_state()).detected

    async def install_state(self) -> SourceInstallState:
        def state() -> SourceInstallState:
            installed = self.grant.root.is_dir()
            if not installed:
                return SourceInstallState(installed=False, session_count=0, detected=False)
            memories = sum(1 for _ in _memory_files(self.grant, max_targets=100_000))
            database = self.grant.root / _DB_RELATIVE
            sessions = _count_database_sessions(database)
            return SourceInstallState(
                installed=True,
                session_count=memories + sessions,
                detected=True,
            )

        return await asyncio.to_thread(state)

    async def count_sessions(self, *, limit: int | None = None) -> int:
        def count() -> int:
            found = 0
            for _ in _memory_files(self.grant, max_targets=100_000):
                found += 1
                if limit is not None and found >= limit:
                    return found
            database = self.grant.root / _DB_RELATIVE
            found += _count_database_sessions(database)
            return found if limit is None else min(found, limit)

        return await asyncio.to_thread(count)

    async def has_changes(self, options: ScanOptions) -> bool:
        def changed() -> bool:
            if any(
                not is_unchanged(item, options.cursors)
                for item in _memory_files(
                    self.grant, max_targets=options.max_scan_targets or 100_000
                )
            ):
                return True
            source_file = _database_file(self.grant)
            if source_file is None:
                return False
            return not _database_unchanged(source_file, options.cursors.get(source_file.safe_id))

        return await asyncio.to_thread(changed)

    async def live_baseline(self) -> dict[str, SourceCursor]:
        def cursors() -> dict[str, SourceCursor]:
            result = {
                item.safe_id: source_cursor(item, f"byte:{item.size}").model_copy(
                    update={"read_to_end": True}
                )
                for item in _memory_files(self.grant, max_targets=100_000)
            }
            source_file = _database_file(self.grant)
            if source_file is not None:
                result[source_file.safe_id] = _database_cursor(
                    source_file, "row:0", read_to_end=True
                )
            return result

        return await asyncio.to_thread(cursors)

    async def scan(self, options: ScanOptions) -> AsyncIterator[ScanEvent]:
        try:
            files = await asyncio.to_thread(
                lambda: list(
                    _memory_files(self.grant, max_targets=options.max_scan_targets or 100_000)
                )
            )
        except SourceAccessError as error:
            if error.code is SourceAccessErrorCode.BUDGET_EXCEEDED:
                yield ScanFailure(reason_code=ScanIssueCode.BUDGET_EXCEEDED)
                return
            raise
        yield ScanProgressEvent(phase=ScanPhase.DISCOVER, discovered_increment=len(files))
        emitted = 0
        for listed in files:
            if is_unchanged(listed, options.cursors):
                continue
            try:
                source_file = listed.admit()
                limit = min(
                    options.max_source_file_bytes or _MAX_MEMORY_BYTES,
                    _MAX_MEMORY_BYTES,
                )
                if source_file.size > limit:
                    yield ScanFailure(reason_code=ScanIssueCode.FILE_TOO_LARGE)
                    continue
                text = await asyncio.to_thread(_read_markdown, source_file)
            except SourceAccessError as error:
                if error.code in {
                    SourceAccessErrorCode.GRANT_REQUIRED,
                    SourceAccessErrorCode.SOURCE_PERMISSION_CHANGED,
                    SourceAccessErrorCode.SOURCE_IDENTITY_CHANGED,
                }:
                    raise
                reason = (
                    ScanIssueCode.FILE_TOO_LARGE
                    if error.code is SourceAccessErrorCode.FILE_TOO_LARGE
                    else ScanIssueCode.UNSUPPORTED_SCHEMA
                )
                yield ScanFailure(reason_code=reason)
                continue
            except UnicodeError:
                yield ScanFailure(reason_code=ScanIssueCode.UNSUPPORTED_SCHEMA)
                continue
            digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
            cursor: SourceCursor = source_cursor(source_file, f"sha256:{digest}").model_copy(
                update={"read_to_end": True}
            )
            if not text.strip():
                yield ScanCursorTouch(cursor=cursor)
                continue
            relative = source_file.relative_path
            project = relative.parts[3] if len(relative.parts) == 6 else None
            parsed = ParsedMessage(
                conversation_id=(
                    "zcode-memory:" + hashlib.sha256(str(relative.parent).encode()).hexdigest()
                ),
                message_id=source_file.safe_id,
                role="memory",
                written_by=WrittenBy.UNKNOWN,
                verbatim=text,
                created_at=datetime.fromtimestamp(source_file.modified_ns / 1_000_000_000, UTC),
                project=project,
                record_type="auto_memory_markdown",
                content_kind=EvidenceContentKind.MEMORY_CONTENT,
            )
            yield ScannedEvidence(
                evidence=to_evidence(
                    source_id=self.descriptor.source_id,
                    source_file=source_file,
                    parsed=parsed,
                    ordinal=source_file.safe_id,
                    source_version="zcode-cli-memory-v1",
                ),
                cursor=cursor,
            )
            emitted += 1
            if options.max_messages is not None and emitted >= options.max_messages:
                return

        source_file = await asyncio.to_thread(_database_file, self.grant)
        if source_file is None:
            yield ScanProgressEvent(phase=ScanPhase.DONE)
            return
        previous = options.cursors.get(source_file.safe_id)
        unchanged = await asyncio.to_thread(_database_unchanged, source_file, previous)
        if unchanged:
            yield ScanProgressEvent(phase=ScanPhase.DONE)
            return
        checkpoint = previous.checkpoint if previous is not None else "row:0"
        remaining = None if options.max_messages is None else options.max_messages - emitted
        if remaining is not None and remaining <= 0:
            yield ScanProgressEvent(phase=ScanPhase.DONE)
            return
        try:
            events = iterate_in_worker(
                lambda: _message_rows(
                    source_file, _row_checkpoint(checkpoint), max_messages=remaining
                ),
                scope_key=self.descriptor.source_id,
            )
            async for event in events:
                yield event
                if isinstance(event, ScannedEvidence):
                    emitted += 1
                    if options.max_messages is not None and emitted >= options.max_messages:
                        return
        except sqlite3.Error:
            yield ScanFailure(reason_code=ScanIssueCode.SOURCE_BUSY)
            return
        yield ScanProgressEvent(phase=ScanPhase.DONE)


def _read_markdown(source_file: AuthorizedSourceFile) -> str:
    with source_file.open_binary() as stream:
        text = stream.read(_MAX_MEMORY_BYTES + 1).decode("utf-8-sig")
    body = _FRONTMATTER.sub("", text)
    # The blank line that separated the frontmatter from the body is not part
    # of the memory; leave files without frontmatter exactly as they were.
    return body.lstrip("\r\n") if body != text else text


def create_zcode_adapter(grant: AuthorizedSourceRoot) -> ZCodeAdapter:
    return ZCodeAdapter(grant)
