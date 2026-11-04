"""Qoder CN CLI auto-memory Markdown, within an authorized config root.

Qoder's documented roots are ``memory/`` and ``projects/*/memory/`` under
``~/.qoder-cn``. Markdown references remain text; this reader never resolves
an ``@`` import or a link from a memory file.
"""

import asyncio
import hashlib
import re
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime

from pydantic import JsonValue

from one_memory.imports.access import (
    AuthorizedSourceFile,
    AuthorizedSourceRoot,
    SourceAccessError,
    SourceAccessErrorCode,
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
from one_memory.imports.models import EvidenceContentKind, WrittenBy
from one_memory.imports.sources.claude_code import parse_claude_code_record
from one_memory.imports.sources.common import (
    JsonlSourceAdapter,
    ParsedMessage,
    ParsedSkip,
    SourceInstallState,
    SourceRecordContext,
    is_unchanged,
    source_cursor,
    to_evidence,
)

QODER_CN_DESCRIPTOR = SourceDescriptor(
    source_id="qoder",
    display_name="Qoder CN",
    storage_kinds=frozenset({StorageKind.MARKDOWN, StorageKind.JSONL}),
    capabilities=SourceCapabilities(
        can_append=True,
        can_observe_edits=True,
        can_observe_deletes=False,
        can_reconcile_complete_set=False,
    ),
)

_MAX_MEMORY_BYTES = 2 * 1024 * 1024
_SESSION_FILE = re.compile(r"^[0-9a-fA-F-]{36}\.jsonl$")
_MEMORY_INDEX = "memory.md"
#: Qoder's memory files start with YAML metadata (`name`, `description`,
#: `metadata.type`). It describes the file, not the memory, so it is removed
#: before the body is stored as memory content.
_FRONTMATTER = re.compile(r"\A---[ \t]*\r?\n.*?\r?\n---[ \t]*(?:\r?\n|\Z)", re.DOTALL)


def _is_transcript(source_file: AuthorizedSourceFile) -> bool:
    parts = source_file.relative_path.parts
    return len(parts) == 3 and parts[0] == "projects" and bool(_SESSION_FILE.fullmatch(parts[2]))


def parse_qoder_record(
    record: dict[str, JsonValue], context: SourceRecordContext
) -> ParsedMessage | ParsedSkip:
    """Qoder CN's observed JSONL envelope is Claude-like, with provenance gates."""
    kind = record.get("type")
    if kind == "assistant" and record.get("isApiErrorMessage") is True:
        return ParsedSkip(ScanIssueCode.UNKNOWN_RECORD)
    if kind == "user":
        origin = record.get("origin")
        origin_kind = origin.get("kind") if isinstance(origin, dict) else None
        message = record.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        has_tool_result = isinstance(content, list) and any(
            isinstance(block, dict) and block.get("type") == "tool_result" for block in content
        )
        if not has_tool_result and (
            origin_kind not in (None, "human")
            or (origin_kind is None and record.get("userType") == "external")
        ):
            return ParsedSkip(ScanIssueCode.NOT_WRITTEN_BY_PERSON)
    return parse_claude_code_record(record, context)


def _memory_files(
    grant: AuthorizedSourceRoot, *, max_targets: int
) -> Iterator[AuthorizedSourceFile]:
    """List only documented memory directories, excluding linked directories."""
    grant.check_root()
    root = grant.root
    directories = [root / "memory"]
    projects = root / "projects"
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


class QoderCnMemoryAdapter:
    def __init__(self, grant: AuthorizedSourceRoot) -> None:
        if grant.source_id != QODER_CN_DESCRIPTOR.source_id:
            raise ValueError("Descriptor and authorized root source IDs must match")
        self.grant = grant
        self.descriptor = QODER_CN_DESCRIPTOR
        self._transcripts = JsonlSourceAdapter(
            descriptor=self.descriptor,
            grant=grant,
            parser=parse_qoder_record,
            source_version="qoder-cn-transcript-v1",
            file_predicate=_is_transcript,
        )

    async def detect(self) -> bool:
        return (await self.install_state()).detected

    async def install_state(self) -> SourceInstallState:
        installed = await asyncio.to_thread(self.grant.root.is_dir)
        count = await self.count_sessions() if installed else 0
        return SourceInstallState(installed=installed, session_count=count, detected=installed)

    async def count_sessions(self, *, limit: int | None = None) -> int:
        def count() -> int:
            found = 0
            for _ in _memory_files(self.grant, max_targets=100_000):
                found += 1
                if limit is not None and found >= limit:
                    break
            return found

        memory_count = await asyncio.to_thread(count)
        transcript_count = await self._transcripts.count_sessions(limit=limit)
        return memory_count + transcript_count

    async def has_changes(self, options: ScanOptions) -> bool:
        def changed() -> bool:
            return any(
                not is_unchanged(item, options.cursors)
                for item in _memory_files(
                    self.grant, max_targets=options.max_scan_targets or 100_000
                )
            )

        return await asyncio.to_thread(changed) or await self._transcripts.has_changes(options)

    async def live_baseline(self) -> dict[str, SourceCursor]:
        def markdown_cursors() -> dict[str, SourceCursor]:
            return {
                item.safe_id: source_cursor(item, f"byte:{item.size}").model_copy(
                    update={"read_to_end": True}
                )
                for item in _memory_files(self.grant, max_targets=100_000)
            }

        memory = await asyncio.to_thread(markdown_cursors)
        return {**memory, **await self._transcripts.live_baseline()}

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
                limit = min(options.max_source_file_bytes or _MAX_MEMORY_BYTES, _MAX_MEMORY_BYTES)
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
            project = relative.parts[1] if len(relative.parts) == 4 else None
            parsed = ParsedMessage(
                conversation_id=f"qoder-memory:{hashlib.sha256(str(relative.parent).encode()).hexdigest()}",
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
                    source_version="qoder-cn-cli-memory-v1",
                ),
                cursor=cursor,
            )
            emitted += 1
            if options.max_messages is not None and emitted >= options.max_messages:
                return
        remaining = None if options.max_messages is None else options.max_messages - emitted
        transcript_options = options.model_copy(update={"max_messages": remaining})
        async for event in self._transcripts.scan(transcript_options):
            yield event
        yield ScanProgressEvent(phase=ScanPhase.DONE)


def _read_markdown(source_file: AuthorizedSourceFile) -> str:
    with source_file.open_binary() as stream:
        text = stream.read(_MAX_MEMORY_BYTES + 1).decode("utf-8-sig")
    body = _FRONTMATTER.sub("", text)
    # The blank line that separated the frontmatter from the body is not part
    # of the memory; leave files without frontmatter exactly as they were.
    return body.lstrip("\r\n") if body != text else text


def create_qoder_cn_adapter(grant: AuthorizedSourceRoot) -> QoderCnMemoryAdapter:
    return QoderCnMemoryAdapter(grant)
