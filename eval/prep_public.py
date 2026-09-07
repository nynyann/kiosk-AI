"""Lấy một bộ dữ liệu tiếng Việt công khai về thành manifest chạy được với eval/wer.py.

Vì sao cần file này: `data/eval/testset.csv` là tập tự thu của nhóm, chưa có
file âm thanh. Muốn có con số nền để đối chứng thì chạy mô hình trên bộ công
khai trước. Chênh lệch giữa hai bên chính là luận điểm mục 2.4.

    python -m eval.prep_public --dataset vivos   --limit 50
    python -m eval.prep_public --dataset fleurs  --limit 50
    python -m eval.prep_public --dataset vietmed --limit 60
    python -m eval.prep_public --dataset vimd    --limit 60

Kết quả: data/eval/public/<tên bộ>/{audio/*.wav, manifest.csv}
Chạy đo:  python -m eval.wer --manifest data/eval/public/vivos/manifest.csv --model ... --tag ...

HAI CÁI BẪY ĐÃ VẤP, ĐỪNG VẤP LẠI
--------------------------------
1. VIVOS và FLEURS trên HuggingFace là dạng "loading script". `datasets` từ
   bản 4 trở đi không chạy script nữa, báo "Dataset scripts are no longer
   supported". Cách vòng qua: HF tự sinh sẵn bản parquet ở nhánh
   `refs/convert/parquet` cho gần như mọi bộ, đọc thẳng nhánh đó.
2. `datasets` bản mới giải mã âm thanh bằng torchcodec, cài trên Windows rất
   phiền. Cách vòng qua: `Audio(decode=False)` để lấy bytes thô rồi tự giải mã
   bằng soundfile. Nhanh hơn và bớt một phụ thuộc nặng.

LẤY MẪU: CHIA ĐỀU THEO NHÓM, KHÔNG PHẢI LẤY N DÒNG ĐẦU
------------------------------------------------------
Bản đầu của file này lấy 50 dòng đầu, và hậu quả lộ ra ngay: cả 50 câu FLEURS
đều là giọng nam, vì file parquet xếp theo người nói. Số đo trên mẫu như vậy
không đại diện cho bộ.

Giờ mỗi bộ khai báo `balance_on` là cột cần chia đều, và việc chọn dòng làm
theo hai lượt:

  Lượt 1  đọc riêng cột nhãn đó, không đụng vào âm thanh. Cột nhãn chỉ vài chục
          KB nên đọc cả bộ cũng nhanh, và sau lượt này mới biết bộ có bao nhiêu
          nhóm để chia hạn ngạch.
  Lượt 2  duyệt dữ liệu thật, chỉ ghi ra những dòng đã chọn ở lượt 1.

Phải làm hai lượt vì các file parquet xếp theo nhóm: VietMed để hết News rồi
mới tới Podcast, ViMD để hết miền Bắc rồi mới tới miền Trung. Quyết định theo
kiểu vừa duyệt vừa chọn thì nhóm đầu tiên ăn hết hạn ngạch trước khi chương
trình kịp biết còn nhóm nào phía sau.

Trong mỗi nhóm, các dòng được lấy cách đều nhau chứ không lấy k dòng đầu, để
không dồn hết vào một người nói.

BA ĐIỀU PHẢI GHI VÀO BÀI KHI DÙNG SỐ TỪ ĐÂY
-------------------------------------------
1. VIVOS và FLEURS là giọng người trưởng thành đọc trong phòng yên tĩnh, tức là
   mức nền "điều kiện lý tưởng", không phải điều kiện kiosk. VietMed thì ngược
   lại: nói tự nhiên, thu ở hiện trường.
2. Không bộ nào ở đây có nhãn tuổi, nên cột `age_group` luôn trống. Common Voice
   có nhãn tuổi nhưng dùng không được, lý do ghi trong data/eval/README.md.
3. Nội dung các bộ này gần như không có từ vựng hành chính, nên chỉ số
   "term recall" của eval/wer.py sẽ trống. Chỉ số đó chỉ có nghĩa trên tập tự
   thu của nhóm.
"""

from __future__ import annotations

import argparse
import csv
import io
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

BASE = Path(__file__).resolve().parent.parent
OUT_ROOT = BASE / "data" / "eval" / "public"
HF_TEMPLATE = "hf://datasets/{repo}@refs/convert/parquet/{path}"


# ---------------------------------------------------------------------------
# Ánh xạ nhãn về đúng từ vựng mà data/eval/testset.csv đang dùng, để hai bên so
# được với nhau. Mỗi bộ mã hoá một kiểu, không dùng chung được.
# ---------------------------------------------------------------------------

# FLEURS: kiểu ClassLabel, 0 là nam, 1 là nữ.
_FLEURS_GENDER = {0: "nam", 1: "nữ"}
# ViMD: theo thẻ dữ liệu, 0 là nữ và 1 là nam. Ngược với FLEURS, đừng dùng lẫn.
_VIMD_GENDER = {0: "nữ", 1: "nam"}
# VietMed ghi bằng chữ tiếng Anh.
_VIETMED_GENDER = {"Male": "nam", "Female": "nữ"}

# VietMed ghi giọng theo vùng nhỏ. Gộp về ba miền cho khớp testset.csv.
_VIETMED_REGION = {
    "North": "bắc",
    "North Central Coast": "trung",
    "South Central Coast": "trung",
    "South East": "nam",
    "South West": "nam",
}
_VIMD_REGION = {"North": "bắc", "Central": "trung", "South": "nam"}


def _vivos(ex: dict, i: int) -> dict:
    return {
        "transcript": (ex.get("sentence") or "").strip(),
        "speaker_id": str(ex.get("speaker_id") or f"vivos_{i:04d}"),
        "gender": "",
        "region": "",
        "noise_level": "yên tĩnh",      # bộ thu trong phòng đọc
    }


def _fleurs(ex: dict, i: int) -> dict:
    return {
        "transcript": (ex.get("transcription") or "").strip(),
        "speaker_id": str(ex.get("id") or f"fleurs_{i:04d}"),
        "gender": _FLEURS_GENDER.get(ex.get("gender"), ""),
        "region": "",
        "noise_level": "yên tĩnh",
    }


def _vietmed(ex: dict, i: int) -> dict:
    # `rec_condition` là điều kiện thu thật: Podcast, Tel, Consultation, v.v.
    # Đặt nó vào cột noise_level để eval/wer.py tách WER theo điều kiện thu.
    # Đây là bảng gần "môi trường ồn" nhất mà dữ liệu công khai cho được.
    return {
        "transcript": (ex.get("text") or "").strip(),
        "speaker_id": str(ex.get("speaker_name") or f"vietmed_{i:04d}"),
        "gender": _VIETMED_GENDER.get(ex.get("gender"), ""),
        "region": _VIETMED_REGION.get(ex.get("accent"), ""),
        "noise_level": str(ex.get("rec_condition") or ""),
    }


def _vimd(ex: dict, i: int) -> dict:
    return {
        "transcript": (ex.get("text") or "").strip(),
        "speaker_id": str(ex.get("speakerID") or f"vimd_{i:04d}"),
        "gender": _VIMD_GENDER.get(ex.get("gender"), ""),
        "region": _VIMD_REGION.get(ex.get("region"), ""),
        "noise_level": "",              # bộ không ghi điều kiện thu, để trống
    }


# Mỗi mục: repo trên HuggingFace, danh sách file parquet, hàm ánh xạ nhãn,
# và cột cần chia đều khi lấy mẫu (None là không chia).
SOURCES: Dict[str, tuple] = {
    "vivos": ("AILAB-VNUHCM/vivos", ["default/test/0000.parquet"], _vivos, None),
    "fleurs": ("google/fleurs", ["vi_vn/test/0000.parquet"], _fleurs, "gender"),
    "vietmed": ("leduckhai/VietMed", ["default/test/0000.parquet"], _vietmed,
                "rec_condition"),
    # ViMD chia tập test thành 8 mảnh và xếp theo vùng: mảnh 0-3 miền Bắc,
    # mảnh 3-4 và 6-7 miền Trung, mảnh 4-6 miền Nam.
    #
    # Chỉ lấy ba mảnh, mỗi miền một mảnh, chứ không lấy cả 8. Lý do là tiền
    # băng thông: mỗi mảnh nặng khoảng 600MB vì chứa âm thanh, liệt kê đủ 8 là
    # tải về 4767MB chỉ để giữ lại 60 câu. Ba mảnh này đủ cả ba miền và mỗi
    # mảnh còn 145-245 dòng, thừa cho hạn ngạch 20 câu mỗi miền.
    #
    # Đọc chọn lọc không cứu được: parquet của bộ này để 100 dòng một row
    # group nặng khoảng 320MB, còn API lấy từng dòng của HuggingFace thì trả
    # lỗi 500 với bộ này.
    "vimd": ("nguyendv02/ViMD_Dataset",
             ["default/partial-test/0000.parquet",   # miền Bắc,  245 dòng
              "default/partial-test/0005.parquet",   # miền Nam,  145 dòng
              "default/partial-test/0007.parquet"],  # miền Trung, 145 dòng
             _vimd, "region"),
}


# ---------------------------------------------------------------------------
# Common Voice: đọc từ file tải tay, không qua HuggingFace
# ---------------------------------------------------------------------------
# Common Voice không còn phát hành qua `datasets` nữa. Phải vào
# mozilladatacollective.com, đăng nhập, tải một file .tar.gz rồi giải nén.
# Xem data/eval/README.md để biết đường dẫn và các cảnh báo khi dùng bộ này.

CV_AGE_MAP = {
    "twenties": "18-44", "thirties": "18-44", "fourties": "18-44",
    "fifties": "45-59",
    "sixties": "60+", "seventies": "60+", "eighties": "60+", "nineties": "60+",
}
# "teens" cố ý không ánh xạ. Nhóm tuổi của bài bắt đầu từ 18, còn "teens" của
# Common Voice là 10-19, xếp vào 18-44 là sai. Các dòng đó bị bỏ hẳn.

CV_GENDER_MAP = {"male_masculine": "nam", "female_feminine": "nữ"}


def prep_common_voice(cv_dir: Path, limit: int, split: str = "validated") -> Path:
    """Dựng manifest từ thư mục Common Voice đã giải nén.

    Dùng `validated.tsv` chứ không phải `test.tsv`, và đây là chỗ phải cẩn
    thận: tập test chính thức của bản tiếng Việt KHÔNG có người nào nhóm 60+,
    chỉ đúng 1 clip nhóm seventies trên 1005 dòng. Toàn bộ clip người cao tuổi
    nằm trong validated.tsv. Nhưng cả 2816 clip nhóm sixties ở đó cũng chỉ từ
    2 người, nên số đo cho nhóm 60+ là số đo của hai giọng cụ thể. Hàm này in
    số người nói của từng nhóm ra màn hình để không ai quên điều đó.
    """
    import csv
    import subprocess

    vi_dir = cv_dir / "cv-corpus-26.0-2026-06-12" / "vi"
    if not vi_dir.exists():                     # cho phép trỏ thẳng vào thư mục vi
        vi_dir = cv_dir
    tsv = vi_dir / f"{split}.tsv"
    if not tsv.exists():
        raise SystemExit(f"Không thấy {tsv}")

    # Ô `sentence` trong Common Voice có thể rất dài, vượt hạn mặc định của csv.
    csv.field_size_limit(10 ** 7)
    rows_in = list(csv.DictReader(tsv.open(encoding="utf-8"), delimiter="\t"))

    # Chỉ giữ dòng có nhãn tuổi ánh xạ được, rồi chia đều ba nhóm.
    usable = [(i, r) for i, r in enumerate(rows_in)
              if CV_AGE_MAP.get((r.get("age") or "").strip())]
    by_group: Dict[str, List[tuple]] = defaultdict(list)
    for i, r in usable:
        by_group[CV_AGE_MAP[r["age"].strip()]].append((i, r))

    base_quota, remainder = divmod(limit, max(len(by_group), 1))
    chosen: List[tuple] = []
    for rank, (group, items) in enumerate(
            sorted(by_group.items(), key=lambda kv: len(kv[1]))):
        quota = min(base_quota + (1 if rank >= len(by_group) - remainder else 0),
                    len(items))
        step = len(items) / quota if quota else 1
        chosen += [items[int(k * step)] for k in range(quota)]

    out_dir = OUT_ROOT / "common_voice"
    audio_dir = out_dir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    rows: List[dict] = []
    speakers: Dict[str, set] = defaultdict(set)
    for n, (i, r) in enumerate(chosen):
        src = vi_dir / "clips" / r["path"]
        if not src.exists():
            print(f"  [bỏ qua] không thấy {src.name}")
            continue
        wav = audio_dir / f"common_voice_{n:04d}.wav"
        # Clip là mp3. Dùng ffmpeg thay vì soundfile vì soundfile đọc mp3 phụ
        # thuộc phiên bản libsndfile, còn ffmpeg thì repo đã bắt buộc phải có.
        proc = subprocess.run(
            ["ffmpeg", "-y", "-i", str(src), "-ar", "16000", "-ac", "1",
             "-c:a", "pcm_s16le", str(wav)],
            capture_output=True, timeout=120)
        if proc.returncode != 0:
            print(f"  [bỏ qua] ffmpeg không đọc được {src.name}")
            continue

        group = CV_AGE_MAP[r["age"].strip()]
        speakers[group].add(r["client_id"])
        rows.append({
            "audio_path": f"audio/{wav.name}",
            "transcript": (r.get("sentence") or "").strip(),
            "speaker_id": r["client_id"][:24],
            "age_group": group,
            "gender": CV_GENDER_MAP.get((r.get("gender") or "").strip(), ""),
            "region": "",
            "noise_level": "yên tĩnh",   # thu bằng micro cá nhân, không phải hiện trường
            "procedure_id": "",
            "note": f"common_voice_26.0 {split} #{i}",
        })
        if len(rows) % 10 == 0:
            print(f"  ...{len(rows)} câu")

    manifest = out_dir / "manifest.csv"
    with manifest.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"[prep] Đã ghi {len(rows)} câu vào {manifest}")
    print("[prep] Số NGƯỜI NÓI của từng nhóm tuổi, đọc kỹ trước khi trích số:")
    for group in sorted(speakers):
        n_clip = sum(1 for r in rows if r["age_group"] == group)
        print(f"         {group:<8} {n_clip:>3} câu từ {len(speakers[group])} người")
    return manifest


def pick_balanced_rows(urls: List[str], column: str, limit: int) -> Dict[int, str]:
    """Lượt 1: chọn trước những dòng sẽ lấy, chia đều theo `column`.

    Chỉ đọc đúng một cột nhãn nên rất nhẹ, không tải âm thanh. Trả về map
    {số thứ tự dòng trong toàn bộ luồng: tên nhóm}, để lượt 2 chỉ việc đối
    chiếu. Số thứ tự tính liên tục qua các file theo đúng thứ tự trong `urls`,
    khớp với cách `datasets` nối các file lại khi phát luồng.
    """
    import fsspec
    import pyarrow.parquet as pq

    labels: List[str] = []
    for u in urls:
        with fsspec.open(u).open() as fh:
            table = pq.ParquetFile(fh).read(columns=[column])
        labels.extend(str(v) for v in table.to_pydict()[column])

    by_group: Dict[str, List[int]] = defaultdict(list)
    for idx, lab in enumerate(labels):
        by_group[lab].append(idx)

    n_groups = len(by_group)
    base_quota, remainder = divmod(limit, n_groups)

    chosen: Dict[int, str] = {}
    # Nhóm ít câu nhất xét trước, để phần dư dồn cho nhóm còn nhiều câu.
    for rank, (group, idxs) in enumerate(
            sorted(by_group.items(), key=lambda kv: len(kv[1]))):
        quota = min(base_quota + (1 if rank >= n_groups - remainder else 0),
                    len(idxs))
        if quota <= 0:
            continue
        # Lấy cách đều trong nhóm thay vì k dòng đầu, tránh dồn vào một người.
        step = len(idxs) / quota
        for k in range(quota):
            chosen[idxs[int(k * step)]] = group
    return chosen


def prep(name: str, limit: int) -> Path:
    import soundfile as sf
    from datasets import Audio, load_dataset

    repo, paths, mapper, balance_on = SOURCES[name]
    urls = [HF_TEMPLATE.format(repo=repo, path=p) for p in paths]

    out_dir = OUT_ROOT / name
    audio_dir = out_dir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    print(f"[prep] Đọc {repo}, {len(paths)} file parquet, lấy {limit} câu")
    if balance_on:
        print(f"[prep] Chia đều theo cột '{balance_on}'")

    # Lượt 1: chốt danh sách dòng cần lấy trước khi đụng vào âm thanh.
    chosen: Dict[int, str] = {}
    if balance_on:
        chosen = pick_balanced_rows(urls, balance_on, limit)
        print(f"[prep] Đã chọn {len(chosen)} dòng, "
              f"{len(set(chosen.values()))} nhóm")

    ds = load_dataset("parquet", data_files={"test": urls}, split="test",
                      streaming=True)
    ds = ds.cast_column("audio", Audio(decode=False))  # tự giải mã, xem đầu file

    # Lượt 2: duyệt dữ liệu thật, chỉ ghi ra những dòng đã chọn.
    taken: Dict[str, int] = defaultdict(int)
    rows: List[dict] = []

    for i, ex in enumerate(ds):
        if len(rows) >= limit:
            break
        if balance_on and i not in chosen:
            continue

        data, sr = sf.read(io.BytesIO(ex["audio"]["bytes"]))
        if data.ndim > 1:                    # gộp hai kênh về mono
            data = data.mean(axis=1)
        if sr != 16000:                      # PhoWhisper chỉ nhận 16kHz
            import librosa
            data = librosa.resample(data, orig_sr=sr, target_sr=16000)

        meta = mapper(ex, i)
        if not meta["transcript"]:           # câu rỗng thì bỏ, đo WER vô nghĩa
            continue

        wav = audio_dir / f"{name}_{len(rows):04d}.wav"
        sf.write(wav, data, 16000, subtype="PCM_16")
        if balance_on:
            taken[str(ex.get(balance_on))] += 1

        rows.append({
            "audio_path": f"audio/{wav.name}",
            "transcript": meta["transcript"],
            "speaker_id": meta["speaker_id"][:24],
            "age_group": "",                 # không bộ nào có nhãn tuổi
            "gender": meta["gender"],
            "region": meta["region"],
            "noise_level": meta["noise_level"],
            "procedure_id": "",
            "note": f"{repo} test #{i}",
        })
        if len(rows) % 10 == 0:
            print(f"  ...{len(rows)} câu")

    if not rows:
        raise SystemExit("Không lấy được câu nào.")

    manifest = out_dir / "manifest.csv"
    with manifest.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"[prep] Đã ghi {len(rows)} câu vào {manifest}")
    if balance_on:
        print(f"[prep] Phân bố theo '{balance_on}': {dict(taken)}")
    return manifest


def main() -> None:
    # Console Windows mặc định cp1252, in tiếng Việt là vỡ. Ép utf-8.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", choices=sorted(SOURCES) + ["common_voice"],
                    required=True)
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--cv-dir", type=Path,
                    default=OUT_ROOT / "cv_raw",
                    help="Thư mục Common Voice đã giải nén (chỉ dùng cho "
                         "--dataset common_voice)")
    args = ap.parse_args()
    if args.dataset == "common_voice":
        prep_common_voice(args.cv_dir, args.limit)
    else:
        prep(args.dataset, args.limit)


if __name__ == "__main__":
    main()
