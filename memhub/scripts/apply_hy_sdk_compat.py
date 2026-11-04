"""Apply a narrow, version-checked fix to HY 2.0.8/2.0.13's explicit raw search.
Ordinary memory search remains unchanged. Reapply after uv sync.
"""
from importlib.metadata import version
from importlib.util import find_spec
from pathlib import Path


def main():
    if version('hy-memory') not in {'2.0.8', '2.0.13'}:
        raise RuntimeError('Revalidate the raw-search compatibility patch for this SDK version')
    spec = find_spec('hy_memory')
    assert spec and spec.origin
    path = Path(spec.origin).parent / 'client.py'
    source = path.read_text(encoding='utf-8')
    start = source.index('    async def _search_explicit_raw_layer(')
    end = source.index('\n    @staticmethod', start)
    block = source[start:end]
    original = 'status_filter=[MemoryStatus.ACTIVE],'
    replacement = 'status_filter=[MemoryStatus.ACTIVE, MemoryStatus.SHADOW],'
    if replacement in block:
        print('HY 2.0.8/2.0.13 explicit raw-search patch already applied')
        return
    if block.count(original) != 1:
        raise RuntimeError('Unexpected SDK implementation; refusing to patch')
    block = block.replace(original, replacement)
    block = block.replace('"status": MemoryStatus.ACTIVE.value,', '"status": node.status.value,')
    path.write_text(source[:start] + block + source[end:], encoding='utf-8')
    print('Patched HY 2.0.8/2.0.13 explicit raw search to include retained shadow originals')

if __name__ == '__main__':
    main()
