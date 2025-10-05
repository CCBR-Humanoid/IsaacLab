from rich.prompt import Prompt

include_ros = Prompt.ask("Do you want ROS 2 in your container?", choices=["yes", "no"], default="no")
include_webrtc = Prompt.ask("Do you want WebRTC streaming in your container? (yes = remote GUI, no = headless)", choices=["yes", "no"], default="no")
include_gazebo = Prompt.ask("Do you want Gazebo in your container?", choices=["yes", "no"], default="no")
include_cloudxr_runtime = Prompt.ask(
    "Do you want CloudXR runtime in your container?", choices=["yes", "no"], default="no"
)

# TODO: Implement this