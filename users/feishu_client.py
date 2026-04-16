"""飞书开放平台简易客户端：组织架构与成员拉取。"""

from __future__ import annotations

import json
import os
import ssl
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class FeishuAPIError(RuntimeError):
    pass


@dataclass
class FeishuDepartment:
    department_id: str
    name: str
    parent_department_id: str | None


@dataclass
class FeishuUser:
    open_id: str
    union_id: str
    name: str
    employee_no: str
    department_ids: list[str]


class FeishuClient:
    def __init__(self, app_id: str, app_secret: str, base_url: str = "https://open.feishu.cn"):
        app_id = (app_id or "").strip()
        app_secret = (app_secret or "").strip()
        if not app_id or not app_secret:
            raise ValueError("缺少 FEISHU_APP_ID / FEISHU_APP_SECRET")
        self.app_id = app_id
        self.app_secret = app_secret
        self.base_url = base_url.rstrip("/")
        self._tenant_access_token: str | None = None

        cafile = (os.environ.get("FEISHU_CA_BUNDLE") or os.environ.get("REQUESTS_CA_BUNDLE") or "").strip()
        if cafile:
            self._ssl_context = ssl.create_default_context(cafile=cafile)
        else:
            self._ssl_context = ssl.create_default_context()

    def _request(self, method: str, path: str, *, query: dict[str, Any] | None = None, body: dict[str, Any] | None = None, auth: bool = True) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        if query:
            url += "?" + urlencode(query)

        payload = None
        headers = {"Content-Type": "application/json; charset=utf-8"}
        if body is not None:
            payload = json.dumps(body).encode("utf-8")
        if auth:
            headers["Authorization"] = f"Bearer {self.tenant_access_token}"

        req = Request(url=url, method=method.upper(), data=payload, headers=headers)
        with urlopen(req, timeout=30, context=self._ssl_context) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        code = int(data.get("code", -1))
        if code != 0:
            msg = data.get("msg") or data.get("message") or "unknown error"
            raise FeishuAPIError(f"Feishu API error code={code}, msg={msg}, path={path}")
        return data

    @property
    def tenant_access_token(self) -> str:
        if self._tenant_access_token:
            return self._tenant_access_token
        data = self._request(
            "POST",
            "/open-apis/auth/v3/tenant_access_token/internal",
            body={"app_id": self.app_id, "app_secret": self.app_secret},
            auth=False,
        )
        token = (data.get("tenant_access_token") or "").strip()
        if not token:
            raise FeishuAPIError("tenant_access_token 为空")
        self._tenant_access_token = token
        return token

    def list_departments(self, root_department_id: str = "0") -> list[FeishuDepartment]:
        departments: list[FeishuDepartment] = []
        page_token = ""

        while True:
            data = self._request(
                "GET",
                "/open-apis/contact/v3/departments",
                query={
                    "department_id": root_department_id,
                    "department_id_type": "department_id",
                    "fetch_child": "true",
                    "page_size": 50,
                    "page_token": page_token,
                },
            )
            items = (((data.get("data") or {}).get("items")) or [])
            for item in items:
                did = str(item.get("department_id") or "").strip()
                if not did:
                    continue
                departments.append(
                    FeishuDepartment(
                        department_id=did,
                        name=str(item.get("name") or "").strip(),
                        parent_department_id=str(item.get("parent_department_id") or "").strip() or None,
                    )
                )

            page_token = ((data.get("data") or {}).get("page_token") or "").strip()
            has_more = bool((data.get("data") or {}).get("has_more"))
            if not has_more:
                break

        return departments

    def list_users_by_department(self, department_id: str) -> list[FeishuUser]:
        users: list[FeishuUser] = []
        page_token = ""

        while True:
            data = self._request(
                "GET",
                "/open-apis/contact/v3/users/find_by_department",
                query={
                    "department_id": department_id,
                    "department_id_type": "department_id",
                    "user_id_type": "open_id",
                    "page_size": 50,
                    "page_token": page_token,
                },
            )
            items = (((data.get("data") or {}).get("items")) or [])
            for item in items:
                employee_no = str(item.get("employee_no") or "").strip()
                open_id = str(item.get("open_id") or "").strip()
                if not employee_no or not open_id:
                    continue
                dept_ids = [str(x).strip() for x in (item.get("department_ids") or []) if str(x).strip()]
                users.append(
                    FeishuUser(
                        open_id=open_id,
                        union_id=str(item.get("union_id") or "").strip(),
                        name=str(item.get("name") or "").strip(),
                        employee_no=employee_no,
                        department_ids=dept_ids,
                    )
                )

            page_token = ((data.get("data") or {}).get("page_token") or "").strip()
            has_more = bool((data.get("data") or {}).get("has_more"))
            if not has_more:
                break

        return users
