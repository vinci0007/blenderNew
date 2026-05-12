from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Any, Dict, Iterable, List


SUPPORTED_IMAGE_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
}


def _guess_image_mime_type(path: Path) -> str:
    mime_type, _ = mimetypes.guess_type(str(path))
    if mime_type in SUPPORTED_IMAGE_MIME_TYPES:
        return mime_type
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".png":
        return "image/png"
    if suffix == ".webp":
        return "image/webp"
    if suffix == ".gif":
        return "image/gif"
    raise ValueError(
        f"unsupported image type for '{path}'. "
        "Supported image formats: jpg, jpeg, png, webp, gif"
    )


def load_image_content_blocks(image_paths: Iterable[str]) -> List[Dict[str, Any]]:
    blocks: List[Dict[str, Any]] = []
    for image_path in image_paths:
        path = Path(image_path).expanduser()
        try:
            resolved = path.resolve(strict=True)
        except OSError as exc:
            raise FileNotFoundError(f"failed to read image '{image_path}': {exc}") from exc
        mime_type = _guess_image_mime_type(resolved)
        data = base64.b64encode(resolved.read_bytes()).decode("ascii")
        blocks.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:{mime_type};base64,{data}"},
                "media_type": mime_type,
                "source_path": str(resolved),
            }
        )
    return blocks


def attach_visual_inputs_to_messages(
    messages: List[Dict[str, Any]],
    visual_inputs: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    if not visual_inputs:
        return messages

    converted = [dict(message) for message in messages]
    for message in converted:
        if message.get("role") != "user":
            continue
        content = message.get("content")
        if isinstance(content, list):
            message["content"] = list(content) + [dict(block) for block in visual_inputs]
        else:
            text = "" if content is None else str(content)
            message["content"] = [{"type": "text", "text": text}] + [
                dict(block) for block in visual_inputs
            ]
        return converted

    converted.append(
        {
            "role": "user",
            "content": [{"type": "text", "text": ""}] + [dict(block) for block in visual_inputs],
        }
    )
    return converted
