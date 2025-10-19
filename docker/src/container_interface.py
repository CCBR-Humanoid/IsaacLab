# Copyright (c) 2022-2025, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .gui.state_file import StateFile
from .gui.x11 import x11_check, x11_refresh, x11_cleanup


class ContainerInterface:
    """A helper class for managing Isaac Lab containers."""

    def __init__(
        self,
        context_dir: Path,
        profile: str = "base",
        yamls: list[str] | None = None,
        envs: list[str] | None = None,
        statefile: StateFile | None = None,
        suffix: str | None = None,
        project_name: str | None = None,
    ):
        """Initialize the container interface with the given parameters.

        Args:
            context_dir: The context directory for Docker operations.
            profile: The profile name for the container. Defaults to "base".
            yamls: A list of yaml files to extend ``docker-compose.yaml`` settings. These are extended in the order
                they are provided.
            envs: A list of environment variable files to extend the ``.env.base`` file. These are extended in the order
                they are provided.
            statefile: An instance of the :class:`Statefile` class to manage state variables. Defaults to None, in
                which case a new configuration object is created by reading the configuration file at the path
                ``context_dir/.container.cfg``.
            suffix: Optional docker image and container name suffix.  Defaults to None, in which case, the docker name
                suffix is set to the empty string. A hyphen is inserted in between the profile and the suffix if
                the suffix is a nonempty string.  For example, if "base" is passed to profile, and "custom" is
                passed to suffix, then the produced docker image and container will be named ``isaac-lab-base-custom``.
        """
        # set the context directory
        self.context_dir = context_dir
        self.project_name = "" if project_name is None else project_name

        # create a state-file if not provided
        # the state file is a manager of run-time state variables that are saved to a file
        if statefile is None:
            self.statefile = StateFile(path=self.context_dir / ".container.cfg")
        else:
            self.statefile = statefile

        # set the profile and container name
        self.profile = profile
        if self.profile == "isaaclab":
            # Silently correct from isaaclab to base, because isaaclab is a commonly passed arg
            # but not a real profile
            self.profile = "base"

        # set the docker image and container name suffix
        if suffix is None or suffix == "":
            # if no name suffix is given, default to the empty string as the name suffix
            self.suffix = ""
        else:
            # insert a hyphen before the suffix if a suffix is given
            self.suffix = f"-{suffix}"

        self.container_name = f"isaac-lab-{self.profile}{self.suffix}"
        self.image_name = f"isaac-lab-{self.profile}{self.suffix}:latest"

        # keep the environment variables from the current environment,
        # except make sure that the docker name suffix is set from the script
        self.environ = os.environ.copy()
        self.environ["DOCKER_NAME_SUFFIX"] = self.suffix
        self.environ["COMPOSE_PROJECT_NAME"] = self.project_name

        # resolve the image extension through the passed yamls and envs
        self._resolve_image_extension(yamls, envs)
        # load the environment variables from the .env files
        self._parse_dot_vars()

    """
    Operations.
    """

    def is_container_running(self) -> bool:
        """Check if the container is running.

        Returns:
            True if the container is running, otherwise False.
        """
        status = subprocess.run(
            ["docker", "container", "inspect", "-f", "{{.State.Status}}", self.container_name],
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip()
        return status == "running"

    def does_image_exist(self) -> bool:
        """Check if the Docker image exists.

        Returns:
            True if the image exists, otherwise False.
        """
        result = subprocess.run(["docker", "image", "inspect", self.image_name], capture_output=True, text=True)
        return result.returncode == 0

    def list_running_sessions(self) -> list[dict[str, str]]:
        """List running isaac-lab containers with our CRT labels.

        Returns: list of dicts with keys: id, name, session_id, nickname, profile, gui, access
        """
        try:
            fmt = (
                "{{.ID}}\t{{.Names}}\t{{.Label \"com.crt.session_id\"}}\t"
                "{{.Label \"com.crt.nickname\"}}\t{{.Label \"com.crt.profile\"}}\t"
                "{{.Label \"com.crt.gui\"}}\t{{.Label \"com.crt.access\"}}"
            )
            out = subprocess.check_output(
                ["docker", "ps", "--filter", "name=^/isaac-lab-", "--format", fmt], text=True
            ).strip()
            rows = []
            for line in out.splitlines():
                parts = line.split("\t")
                if len(parts) >= 7:
                    _, name, session_id, nickname, profile, gui, access = parts[:7]
                elif len(parts) >= 5:
                    # Backward compatibility when labels for gui/access are missing
                    _, name, session_id, nickname, profile = parts[:5]
                    gui = "webrtc" if ("webrtc" in (profile or "")) else "none"
                    access = (
                        "remote" if (profile or "").endswith("-remote") else ("local" if ("webrtc" in (profile or "")) else "unknown")
                    )
                else:
                    continue

                rows.append(
                    {
                        "id": parts[0],
                        "name": name,
                        "session_id": session_id,
                        "nickname": nickname,
                        "profile": profile,
                        "gui": gui or ("webrtc" if ("webrtc" in (profile or "")) else "none"),
                        "access": access or (
                            "remote" if (profile or "").endswith("-remote") else ("local" if ("webrtc" in (profile or "")) else "unknown")
                        ),
                    }
                )
            return rows
        except Exception:
            return []

    def start(self):
        """Build and start the Docker container using the Docker compose command."""
        print(
            f"[INFO] Building the docker image and starting the container '{self.container_name}' in the background...\n"
        )
        # Ensure per-session bash history file exists
        sid = self.environ.get("SESSION_ID") or self.project_name or ""
        hist_dir = self.context_dir / ".isaac-lab" / "history"
        hist_dir.mkdir(parents=True, exist_ok=True)
        hist_name = f"bash_history-{sid}" if sid else "bash_history"
        container_history_file = hist_dir / hist_name
        if not container_history_file.exists():
            # Create the file with sticky bit on the group
            container_history_file.touch(mode=0o2644, exist_ok=True)

        # Optionally pre-build base image: skip by default for faster startup; will build-on-demand during up
        if self.environ.get("FORCE_REBUILD_BASE") == "1":
            subprocess.run(
                [
                    "docker",
                    "compose",
                    "--file",
                    str(self.context_dir / "docker" / "composers" / "docker-compose.yaml"),
                    "--env-file",
                    str(self.context_dir / "docker" / "envs" / ".env.base"),
                    "build",
                    "isaac-lab-base",
                ],
                check=False,
                cwd=self.context_dir,
                env=self.environ,
            )

        # Optionally enable X11 overlay only if requested
        add_args = list(self.add_yamls)
        local_env = self.environ.copy()
        # Ensure compose has interpolation variables even if --env-file is ignored by some paths
        if hasattr(self, "dot_vars") and isinstance(self.dot_vars, dict):
            local_env.update({k: str(v) for k, v in self.dot_vars.items()})
        if local_env.get("SESSION_GUI") == "x11":
            # Use a per-session namespace for X11 to avoid file reuse across sessions
            self.statefile.namespace = f"X11-{local_env.get('SESSION_ID','default')}"
            try:
                x11_yaml_args, x11_envars = x11_check(self.statefile) or (None, None)
            except Exception:
                x11_yaml_args, x11_envars = (None, None)
            if x11_envars:
                # Adjust mount path variable name for this session and add overlay
                add_args += ["--file", str(self.context_dir / "docker" / "composers" / "docker-compose-x11.yaml")]
                local_env.update(x11_envars)

        # If using remote WebRTC, include tailscale composer overlay
        if self.profile in ("webrtc-remote", "ros2-webrtc-remote"):
            add_args += ["--file", str(self.context_dir / "docker" / "composers" / "docker-compose-tailscale.yaml")]

        # build the image for the profile
        # Compose up (no explicit --build, it will build missing images but reuse cache)
        subprocess.run(
            ["docker", "compose"]
            + add_args
            + self.add_profiles
            + self.add_env_files
            + ["up", "--detach", "--remove-orphans"],
            check=False,
            cwd=self.context_dir,
            env=local_env,
        )

    def enter(self):
        """Enter the running container by executing a bash shell.

        Raises:
            RuntimeError: If the container is not running.
        """
        if self.is_container_running():
            print(f"[INFO] Entering the existing '{self.container_name}' container in a bash session...\n")
            # refresh X11 cookie if this session was launched with X11
            if self.environ.get("SESSION_GUI") == "x11":
                self.statefile.namespace = f"X11-{self.environ.get('SESSION_ID','default')}"
                try:
                    x11_refresh(self.statefile)
                except Exception:
                    pass
            subprocess.run([
                "docker",
                "exec",
                "--interactive",
                "--tty",
                *(["-e", f"DISPLAY={os.environ['DISPLAY']}"] if "DISPLAY" in os.environ else []),
                f"{self.container_name}",
                "bash",
            ])
        else:
            raise RuntimeError(f"The container '{self.container_name}' is not running.")

    def stop(self):
        """Stop the running container using the Docker compose command.

        Raises:
            RuntimeError: If the container is not running.
        """
        if self.is_container_running():
            print(f"[INFO] Stopping the launched docker container '{self.container_name}'...\n")
            # Build compose args similar to start (for overlays), but do not filter by profile on down
            add_args = list(self.add_yamls)
            # Include tailscale overlay if this session used remote WebRTC
            prof = (self.profile or "")
            if prof.endswith("-remote"):
                add_args += ["--file", str(self.context_dir / "docker" / "composers" / "docker-compose-tailscale.yaml")]
            local_env = self.environ.copy()
            if hasattr(self, "dot_vars") and isinstance(self.dot_vars, dict):
                local_env.update({k: str(v) for k, v in self.dot_vars.items()})
            subprocess.run(
                ["docker", "compose"] + add_args + self.add_env_files + ["down", "--volumes", "--remove-orphans"],
                check=False,
                cwd=self.context_dir,
                env=local_env,
            )
            # Fallback: if container still running, force remove it (and tailscale sidecar)
            if self.is_container_running():
                subprocess.run(["docker", "rm", "-f", self.container_name], check=False)
            # Attempt stopping tailscale sidecar for this session (ignore if already removed)
            sid = self.environ.get("SESSION_ID") or self.project_name or ""
            if sid:
                # Check if tailscale container exists before removing
                ts_name = f"tailscale-{sid}"
                result = subprocess.run(["docker", "ps", "-a", "--filter", f"name=^{ts_name}$", "--format", "{{.Names}}"], capture_output=True, text=True, check=False)
                if ts_name in (result.stdout or ""):
                    subprocess.run(["docker", "rm", "-f", ts_name], check=False)
            # Clean X11 artifacts if this session used X11
            if self.environ.get("SESSION_GUI") == "x11":
                self.statefile.namespace = f"X11-{self.environ.get('SESSION_ID','default')}"
                try:
                    x11_cleanup(self.statefile)
                except Exception:
                    pass
        else:
            raise RuntimeError(f"Can't stop container '{self.container_name}' as it is not running.")

    def copy(self, output_dir: Path | None = None):
        """Copy artifacts from the running container to the host machine.

        Args:
            output_dir: The directory to copy the artifacts to. Defaults to None, in which case
                the context directory is used.

        Raises:
            RuntimeError: If the container is not running.
        """
        if self.is_container_running():
            print(f"[INFO] Copying artifacts from the '{self.container_name}' container...\n")
            if output_dir is None:
                output_dir = self.context_dir

            # create a directory to store the artifacts
            output_dir = output_dir.joinpath("artifacts")
            if not output_dir.is_dir():
                output_dir.mkdir()

            # define dictionary of mapping from docker container path to host machine path
            docker_isaac_lab_path = Path(self.dot_vars["DOCKER_ISAACLAB_PATH"])
            artifacts = {
                docker_isaac_lab_path.joinpath("logs"): output_dir.joinpath("logs"),
                docker_isaac_lab_path.joinpath("docs/_build"): output_dir.joinpath("docs"),
                docker_isaac_lab_path.joinpath("data_storage"): output_dir.joinpath("data_storage"),
            }
            # print the artifacts to be copied
            for container_path, host_path in artifacts.items():
                print(f"\t -{container_path} -> {host_path}")
            # remove the existing artifacts
            for path in artifacts.values():
                shutil.rmtree(path, ignore_errors=True)

            # copy the artifacts
            for container_path, host_path in artifacts.items():
                subprocess.run(
                    [
                        "docker",
                        "cp",
                        f"isaac-lab-{self.profile}{self.suffix}:{container_path}/",
                        f"{host_path}",
                    ],
                    check=False,
                )
            print("\n[INFO] Finished copying the artifacts from the container.")
        else:
            raise RuntimeError(f"The container '{self.container_name}' is not running.")

    def config(self, output_yaml: Path | None = None):
        """Process the Docker compose configuration based on the passed yamls and environment files.

        If the :attr:`output_yaml` is not None, the configuration is written to the file. Otherwise, it is printed to
        the terminal.

        Args:
            output_yaml: The path to the yaml file where the configuration is written to. Defaults
                to None, in which case the configuration is printed to the terminal.
        """
        print("[INFO] Configuring the passed options into a yaml...\n")

        # resolve the output argument
        if output_yaml is not None:
            output = ["--output", output_yaml]
        else:
            output = []

        # run the docker compose config command to generate the configuration
        subprocess.run(
            ["docker", "compose"] + self.add_yamls + self.add_profiles + self.add_env_files + ["config"] + output,
            check=False,
            cwd=self.context_dir,
            env=self.environ,
        )

    """
    Helper functions.
    """

    def configure(self, yamls: list[str] | None = None, envs: list[str] | None = None):
        """Public wrapper to set compose YAML overlays and env files, then re-parse vars.

        Args:
            yamls: Additional docker-compose YAML files to include (order matters).
            envs: Environment files to layer (order matters).
        """
        self._resolve_image_extension(yamls, envs)
        self._parse_dot_vars()

    def _resolve_image_extension(self, yamls: list[str] | None = None, envs: list[str] | None = None):
        """
        Resolve the image extension by setting up YAML files, profiles, and environment files for the Docker compose command.

        Args:
            yamls: A list of yaml files to extend ``docker-compose.yaml`` settings. These are extended in the order
                they are provided.
            envs: A list of environment variable files to extend the ``.env.base`` file. These are extended in the order
                they are provided.
        """
        self.add_yamls = ["--file", str(self.context_dir / "docker" / "composers" / "docker-compose.yaml")]
        self.add_profiles = ["--profile", f"{self.profile}"]
        self.add_env_files = []

        # extend the env file based on the passed envs
        if envs is not None:
            for env in envs:
                self.add_env_files += ["--env-file", env]

        # extend the docker-compose.yaml based on the passed yamls
        if yamls:
            for yaml in yamls:
                self.add_yamls += ["--file", yaml]

    def _parse_dot_vars(self):
        """Parse the environment variables from the .env files.

        Based on the passed ".env" files, this function reads the environment variables and stores them in a dictionary.
        The environment variables are read in order and overwritten if there are name conflicts, mimicking the behavior
        of Docker compose.
        """
        self.dot_vars: dict[str, Any] = {}

        # check if the number of arguments is even for the env files
        if len(self.add_env_files) % 2 != 0:
            raise RuntimeError(
                "The parameters for env files are configured incorrectly. There should be an even number of arguments."
                f" Received: {self.add_env_files}."
            )

        def _normalize_value(val: str) -> str:
            v = val.strip()
            # Strip matching quotes (single or double)
            if (len(v) >= 2) and ((v[0] == v[-1]) and v[0] in ('"', "'")):
                v = v[1:-1]
            return v

        # read the environment variables from the .env files
        for i in range(1, len(self.add_env_files), 2):
            env_path = self.context_dir / self.add_env_files[i]
            with open(env_path, "r", encoding="utf-8") as f:
                for raw in f:
                    line = raw.strip()
                    if not line or line.startswith("#"):
                        continue
                    if line.lower().startswith("export "):
                        line = line[7:].lstrip()
                    if "=" not in line:
                        continue
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = _normalize_value(val)
                    self.dot_vars[key] = val
