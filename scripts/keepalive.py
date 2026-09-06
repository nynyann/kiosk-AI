"""Gọi /health định kỳ cho máy chủ khỏi ngủ đông.

Máy chủ container miễn phí ngủ sau 15 phút không có ai gọi, và lúc tỉnh dậy
mất 30-60 giây. Nếu giám khảo mở link đúng lúc đó thì coi như hỏng.

Chạy trên máy cá nhân của một bạn trong nhóm từ hôm nộp bài đến hôm chấm:

    python scripts/keepalive.py https://may-chu-cua-nhom.onrender.com

Trước buổi chấm 10 phút, gọi thêm /warmup để nạp sẵn mô hình:

    curl -X POST https://may-chu-cua-nhom.onrender.com/warmup
"""

import sys
import time
import urllib.request
from datetime import datetime

INTERVAL = 600  # 10 phút, dưới ngưỡng ngủ 15 phút


def ping(base: str) -> None:
    try:
        with urllib.request.urlopen(f"{base}/health", timeout=90) as r:
            body = r.read().decode()[:120]
        print(f"[{datetime.now():%H:%M:%S}] ok  {body}")
    except Exception as exc:
        print(f"[{datetime.now():%H:%M:%S}] HỎNG  {exc}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("Dùng: python scripts/keepalive.py https://dia-chi-may-chu")
    base = sys.argv[1].rstrip("/")
    print(f"Gọi {base}/health mỗi {INTERVAL // 60} phút. Ctrl+C để dừng.")
    while True:
        ping(base)
        time.sleep(INTERVAL)
