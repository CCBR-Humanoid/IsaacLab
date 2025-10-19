"""Interactive runner for starting, entering, and stopping Isaac Lab containers."""
import os
from pathlib import Path
from rich import print

from src.utils import (
    is_remote_session,
    generate_nickname,
    select_option,
    option,
    PRESET_THEMES,
    generate_session_id,
)
from src.gui.interfaces import GUIInterface
from src.container_interface import ContainerInterface as Container

THEME = PRESET_THEMES["Dracula"]

def ask_action():
    _, val = select_option(
        "What do you want to do?",
        option("Start new session", value="start"),
        option("Enter a session", value="enter"),
        option("Stop a session", value="stop"),
        option("List sessions", value="list"),
        theme=THEME,
    )
    return val

def ask_gui_mode() -> GUIInterface:
    x11_warn = None
    x11_info = None
    if not os.environ.get("DISPLAY"):
        x11_warn = "DISPLAY is not set; X11 may not work in this session."
    else:
        x11_info = f"Using DISPLAY={os.environ.get('DISPLAY')}"
    _, selected = select_option(
        "Select GUI Interface",
        option("WebRTC", "Use WebRTC streaming", value=GUIInterface.WEBRTC, recommended=True,
               info="Local: uses LAN IP; Remote: uses Tailscale 100.x"),
        option("X11 Forwarding", "Use X11 display forwarding", value=GUIInterface.X11, warning=x11_warn, info=x11_info),
        option("None", "Headless", value=GUIInterface.NONE),
        default=GUIInterface.WEBRTC,
        theme=THEME,
    )
    return selected

def ask_ros_support() -> bool:
    _, val = select_option(
        "Do you want ROS support?",
        option("Yes", "Enable ROS2 Humble", value=True),
        option("No", "Disable ROS", value=False),
        default=False,
        theme=THEME,
    )
    return val

def ask_rebuild() -> bool:
    # Only ask if user wants to override default (no rebuild)
    _, val = select_option(
        "Force rebuild images?",
        option("No", "Use cache, build only if missing", value=False, recommended=True),
        option("Yes", "Rebuild base image before starting", value=True),
        theme=THEME,
    )
    return val

def choose_running_session(ci: Container):
    rows = ci.list_running_sessions()
    if not rows:
        print("[yellow]No running sessions found.[/yellow]")
        return None
    # Optional filtering before selection
    rows = apply_filters(rows)
    if not rows:
        print("[yellow]No sessions match your filters.[/yellow]")
        return None
    opts = []
    for r in rows:
        badge = f"{r.get('gui','')}|{r.get('access','')}" if r.get('gui') else (r.get('profile','') or '')
        label = f"{r.get('nickname') or '(no name)'}"
        desc = f"{r['name']}    {badge}"
        opts.append(option(label, description=desc, value=r))
    _, val = select_option("Select a session", *opts, theme=THEME)
    return val

def ask_filters():
    # GUI filter
    _, gui_filter = select_option(
        "Filter by GUI?",
        option("All", value="all", recommended=True),
        option("WebRTC", value="webrtc"),
        option("X11", value="x11"),
        option("None", value="none"),
        theme=THEME,
    )
    # Access filter
    _, access_filter = select_option(
        "Filter by access?",
        option("All", value="all", recommended=True),
        option("Local", value="local"),
        option("Remote", value="remote"),
        theme=THEME,
    )
    # Nickname substring
    try:
        from prompt_toolkit import prompt
        nickname_query = prompt("Nickname contains (optional): ")
    except Exception:
        nickname_query = ""
    nickname_query = str(nickname_query or "")
    return {"gui": gui_filter, "access": access_filter, "nickname": nickname_query.strip()}

def apply_filters(rows: list[dict]):
    # Ask filters interactively
    flt = ask_filters()
    gui = flt["gui"]
    access = flt["access"]
    nickname_sub = flt["nickname"].lower()
    def match(row):
        if gui != "all":
            if (row.get("gui") or "").lower() != gui:
                return False
        if access != "all":
            if (row.get("access") or "").lower() != access:
                return False
        if nickname_sub:
            if nickname_sub not in (row.get("nickname") or "").lower():
                return False
        return True
    return [r for r in rows if match(r)]

def main():
    action = ask_action()

    # Create interface bound to repo root (runner.py is under <repo>/docker)
    root = Path(__file__).resolve().parent.parent
    ci = Container(context_dir=root)

    if action == "start":
        gui = ask_gui_mode()
        ros = ask_ros_support()
        remote = is_remote_session()
        force_rebuild = ask_rebuild()

        # Enforce only one local GUI (X11 or WebRTC-local) at a time
        if not remote and gui in (GUIInterface.X11, GUIInterface.WEBRTC):
            running = ci.list_running_sessions()
            if any(r.get("profile", "").endswith("webrtc-local") or r.get("profile") in ("base", "ros2") for r in running):
                print("[red]A local GUI session already appears to be running. Stop it before starting another.[/red]")
                return

        session_id = generate_session_id()
        nickname = generate_nickname()

        # Map to compose profile
        if gui == GUIInterface.NONE and not ros:
            profile = "base"
        elif gui == GUIInterface.NONE and ros:
            profile = "ros2"
        elif gui == GUIInterface.WEBRTC and not ros:
            profile = "webrtc-remote" if remote else "webrtc-local"
        elif gui == GUIInterface.WEBRTC and ros:
            profile = "ros2-webrtc-remote" if remote else "ros2-webrtc-local"
        elif gui == GUIInterface.X11 and not ros:
            profile = "base"  # we overlay X11
        elif gui == GUIInterface.X11 and ros:
            profile = "ros2"   # we overlay X11
        else:
            profile = "base"

        # Set env for compose
        ci.profile = profile
        ci.project_name = session_id
        ci.environ["COMPOSE_PROJECT_NAME"] = session_id
        ci.environ["SESSION_ID"] = session_id
        ci.environ["SESSION_NICKNAME"] = nickname
        ci.environ["SESSION_ACCESS"] = "remote" if remote else "local"
        ci.environ["SESSION_GUI"] = (
            "x11" if gui == GUIInterface.X11 else ("webrtc" if gui == GUIInterface.WEBRTC else "none")
        )
        ci.environ["FORCE_REBUILD_BASE"] = "1" if force_rebuild else "0"

        # Point env files and base compose
        ci.configure(
            yamls=[],
            envs=[str(root / "docker" / "envs" / ".env.base")]
            + ([str(root / "docker" / "envs" / ".env.ros2")] if ros else [])
            + ([str(root / "docker" / "envs" / ".env.webrtc")] if gui == GUIInterface.WEBRTC else [])
            + (([str(root / "docker" / "envs" / ".env.tailscale")] if (gui == GUIInterface.WEBRTC and remote) else []))
        )

        print(f"[bold green]Starting[/bold green] session {session_id} as '{nickname}' with profile '{profile}'...")
        ci.start()

    elif action == "enter":
        row = choose_running_session(ci)
        if not row:
            return
        # Ensure interface matches the selected session's profile for overlays
        if row.get("profile"):
            ci.profile = row["profile"]
        # Set project/session env so exec picks up the right context when needed
        if row.get("session_id"):
            ci.project_name = row["session_id"]
            ci.environ["COMPOSE_PROJECT_NAME"] = row["session_id"]
            ci.environ["SESSION_ID"] = row["session_id"]
        if row.get("nickname") is not None:
            ci.environ["SESSION_NICKNAME"] = row.get("nickname") or ""
        # Propagate GUI/access so X11 refresh logic and labels behave correctly on enter
        if row.get("gui"):
            ci.environ["SESSION_GUI"] = row.get("gui")
        if row.get("access"):
            ci.environ["SESSION_ACCESS"] = row.get("access")
        # Re-seed compose env-files based on profile for proper interpolation
        envs = [str(root / "docker" / "envs" / ".env.base")]
        prof = (row.get("profile") or "")
        if prof.startswith("ros2"):
            envs.append(str(root / "docker" / "envs" / ".env.ros2"))
        if "webrtc" in prof:
            envs.append(str(root / "docker" / "envs" / ".env.webrtc"))
        if prof.endswith("-remote"):
            envs.append(str(root / "docker" / "envs" / ".env.tailscale"))
        ci.configure(yamls=[], envs=envs)
        ci.container_name = row["name"]
        ci.enter()

    elif action == "stop":
        row = choose_running_session(ci)
        if not row:
            return
        # Confirm with the user before stopping the selected session
        try:
            from src.utils import select_option, option
            label = row.get("nickname") or "(no name)"
            desc = f"{row['name']}    {(row.get('gui') or row.get('profile') or '')}"
            _, confirm = select_option(
                f"Stop session '{label}'?",
                option("No", "Cancel and return", value=False, recommended=True),
                option("Yes", f"Stop and remove non-persistent volumes for {desc}", value=True),
                theme=THEME,
            )
            if not confirm:
                print("[yellow]Cancelled.[/yellow]")
                return
        except Exception:
            # If interactive UI is not available, default to proceeding
            pass
        if row.get("profile"):
            ci.profile = row["profile"]
        if row.get("session_id"):
            ci.project_name = row["session_id"]
            ci.environ["COMPOSE_PROJECT_NAME"] = row["session_id"]
            ci.environ["SESSION_ID"] = row["session_id"]
        if row.get("nickname") is not None:
            ci.environ["SESSION_NICKNAME"] = row.get("nickname") or ""
        # Re-seed compose env-files based on profile for proper interpolation
        envs = [str(root / "docker" / "envs" / ".env.base")]
        prof = (row.get("profile") or "")
        if prof.startswith("ros2"):
            envs.append(str(root / "docker" / "envs" / ".env.ros2"))
        if "webrtc" in prof:
            envs.append(str(root / "docker" / "envs" / ".env.webrtc"))
        if prof.endswith("-remote"):
            envs.append(str(root / "docker" / "envs" / ".env.tailscale"))
        ci.configure(yamls=[], envs=envs)
        ci.container_name = row["name"]
        ci.stop()

    elif action == "list":
        rows = ci.list_running_sessions()
        if not rows:
            print("[yellow]No running sessions found.[/yellow]")
            return
        rows = apply_filters(rows)
        if not rows:
            print("[yellow]No sessions match your filters.[/yellow]")
            return
        for r in rows:
            badge = f"{r.get('gui','')}|{r.get('access','')}" if r.get('gui') else r.get('profile','')
            print(f"• {r.get('nickname') or '(no name)'}  [dim]{r['name']}[/dim]  [cyan]{badge}[/cyan]")

if __name__ == "__main__":
    main()