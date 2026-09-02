"""
Google Drive backend (Drive v3).

Implemented from the Drive v3 REST API, which has been stable for years:

  folders   POST /drive/v3/files  with mimeType application/vnd.google-apps.folder
            and parents=[parent_id]
  lookup    GET  /drive/v3/files?q=...  to avoid creating the same folder twice
  upload    POST /upload/drive/v3/files?uploadType=multipart  (metadata + bytes)
  share     POST /drive/v3/permissions  (role=reader, type=anyone) - only when
            you ask for it

NOT RUN AGAINST A REAL ACCOUNT HERE - this machine has no Drive credentials.
The request shapes come from the published API, not from a live call, so treat
the first run as a test: use dry_run=True, read `calls`, then go live.

Auth: an OAuth access token with the `drive.file` scope, passed in or taken from
GOOGLE_DRIVE_TOKEN. `drive.file` is the right scope - it grants access only to
files this app creates, not the user's whole Drive.
"""

from __future__ import annotations

import json
import mimetypes
import os
import urllib.error
import urllib.parse
import urllib.request

from . import Remote

API = "https://www.googleapis.com/drive/v3"
UPLOAD_API = "https://www.googleapis.com/upload/drive/v3"
FOLDER_MIME = "application/vnd.google-apps.folder"


class GoogleDriveBackend:
    name = "gdrive"

    def __init__(self, token: str = "", root_folder_id: str = "root",
                 dry_run: bool = True, share: bool = False):
        self.token = token or os.environ.get("GOOGLE_DRIVE_TOKEN", "")
        self.root_folder_id = root_folder_id
        self.dry_run = dry_run
        self.share = share
        self.calls: list = []
        self._folders: dict[str, str] = {"": root_folder_id}
        if not self.token and not dry_run:
            raise RuntimeError(
                "No Drive token. Pass token= or set GOOGLE_DRIVE_TOKEN "
                "(OAuth access token with the drive.file scope).")

    # -- HTTP -------------------------------------------------------------
    def _request(self, method: str, url: str, body=None, headers=None, raw=False):
        headers = {"Authorization": f"Bearer {self.token}", **(headers or {})}
        if body is not None and not raw:
            body = json.dumps(body).encode()
            headers.setdefault("Content-Type", "application/json")
        request = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                text = response.read().decode()
                return json.loads(text) if text else {}
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="ignore")[:400]
            raise RuntimeError(f"Drive {method} {url} -> {exc.code}: {detail}") from None

    # -- folders ----------------------------------------------------------
    def ensure_folder(self, path: str) -> str:
        """Create the folder chain, one segment at a time, reusing what exists."""
        path = path.strip("/")
        if path in self._folders:
            return self._folders[path]

        parent_id = self.root_folder_id
        walked = []
        for segment in path.split("/"):
            walked.append(segment)
            key = "/".join(walked)
            if key in self._folders:
                parent_id = self._folders[key]
                continue
            parent_id = self._folder_named(segment, parent_id) or \
                self._create_folder(segment, parent_id)
            self._folders[key] = parent_id
        return parent_id

    def _folder_named(self, name: str, parent_id: str) -> str:
        escaped = name.replace("'", "\\'")
        query = (f"name = '{escaped}' and mimeType = '{FOLDER_MIME}' "
                 f"and '{parent_id}' in parents and trashed = false")
        url = f"{API}/files?" + urllib.parse.urlencode(
            {"q": query, "fields": "files(id,name)", "pageSize": 1})
        self.calls.append(("GET", url))
        if self.dry_run:
            return ""
        files = self._request("GET", url).get("files", [])
        return files[0]["id"] if files else ""

    def _create_folder(self, name: str, parent_id: str) -> str:
        body = {"name": name, "mimeType": FOLDER_MIME, "parents": [parent_id]}
        self.calls.append(("POST", f"{API}/files", body))
        if self.dry_run:
            return f"dry-run-folder:{name}"
        return self._request("POST", f"{API}/files?fields=id", body)["id"]

    # -- files ------------------------------------------------------------
    def upload(self, local_path: str, remote_path: str) -> Remote:
        folder_id = self.ensure_folder(os.path.dirname(remote_path))
        name = os.path.basename(remote_path)
        metadata = {"name": name, "parents": [folder_id]}
        url = f"{UPLOAD_API}/files?uploadType=multipart&fields=id,webViewLink"
        self.calls.append(("POST", url, metadata))
        if self.dry_run:
            return Remote(id=f"dry-run-file:{name}", path=remote_path, dry_run=True)

        boundary = "----budgetsync7c1f"
        mime = mimetypes.guess_type(local_path)[0] or "application/octet-stream"
        with open(local_path, "rb") as fh:
            payload = fh.read()
        body = b"".join([
            f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n".encode(),
            json.dumps(metadata).encode(), b"\r\n",
            f"--{boundary}\r\nContent-Type: {mime}\r\n\r\n".encode(),
            payload, f"\r\n--{boundary}--\r\n".encode(),
        ])
        created = self._request(
            "POST", url, body, raw=True,
            headers={"Content-Type": f"multipart/related; boundary={boundary}"})

        remote = Remote(id=created["id"], path=remote_path,
                        url=created.get("webViewLink", ""))
        if self.share:
            self._share(remote.id)
        return remote

    def _share(self, file_id: str):
        body = {"role": "reader", "type": "anyone"}
        self.calls.append(("POST", f"{API}/files/{file_id}/permissions", body))
        if not self.dry_run:
            self._request("POST", f"{API}/files/{file_id}/permissions", body)

    def link(self, remote: Remote) -> str:
        return remote.url or f"https://drive.google.com/file/d/{remote.id}/view"
