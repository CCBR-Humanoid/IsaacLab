from __future__ import annotations

import os
from pathlib import Path

from .base_gui_interface import BaseGUIInterface
from ..x11 import x11_check, x11_refresh, x11_cleanup
from ..state_file import StateFile


class X11Interface(BaseGUIInterface):
    """X11 GUI handler that manages cookie file, overlay, and exec envs.

    Usage pattern:
    - call start() before compose up to prepare overlay and env updates
    - call prepare_enter() before docker exec to refresh cookie and populate exec envs
    - call cleanup() after compose down to delete cookie and state entries
    """

    def __init__(self, context_dir: Path, statefile: StateFile, session_id: str, access: str | None = None):
        self.context_dir = context_dir
        self.statefile = statefile
        self.session_id = session_id
        self.access = access or "unknown"
        self.extra_compose_files: list[str] = []
        self.env_updates: dict[str, str] = {}
        self.exec_env: dict[str, str] = {}

    def start(self):
        """Prepare X11 overlay and env for compose start."""
        # Require DISPLAY in host env to be meaningful; otherwise skip quietly
        if "DISPLAY" not in os.environ:
            return
        # Namespace per session and configure xauth
        self.statefile.namespace = f"X11-{self.session_id}"
        _args, envars = x11_check(self.statefile) or (None, None)
        if envars:
            self.env_updates.update(envars)
            self.extra_compose_files.append(str(self.context_dir / "docker" / "composers" / "docker-compose-x11.yaml"))
        # Exec env used when entering
        self.exec_env["XAUTHORITY"] = "/tmp/.isaaclab-docker.xauth"
        if "DISPLAY" in os.environ:
            self.exec_env["DISPLAY"] = os.environ["DISPLAY"]

    def prepare_enter(self):
        """Refresh the X11 cookie and set exec envs for docker exec."""
        if self.statefile.namespace is None:
            self.statefile.namespace = f"X11-{self.session_id}"
        try:
            x11_refresh(self.statefile)
        except Exception:
            pass
        # ensure exec_env populated even if start() was not called in this process
        self.exec_env.setdefault("XAUTHORITY", "/tmp/.isaaclab-docker.xauth")
        if "DISPLAY" in os.environ:
            self.exec_env["DISPLAY"] = os.environ["DISPLAY"]

    def stop(self):
        """No-op for X11; cleanup happens in cleanup()."""
        return

    def cleanup(self):
        """Remove the xauth cookie and delete state sections."""
        if self.statefile.namespace is None:
            self.statefile.namespace = f"X11-{self.session_id}"
        try:
            x11_cleanup(self.statefile)
        except Exception:
            pass
        # Remove session and legacy sections, then persist
        try:
            ns = self.statefile.namespace
            if ns:
                self.statefile.delete_section(ns)
            self.statefile.delete_section("X11")
            self.statefile.save()
        except Exception:
            pass