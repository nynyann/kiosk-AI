"""Sinh sẵn mp3 cho MỌI câu kiosk có thể nói, lưu vào data/tts/ để commit.

Chạy ở máy nhà, cần mạng:

    python scripts/build_tts_cache.py            # chỉ sinh câu còn thiếu
    python scripts/build_tts_cache.py --force    # sinh lại tất cả (đổi giọng)

Vì sao phải có bước này: dịch vụ giọng đọc của Edge hỏng ngẫu nhiên với giọng
tiếng Việt (đo 15/09/2026: có lúc 5/6 lần liên tiếp trả "No audio was
received"). Máy chủ thật mà gặp đợt như vậy là kiosk im, giao diện rơi về
giọng trình duyệt vốn không có tiếng Việt. Mọi câu đều biết trước (sinh từ
data/kb/), nên sinh một lần ở đây, thử lại tới khi được, rồi commit mp3 theo
repo. Máy chủ đọc từ đĩa, không phụ thuộc mạng cho các câu quen.

Sửa kho tri thức xong thì chạy lại: file cũ không dùng nữa được dọn, file mới
sinh thêm. Tên file là băm của giọng + câu, nên không sợ phát nhầm.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

from app import config, kb, tts  # noqa: E402

MAX_ROUNDS = 12          # số vòng đi qua danh sách câu còn thiếu
PAUSE_BETWEEN_ROUNDS = 8  # giây; dịch vụ hay hỏng theo đợt, nghỉ một chút rồi thử lại


async def main(force: bool) -> int:
    kb.load_kb()
    texts = list(dict.fromkeys(t for t in kb.all_speech_texts() if t))
    voice = config.TTS_VOICE
    config.TTS_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    wanted = {tts.disk_path(t, voice).name: t for t in texts}
    # Dọn file không còn ứng với câu nào (kho đã sửa).
    stale = [f for f in config.TTS_CACHE_DIR.glob("*.mp3") if f.name not in wanted]
    for f in stale:
        f.unlink()
    if stale:
        print(f"đã xoá {len(stale)} file cũ không còn dùng")

    if force:
        for name in wanted:
            (config.TTS_CACHE_DIR / name).unlink(missing_ok=True)

    missing = [t for t in texts if not tts.disk_path(t, voice).is_file()]
    print(f"{len(texts)} câu, đã có {len(texts) - len(missing)}, cần sinh {len(missing)}, giọng {voice}")

    for round_no in range(1, MAX_ROUNDS + 1):
        if not missing:
            break
        print(f"--- vòng {round_no}: còn {len(missing)} câu")
        still = []
        for t in missing:
            t0 = time.time()
            try:
                # synthesize tự thử 4 lần và tự ghi đĩa khi được.
                await tts.synthesize(t, timeout=40)
                print(f"  ok  {time.time() - t0:4.1f}s  {t[:60]}")
            except tts.TtsError as exc:
                print(f"  hỏng {time.time() - t0:4.1f}s  ({exc.code}) {t[:60]}")
                still.append(t)
        missing = still
        if missing and round_no < MAX_ROUNDS:
            await asyncio.sleep(PAUSE_BETWEEN_ROUNDS)

    on_disk = len(list(config.TTS_CACHE_DIR.glob("*.mp3")))
    size_mb = sum(f.stat().st_size for f in config.TTS_CACHE_DIR.glob("*.mp3")) / 1e6
    print(f"\nxong: {on_disk} file, {size_mb:.1f} MB trong {config.TTS_CACHE_DIR}")
    if missing:
        print(f"CÒN THIẾU {len(missing)} câu, chạy lại sau:")
        for t in missing:
            print("  -", t[:80])
        return 1
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="sinh lại tất cả")
    args = ap.parse_args()
    sys.exit(asyncio.run(main(args.force)))
