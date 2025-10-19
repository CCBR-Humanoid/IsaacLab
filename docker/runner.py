"""Interactive and CLI runner for starting, entering, and stopping Isaac Lab containers."""
import os
import sys
import argparse
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


def _detect_lan_ip() -> str | None:
    """Best-effort detection of the host's primary LAN IPv4 address.

    Tries a UDP 'connect' trick to learn the default route interface address,
    with safe fallbacks.
    """
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
        finally:
            s.close()
        if ip and not ip.startswith("127."):
            return ip
    except Exception:
        pass
    # Fallbacks
    try:
        import socket
        ip = socket.gethostbyname(socket.gethostname())
        if ip and not ip.startswith("127."):
            return ip
    except Exception:
        pass
    return None


def _tailscale_ip_for_session(session_id: str) -> str | None:
    """Return the Tailscale 100.x IPv4 for the sidecar of this session, if available."""
    import subprocess
    ts_name = f"tailscale-{session_id}"
    try:
        out = subprocess.check_output(
            ["docker", "exec", ts_name, "tailscale", "ip", "-4"], text=True
        ).strip()
        for line in out.splitlines():
            if line.strip().startswith("100."):
                return line.strip()
    except Exception:
        return None
    return None


def print_webrtc_instructions(ci: Container, row: dict):
    """Pretty-print how to connect to a WebRTC session via the Isaac Lab WebRTC app."""
    prof = (row.get("profile") or "")
    access = (row.get("access") or ("remote" if prof.endswith("-remote") else "local")).lower()
    session_id = row.get("session_id") or ci.environ.get("SESSION_ID") or ""

    # Ports from env files (with defaults)
    http_port = (getattr(ci, "dot_vars", {}) or {}).get("WEBRTC_HTTP_PORT", "8211")
    tcp_port = (getattr(ci, "dot_vars", {}) or {}).get("WEBRTC_TCP_PORT", "49100")
    udp_port = (getattr(ci, "dot_vars", {}) or {}).get("WEBRTC_UDP_PORT", "47998")

    # IP selection
    if access == "remote":
        ip = _tailscale_ip_for_session(session_id) or "100.x.x.x"
        ip_hint = "Tailscale 100.x address"
    else:
        ip = _detect_lan_ip() or "<your LAN IP>"
        ip_hint = "host LAN address"

    nick = row.get("nickname") or "(no name)"
    print("\n[bold cyan]How to connect to this WebRTC session[/bold cyan]")
    print(f"• Session: [bold]{nick}[/bold]  [dim]{row.get('name','')}[/dim]")
    print(f"• Mode: webrtc-{access}")
    print(f"• IP: [bold]{ip}[/bold]  ([dim]{ip_hint}[/dim])")
    print("  Then click Connect.")
    if access == "remote":
        print("  Note: The runner waits for the Tailscale sidecar to be healthy; if the IP shows as 100.x.x.x placeholder,")
        print("        run 'docker exec tailscale-<SESSION_ID> tailscale ip -4' to reveal the exact address.")
    print("")


def _check_port_listening_host(port: str, proto: str) -> bool:
    import subprocess
    try:
        if proto.lower() == "tcp":
            out = subprocess.check_output(["ss", "-lnt"], text=True)
        else:
            out = subprocess.check_output(["ss", "-lun"], text=True)
        return f":{port} " in out or f":{port}\n" in out
    except Exception:
        return False


def _check_port_listening_in_container(container: str, port: str, proto: str) -> bool:
    import subprocess
    try:
        if proto.lower() == "tcp":
            cmd = ["docker", "exec", container, "bash", "-lc", "ss -lnt | cat"]
        else:
            cmd = ["docker", "exec", container, "bash", "-lc", "ss -lun | cat"]
        out = subprocess.check_output(cmd, text=True)
        return f":{port} " in out or f":{port}\n" in out
    except Exception:
        return False


def diagnose_webrtc_local(ci: Container, row: dict):
    http_port = (getattr(ci, "dot_vars", {}) or {}).get("WEBRTC_HTTP_PORT", "8211")
    tcp_port = (getattr(ci, "dot_vars", {}) or {}).get("WEBRTC_TCP_PORT", "49100")
    udp_port = (getattr(ci, "dot_vars", {}) or {}).get("WEBRTC_UDP_PORT", "47998")
    name = row.get("name") or ci.container_name

    print("[dim]Quick WebRTC checks (local):[/dim]")
    ok_host_http = _check_port_listening_host(http_port, "tcp")
    ok_host_tcp = _check_port_listening_host(tcp_port, "tcp")
    ok_host_udp = _check_port_listening_host(udp_port, "udp")
    print(f"  Host listening HTTP {http_port}: {'[green]OK[/green]' if ok_host_http else '[red]NO[/red]'}")
    print(f"  Host listening TCP  {tcp_port}: {'[green]OK[/green]' if ok_host_tcp else '[red]NO[/red]'}")
    print(f"  Host listening UDP  {udp_port}: {'[green]OK[/green]' if ok_host_udp else '[red]NO[/red]'}")

    ok_ct_http = _check_port_listening_in_container(name, http_port, "tcp")
    ok_ct_tcp = _check_port_listening_in_container(name, tcp_port, "tcp")
    ok_ct_udp = _check_port_listening_in_container(name, udp_port, "udp")
    print(f"  Container listening HTTP {http_port}: {'[green]OK[/green]' if ok_ct_http else '[red]NO[/red]'}")
    print(f"  Container listening TCP  {tcp_port}: {'[green]OK[/green]' if ok_ct_tcp else '[red]NO[/red]'}")
    print(f"  Container listening UDP  {udp_port}: {'[green]OK[/green]' if ok_ct_udp else '[red]NO[/red]'}")

    if not (ok_host_http and ok_ct_http):
        print("[yellow]Hint:[/yellow] If HTTP is not listening, ensure LIVESTREAM is correctly set (local should be 2) and no other service uses the port.")
    if not (ok_host_tcp and ok_ct_tcp):
        print("[yellow]Hint:[/yellow] If TCP isn’t listening, check port conflicts and that Isaac Lab’s WebRTC extension enabled streaming.")
    if not (ok_host_udp and ok_ct_udp):
        print("[yellow]Hint:[/yellow] If UDP isn’t listening, verify firewall rules allow UDP on the chosen port.")

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
    remote = is_remote_session()
    x11_warn = None
    x11_info = None
    if not os.environ.get("DISPLAY"):
        x11_warn = "DISPLAY is not set; X11 may not work in this session."
    else:
        x11_info = f"Using DISPLAY={os.environ.get('DISPLAY')}"
    _, selected = select_option(
        "Select GUI Interface",
        option("WebRTC", "Use WebRTC streaming", value=GUIInterface.WEBRTC, recommended=remote,
               info="Local: uses LAN IP; Remote: uses Tailscale 100.x"),
        option("X11 Forwarding", "Use X11 display forwarding", value=GUIInterface.X11, warning=x11_warn, info=x11_info, recommended=not remote),
        option("None", "Headless", value=GUIInterface.NONE),
        default=GUIInterface.NONE,
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

def _dispatch_cli_or_interactive():
    parser = argparse.ArgumentParser(prog="lab", description="Isaac Lab Docker session manager")
    sub = parser.add_subparsers(dest="action")

    # list
    p_list = sub.add_parser("list", help="List running sessions")
    p_list.add_argument("--gui", choices=["all", "webrtc", "x11", "none"], default="all")
    p_list.add_argument("--access", choices=["all", "local", "remote"], default="all")
    p_list.add_argument("--nickname", default="", help="Filter by nickname substring (case-insensitive)")

    # start
    p_start = sub.add_parser("start", help="Start a new session")
    p_start.add_argument("--gui", choices=["webrtc", "x11", "none"], help="GUI mode")
    p_start.add_argument("--ros", action="store_true", help="Enable ROS2")
    p_start.add_argument("--no-ros", action="store_true", help="Disable ROS2 explicitly")
    p_start.add_argument("--remote", action="store_true", help="Treat session as remote (Tailscale)")
    p_start.add_argument("--rebuild", action="store_true", help="Force rebuild of base image")

    # enter
    p_enter = sub.add_parser("enter", help="Enter a running session")
    p_enter.add_argument("--name", help="Container name (e.g., isaac-lab-<SESSION_ID>)")
    p_enter.add_argument("--id", dest="session_id", help="Session ID to match")

    # stop
    p_stop = sub.add_parser("stop", help="Stop a running session")
    p_stop.add_argument("--name", help="Container name (e.g., isaac-lab-<SESSION_ID>)")
    p_stop.add_argument("--id", dest="session_id", help="Session ID to match")
    p_stop.add_argument("-y", "--yes", action="store_true", help="Do not prompt for confirmation")

    # Filter out any accidental empty-string args from shells/wrappers
    argv = [a for a in sys.argv[1:] if str(a).strip() != ""]
    if not argv:
        # No CLI args -> interactive menu
        args = argparse.Namespace(action=None)
        action = ask_action()
    else:
        args = parser.parse_args(argv)
        action = args.action or ask_action()

    # Create interface bound to repo root (runner.py is under <repo>/docker)
    root = Path(__file__).resolve().parent.parent
    ci = Container(context_dir=root)

    if action == "start":
        # GUI
        if hasattr(args, "gui") and args.gui:
            gui = GUIInterface.WEBRTC if args.gui == "webrtc" else (GUIInterface.X11 if args.gui == "x11" else GUIInterface.NONE)
        else:
            gui = ask_gui_mode()
        # ROS
        ros = None
        if getattr(args, "ros", False) and not getattr(args, "no_ros", False):
            ros = True
        elif getattr(args, "no_ros", False):
            ros = False
        if ros is None:
            ros = ask_ros_support()
        # remote
        remote = getattr(args, "remote", False) or is_remote_session()
        # rebuild
        force_rebuild = getattr(args, "rebuild", False) or ask_rebuild()

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
        # If starting a WebRTC session, show connection instructions right away
        if gui == GUIInterface.WEBRTC:
            row = {
                "profile": profile,
                "access": ("remote" if remote else "local"),
                "session_id": session_id,
                "nickname": nickname,
                "name": f"isaac-lab-{session_id}",
                "gui": "webrtc",
            }
            print_webrtc_instructions(ci, row)
            if not remote:
                diagnose_webrtc_local(ci, row)

    elif action == "enter":
        # Try to pick by CLI args if provided, else interactive chooser
        row = None
        name = getattr(args, "name", None)
        sid_query = getattr(args, "session_id", None)
        if name or sid_query:
            rows = ci.list_running_sessions()
            for r in rows:
                if name and r.get("name") == name:
                    row = r
                    break
                if sid_query and r.get("session_id") == sid_query:
                    row = r
                    break
        if not row:
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
        if row.get("gui") is not None:
            ci.environ["SESSION_GUI"] = str(row.get("gui") or "")
        if row.get("access") is not None:
            ci.environ["SESSION_ACCESS"] = str(row.get("access") or "")
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
        # If this is a WebRTC session, print connection instructions before entering
        is_webrtc = (row.get("gui") or "").lower() == "webrtc" or ("webrtc" in (row.get("profile") or ""))
        if is_webrtc:
            print_webrtc_instructions(ci, row)
            if (row.get("access") or "local").lower() == "local":
                diagnose_webrtc_local(ci, row)
        ci.enter()

    elif action == "stop":
        # Try to pick by CLI args if provided, else interactive chooser
        row = None
        name = getattr(args, "name", None)
        sid_query = getattr(args, "session_id", None)
        if name or sid_query:
            rows = ci.list_running_sessions()
            for r in rows:
                if name and r.get("name") == name:
                    row = r
                    break
                if sid_query and r.get("session_id") == sid_query:
                    row = r
                    break
        if not row:
            row = choose_running_session(ci)
        if not row:
            return
        # Confirm with the user before stopping the selected session
        skip_confirm = getattr(args, "yes", False)
        if not skip_confirm:
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
                    print("[yellow]Cancelled.[/yellow]\n")
                    return
            except Exception:
                # If interactive UI is not available, proceed
                pass
        if row.get("profile"):
            ci.profile = row["profile"]
        if row.get("session_id"):
            ci.project_name = row["session_id"]
            ci.environ["COMPOSE_PROJECT_NAME"] = row["session_id"]
            ci.environ["SESSION_ID"] = row["session_id"]
        if row.get("nickname") is not None:
            ci.environ["SESSION_NICKNAME"] = row.get("nickname") or ""
        # Propagate GUI/access labels so X11 cleanup triggers correctly
        if row.get("gui") is not None:
            ci.environ["SESSION_GUI"] = str(row.get("gui") or "")
        if row.get("access") is not None:
            ci.environ["SESSION_ACCESS"] = str(row.get("access") or "")
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
        # If CLI filters were provided, apply them non-interactively; else print all
        if hasattr(args, "gui") and hasattr(args, "access") and hasattr(args, "nickname"):
            gui = args.gui
            access = args.access
            nickname_sub = (args.nickname or "").lower()
            def match(row):
                if gui != "all" and (row.get("gui") or "").lower() != gui:
                    return False
                if access != "all" and (row.get("access") or "").lower() != access:
                    return False
                if nickname_sub and nickname_sub not in (row.get("nickname") or "").lower():
                    return False
                return True
            rows = [r for r in rows if match(r)]
        if not rows:
            print("[yellow]No sessions match your filters.[/yellow]")
            return
        for r in rows:
            badge = f"{r.get('gui','')}|{r.get('access','')}" if r.get('gui') else r.get('profile','')
            print(f"• {r.get('nickname') or '(no name)'}  [dim]{r['name']}[/dim]  [cyan]{badge}[/cyan]")

if __name__ == "__main__":
    _dispatch_cli_or_interactive()