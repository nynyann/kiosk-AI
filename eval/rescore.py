"""Tính lại WER sau chuẩn hoá từ kết quả đã có, KHÔNG chạy lại mô hình.

Vì sao cần: vòng lặp chính của bài (mục cuối README) là "sửa app/normalize.py
-> đo lại -> ghi mức cải thiện". Chạy lại mô hình mất vài chục phút mỗi lượt,
mà phần chạy mô hình thì không đổi gì. `hyp_raw` đã nằm sẵn trong
results/*.json. Chỉ khâu chuẩn hoá đổi, nên chỉ cần tính lại khâu đó.

    python -m eval.rescore                 # tính lại mọi file trong results/
    python -m eval.rescore --out results2  # ghi sang chỗ khác để giữ bản cũ

In ra WER cũ so với WER mới của từng lượt đo. Đó chính là "mức cải thiện"
cần ghi lại sau mỗi lần bổ sung HARD_FIXES hoặc sửa luật chuẩn hoá.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.normalize import normalize as admin_normalize  # noqa: E402
from eval.wer import summarize, term_recall, wer  # noqa: E402


def rescore_file(src: Path, out_dir: Path) -> tuple[float, float]:
    d = json.loads(src.read_text(encoding="utf-8"))
    old_wer = d["wer_norm"]

    for r in d["records"]:
        hyp_norm = admin_normalize(r["hyp_raw"])
        # Chuẩn hoá cả hai phía, giống hệt eval/wer.py. Xem ghi chú
        # "HAI CON SỐ WER" ở đầu file đó.
        ref_norm = admin_normalize(r["transcript"])
        r["hyp_norm"] = hyp_norm
        r["transcript_norm"] = ref_norm
        r["wer_norm"] = round(wer(ref_norm, hyp_norm), 4)
        r["terms"] = term_recall(ref_norm, hyp_norm)

    fresh = summarize(d["records"], d["tag"])
    fresh["manifest"] = d.get("manifest", "")

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / src.name).write_text(
        json.dumps(fresh, ensure_ascii=False, indent=2), encoding="utf-8")
    return old_wer, fresh["wer_norm"]


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", type=Path, default=Path("results"))
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    out_dir = args.out or args.results

    files = sorted(args.results.glob("*.json"))
    if not files:
        raise SystemExit(f"Không có file kết quả nào trong {args.results}")

    w = max(len(f.stem) for f in files)
    print(f"{'LƯỢT ĐO'.ljust(w)}  {'WER cũ':>8}  {'WER mới':>8}  {'đổi':>8}")
    print("-" * (w + 30))
    for f in files:
        old, new = rescore_file(f, out_dir)
        # dấu âm = tốt lên
        print(f"{f.stem.ljust(w)}  {old:>7.1%}  {new:>7.1%}  {new - old:>+7.1%}")
    print(f"\nĐã ghi vào {out_dir}")


if __name__ == "__main__":
    main()
