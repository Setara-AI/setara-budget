"""
Frame.io backend (V4).

WHAT IS VERIFIED, and what is not - read this before pointing it at a real account.

VERIFIED against Frame.io's published V4 reference (read 2026-08-26):
  * base URL          https://api.frame.io/v4
  * auth              Authorization: Bearer <token>
  * GET /me           who the token belongs to
  * GET /accounts     the accounts the token can see

NOT VERIFIED: Frame.io's public documentation index does not expose the
folder-create or file-upload request shapes. The two methods below are written
to the shapes Frame.io's V4 uses (a `data` envelope, and a `local_upload` call
that returns pre-signed `upload_urls` you then PUT the bytes to), but they have
NOT been run against a live account, and the endpoint templates are class
attributes precisely so they can be corrected in one place.

Because of that, `dry_run` defaults to True. Run it, read `calls`, check them
against your account's API reference, then set dry_run=False. Frame.io also
publishes an official Python SDK - if these shapes have moved, that SDK is the
better lane, and `push_approved` will drive it just as happily behind the same
Backend interface.

Auth: a developer token or OAuth access token, passed in or from FRAMEIO_TOKEN.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from . import Remote

API = "https://api.frame.io/v4"


class FrameIoBackend:
    name = "frameio"

    # Endpoint templates - the unverified ones are marked. Correct here, once.
    ME = "/me"                                                    # verified
    ACCOUNTS = "/accounts"                                        # verified
    CREATE_FOLDER = "/accounts/{account_id}/folders/{parent_id}/children"   # UNVERIFIED
    LOCAL_UPLOAD = "/accounts/{account_id}/folders/{parent_id}/files/local_upload"  # UNVERIFIED

    def __init__(self, token: str = "", account_id: str = "", root_folder_id: str = "",
                 dry_run: bool = True):
        self.token = token or os.environ.get("FRAMEIO_TOKEN", "")
        self.account_id = account_id or os.environ.get("FRAMEIO_ACCOUNT_ID", "")
        self.root_folder_id = root_folder_id or os.environ.get("FRAMEIO_ROOT_FOLDER_ID", "")
        self.dry_run = dry_run
        self.calls: list = []
        self._folders: dict[str, str] = {"": self.root_folder_id}
        if not self.dry_run and not self.token:
            raise RuntimeError("No Frame.io token. Pass token= or set FRAMEIO_TOKEN.")

    # -- HTTP -------------------------------------------------------------
    def _request(self, method: str, path: str, body=None, url: str = "", raw=False):
        target = url or (API + path)
        headers = {"Authorization": f"Bearer {self.token}"}
        if body is not None and not raw:
            body = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(target, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                text = response.read().decode()
                return json.loads(text) if text else {}
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="ignore")[:400]
            raise RuntimeError(f"Frame.io {method} {target} -> {exc.code}: {detail}") from None

    # -- discovery (verified endpoints) -----------------------------------
    def whoami(self) -> dict:
        self.calls.append(("GET", API + self.ME))
        return {"dry_run": True} if self.dry_run else self._request("GET", self.ME)

    def accounts(self) -> list:
        self.calls.append(("GET", API + self.ACCOUNTS))
        if self.dry_run:
            return []
        payload = self._request("GET", self.ACCOUNTS)
        return payload.get("data", payload if isinstance(payload, list) else [])

    def resolve_account(self) -> str:
        """Use the configured account, or the only one the token can see."""
        if self.account_id:
            return self.account_id
        found = self.accounts()
        if len(found) == 1:
            self.account_id = found[0].get("id", "")
        elif len(found) > 1:
            raise RuntimeError(
                "This token sees several accounts - pass account_id= explicitly: "
                + ", ".join(f"{a.get('id')} ({a.get('display_name', a.get('name', '?'))})"
                            for a in found))
        return self.account_id

    # -- folders (UNVERIFIED shape) ---------------------------------------
    def ensure_folder(self, path: str) -> str:
        path = path.strip("/")
        if path in self._folders:
            return self._folders[path]

        account_id = self.resolve_account() if not self.dry_run else (self.account_id or "ACCOUNT")
        parent_id = self.root_folder_id or "ROOT"
        walked = []
        for segment in path.split("/"):
            walked.append(segment)
            key = "/".join(walked)
            if key in self._folders:
                parent_id = self._folders[key]
                continue
            endpoint = self.CREATE_FOLDER.format(account_id=account_id, parent_id=parent_id)
            body = {"data": {"name": segment, "type": "folder"}}
            self.calls.append(("POST", API + endpoint, body))
            if self.dry_run:
                parent_id = f"dry-run-folder:{key}"
            else:
                created = self._request("POST", endpoint, body)
                parent_id = created.get("data", created).get("id", "")
            self._folders[key] = parent_id
        return parent_id

    # -- upload (UNVERIFIED shape) ----------------------------------------
    def upload(self, local_path: str, remote_path: str) -> Remote:
        """Two-step: ask for pre-signed URLs, then PUT the bytes to them."""
        folder_id = self.ensure_folder(os.path.dirname(remote_path))
        name = os.path.basename(remote_path)
        size = os.path.getsize(local_path) if os.path.exists(local_path) else 0
        account_id = self.account_id or "ACCOUNT"
        endpoint = self.LOCAL_UPLOAD.format(account_id=account_id, parent_id=folder_id)
        body = {"data": {"name": name, "file_size": size}}

        self.calls.append(("POST", API + endpoint, body))
        if self.dry_run:
            return Remote(id=f"dry-run-file:{name}", path=remote_path, dry_run=True)

        created = self._request("POST", endpoint, body).get("data", {})
        upload_urls = created.get("upload_urls") or []
        if not upload_urls:
            raise RuntimeError(
                f"Frame.io returned no upload_urls for {name}. The local_upload shape has "
                f"probably changed - correct FrameIoBackend.LOCAL_UPLOAD and this method, "
                f"or drive the official SDK behind the same Backend interface.")

        with open(local_path, "rb") as fh:
            payload = fh.read()
        chunk = -(-len(payload) // len(upload_urls))        # ceil division
        for index, url in enumerate(upload_urls):
            part = payload[index * chunk:(index + 1) * chunk]
            self._request("PUT", "", part, url=url, raw=True)

        return Remote(id=created.get("id", ""), path=remote_path,
                      url=created.get("view_url", ""))

    def link(self, remote: Remote) -> str:
        return remote.url
