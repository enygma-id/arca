# SPDX-License-Identifier: AGPL-3.0-only
"""Command-line interface for ARCA: serve, run, and inspect commands."""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path

from . import __version__


class ArcaError(Exception):
    pass


class ArcaInputError(ArcaError):
    pass


def _emit(obj: dict) -> None:
    print(json.dumps(obj, ensure_ascii=False, allow_nan=False), flush=True)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="arca",
        description=f"ARCA v{__version__} - GIS-native BIM-to-GIS conversion engine (IFC/SKP)",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    sub = p.add_subparsers(dest="command")

    s = sub.add_parser("serve", aliases=["studio"], help="Launch Web Studio & 3D Viewer")
    s.add_argument("--port", type=int, default=8080, help="Server port (default: 8080)")
    s.add_argument("--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1)")
    s.add_argument("--workspace", type=Path, default=None, help="Data & viewer storage folder")
    s.add_argument("--no-browser", action="store_true", help="Do not open browser automatically")

    r = sub.add_parser("run", aliases=["convert"], help="Convert IFC/SKP via CLI")
    r.add_argument("input", type=Path, help=".ifc or .skp file or folder")
    r.add_argument("--out", type=Path, default=Path("./output"), help="Output directory")
    r.add_argument("--generate", choices=("all", "lod1.3", "glb"), default="all")
    r.add_argument("--anchor-lon", type=float, default=None)
    r.add_argument("--anchor-lat", type=float, default=None)
    r.add_argument("--crs", default=None)
    r.add_argument("--rotate", type=float, default=0.0)
    r.add_argument("--source-unit", choices=("auto", "m", "mm", "cm"), default="auto")
    r.add_argument("--metadata", type=Path, default=None, help="Path to companion metadata JSON / GeoJSON file")
    r.add_argument("--events", choices=("human", "jsonl"), default="human")
    r.add_argument("--cancel-file", type=Path)
    r.add_argument("--quiet", action="store_true")

    i = sub.add_parser("inspect", help="Inspect georeferencing metadata of IFC/SKP file")
    i.add_argument("file", type=Path, help="IFC or SKP model file")
    i.add_argument("--metadata", type=Path, default=None, help="Path to companion metadata JSON / GeoJSON file")

    return p


def _run(args: argparse.Namespace) -> int:
    from . import engine

    def progress(current: int, total: int, message: str) -> None:
        if args.events == "jsonl":
            _emit({"type": "progress", "current": current, "total": total, "message": message})
        elif not args.quiet:
            print(f"{message} [{current}/{total}]", file=sys.stderr)

    def log(message: str) -> None:
        if args.events == "jsonl":
            _emit({"type": "log", "message": message})
        elif not args.quiet:
            print(message, file=sys.stderr)

    cancel_flag = (lambda: args.cancel_file.exists()) if args.cancel_file else None

    sub_parser = engine.build_parser()
    cli_args = [
        str(args.input),
        "--out", str(args.out),
        "--generate", args.generate,
        "--source-unit", args.source_unit,
        "--rotate", str(args.rotate),
    ]
    if args.anchor_lon is not None and args.anchor_lat is not None:
        cli_args.extend(["--anchor-lon", str(args.anchor_lon), "--anchor-lat", str(args.anchor_lat)])
    if args.crs:
        cli_args.extend(["--crs", args.crs])
    if getattr(args, "metadata", None):
        cli_args.extend(["--metadata", str(args.metadata)])

    parsed_cli = sub_parser.parse_args(cli_args)
    if cancel_flag and cancel_flag():
        return 130

    engine.process_one(
        args=parsed_cli,
        input_path=args.input.resolve(),
        out_dir=args.out.resolve(),
        batch=False,
        dataset=engine.safe_slug(args.input.stem),
    )

    if args.events == "jsonl":
        _emit({"type": "result", "status": "done"})
    return 0


def _serve(args: argparse.Namespace) -> int:
    from .server import start_studio
    try:
        start_studio(
            host=args.host,
            port=args.port,
            workspace=args.workspace,
            open_browser=not args.no_browser,
        )
    except KeyboardInterrupt:
        pass
    return 0


def _inspect(args: argparse.Namespace) -> int:
    from . import engine
    info = engine.inspect_model_file(args.file, metadata_path=getattr(args, "metadata", None))
    print(json.dumps(info, indent=2))
    return 0


def _main(argv: list[str] | None = None) -> int:
    parser = build_parser()

    if argv is None:
        argv = sys.argv[1:]
    if not argv:
        argv = ["serve"]

    args = parser.parse_args(argv)

    if args.command in ("serve", "studio") or args.command is None:
        return _serve(args)
    if args.command in ("run", "convert"):
        return _run(args)
    if args.command == "inspect":
        return _inspect(args)

    raise ArcaInputError(f"Unknown command: {args.command}")


def main(argv: list[str] | None = None) -> int:
    events = "jsonl" if "--events" in (argv or sys.argv[1:]) and "jsonl" in (argv or sys.argv[1:]) else "human"
    try:
        return _main(argv)
    except ArcaInputError as exc:
        if events == "jsonl":
            _emit({"type": "error", "code": "INPUT", "message": str(exc)})
        else:
            print(f"[error] {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        if events == "jsonl":
            _emit({"type": "error", "code": "CANCELLED", "message": "Cancelled by user"})
        else:
            print("\nCancelled.", file=sys.stderr)
        return 130
    except ArcaError as exc:
        if events == "jsonl":
            _emit({"type": "error", "code": "ERROR", "message": str(exc)})
        else:
            print(f"[error] {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # pragma: no cover - final CLI boundary
        if events == "jsonl":
            _emit({"type": "error", "code": "INTERNAL", "message": str(exc)})
        else:
            traceback.print_exc(file=sys.stderr)
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
