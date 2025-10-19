from __future__ import annotations

from pathlib import Path

from .base_gui_interface import BaseGUIInterface


class WebRTCInterface(BaseGUIInterface):
    """WebRTC handler providing compose overlays and env for local/remote modes."""

    def __init__(self, context_dir: Path, is_remote: bool):
        self.context_dir = context_dir
        self.is_remote = is_remote
        self.extra_compose_files: list[str] = []
        self.env_updates: dict[str, str] = {}

    def start(self):
        """Set overlays for WebRTC, adding tailscale overlay when remote."""
        # The base compose already sets LIVESTREAM/ENABLE_CAMERAS via env files.
        if self.is_remote:
            self.extra_compose_files.append(str(self.context_dir / "docker" / "composers" / "docker-compose-tailscale.yaml"))

    def stop(self):
        return

    def cleanup(self):
        return