"""Push text and payload (WP-17). Pure: shortens an AlertMessage for a push notification.

Lengths are Unicode code points (`len()`), as in the contract. The body is shortened by taking
whole lines from the start (WP-08 orders them by importance); only a first line that is too long
on its own is cut, on a word boundary.
"""

import json
import re
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, field_validator

from shakka.domain.messages import AlertMessage

PUSH_TITLE_MAX: Final = 50  # code points (decision Lars)
PUSH_BODY_MAX: Final = 150  # code points (decision Lars)
PUSH_PAYLOAD_MAX_BYTES: Final = 3000  # UTF-8 bytes of PushPayload.to_json()
PUSH_TAG_MAX: Final = 64
ELLIPSIS: Final = "…"  # U+2026
FALLBACK_TITLE: Final = "Shakka"
_TAG_PATTERN: Final = re.compile(r"[A-Za-z0-9_.:-]+")
_TRAILING_SEPARATORS: Final = " \t·,;:–-"


def _single_line(value: str) -> str:
    if "\n" in value or "\r" in value:
        raise ValueError("title must not contain a newline")
    return value


class PushText(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    title: str = Field(min_length=1, max_length=PUSH_TITLE_MAX)
    body: str = Field(max_length=PUSH_BODY_MAX)

    _check_title = field_validator("title")(_single_line)


class PushPayload(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    title: str = Field(min_length=1, max_length=PUSH_TITLE_MAX)
    body: str = Field(max_length=PUSH_BODY_MAX)
    url: str = Field(min_length=1, pattern=r"^\S+$")
    tag: str = Field(min_length=1, max_length=PUSH_TAG_MAX)

    _check_title = field_validator("title")(_single_line)

    @field_validator("tag")
    @classmethod
    def _tag_chars(cls, value: str) -> str:
        if not _TAG_PATTERN.fullmatch(value):
            raise ValueError("tag has invalid characters")
        return value

    def to_json(self) -> str:
        return json.dumps(
            {"title": self.title, "body": self.body, "url": self.url, "tag": self.tag},
            ensure_ascii=False,
            separators=(",", ":"),
        )


def shorten_words(text: str, limit: int) -> str:
    """Shorten to at most `limit` code points, on a word boundary, ending in "…"."""
    if limit < 2:
        raise ValueError("limit must be at least 2")
    if len(text) <= limit:
        return text
    head = text[: limit - 1]  # room for the ellipsis
    if not text[limit - 1].isspace():  # the cut falls inside a word
        cut = max((i for i, c in enumerate(head) if c.isspace()), default=-1)
        if cut > 0:
            head = head[:cut]
    head = head.rstrip(_TRAILING_SEPARATORS)
    if not head:  # one word longer than the limit: no boundary exists
        head = text[: limit - 1].rstrip()
    return head + ELLIPSIS


def to_push_text(message: AlertMessage) -> PushText:
    title = shorten_words(message.title, PUSH_TITLE_MAX)
    if not title.strip():
        title = FALLBACK_TITLE
    body = message.body
    if len(body) > PUSH_BODY_MAX:
        lines = body.split("\n")
        taken: list[str] = []
        for line in lines:
            if len("\n".join([*taken, line])) > PUSH_BODY_MAX:
                break
            taken.append(line)
        body = "\n".join(taken) if taken else shorten_words(lines[0], PUSH_BODY_MAX)
    return PushText(title=title, body=body)


def spot_path(spot_id: str) -> str:
    return f"/spot/{spot_id}"


def push_tag(state_id: str) -> str:
    return f"alert-{state_id}"


def payload_size(payload: PushPayload) -> int:
    return len(payload.to_json().encode("utf-8"))


def build_push_payload(message: AlertMessage, *, tag: str) -> PushPayload:
    text = to_push_text(message)
    url = message.go_url or spot_path(message.spot_id)
    payload = PushPayload(title=text.title, body=text.body, url=url, tag=tag)
    if payload_size(payload) > PUSH_PAYLOAD_MAX_BYTES and message.go_url:
        payload = PushPayload(
            title=text.title, body=text.body, url=spot_path(message.spot_id), tag=tag
        )
    if payload_size(payload) > PUSH_PAYLOAD_MAX_BYTES:
        raise ValueError("push payload does not fit in the size limit")
    return payload
