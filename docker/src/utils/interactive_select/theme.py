from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Styles:
    title: str = "bold cyan"
    help: str = "dim"
    pointer: str = "bold magenta"
    selected: str = "black on bright_cyan"
    option: str = "white"
    description: str = "dim"


@dataclass
class Theme:
    accent: str = "#00bcd4"
    background: str = "#1e1e1e"
    foreground: str = "#e5e5e5"
    muted: str = "#9aa0a6"
    warning: str = "#f39c12"
    info: str = "#3fa7ff"
    selected_bg: str = "#00bcd4"
    selected_fg: str = "#000000"
    button_bg: str = "#444444"
    button_fg: str = "#ffffff"
    button_focus_bg: str = "#00bcd4"
    button_focus_fg: str = "#000000"


# Curated presets
PRESET_THEMES = {
    "Default": Theme(),
    "Solarized Dark": Theme(
        accent="#268bd2",
        background="#002b36",
        foreground="#93a1a1",
        muted="#657b83",
        selected_bg="#2aa198",
        selected_fg="#002b36",
        button_bg="#073642",
        button_fg="#eee8d5",
        button_focus_bg="#268bd2",
        button_focus_fg="#002b36",
    ),
    "Dracula": Theme(
        accent="#8be9fd",
        background="#282a36",
        foreground="#f8f8f2",
        muted="#6272a4",
        selected_bg="#50fa7b",
        selected_fg="#000000",
        button_bg="#44475a",
        button_fg="#f8f8f2",
        button_focus_bg="#8be9fd",
        button_focus_fg="#000000",
    ),
    "Nord": Theme(
        accent="#88c0d0",
        background="#2e3440",
        foreground="#e5e9f0",
        muted="#81a1c1",
        selected_bg="#a3be8c",
        selected_fg="#2e3440",
        button_bg="#3b4252",
        button_fg="#e5e9f0",
        button_focus_bg="#88c0d0",
        button_focus_fg="#2e3440",
    ),
    "Gruvbox Dark": Theme(
        accent="#fabd2f",
        background="#282828",
        foreground="#ebdbb2",
        muted="#a89984",
        selected_bg="#b8bb26",
        selected_fg="#1d2021",
        button_bg="#3c3836",
        button_fg="#ebdbb2",
        button_focus_bg="#fabd2f",
        button_focus_fg="#1d2021",
    ),
    "One Light": Theme(
        accent="#4078f2",
        background="#fafafa",
        foreground="#383a42",
        muted="#9da0a7",
        selected_bg="#a8d1ff",
        selected_fg="#000000",
        button_bg="#eaeaea",
        button_fg="#000000",
        button_focus_bg="#7aa2ff",
        button_focus_fg="#000000",
    ),
}
