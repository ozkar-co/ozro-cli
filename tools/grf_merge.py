#!/usr/bin/env python3
"""Merge GRF v2 archives with first-wins priority (copy compressed blobs as-is).

Preserves DES-encrypted entries. Does not recompress payloads.

Example (matches planned OzRo flatten):
  python3 tools/grf_merge.py --out tmp/data.grf \\
      patch/gefenia.grf \\
      tmp/renewal2021.grf \\
      tmp/resources2021.grf \\
      tmp/rdata.grf \\
      tmp/data.grf
"""

from __future__ import annotations

import argparse
import struct
import sys
import zlib
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from grf import HEADER_SIZE, Grf, GrfError  # noqa: E402


@dataclass(frozen=True)
class Winner:
    src_index: int
    name_bytes: bytes
    type: int
    srclen: int
    srclen_aligned: int
    declen: int
    srcpos: int


def merge(out_path: Path, sources: list[Path]) -> None:
    if not sources:
        raise GrfError("no source GRFs")

    grfs: list[Grf] = []
    winners: dict[bytes, Winner] = {}

    for i, src in enumerate(sources):
        print(f"indexing {src} …", flush=True)
        grf = Grf(src)
        grfs.append(grf)
        for entry in grf.entries:
            key = entry.name_bytes.lower()
            if key in winners:
                continue
            winners[key] = Winner(
                src_index=i,
                name_bytes=entry.name_bytes,
                type=entry.type,
                srclen=entry.srclen,
                srclen_aligned=entry.srclen_aligned,
                declen=entry.declen,
                srcpos=entry.srcpos,
            )

    items = sorted(winners.values(), key=lambda w: w.name_bytes.lower())
    print(f"writing {len(items)} entries → {out_path}", flush=True)

    handles = [src.open("rb") for src in sources]
    try:
        data_blob_size = 0
        # First write header placeholder + payloads, build table as we go
        tmp = out_path.with_suffix(out_path.suffix + ".partial")
        table = bytearray()
        with tmp.open("wb") as out:
            out.write(b"\x00" * HEADER_SIZE)  # placeholder
            for n, w in enumerate(items):
                if n and n % 20000 == 0:
                    print(f"  … {n}/{len(items)}", flush=True)
                srcpos_out = data_blob_size
                handles[w.src_index].seek(w.srcpos)
                payload = handles[w.src_index].read(w.srclen_aligned)
                if len(payload) != w.srclen_aligned:
                    name = w.name_bytes.decode("cp949", errors="replace")
                    raise GrfError(
                        f"truncated payload in {sources[w.src_index]}: {name}"
                    )
                out.write(payload)
                data_blob_size += w.srclen_aligned
                table += w.name_bytes + b"\x00"
                table += struct.pack(
                    "<III", w.srclen, w.srclen_aligned, w.declen
                )
                table += bytes([w.type])
                table += struct.pack("<I", srcpos_out)

            compressed_table = zlib.compress(bytes(table), 9)
            out.write(struct.pack("<II", len(compressed_table), len(table)))
            out.write(compressed_table)

            header = bytearray(b"Master of Magic\x00")
            header += bytes(range(1, 15))
            header += struct.pack("<I", data_blob_size)  # table_offset
            header += struct.pack("<I", 0)
            header += struct.pack("<I", len(items) + 7)
            header += struct.pack("<I", 0x00000200)
            if len(header) != HEADER_SIZE:
                raise GrfError(f"header size {len(header)} != {HEADER_SIZE}")
            out.seek(0)
            out.write(header)
    finally:
        for fh in handles:
            fh.close()

    tmp.replace(out_path)

    counts: dict[str, int] = {}
    for w in items:
        name = sources[w.src_index].name
        counts[name] = counts.get(name, 0) + 1
    print(f"{out_path}: {len(items)} entries, {out_path.stat().st_size} bytes")
    for name, n in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"  from {name}: {n}")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument(
        "sources",
        nargs="+",
        type=Path,
        help="GRFs in priority order (first wins)",
    )
    args = p.parse_args()
    try:
        merge(args.out, args.sources)
    except (GrfError, OSError, zlib.error) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
