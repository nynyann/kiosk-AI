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

HAI CON SỐ WER, ĐO HAI THỨ KHÁC NHAU
------------------------------------
  wer_raw   bản chuẩn nguyên văn  so với  văn bản thô của mô hình
            Đo riêng mô hình nghe. Không có phần nào của nhóm chen vào.

  wer_norm  bản chuẩn ĐÃ chuẩn hoá  so với  văn bản mô hình ĐÃ chuẩn hoá
            Đo cả dây chuyền, tức là văn bản cuối cùng đem đi tra cứu.

Chuẩn hoá cả hai phía là bắt buộc, không phải cho đẹp. `normalize()` có khâu
bỏ từ đệm, mà bản chuẩn của các bộ nói tự nhiên thì chép nguyên văn nên có đủ
"thế thì", "là cái". Chỉ chuẩn hoá một phía thì mọi từ đệm bị bỏ đều bị tính
là lỗi xoá, tức là tự bơm WER lên. Đo trên VietMed và ViMD thấy mức bơm khoảng
0.1 đến 0.6 điểm.

Ngược lại cũng phải cẩn thận: chuẩn hoá hai phía làm nhẹ đi những lỗi mà
HARD_FIXES sửa được ở cả hai bên. Vì vậy phải LUÔN báo cáo cả hai con số, đừng
chỉ trích một cái.

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
        # Chuẩn hoá CẢ HAI PHÍA khi đo WER sau chuẩn hoá. Xem ghi chú
        # "HAI CON SỐ WER" ở đầu file để biết vì sao.
        ref_norm = admin_normalize(ref) if apply_normalize else ref

        rec = {
            **row,
            "hyp_raw": raw,
            "hyp_norm": hyp_norm,
            "transcript_norm": ref_norm,
            "confidence": round(min(max(conf, 0.0), 1.0), 3),
            "wer_raw": round(wer(ref, raw), 4),
            "wer_norm": round(wer(ref_norm, hyp_norm), 4),
            "terms": term_recall(ref_norm, hyp_norm),
        }
        records.append(rec)
        print(f"  [{i}/{len(rows)}] WER thô {rec['wer_raw']:.2f} -> "
              f"sau chuẩn hoá {rec['wer_norm']:.2f}  | {row.get('age_group','?')}")

    res = summarize(records, tag)
    # Luôn ghi dạng dấu gạch chuôi. Windows trả "data\eval\..." còn dòng
    # lệnh gõ tay ra "data/eval/...", hai dạng đó khác chuỗi nên compare()
    # sẽ tách cùng một bộ dữ liệu thành hai nhóm rồi không so được với nhau.
    res["manifest"] = manifest.as_posix()
    return res


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
def compare(results_dir: Path) -> None:
    """Đọc mọi results/<tag>.json và in bảng so sánh nhiều mô hình.

    Đây là bảng đưa thẳng vào mục 4.3. Cột "chuẩn hoá" cho thấy phần chuẩn hoá
    của mình gỡ lại được bao nhiêu. Nếu con số đó nhỏ thì phải nói thật là nhỏ.
    """
    files = sorted(results_dir.glob("*.json"))
    if not files:
        raise SystemExit(f"Không có file kết quả nào trong {results_dir}")

    res = []
    for f in files:
        try:
            res.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception as exc:  # noqa: BLE001
            print(f"  [bỏ qua] {f.name}: {exc}")
    # So mô hình chỉ có nghĩa TRONG CÙNG một bộ dữ liệu. Xếp chung 4 kết quả
    # của 2 mô hình x 2 bộ rồi so khoảng tin cậy là so nhầm bộ với bộ.
    by_set: Dict[str, List[dict]] = defaultdict(list)
    for r in res:
        by_set[r.get("manifest") or "(không rõ bộ dữ liệu)"].append(r)

    w = max(len(r["tag"]) for r in res)
    for manifest_path, group in sorted(by_set.items()):
        group.sort(key=lambda r: r["wer_norm"])
        print()
        print(f"BỘ DỮ LIỆU: {manifest_path}")
        print("=" * (w + 58))
        print(f"{'MÔ HÌNH'.ljust(w)}  {'n':>3}  {'WER thô':>8}  {'WER chuẩn hoá':>14}  "
              f"{'KTC 95%':>17}  {'corr':>6}")
        print("-" * (w + 58))
        for r in group:
            ci = f"{r['wer_ci95'][0]:.1%}-{r['wer_ci95'][1]:.1%}"
            print(f"{r['tag'].ljust(w)}  {r['n']:>3}  {r['wer_raw']:>7.1%}  "
                  f"{r['wer_norm']:>13.1%}  {ci:>17}  {r['conf_wer_corr']:>+6.2f}")
        print("-" * (w + 58))

        best = group[0]
        print(f"Thấp nhất: {best['tag']}, WER {best['wer_norm']:.1%}")
        if len(group) > 1:
            second = group[1]
            gap = second["wer_norm"] - best["wer_norm"]
            overlap = best["wer_ci95"][1] >= second["wer_ci95"][0]
            print(f"Cách {second['tag']} {gap:.1%} tuyệt đối.")
            if overlap:
                print("  -> Hai khoảng tin cậy CHỒNG NHAU: chưa đủ căn cứ nói mô hình")
                print("     này tốt hơn. Viết đúng như vậy, đừng khẳng định quá.")
            else:
                print("  -> Hai khoảng tin cậy TÁCH RỜI: kết luận đứng được ở cỡ mẫu này.")

    # nhóm nào cũng đo được thì so luôn theo nhóm
    fields = {f for r in res for f in r.get("by_group", {})}
    for field in sorted(fields):
        vals = sorted({v for r in res for v in r.get("by_group", {}).get(field, {})})
        if not vals:
            continue
        print()
        print(f"  WER theo {field}")
        print(f"    {'mô hình'.ljust(w)}  " + "  ".join(v.rjust(12) for v in vals))
        for r in res:
            cells = []
            for v in vals:
                st = r.get("by_group", {}).get(field, {}).get(v)
                cells.append((f"{st['wer']:.1%} (n={st['n']})" if st else "-").rjust(12))
            print(f"    {r['tag'].ljust(w)}  " + "  ".join(cells))


# ---------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, default=Path("data/eval/testset.csv"))
    ap.add_argument("--model", default="models/PhoWhisper-small-ct2")
    ap.add_argument("--tag", default=None)
    ap.add_argument("--out", type=Path, default=Path("results"))
    ap.add_argument("--no-normalize", action="store_true")
    ap.add_argument("--compare", type=Path, default=None,
                    help="Chỉ in bảng so sánh từ các file results/*.json đã có")
    args = ap.parse_args()

    if args.compare:
        compare(args.compare)
        return

    tag = args.tag or Path(args.model).name
    res = evaluate(args.manifest, args.model, tag, apply_normalize=not args.no_normalize)
    print_report(res)

    args.out.mkdir(parents=True, exist_ok=True)
    dest = args.out / f"{tag}.json"
    dest.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nĐã ghi {dest}")


if __name__ == "__main__":
    main()
