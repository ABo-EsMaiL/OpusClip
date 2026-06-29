"""Example: Batch process videos from a CSV file."""

import csv
import json
import sys
from pathlib import Path

from opusclip.config import PipelineConfig
from opusclip.provider_factory import ProviderFactory
from opusclip.cli import _dictify


def process_csv(csv_path: str, output_root: str) -> None:
    config = PipelineConfig.from_env()
    output_dir = Path(output_root)
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        sources = [row["source"] for row in reader]

    if not sources:
        print("No sources found in CSV.", file=sys.stderr)
        return

    factory = ProviderFactory(config)
    results = []

    for src in sources:
        print(f"\nProcessing: {src}")
        pipeline = factory.create_pipeline(src)
        try:
            result = pipeline.run(src, resume=False)
            results.append(result)
            print(f"  OK — {result.successful_clips}/{result.total_clips} clips")
        except Exception as e:
            print(f"  FAIL — {e}")
            results.append(None)

    # Write summary
    summary_path = output_dir / "batch_summary.json"
    summary_data = []
    for i, r in enumerate(results):
        if r:
            summary_data.append(_dictify(r))
        else:
            summary_data.append({"source": sources[i], "error": "Pipeline failed"})

    summary_path.write_text(
        json.dumps(summary_data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\nBatch summary written to {summary_path}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <videos.csv> <output_dir>")
        print("CSV must have a 'source' column with video paths or URLs.")
        sys.exit(1)
    process_csv(sys.argv[1], sys.argv[2])
