"""Local backend - mirror approved assets to another folder (a NAS, a synced drive)."""

from __future__ import annotations

import os
import shutil

from . import Remote


class LocalBackend:
    name = "local"

    def __init__(self, root: str, dry_run: bool = False):
        self.root = root
        self.dry_run = dry_run
        self.calls: list = []

    def ensure_folder(self, path: str) -> str:
        target = os.path.join(self.root, path)
        self.calls.append(("mkdir", target))
        if not self.dry_run:
            os.makedirs(target, exist_ok=True)
        return target

    def upload(self, local_path: str, remote_path: str) -> Remote:
        target = os.path.join(self.root, remote_path)
        self.calls.append(("copy", local_path, target))
        if not self.dry_run:
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copy2(local_path, target)
        return Remote(id=target, path=remote_path, url=f"file://{target}",
                      dry_run=self.dry_run)

    def link(self, remote: Remote) -> str:
        return remote.url
