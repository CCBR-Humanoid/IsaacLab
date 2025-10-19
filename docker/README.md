# Isaac Lab Docker Runner

A simple, friendly way to build, run, enter, and stop Isaac Lab containers with the interactive `runner.py`. This guide explains the available modes (headless, WebRTC, and X11), ROS2 support, and how to connect via the Isaac Lab WebRTC app locally or remotely (Tailscale).

## Prerequisites
- Docker and NVIDIA Container Toolkit installed and working (for GPU access)
- Linux host with an X server for X11 mode (optional)
- Tailscale account for remote WebRTC (optional)

## Quick start
- Run the interactive runner:
  - From VS Code: use the launch config “Python: Run docker/runner.py (debugpy)” or the task "run_docker_runner".
  - From terminal: `python3 docker/runner.py`
- Pick an action:
  - Start new session
  - Enter a session
  - Stop a session
  - List sessions

## Start options
When starting a new session, the runner guides you through a few choices:

- GUI Interface
  - WebRTC: Stream Isaac Lab’s UI to your browser (recommended)
  - X11 Forwarding: Use your local X server (Linux) for the Isaac Lab GUI
  - None: Headless

- ROS support
  - Yes: Use ROS 2 Humble inside the container
  - No: No ROS dependencies

- Force rebuild images
  - No (default): Use cached layers unless missing
  - Yes: Force a rebuild of the base image before starting

The runner will also:
- Generate a unique session ID and nickname
- Label the container so sessions are easy to list and pick later
- Create a per-session bash history file mounted into the container

## Profiles and overlays
Internally the runner maps your selections to compose profiles and overlays:

- Base (no GUI): `base`
- Base + WebRTC over LAN: `webrtc-local`
- Base + WebRTC over Tailscale (remote): `webrtc-remote` + Tailscale overlay
- ROS2 variants: `ros2`, `ros2-webrtc-local`, `ros2-webrtc-remote`
- X11: applies the X11 overlay on top of the base or ros2 profile

## WebRTC mode
WebRTC is the easiest way to view and interact with Isaac Lab’s UI in a browser.

- Local LAN (webrtc-local)
  - The container runs on your host network. Use your host’s LAN IP address.

- Remote (webrtc-remote)
  - Uses a Tailscale sidecar container to give the session a 100.x address.
  - The Isaac Lab container shares the Tailscale service’s network namespace.

### Connecting with the Isaac Lab WebRTC app
1. Start a session in WebRTC mode (local or remote).
2. Find the IP to use:
   - Local: your host’s LAN IP (e.g., 192.168.x.x)
   - Remote: the Tailscale 100.x IP of the `tailscale-<SESSION_ID>` container (visible in `docker logs tailscale-<SESSION_ID>` or `tailscale ip` within that container). The runner waits for health (100.x) before starting the app.
3. Open the Isaac Lab WebRTC web app and enter:
   - IP: the host (LAN or Tailscale 100.x) address
   - Ports: use the values from `.env.webrtc` if you changed them; otherwise keep defaults
4. You should see and control the Isaac Lab UI in your browser.

## Tailscale setup (for remote WebRTC)
Remote mode requires a Tailscale auth key configured via env file.

1. Copy the example file:
   - `cp docker/envs/.env.tailscale.example docker/envs/.env.tailscale`
2. Generate a Tailscale auth key from your Tailscale admin console.
   - It must be an ephemeral, pre-authorized key (type starts with `tskey-`).
   - Recommended: mint it as "ephemeral" and "preauthorized" so the compose can join without interaction.
3. Put the key into `.env.tailscale`:
   - `TS_AUTHKEY=tskey-...`  (no quotes)
   - If your key wasn’t minted with ephemeral=true, you can also append `?ephemeral=true` (see the comments in `docker/composers/docker-compose-tailscale.yaml`).
4. Start a remote WebRTC session via the runner.
   - The sidecar’s healthcheck waits until a 100.x address is assigned.

Security notes:
- Treat your TS_AUTHKEY like a secret. Do not commit `.env.tailscale` to version control.
- Keys can be scoped and time-limited; prefer ephemeral keys.

## X11 mode (Linux)
X11 forwards the container’s GUI to your host X server.

- Requirements
  - A running X server on your host
  - DISPLAY must be set in your shell (the runner warns if not)

- How it works
  - The runner prepares a temporary Xauthority cookie and mounts `/tmp/.X11-unix` and the cookie into the container.
  - The overlay sets `DISPLAY` and `XAUTHORITY=/tmp/.isaaclab-docker.xauth` in the container.

- Limitations
  - You must start a session with the X11 overlay to use X11. You can’t enter a non-X11 session and enable X11 later.

## Managing sessions
- Enter a session
  - Use the runner’s “Enter a session” and pick by nickname/name. Opens an interactive bash in the container.
  - For X11 sessions, the runner refreshes the Xauthority cookie and sets XAUTHORITY for you.

- Stop a session
  - The runner asks for confirmation before stopping.
  - It brings down the compose stack and removes any non-persistent per-session volumes (logs/docs/data).
  - Persistent caches (isaac-cache-* and isaaclab-terrain-cache) are preserved.

- List sessions
  - Shows running containers with nicknames and GUI/access badges.
  - Filter by GUI, access type, and nickname substring.

## Customization
- Change base image/version: edit `docker/envs/.env.base`.
- Port tweaks for WebRTC: edit `docker/envs/.env.webrtc`.
- ROS 2 package: edit `docker/envs/.env.ros2`.

## Troubleshooting
- WebRTC not reachable on LAN
  - Confirm host firewall rules and that you’re using the host’s LAN IP.
  - Check that ports in `.env.webrtc` are open and not conflicting.

- Remote (Tailscale) not reachable
  - Check the tailscale container logs: `docker logs tailscale-<SESSION_ID>`.
  - Verify TS_AUTHKEY is set and valid, and that a 100.x address appears.

- X11 errors (cannot open display)
  - Ensure DISPLAY is set on the host and that you started the session in X11 mode (not after starting).

## Where things live
- Compose files: `docker/composers/`
- Env files: `docker/envs/`
- Runner/orchestration code: `docker/runner.py`, `docker/src/`

Enjoy smooth container sessions with the runner! If you have ideas to streamline more workflows, we can add them.
