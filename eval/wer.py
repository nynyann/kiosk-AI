"""Đo WER và tách kết quả theo nhóm. Đây là phần lõi khoa học của cả bài.

Luận điểm của nhóm: các mô hình tiếng Việt sẵn có hỏng ở đúng nhóm người mà
đề bài muốn phục vụ. Muốn nói câu đó thì phải có bảng số. File này sinh ra
bảng số đó.

Bốn thứ nó tính:
  1. WER tổng, có khoảng tin cậy bootstrap
  2. WER tách theo nhóm tuổi / vùng miền / mức ồn
  3. Tỷ lệ lỗi RIÊNG trên cụm từ vựng hành chính  <- chỉ số ăn tiền
  4. Tương quan giữa điểm tin cậy của mô hình và WER thật

Chỉ số 3 là chỗ khác biệt. WER tổng che mất vấn đề: một câu 12 từ nghe sai
đúng 2 chữ "cư trú" thì WER chỉ 17%, nghe rất ổn, nhưng tra cứu trượt hoàn
toàn và người dân ra về tay không. Phải đo riêng.

Chỉ số 4 quyết định ngưỡng chuyển cán bộ có căn cứ hay không. Nếu điểm tin
cậy không tương quan với lỗi thật thì ngưỡng đặt kiểu gì cũng vô nghĩa, và
tự điều đó là một phát hiện đáng viết vào bài.

CÁCH CHẠY
---------
    python -m eval.wer --manifest data/eval/testset.csv --model models/PhoWhisper-small-ct2

Chạy nhiều mô hình rồi so:
    python -m eval.wer --manifest ... --model A --tag PhoWhisper-small
    python -m eval.wer --manifest ... --model B --tag Whisper-large-v3
    python -m eval.wer --compare results/
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.normalize import normalize as admin_normalize  # noqa: E402

# ---------------------------------------------------------------------------
# Cụm từ vựng hành chính cần theo dõi riêng.
# Thêm vào đây mỗi khi phát hiện một cụm hay bị nghe sai.
TRACKED_TERMS = [
    "cư trú", "thường trú", "tạm trú", "tạm vắng",
    "căn cước công dân", "hộ tịch", "khai sinh", "khai tử", "kết hôn",
    "chứng thực", "sao y bản chính", "uỷ quyền",
    "bảo hiểm y tế", "trợ cấp xã hội", "hưu trí",
    "quyền sử dụng đất", "dịch vụ công", "một cửa", "định danh điện tử",
]


def wer_normalize(s: str) -> str:
    """Chuẩn hoá TRƯỚC khi đo WER.

    Cố ý nhẹ tay: hạ chữ thường, bỏ dấu câu, gộp khoảng trắng. GIỮ NGUYÊN dấu
    thanh — bỏ dấu để đo là tự làm đẹp số liệu, vì nghe "cư chú" thành "cư trú"
    là lỗi thật và tra cứu sẽ trượt thật.
    """
    s = unicodedata.normalize("NFC", s.lower())
    s = re.sub(r"[^\w\sÀ-ỹ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def edit_ops(ref: Sequence[str], hyp: Sequence[str]) -> Dict[str, int]:
    """Levenshtein trên mức từ, trả về số lần thay/xoá/thêm."""
    n, m = len(ref), len(hyp)
    # d[i][j] = (chi phí, sub, del, ins)
    d = [[(0, 0, 0, 0)] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        d[i][0] = (i, 0, i, 0)
    for j in range(1, m + 1):
        d[0][j] = (j, 0, 0, j)
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if ref[i - 1] == hyp[j - 1]:
                d[i][j] = d[i - 1][j - 1]
                continue
            c_sub, c_del, c_ins = d[i - 1][j - 1][0], d[i - 1][j][0], d[i][j - 1][0]
            best = min(c_sub, c_del, c_ins)
            if best == c_sub:
                p = d[i - 1][j - 1]; d[i][j] = (best + 1, p[1] + 1, p[2], p[3])
            elif best == c_del:
                p = d[i - 1][j]; d[i][j] = (best + 1, p[1], p[2] + 1, p[3])
            else:
                p = d[i][j - 1]; d[i][j] = (best + 1, p[1], p[2], p[3] + 1)
    total, sub, dele, ins = d[n][m]
    return {"sub": sub, "del": dele, "ins": ins, "errors": total, "ref_len": n}


def wer(ref: str, hyp: str) -> float:
    r, h = wer_normalize(ref).split(), wer_normalize(hyp).split()
    if not r:
        return 0.0 if not h else 1.0
    return edit_ops(r, h)["errors"] / len(r)


def term_recall(ref: str, hyp: str, terms: List[str] = TRACKED_TERMS) -> Dict[str, bool]:
    """Với mỗi cụm hành chính CÓ trong câu chuẩn, mô hình có bắt đúng không.

    Đây là chỉ số 3. Trả về dict {cụm: đúng/sai} chỉ cho các cụm có mặt.
    """
    r, h = wer_normalize(ref), wer_normalize(hyp)
    return {t: (wer_normalize(t) in h) for t in terms if wer_normalize(t) in r}


def bootstrap_ci(values: List[float], n_iter: int = 2000, alpha: float = 0.05,
                 seed: int = 42) -> tuple[float, float]:
    """Khoảng tin cậy cho WER trung bình. Tập kiểm thử 30 câu thì nhỏ, phải
    báo khoảng tin cậy, nếu không giám khảo hỏi ngay là số này có chắc không."""
    if len(values) < 2:
        return (0.0, 0.0)
    rng = random.Random(seed)
    means = []
    for _ in range(n_iter):
        sample = [values[rng.randrange(len(values))] for _ in values]
        means.append(sum(sample) / len(sample))
    means.sort()
    return (means[int(n_iter * alpha / 2)], means[int(n_iter * (1 - alpha / 2))])


def pearson(xs: List[float], ys: List[float]) -> float:
    """Tương quan điểm tin cậy vs WER. Chỉ số 4."""
    n = len(xs)
    if n < 3:
        return 0.0
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = sum((x - mx) ** 2 for x in xs) ** 0.5
    dy = sum((y - my) ** 2 for y in ys) ** 0.5
    return num / (dx * dy) if dx and dy else 0.0


# ---------------------------------------------------------------------------
def evaluate(manifest: Path, model_path: str, tag: str,
             apply_normalize: bool = True) -> dict:
    """Chạy mô hình trên toàn bộ manifest và tổng hợp kết quả."""
    from faster_whisper import WhisperModel

    rows = list(csv.DictReader(manifest.open(encoding="utf-8")))
    if not rows:
        raise SystemExit(f"Manifest rỗng: {manifest}")

    model = WhisperModel(model_path, device="cpu", compute_type="int8")
    base = manifest.parent

    records = []
    for i, row in enumerate(rows, 1):
        audio = base / row["audio_path"]
        if not audio.exists():
            print(f"  [bỏ qua] không thấy file {audio}")
            continue

        segs, _ = model.transcribe(str(audio), language="vi", beam_size=5,
                                   vad_filter=True, condition_on_previous_text=False)
        segs = list(segs)
        raw = " ".join(s.text.strip() for s in segs).strip()
        conf = 0.0
        if segs:
            import math
            conf = sum(math.exp(s.avg_logprob or -5) for s in segs) / len(segs)

        ref = row["transcript"]
        hyp_norm = admin_normalize(raw) if apply_normalize else raw

        rec = {
            **row,
            "hyp_raw": raw,
            "hyp_norm": hyp_norm,
            "confidence": round(min(max(conf, 0.0), 1.0), 3),
            "wer_raw": round(wer(ref, raw), 4),
            "wer_norm": round(wer(ref, hyp_norm), 4),
            "terms": term_recall(ref, hyp_norm),
        }
        records.append(rec)
        print(f"  [{i}/{len(rows)}] WER thô {rec['wer_raw']:.2f} -> "
              f"sau chuẩn hoá {rec['wer_norm']:.2f}  | {row.get('age_group','?')}")

    return summarize(records, tag)


def summarize(records: List[dict], tag: str) -> dict:
    wers = [r["wer_norm"] for r in records]
    lo, hi = bootstrap_ci(wers)

    # tách nhóm
    groups: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))
    for field in ("age_group", "region", "noise_level", "gender"):
        for r in records:
            v = (r.get(field) or "").strip()
            if v:
                groups[field][v].append(r["wer_norm"])

    breakdown = {
        field: {
            v: {
                "n": len(vals),
                "wer": round(sum(vals) / len(vals), 4),
                "ci": [round(x, 4) for x in bootstrap_ci(vals)],
            }
            for v, vals in sorted(buckets.items())
        }
        for field, buckets in groups.items()
    }

    # tỷ lệ bắt đúng từng cụm hành chính
    term_stats: Dict[str, List[bool]] = defaultdict(list)
    for r in records:
        for t, ok in r["terms"].items():
            term_stats[t].append(ok)
    terms = {
        t: {"n": len(v), "recall": round(sum(v) / len(v), 3)}
        for t, v in sorted(term_stats.items(), key=lambda kv: sum(kv[1]) / len(kv[1]))
    }

    return {
        "tag": tag,
        "n": len(records),
        "wer_raw": round(sum(r["wer_raw"] for r in records) / len(records), 4),
        "wer_norm": round(sum(wers) / len(wers), 4),
        "wer_ci95": [round(lo, 4), round(hi, 4)],
        "normalize_gain": round(
            sum(r["wer_raw"] for r in records) / len(records) - sum(wers) / len(wers), 4),
        "conf_wer_corr": round(pearson([r["confidence"] for r in records], wers), 3),
        "by_group": breakdown,
        "by_term": terms,
        "records": records,
    }


def print_report(res: dict) -> None:
    print(f"\n{'=' * 62}\nMÔ HÌNH: {res['tag']}   ({res['n']} câu)\n{'=' * 62}")
    print(f"WER thô            {res['wer_raw']:.1%}")
    print(f"WER sau chuẩn hoá  {res['wer_norm']:.1%}   "
          f"(KTC 95%: {res['wer_ci95'][0]:.1%} – {res['wer_ci95'][1]:.1%})")
    print(f"Chuẩn hoá cải thiện {res['normalize_gain']:.1%} tuyệt đối")
    print(f"Tương quan điểm tin cậy vs WER: {res['conf_wer_corr']:+.2f}")
    if abs(res["conf_wer_corr"]) < 0.3:
        print("  -> Tương quan yếu: mô hình KHÔNG tự biết lúc nào mình nghe sai.")
        print("     Đây là lập luận cho cơ chế chuyển cán bộ, viết vào mục 4.3.")

    for field, buckets in res["by_group"].items():
        print(f"\n  Tách theo {field}")
        for v, st in buckets.items():
            print(f"    {v:<18} n={st['n']:<3} WER {st['wer']:.1%}  "
                  f"[{st['ci'][0]:.1%} – {st['ci'][1]:.1%}]")

    print("\n  Cụm hành chính bắt kém nhất")
    for t, st in list(res["by_term"].items())[:10]:
        print(f"    {t:<24} n={st['n']:<3} bắt đúng {st['recall']:.0%}")


# ---------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, default=Path("data/eval/testset.csv"))
    ap.add_argument("--model", default="models/PhoWhisper-small-ct2")
    ap.add_argument("--tag", default=None)
    ap.add_argument("--out", type=Path, default=Path("results"))
    ap.add_argument("--no-normalize", action="store_true")
    args = ap.parse_args()

    tag = args.tag or Path(args.model).name
    res = evaluate(args.manifest, args.model, tag, apply_normalize=not args.no_normalize)
    print_report(res)

    args.out.mkdir(parents=True, exist_ok=True)
    dest = args.out / f"{tag}.json"
    dest.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nĐã ghi {dest}")


if __name__ == "__main__":
    main()
