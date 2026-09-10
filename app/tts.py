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


def cache_info() -> dict:
    return {"entries": len(_cache),
            "bytes": sum(len(v) for v in _cache.values()),
            "max_entries": config.TTS_CACHE_SIZE}


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

    buf = bytearray()
    try:
        comm = edge_tts.Communicate(text, voice, rate=config.TTS_RATE)
        # Đặt hạn giờ: mạng ở nơi đặt kiosk có thể chập chờn, mà người dân
        # đang đứng chờ trước màn hình. Quá hạn thì thà báo hỏng sớm để giao
        # diện rơi về giọng của trình duyệt, còn hơn treo im lặng.
        async def _pull():
            async for chunk in comm.stream():
                if chunk["type"] == "audio":
                    buf.extend(chunk["data"])

        await asyncio.wait_for(_pull(), timeout=timeout or config.TTS_TIMEOUT_SECONDS)
    except asyncio.TimeoutError as exc:
        raise TtsError("Máy chủ đọc chậm quá, bác đọc giúp con phần chữ trên màn hình.",
                       "tts_timeout") from exc
    except Exception as exc:  # noqa: BLE001
        raise TtsError("Máy chưa đọc thành tiếng được.", "tts_failed") from exc

    if not buf:
        raise TtsError("Máy chưa đọc thành tiếng được.", "tts_failed")

    audio = bytes(buf)
    _cache[k] = audio
    while len(_cache) > config.TTS_CACHE_SIZE:
        _cache.popitem(last=False)
    return audio
