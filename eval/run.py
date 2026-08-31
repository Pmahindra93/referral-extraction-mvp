"""Run the pipeline over the whole dataset and score it against ground truth.

Usage: python -m eval.run [--limit N] [--no-cache]
Writes the full mismatch report to outputs/eval-report.json.
"""

import argparse
import json
from collections import defaultdict

from eval.scoring import compare_record
from pipeline import config
from pipeline.process import extract


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, help="only eval the first N files")
    parser.add_argument("--no-cache", action="store_true", help="re-run all API calls")
    args = parser.parse_args()

    if not config.GROUND_TRUTH_PATH.exists() or not config.REFERRAL_DIR.exists():
        raise SystemExit(
            "Dataset not found. Place the letters at data/referral-files/ and the "
            "ground truth at data/output-true-values.json (see README)."
        )
    ground_truth = json.loads(config.GROUND_TRUTH_PATH.read_text())
    if args.limit:
        ground_truth = ground_truth[: args.limit]

    per_field = defaultdict(lambda: [0, 0])  # field -> [matches, total]
    per_file = {}
    mismatches = []

    for i, truth in enumerate(ground_truth, 1):
        file_name = truth["file"]
        path = config.REFERRAL_DIR / file_name
        print(f"[{i}/{len(ground_truth)}] {file_name} ... ", end="", flush=True)
        try:
            extracted = extract(path, use_cache=not args.no_cache).model_dump()
        except Exception as e:
            print(f"EXTRACTION FAILED: {e} — scoring all fields as misses")
            extracted = None

        results = compare_record(truth, extracted or {})
        if extracted is None:
            # Force every comparison to a miss: compare_record substitutes empty
            # defaults, which would let ground-truth-empty fields "match" a
            # document we never extracted.
            for r in results.values():
                r["match"] = False
                r["actual"] = "<extraction failed>"
        matched = sum(r["match"] for r in results.values())
        per_file[file_name] = matched / len(results)
        if extracted:
            print(f"{matched}/{len(results)}")

        for field, r in results.items():
            per_field[field][1] += 1
            if r["match"]:
                per_field[field][0] += 1
            else:
                mismatches.append({"file": file_name, "field": field, **r})

    total_matched = sum(m for m, _ in per_field.values())
    total = sum(t for _, t in per_field.values())
    overall = total_matched / total if total else 0.0

    print(f"\n{'='*60}\nOVERALL ACCURACY: {overall:.1%}  ({total_matched}/{total} fields)")
    print(f"\nWorst fields:")
    for field, (m, t) in sorted(per_field.items(), key=lambda kv: kv[1][0] / kv[1][1]):
        if m < t:
            print(f"  {field:25s} {m}/{t}  ({m/t:.0%})")
    print(f"\nWorst files:")
    for f, acc in sorted(per_file.items(), key=lambda kv: kv[1])[:5]:
        print(f"  {f:25s} {acc:.0%}")

    config.OUTPUT_DIR.mkdir(exist_ok=True)
    report_path = config.OUTPUT_DIR / "eval-report.json"
    report_path.write_text(json.dumps({
        "overall_accuracy": overall,
        "fields_matched": total_matched,
        "fields_total": total,
        "per_field": {f: {"matched": m, "total": t} for f, (m, t) in per_field.items()},
        "per_file": per_file,
        "mismatches": mismatches,
    }, indent=2))
    print(f"\nFull report: {report_path}")


if __name__ == "__main__":
    main()
