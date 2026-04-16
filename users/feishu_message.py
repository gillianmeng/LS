"""飞书消息推送工具。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Iterable

from .feishu_client import FeishuClient, FeishuAPIError


@dataclass
class FeishuPushResult:
    sent_count: int
    skipped_count: int


class FeishuMessenger:
    def __init__(self, client: FeishuClient | None = None):
        if client is None:
            app_id = os.environ.get("FEISHU_APP_ID", "").strip()
            app_secret = os.environ.get("FEISHU_APP_SECRET", "").strip()
            client = FeishuClient(app_id=app_id, app_secret=app_secret)
        self.client = client

    def send_text_to_open_ids(self, open_ids: Iterable[str], content: str) -> FeishuPushResult:
        sent = 0
        skipped = 0
        content = (content or "").strip()
        if not content:
            return FeishuPushResult(sent_count=0, skipped_count=0)

        for open_id in open_ids:
            open_id = (open_id or "").strip()
            if not open_id:
                skipped += 1
                continue
            self.client._request(
                "POST",
                "/open-apis/im/v1/messages?receive_id_type=open_id",
                body={
                    "receive_id": open_id,
                    "msg_type": "text",
                    "content": {"text": content},
                },
            )
            sent += 1
        return FeishuPushResult(sent_count=sent, skipped_count=skipped)

    def send_text_to_user(self, open_id: str, content: str) -> FeishuPushResult:
        return self.send_text_to_open_ids([open_id], content)
