"""Sinh tiếng nói tiếng Việt ở phía máy chủ.

Vì sao không để trình duyệt tự đọc bằng Web Speech API như bản đầu: Web Speech
chỉ đọc được thứ tiếng mà HỆ ĐIỀU HÀNH đã cài sẵn giọng. Máy Windows mặc định
ở Việt Nam thường chỉ có giọng tiếng Anh, thành ra nó lấy giọng Mỹ đọc chữ
tiếng Việt — người già nghe không ra chữ nào. Mà kiosk thì chạy trên máy nào
cũng phải ra tiếng Việt, không thể bắt mỗi máy đi cài gói giọng trước.

Nên máy chủ tự sinh sẵn file mp3 rồi giao diện chỉ việc phát.

Đánh đổi: cần mạng. Nếu gọi hỏng thì trả lỗi đúng định dạng giao kèo, giao diện
tự rơi về Web Speech như cũ — thà giọng Tây còn hơn câm.
"""

from __future__ import annotations

import asyncio
import hashlib
from collections import OrderedDict
from pathlib import Path

import edge_tts

from . import config


class TtsError(Exception):
    def __init__(self, message: str, code: str):
        super().__init__(message)
        self.message = message
        self.code = code


# Bộ nhớ đệm. Nội dung trả lời lấy từ data/kb/ nên chỉ có vài chục câu, hỏi đi
# hỏi lại vẫn ngần ấy câu — sinh lại mỗi lần vừa tốn 1-3 giây vừa tốn lượt gọi
# mạng. OrderedDict dùng như LRU: đụng vào thì đẩy xuống cuối, đầy thì bỏ đầu.
_cache: "OrderedDict[str, bytes]" = OrderedDict()


def _key(text: str, voice: str) -> str:
    return hashlib.sha256(f"{voice}\x00{text}".encode("utf-8")).hexdigest()


def disk_path(text: str, voice: str | None = None) -> Path:
    """File mp3 trên đĩa cho một câu. Tên file là băm của giọng + câu, nên đổi
    giọng hay sửa một chữ trong kho là thành file khác, không phát nhầm."""
    voice = voice or config.TTS_VOICE
    return config.TTS_CACHE_DIR / f"{_key(text, voice)[:20]}.mp3"


def _from_disk(text: str, voice: str) -> bytes | None:
    f = disk_path(text, voice)
    try:
        return f.read_bytes() if f.is_file() else None
    except OSError:
        return None


def _to_disk(text: str, voice: str, audio: bytes) -> None:
    try:
        config.TTS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        disk_path(text, voice).write_bytes(audio)
    except OSError as exc:
        print(f"[tts] không ghi được kho đĩa: {exc}")


def cache_info() -> dict:
    on_disk = len(list(config.TTS_CACHE_DIR.glob("*.mp3"))) if config.TTS_CACHE_DIR.is_dir() else 0
    return {"entries": len(_cache),
            "bytes": sum(len(v) for v in _cache.values()),
            "max_entries": config.TTS_CACHE_SIZE,
            "on_disk": on_disk}


async def synthesize(text: str, voice: str | None = None,
                     timeout: float | None = None) -> bytes:
    """Trả về mp3. Ném TtsError nếu không sinh được.

    `timeout` để trống thì dùng mức lúc phục vụ. Việc hâm nóng lúc khởi động
    truyền mức rộng hơn vì không có ai đứng chờ.
    """
    text = (text or "").strip()
    if not text:
        raise TtsError("Không có nội dung để đọc.", "bad_request")
    if len(text) > config.TTS_MAX_CHARS:
        raise TtsError("Câu cần đọc dài quá.", "text_too_long")

    voice = voice or config.TTS_VOICE
    k = _key(text, voice)

    if k in _cache:
        _cache.move_to_end(k)
        return _cache[k]

    # Kho trên đĩa (đi theo repo) trước, mạng sau. Xem ghi chú TTS_CACHE_DIR.
    disk = _from_disk(text, voice)
    if disk:
        _cache[k] = disk
        while len(_cache) > config.TTS_CACHE_SIZE:
            _cache.popitem(last=False)
        return disk

    # Dịch vụ giọng đọc của Edge trả "No audio was received" KHÔNG ỔN ĐỊNH với
    # giọng tiếng Việt. Đo ngày 15/09/2026 trên cùng một câu, cùng giọng
    # HoaiMy: lúc được lúc không, câu có "!" hoặc "?" hỏng nhiều hơn, và có
    # đợt mọi giá trị rate khác mặc định đều hỏng trong khi bỏ rate thì được.
    # Suốt mấy hôm trước, phần đọc thành tiếng trên máy chủ thật lặng hẳn vì
    # chuyện này mà log chỉ ghi "tts_failed", giao diện rơi về giọng trình
    # duyệt (không có tiếng Việt). Nên: đổi "!" "?" thành "." và thử lại vài
    # lần trong hạn giờ, hai lần đầu giữ tốc độ đã cấu hình, hai lần sau tốc
    # độ mặc định. Một lần hỏng chỉ mất chừng một giây nên vẫn vừa hạn giờ.
    spoken = text.replace("!", ".").replace("?", ".")
    attempts = [{"rate": config.TTS_RATE}] * 2
    if config.TTS_RATE not in ("+0%", "0%", ""):
        attempts += [{}] * 2

    async def _pull(kwargs) -> bytes:
        buf = bytearray()
        comm = edge_tts.Communicate(spoken, voice, **kwargs)
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                buf.extend(chunk["data"])
        return bytes(buf)

    async def _try_all() -> bytes:
        last: Exception | None = None
        for i, kwargs in enumerate(attempts):
            try:
                out = await _pull(kwargs)
                if out:
                    if i:
                        print(f"[tts] được ở lần thử {i + 1}"
                              + ("" if kwargs else " (tốc độ mặc định)")
                              + f": {text[:40]}…")
                    return out
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                last = exc
        raise last or RuntimeError("no audio")

    try:
        # Đặt hạn giờ: mạng ở nơi đặt kiosk có thể chập chờn, mà người dân
        # đang đứng chờ trước màn hình. Quá hạn thì thà báo hỏng sớm để giao
        # diện rơi về giọng của trình duyệt, còn hơn treo im lặng.
        audio = await asyncio.wait_for(_try_all(), timeout=timeout or config.TTS_TIMEOUT_SECONDS)
    except asyncio.TimeoutError as exc:
        raise TtsError("Máy chủ đọc chậm quá, bác đọc giúp cháu phần chữ trên màn hình.",
                       "tts_timeout") from exc
    except Exception as exc:  # noqa: BLE001
        print(f"[tts] hỏng ({type(exc).__name__}): {exc}")
        raise TtsError("Máy chưa đọc thành tiếng được.", "tts_failed") from exc
    _to_disk(text, voice, audio)
    _cache[k] = audio
    while len(_cache) > config.TTS_CACHE_SIZE:
        _cache.popitem(last=False)
    return audio
