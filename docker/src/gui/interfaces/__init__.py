from pathlib import Path
from .webrtc_interface import WebRTCInterface
from .x11_interface import X11Interface
from .gui_interface import GUIInterface
from ..state_file import StateFile


def make_gui_handler(kind: GUIInterface, *, context_dir, statefile: StateFile | None = None, session_id: str = "", access: str | None = None, is_remote: bool = False):
	if statefile is None:
		# Default to repo-level .container.cfg under the provided context dir.
		statefile = StateFile(path=Path(context_dir) / ".container.cfg")
	if kind == GUIInterface.X11:
		return X11Interface(context_dir=context_dir, statefile=statefile, session_id=session_id, access=access)
	if kind == GUIInterface.WEBRTC:
		return WebRTCInterface(context_dir=context_dir, is_remote=is_remote)
	return None