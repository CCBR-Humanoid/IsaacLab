# Installing IsaacLab helper command

This repository includes a simple installer that:
- Optionally installs the Python package described by `pyproject.toml` (if it declares a build system)
- Installs a convenient `lab` command into `~/.local/bin` that runs the interactive Docker runner

## Prerequisites
- Linux with Bash
- Python 3 available as `python3` (or set `PYTHON=/path/to/python`)
- Docker and NVIDIA Container Toolkit installed (for GPU)

## Install steps

1) From the repository root, run:

```bash
./install.sh
```

You may have to first make it executable

```bash
chmod +x install.sh
```

2) If your shell doesn’t pick up the new command immediately, reload your PATH:

```bash
source ~/.bashrc
```

3) Use the command:

```bash
lab           # interactive prompts
lab list      # list sessions
lab start     # guided start
lab enter     # guided enter
lab stop      # guided stop
```

## Notes
- The `lab` wrapper always runs the `docker/runner.py` from this checkout.
- If you want to control which Python interpreter is used, set `PYTHON=/path/to/python` before running `lab` (or when running `install.sh`).
- The installer adds `~/.local/bin` to your PATH in `~/.bashrc` if it is not already present.
- If you prefer a system-wide install, we can add an option to place the wrapper in `/usr/local/bin` (requires sudo).
