#!/usr/bin/env python3
"""Minimal GRF v2 reader/extractor.

Supported: GRF version 0x02xx (rdata.grf uses this). The file table is
zlib-compressed; file entries are zlib-compressed. Gravity DES header/mixed
encryption is decoded via grf_crypt (rAthena-compatible).

Examples:
  python3 tools/grf.py info tmp/rdata.grf
  python3 tools/grf.py list tmp/rdata.grf --filter collection --limit 20
  python3 tools/grf.py extract tmp/rdata.grf \
      "data/texture/유저인터페이스/collection/amber.bmp" --out /tmp/amber.bmp
  python3 tools/grf.py extract-matching tmp/rdata.grf \
      --filter collection --out-dir /tmp/grf-collection --limit 5
"""

from __future__ import annotations

import argparse
import struct
import sys
import zlib
from dataclasses import dataclass
from pathlib import Path

from grf_crypt import (  # noqa: E402
    FILELIST_TYPE_ENCRYPT_HEADER,
    FILELIST_TYPE_ENCRYPT_MIXED,
    grf_decode,
)

GRF_MAGIC = b"Master of Magic"
HEADER_SIZE = 0x2E
FILELIST_TYPE_FILE = 0x01


class GrfError(RuntimeError):
    pass


@dataclass(frozen=True)
class Entry:
    name: str
    name_bytes: bytes
    type: int
    srclen: int
    srclen_aligned: int
    declen: int
    srcpos: int


class Grf:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        with self.path.open("rb") as f:
            header = f.read(HEADER_SIZE)
            if len(header) != HEADER_SIZE or not header.startswith(GRF_MAGIC):
                raise GrfError(f"{self.path}: not a GRF file")
            self.version_raw = struct.unpack_from("<I", header, 0x2A)[0]
            self.version = self.version_raw >> 8
            if self.version != 0x02:
                raise GrfError(
                    f"unsupported GRF version 0x{self.version_raw:08x}; "
                    "only v2 (0x02xx) is supported"
                )
            self.count = struct.unpack_from("<I", header, 0x26)[0] - 7
            self.table_offset = HEADER_SIZE + struct.unpack_from("<I", header, 0x1E)[0]
            f.seek(self.table_offset)
            rsize, esize = struct.unpack("<II", f.read(8))
            compressed = f.read(rsize)
            if len(compressed) != rsize:
                raise GrfError("truncated GRF file table")
            table = zlib.decompress(compressed)
            if len(table) != esize:
                raise GrfError(
                    f"file table size mismatch: {len(table)} != {esize}"
                )
        self.entries = self._parse_table(table)
        self._by_name = {e.name_bytes: e for e in self.entries}

    def _parse_table(self, table: bytes) -> list[Entry]:
        entries: list[Entry] = []
        ofs = 0
        for _ in range(self.count):
            end = table.find(b"\x00", ofs)
            if end < 0:
                raise GrfError("truncated filename in GRF file table")
            name_bytes = table[ofs:end]
            ofs2 = end + 1
            if ofs2 + 17 > len(table):
                raise GrfError("truncated entry in GRF file table")
            typ = table[ofs2 + 12]
            srclen, srclen_aligned, declen = struct.unpack_from("<III", table, ofs2)
            srcpos = struct.unpack_from("<I", table, ofs2 + 13)[0] + HEADER_SIZE
            if typ & FILELIST_TYPE_FILE:
                name = name_bytes.decode("cp949", errors="replace").replace("\\", "/")
                entries.append(
                    Entry(
                        name=name,
                        name_bytes=name_bytes,
                        type=typ,
                        srclen=srclen,
                        srclen_aligned=srclen_aligned,
                        declen=declen,
                        srcpos=srcpos,
                    )
                )
            ofs = ofs2 + 17
        return entries

    def find(self, name: str) -> Entry:
        key = name.replace("/", "\\")
        try:
            key_bytes = key.encode("cp949")
        except UnicodeEncodeError as e:
            raise GrfError(f"path is not representable in CP949: {name!r}") from e
        entry = self._by_name.get(key_bytes)
        if entry is None:
            lower = key_bytes.lower()
            for candidate in self.entries:
                if candidate.name_bytes.lower() == lower:
                    entry = candidate
                    break
        if entry is None:
            raise GrfError(f"file not found in GRF: {name}")
        return entry

    def read(self, entry: Entry) -> bytes:
        with self.path.open("rb") as f:
            f.seek(entry.srcpos)
            raw = bytearray(f.read(entry.srclen_aligned))
        if len(raw) != entry.srclen_aligned:
            raise GrfError(f"truncated data for {entry.name}")
        if entry.type & (FILELIST_TYPE_ENCRYPT_MIXED | FILELIST_TYPE_ENCRYPT_HEADER):
            grf_decode(raw, entry.type, entry.srclen)
        try:
            data = zlib.decompress(bytes(raw[: entry.srclen]))
        except zlib.error as e:
            raise GrfError(f"zlib failed for {entry.name}: {e}") from e
        if len(data) != entry.declen:
            raise GrfError(
                f"decompressed size mismatch for {entry.name}: "
                f"{len(data)} != {entry.declen}"
            )
        return data


def _safe_output_path(root: Path, internal: str) -> Path:
    parts = [p for p in internal.replace("\\", "/").split("/") if p not in ("", ".")]
    if any(p == ".." for p in parts):
        raise GrfError(f"unsafe path in GRF: {internal}")
    return root.joinpath(*parts)


def cmd_info(args: argparse.Namespace) -> None:
    grf = Grf(args.grf)
    print(f"file: {grf.path}")
    print(f"version: 0x{grf.version_raw:08x} (v{grf.version:02x})")
    print(f"entries: {grf.count}")
    print(f"table_offset: {grf.table_offset}")


def cmd_list(args: argparse.Namespace) -> None:
    grf = Grf(args.grf)
    needle = (args.filter or "").lower()
    shown = 0
    for entry in grf.entries:
        if needle and needle not in entry.name.lower():
            continue
        print(f"{entry.type:02x}\t{entry.srclen}\t{entry.declen}\t{entry.name}")
        shown += 1
        if args.limit and shown >= args.limit:
            break
    print(f"-- {shown} entries shown", file=sys.stderr)


def cmd_extract(args: argparse.Namespace) -> None:
    grf = Grf(args.grf)
    entry = grf.find(args.path)
    data = grf.read(entry)
    out = Path(args.out).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)
    print(f"{entry.name} -> {out} ({len(data)} bytes)")


def cmd_extract_matching(args: argparse.Namespace) -> None:
    grf = Grf(args.grf)
    needle = (args.filter or "").lower()
    out_root = Path(args.out_dir).expanduser()
    extracted = 0
    for entry in grf.entries:
        if needle and needle not in entry.name.lower():
            continue
        try:
            data = grf.read(entry)
        except GrfError as e:
            print(f"skip {entry.name}: {e}", file=sys.stderr)
            continue
        out = _safe_output_path(out_root, entry.name)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
        print(f"{entry.name} -> {out} ({len(data)} bytes)")
        extracted += 1
        if args.limit and extracted >= args.limit:
            break
    print(f"-- {extracted} files extracted to {out_root}", file=sys.stderr)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Minimal GRF v2 reader/extractor")
    sub = p.add_subparsers(dest="command", required=True)

    info = sub.add_parser("info", help="show GRF header information")
    info.add_argument("grf")
    info.set_defaults(func=cmd_info)

    ls = sub.add_parser("list", help="list files")
    ls.add_argument("grf")
    ls.add_argument("--filter", default=None, help="case-insensitive substring")
    ls.add_argument("--limit", type=int, default=None)
    ls.set_defaults(func=cmd_list)

    ex = sub.add_parser("extract", help="extract one file")
    ex.add_argument("grf")
    ex.add_argument("path", help="internal path (backslashes or slashes)")
    ex.add_argument("--out", required=True)
    ex.set_defaults(func=cmd_extract)

    exm = sub.add_parser("extract-matching", help="extract files matching a filter")
    exm.add_argument("grf")
    exm.add_argument("--filter", required=True)
    exm.add_argument("--out-dir", required=True)
    exm.add_argument("--limit", type=int, default=None)
    exm.set_defaults(func=cmd_extract_matching)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except (GrfError, OSError, zlib.error) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
