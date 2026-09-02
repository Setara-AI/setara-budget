"""
Sync - where approved assets go.

One small interface, three backends. The pipeline only ever calls the
interface, so moving a show from a local drive to Frame.io or Drive is a
one-line change and never touches the ledger.

    ensure_folder(path)          -> a backend-specific folder id
    upload(local_path, path)     -> a Remote (id + optional link)
    link(remote)                 -> a shareable URL, where the backend has one

CONFIDENCE, stated plainly, because a sync that silently no-ops is worse than
no sync at all:

  local     verified - it is os and shutil
  gdrive    Drive v3 is long-stable and implemented from it; not run here
            because this machine has no Drive credentials
  frameio   V4 auth and account discovery are implemented from the published
            reference; the folder-create and upload shapes are NOT published in
            the public index, so they ship behind dry_run and must be confirmed
            against your account before you trust them

Every backend takes `dry_run`, which records the calls it would make instead of
making them. `push_approved()` in this module is what the app actually calls.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class Remote:
    """Something that now exists on the far side."""

    id: str
    path: str
    url: str = ""
    dry_run: bool = False


class Backend(Protocol):
    name: str

    def ensure_folder(self, path: str) -> str: ...
    def upload(self, local_path: str, remote_path: str) -> Remote: ...
    def link(self, remote: Remote) -> str: ...


@dataclass
class PushResult:
    uploaded: list = field(default_factory=list)     # list[Remote]
    skipped: list = field(default_factory=list)      # (asset_id, reason)
    errors: list = field(default_factory=list)       # (asset_id, message)

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        return (f"{len(self.uploaded)} uploaded, {len(self.skipped)} skipped, "
                f"{len(self.errors)} failed")


def push_approved(library, backend: Backend, only_new: bool = True) -> PushResult:
    """Mirror every APPROVED asset into the backend, preserving the folder shape.

    Only approved assets are ever pushed - the review folders stay local. That
    is the point of the hierarchy: what leaves the building is what was signed
    off, so a link you send is always a locked version.
    """
    import os

    from ..assets import Status

    result = PushResult()
    for asset in library.assets.values():
        if asset.status is not Status.APPROVED or not asset.approved_path:
            result.skipped.append((asset.id, f"status={asset.status.value}"))
            continue
        local = os.path.join(library.root, asset.approved_path)
        if only_new and not os.path.exists(local):
            result.skipped.append((asset.id, "approved file not on disk"))
            continue
        try:
            backend.ensure_folder(os.path.dirname(asset.approved_path))
            result.uploaded.append(backend.upload(local, asset.approved_path))
        except Exception as exc:
            result.errors.append((asset.id, str(exc)))
    return result


def get(name: str, **kwargs) -> Backend:
    """Backend by name: 'local', 'gdrive', 'frameio'."""
    if name == "local":
        from .local import LocalBackend

        return LocalBackend(**kwargs)
    if name == "gdrive":
        from .gdrive import GoogleDriveBackend

        return GoogleDriveBackend(**kwargs)
    if name == "frameio":
        from .frameio import FrameIoBackend

        return FrameIoBackend(**kwargs)
    raise KeyError(f"Unknown backend {name!r}. Known: local, gdrive, frameio")
