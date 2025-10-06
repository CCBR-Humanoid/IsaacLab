from remote_detection import is_remote_session
from ip_utils import tailscale_ips

from rich.prompt import Prompt, Confirm

import subprocess
import os

# TODO: Add support for CloudXR runtime

import json, subprocess

print(os.path.dirname(os.path.abspath(__file__)))

ros = Confirm.ask("Do you want ROS 2 Humble in your container?", default=False)

if is_remote_session():
    webrtc = Confirm.ask(
        "It looks like you are accessing this machine remotely. "
        "Would you like to enable WebRTC streaming for remote GUI access? "
        "(no = headless)",
        default=False
    )
    
    if webrtc:
        LIVESTREAM = 1
        ENABLE_CAMERAS = 1
        PUBLIC_IP = tailscale_ips()["ipv4"]
    
    print(webrtc)
else:
    gui = Confirm.ask(
        "Will you need a GUI for this session? (no = headless)",
        default=False
    )
    
    if gui:
        display_method = Prompt.ask(
            "It looks like you are accessing this machine locally. "
            "How would you like to access the GUI? "
            "(xserver = physical display, webrtc = streaming)",
            choices=["webrtc", "xserver"], default="xserver"
        )
    