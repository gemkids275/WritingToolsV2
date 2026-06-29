from dataclasses import dataclass
from enum import Enum


class AttachmentType(Enum):
    IMAGE = "image"
    TEXT = "text"


@dataclass
class Attachment:
    type: AttachmentType
    label: str
    data: bytes | None = None   # raw bytes cho IMAGE
    text: str | None = None     # nội dung cho TEXT
    mime_type: str = "image/png"
