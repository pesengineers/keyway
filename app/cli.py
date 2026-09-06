from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from app.config import Settings
from app.models import ProcessingFailure
from app.pipeline import VideoProcessor, _atomic_write_text
from app.sources import LocalMediaSource


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="keyway")
    subparsers = parser.add_subparsers(dest="command", required=True)
    process = subparsers.add_parser(
        "process", help="transcribe and analyze one local video"
    )
    process.add_argument("source", type=Path)
    process.add_argument(
        "--output", type=Path, default=Path("output"), help="artifact directory"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = Settings()
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    if args.command == "process":
        return _process(args.source, args.output, settings)
    raise AssertionError(f"Unhandled command: {args.command}")


def _process(source: Path, output_dir: Path, settings: Settings) -> int:
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        media_source = LocalMediaSource(source, settings.max_source_bytes)
        result = VideoProcessor(settings).process(media_source, output_dir)
    except Exception as exc:
        logging.getLogger(__name__).error("Processing failed: %s", exc)
        failure = ProcessingFailure(source_filename=source.name, error=str(exc))
        _atomic_write_text(
            output_dir / "result.json", failure.model_dump_json(indent=2) + "\n"
        )
        return 1

    print((output_dir / "result.json").resolve())
    print(
        f"Processed {result.source_filename} in {result.total_processing_seconds:.3f}s "
        f"({result.transcription.device}/{result.transcription.compute_type})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
