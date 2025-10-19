from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Tuple, Union, Mapping, Any

from rich.console import Console, Group
from rich.panel import Panel
from rich.text import Text
from rich import box
from rich.align import Align
from rich.rule import Rule
import textwrap

from .theme import Theme, Styles

console = Console()


def _is_tty() -> bool:
    try:
        return sys.stdin.isatty() and sys.stdout.isatty()
    except Exception:
        return False


def _iter_keypresses() -> Iterable[str]:
    if os.name == "nt":
        import msvcrt

        while True:
            ch = msvcrt.getwch()
            if ch in ("\r", "\n"):
                yield "enter"
            elif ch == "\x1b":
                yield "escape"
            elif ch in ("q", "Q"):
                yield "q"
            elif ch in ("k", "K"):
                yield "up"
            elif ch in ("j", "J"):
                yield "down"
            elif ch.isdigit():
                yield ch
            elif ch == "\xe0":
                nxt = msvcrt.getwch()
                if nxt == "H":
                    yield "up"
                elif nxt == "P":
                    yield "down"
    else:
        import termios
        import tty

        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setcbreak(fd)
            while True:
                ch = sys.stdin.read(1)
                if ch == "\n":
                    yield "enter"
                elif ch == "\x1b":
                    seq1 = sys.stdin.read(1)
                    if seq1 == "[":
                        seq2 = sys.stdin.read(1)
                        if seq2 == "A":
                            yield "up"
                        elif seq2 == "B":
                            yield "down"
                    else:
                        yield "escape"
                elif ch in ("q", "Q"):
                    yield "q"
                elif ch in ("k", "K"):
                    yield "up"
                elif ch in ("j", "J"):
                    yield "down"
                elif ch.isdigit():
                    yield ch
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


@dataclass
class Option:
    label: str
    description: str = ""
    value: Any = None
    recommended: bool = False
    warning: Optional[str] = None
    info: Optional[str] = None


def option(label: str, description: str = "", value: Any = None, recommended: bool = False, warning: Optional[str] = None, info: Optional[str] = None) -> Option:
    return Option(label=label, description=description, value=value, recommended=recommended, warning=warning, info=info)


def _normalize_options(options_args: Tuple[Any, ...]) -> List[Option]:
    # Allow passing a single sequence of options instead of varargs
    if len(options_args) == 1 and isinstance(options_args[0], (list, tuple)) and not isinstance(options_args[0], Option):
        options_seq = options_args[0]
    else:
        options_seq = options_args

    normalized: List[Option] = []
    for item in options_seq:
        if isinstance(item, Option):
            normalized.append(item)
        elif isinstance(item, tuple):
            if len(item) == 6:
                normalized.append(Option(str(item[0]), item[1], str(item[2]) if item[2] is not None else "", bool(item[3]), str(item[4]) if item[4] is not None else None, str(item[5]) if item[5] is not None else None))
            elif len(item) == 5:
                normalized.append(Option(str(item[0]), item[1], str(item[2]) if item[2] is not None else "", bool(item[3]), str(item[4]) if item[4] is not None else None))
            elif len(item) == 4:
                normalized.append(Option(str(item[0]), item[1], str(item[2]) if item[2] is not None else "", bool(item[3]), None))
            elif len(item) == 3:
                normalized.append(Option(str(item[0]), item[1], str(item[2]) if item[2] is not None else ""))
            elif len(item) == 2:
                normalized.append(Option(str(item[0]), item[1], ""))
            elif len(item) == 1:
                normalized.append(Option(str(item[0]), item[0], ""))
            else:
                raise ValueError("Option tuple must have 1, 2, 3, 4, 5, or 6 elements")
        elif isinstance(item, Mapping):
            # Map label->value
            for k, v in item.items():
                normalized.append(Option(str(k), v, ""))
        else:
            normalized.append(Option(str(item), item, ""))
    if not normalized:
        raise ValueError("select_option requires at least one option")
    # Fill missing values with label
    for n in normalized:
        if n.value is None:
            n.value = n.label
        if n.description is None:
            n.description = ""
    return normalized


class InteractiveSelector:
    def __init__(
        self,
        title: Optional[str],
        options: List[Option],
        default_index: int = 0,
        default: Optional[Any] = None,
        styles: Optional[Styles] = None,
        theme: Optional[Theme] = None,
        pointer: str = "❯",
        show_help: bool = True,
    ) -> None:
        self.title = title
        self.labels: List[str] = [o.label for o in options]
        self.values: List[Any] = [o.value for o in options]
        self.descriptions: List[str] = [o.description for o in options]
        self.recommendeds: List[bool] = [bool(o.recommended) for o in options]
        self.warnings: List[Optional[str]] = [o.warning for o in options]
        self.infos: List[Optional[str]] = [o.info for o in options]

        # Determine initial index
        idx = max(0, min(default_index, len(self.labels) - 1))
        if default is not None and self.labels:
            # Match by label first
            target_label = str(default)
            for i, lab in enumerate(self.labels):
                if lab == target_label:
                    idx = i
                    break
            else:
                tl = target_label.lower()
                found = False
                for i, lab in enumerate(self.labels):
                    if lab.lower() == tl:
                        idx = i
                        found = True
                        break
                if not found:
                    # Match by underlying value
                    for i, val in enumerate(self.values):
                        try:
                            if val == default:
                                idx = i
                                found = True
                                break
                        except Exception:
                            pass
        self.index = idx
        self.theme = theme or Theme()
        self.styles = styles or Styles(
            title=f"bold {self.theme.accent}",
            help=f"{self.theme.muted}",
            pointer=f"bold {self.theme.accent}",
            selected=f"{self.theme.selected_fg} on {self.theme.selected_bg}",
            option=f"{self.theme.foreground}",
            description=f"{self.theme.muted}",
        )
        self.pointer = pointer
        self.show_help = show_help

        # Ensure descriptions list aligned
        if len(self.descriptions) != len(self.labels):
            if len(self.descriptions) > len(self.labels):
                self.descriptions = self.descriptions[: len(self.labels)]
            else:
                self.descriptions = self.descriptions + [""] * (len(self.labels) - len(self.descriptions))
        # Ensure warnings list aligned
        if len(self.warnings) != len(self.labels):
            if len(self.warnings) > len(self.labels):
                self.warnings = self.warnings[: len(self.labels)]
            else:
                self.warnings = self.warnings + [None] * (len(self.labels) - len(self.warnings))
        # Ensure infos list aligned
        if len(self.infos) != len(self.labels):
            if len(self.infos) > len(self.labels):
                self.infos = self.infos[: len(self.labels)]
            else:
                self.infos = self.infos + [None] * (len(self.labels) - len(self.infos))

    def _render(self) -> Panel:
        lines: List[Text] = []
        for i, opt in enumerate(self.labels):
            selected = i == self.index
            pointer = f" {self.pointer} " if selected else "   "

            # Left number column with a trailing position reserved for the recommend marker
            num_digits = Text(f"{i+1:>2}", style=self.styles.help)
            if i < len(self.recommendeds) and self.recommendeds[i]:
                # Replace the trailing space with a subtle symbol to avoid shifting alignment
                rec_sym = Text("✦", style=f"{self.theme.accent} italic")
            else:
                rec_sym = Text(" ", style=self.styles.help)
            num_hint = Text.assemble(num_digits, rec_sym)
            pointer_text = Text(pointer, style=self.styles.pointer if selected else self.styles.help)
            opt_text = Text(opt, style=self.styles.selected if selected else self.styles.option)

            row = Text.assemble(num_hint, pointer_text, opt_text)
            lines.append(row)

            if self.descriptions or self.warnings:
                # Compute indent so description/warning starts further right than label start
                # num (2) + rec_sym (1) + pointer (3) = 6; add +2 padding for sub-lines
                indent_len = 6 + 2
                indent = " " * indent_len

                desc = self.descriptions[i]
                if desc:
                    # Wrap description to panel width minus indent
                    try:
                        term_width = console.size.width
                    except Exception:
                        term_width = 80
                    # Panel padding ~ 2 per side; use computed indent
                    max_width = max(20, term_width - 8)
                    wrapped = textwrap.fill(desc, width=max_width, subsequent_indent=indent, initial_indent=indent)
                    for line in wrapped.splitlines():
                        lines.append(Text(line, style=self.styles.description))

                warn = None
                if self.warnings and 0 <= i < len(self.warnings):
                    warn = self.warnings[i]
                if warn:
                    try:
                        term_width = console.size.width
                    except Exception:
                        term_width = 80
                    max_width = max(20, term_width - 8)
                    warn_initial = indent + "⚠ "
                    warn_subseq = indent + "  "
                    wrapped_w = textwrap.fill(str(warn), width=max_width, subsequent_indent=warn_subseq, initial_indent=warn_initial)
                    for line in wrapped_w.splitlines():
                        lines.append(Text(line, style=f"bold {self.theme.warning}"))

                info = None
                if self.infos and 0 <= i < len(self.infos):
                    info = self.infos[i]
                if info:
                    try:
                        term_width = console.size.width
                    except Exception:
                        term_width = 80
                    max_width = max(20, term_width - 8)
                    info_initial = indent + "ℹ "
                    info_subseq = indent + "  "
                    wrapped_i = textwrap.fill(str(info), width=max_width, subsequent_indent=info_subseq, initial_indent=info_initial)
                    for line in wrapped_i.splitlines():
                        lines.append(Text(line, style=f"{self.theme.info}"))

        content = Group(*lines)
        title_text = Text(self.title, style=self.styles.title) if self.title else None
        help_text = Text(
            "Use ↑/↓ or j/k • 1-9 to jump • Enter to select • q/Esc to cancel",
            style=self.styles.help,
        ) if self.show_help else None

        body_sections = []
        if title_text:
            body_sections.append(title_text)
        body_sections.append(content)
        if help_text:
            body_sections.append(Rule(style=self.styles.help))
            body_sections.append(Align.center(help_text))

        body = Group(*body_sections)

        return Panel(
            body,
            box=box.HEAVY,
            border_style=self.styles.title,
            padding=(1, 2),
        )

    def run(self) -> Optional[Tuple[int, Any]]:
        if not _is_tty():
            return self._fallback_prompt()

        # Prefer prompt_toolkit for mouse support
        try:
            sel_idx = _select_with_prompt_toolkit(
                labels=self.labels,
                title=self.title,
                descriptions=self.descriptions,
                default_index=self.index,
                theme=self.theme,
                recommended=self.recommendeds,
                warnings=self.warnings,
                infos=self.infos,
            )
            if sel_idx is not None:
                self.index = sel_idx
                return self.index, self.values[self.index]
            return None
        except Exception:
            pass

        from rich.live import Live
        with Live(self._render(), console=console, refresh_per_second=30, transient=True) as live:
            for key in _iter_keypresses():
                if key in ("q", "escape"):
                    return None
                if key == "up":
                    self.index = (self.index - 1) % len(self.labels)
                elif key == "down":
                    self.index = (self.index + 1) % len(self.labels)
                elif key == "enter":
                    return self.index, self.values[self.index]
                elif key.isdigit():
                    n = int(key)
                    if 1 <= n <= len(self.labels):
                        self.index = n - 1
                        return self.index, self.values[self.index]
                live.update(self._render())

        return None

    def _fallback_prompt(self) -> Optional[Tuple[int, Any]]:
        if self.title:
            console.print(Text(self.title, style=self.styles.title))
        if self.show_help:
            console.print(Text("Type a number and press Enter • Ctrl+C to cancel", style=self.styles.help))

        for i, opt in enumerate(self.labels):
            # Compose number with either '.' or a subtle recommendation symbol, keeping width the same
            num_digits = Text(f"{i+1:>2}", style=self.styles.help)
            dot_or_sym = Text("✦" if (i < len(self.recommendeds) and self.recommendeds[i]) else ".", style=(f"{self.theme.accent} italic" if (i < len(self.recommendeds) and self.recommendeds[i]) else self.styles.help))
            spacer = Text(" ", style=self.styles.help)
            line = Text.assemble(num_digits, dot_or_sym, spacer, Text(opt, style=self.styles.option))
            console.print(line)
            # indent_len: 2 (digits) + 1 (symbol) + 1 (space) + 2 extra = 6
            base_indent = " " * 6
            if self.descriptions and self.descriptions[i]:
                # Wrap description similarly to rich panel widths (approximate)
                try:
                    term_width = console.size.width
                except Exception:
                    term_width = 80
                max_width = max(20, term_width - 2)
                wrapped = textwrap.fill(self.descriptions[i], width=max_width, initial_indent=base_indent, subsequent_indent=base_indent)
                for ln in wrapped.splitlines():
                    console.print(Text(ln, style=self.styles.description))
            if self.warnings and self.warnings[i]:
                try:
                    term_width = console.size.width
                except Exception:
                    term_width = 80
                max_width = max(20, term_width - 2)
                warn_initial = base_indent + "⚠ "
                warn_subseq = base_indent + "  "
                wrapped_w = textwrap.fill(str(self.warnings[i]), width=max_width, initial_indent=warn_initial, subsequent_indent=warn_subseq)
                for ln in wrapped_w.splitlines():
                    console.print(Text(ln, style=f"bold {self.theme.warning}"))
            if self.infos and self.infos[i]:
                try:
                    term_width = console.size.width
                except Exception:
                    term_width = 80
                max_width = max(20, term_width - 2)
                info_initial = base_indent + "ℹ "
                info_subseq = base_indent + "  "
                wrapped_i = textwrap.fill(str(self.infos[i]), width=max_width, initial_indent=info_initial, subsequent_indent=info_subseq)
                for ln in wrapped_i.splitlines():
                    console.print(Text(ln, style=f"{self.theme.info}"))

        while True:
            try:
                resp = console.input("Select [bold]number[/bold]: ")
            except KeyboardInterrupt:
                return None
            if resp.strip().isdigit():
                n = int(resp)
                if 1 <= n <= len(self.labels):
                    idx = n - 1
                    return idx, self.values[idx]
            console.print("Invalid selection. Please enter a valid number.", style="bold red")


def select_option(
    title: Optional[str],
    *options: Any,
    default_index: int = 0,
    default: Optional[Any] = None,
    show_help: bool = True,
    theme: Optional[Theme] = None,
) -> Tuple[int, Any]:
    normalized = _normalize_options(options)
    selector = InteractiveSelector(
        title=title,
        options=normalized,
        default_index=default_index,
        default=default,
        show_help=show_help,
        theme=theme,
    )
    result = selector.run()
    if result is None:
        raise KeyboardInterrupt("Selection cancelled by user")
    return result


def _select_with_prompt_toolkit(
    labels: Sequence[str],
    title: Optional[str],
    descriptions: Sequence[str],
    default_index: int,
    theme: Theme,
    recommended: Sequence[bool],
    warnings: Sequence[Optional[str]],
    infos: Sequence[Optional[str]],
) -> Optional[int]:
    import importlib
    app_mod = importlib.import_module("prompt_toolkit.application")
    kb_mod = importlib.import_module("prompt_toolkit.key_binding")
    layout_mod = importlib.import_module("prompt_toolkit.layout")
    containers_mod = importlib.import_module("prompt_toolkit.layout.containers")
    controls_mod = importlib.import_module("prompt_toolkit.layout.controls")
    styles_mod = importlib.import_module("prompt_toolkit.styles")
    widgets_mod = importlib.import_module("prompt_toolkit.widgets")

    Application = getattr(app_mod, "Application")
    KeyBindings = getattr(kb_mod, "KeyBindings")
    Layout = getattr(layout_mod, "Layout")
    HSplit = getattr(containers_mod, "HSplit")
    VSplit = getattr(containers_mod, "VSplit", None)
    Window = getattr(containers_mod, "Window")
    WindowAlign = getattr(layout_mod, "WindowAlign", None)
    FormattedTextControl = getattr(controls_mod, "FormattedTextControl")
    Style = getattr(styles_mod, "Style")
    RadioList = getattr(widgets_mod, "RadioList")
    Dialog = getattr(widgets_mod, "Dialog")
    Button = getattr(widgets_mod, "Button")
    Label = getattr(widgets_mod, "Label")

    # Build a custom list view with per-item description lines
    selected_index = max(0, min(default_index, len(labels) - 1))
    line_to_index: List[int] = []  # maps rendered line number -> option index

    def _render_list_fragments():
        nonlocal line_to_index, selected_index
        line_to_index = []
        frags: list = []
        # Determine wrap width from app if possible
        wrap_width = 80

        for i, name in enumerate(labels):
            is_sel = i == selected_index
            pointer = "❯" if is_sel else " "
            # Reserve a single character to the right of the number for a recommend symbol
            num = f"{i+1:>2}"
            sym = "✦" if (0 <= i < len(recommended) and recommended[i]) else " "
            prefix = f" {num}{sym}  {pointer} "
            name_style = "class:radio-selected" if is_sel else ""
            frags.append((name_style, prefix + str(name)))
            frags.append(("", "\n"))
            line_to_index.append(i)

            # Description line(s)
            desc = ""
            if descriptions and 0 <= i < len(descriptions):
                desc = str(descriptions[i] or "")
            if desc:
                # num (2) + sym (1) + pointer+spaces (~3) + padding 2 = 8
                indent = " " * 8
                wrapped = textwrap.fill(desc, width=wrap_width, initial_indent=indent, subsequent_indent=indent)
                for _j, line in enumerate(wrapped.splitlines()):
                    frags.append(("class:desc", line))
                    frags.append(("", "\n"))
                    line_to_index.append(i)
            # Warning line(s)
            warn = None
            if warnings and 0 <= i < len(warnings):
                warn = warnings[i]
            if warn:
                indent = " " * 8
                warn_initial = indent + "⚠ "
                warn_subseq = indent + "  "
                wrappedw = textwrap.fill(str(warn), width=wrap_width, initial_indent=warn_initial, subsequent_indent=warn_subseq)
                for _j, line in enumerate(wrappedw.splitlines()):
                    frags.append(("class:warn", line))
                    frags.append(("", "\n"))
                    line_to_index.append(i)
            # Info line(s)
            info = None
            if infos and 0 <= i < len(infos):
                info = infos[i]
            if info:
                indent = " " * 8
                info_initial = indent + "ℹ "
                info_subseq = indent + "  "
                wrappedi = textwrap.fill(str(info), width=wrap_width, initial_indent=info_initial, subsequent_indent=info_subseq)
                for _j, line in enumerate(wrappedi.splitlines()):
                    frags.append(("class:info", line))
                    frags.append(("", "\n"))
                    line_to_index.append(i)

        if frags and isinstance(frags[-1][1], str) and frags[-1][1].endswith("\n"):
            frags.pop()  # remove trailing newline token
        return frags

    def _mouse_handler(mouse_event):
        nonlocal selected_index
        # Map click row to index
        y = getattr(mouse_event.position, "y", 0)
        if 0 <= y < len(line_to_index):
            idx = line_to_index[y]
            if 0 <= idx < len(labels):
                selected_index = idx
                app.invalidate()
        return None

    list_window = Window(
        content=FormattedTextControl(_render_list_fragments, focusable=True, mouse_handler=_mouse_handler),
        wrap_lines=False,
        dont_extend_height=False,
    )

    result_holder: dict = {"value": None}

    def _do_ok() -> None:
        result_holder["value"] = selected_index
        app.exit(result=selected_index)

    def _do_cancel() -> None:
        result_holder["value"] = None
        app.exit(result=None)

    ok_button = Button(text="Select", handler=_do_ok)
    cancel_button = Button(text="Cancel", handler=_do_cancel)

    header_widgets: List = []
    if title:
        header_widgets.append(Label(text=title))

    help_window = Window(
        content=FormattedTextControl(lambda: [("class:help", "Use mouse or arrows • 1-9 jump • Enter to select • Esc to cancel")]),
        align=WindowAlign.CENTER if WindowAlign else None,
        dont_extend_height=False,
        height=1,
    )

    body = HSplit(header_widgets + [list_window, help_window])

    dialog = Dialog(
        title=title or "Select an option",
        body=body,
        buttons=[ok_button, cancel_button],
        with_background=True,
    )

    Style = getattr(styles_mod, "Style")
    style = Style.from_dict(
        {
            "dialog": f"bg:{theme.background}",
            "dialog.body": f"bg:{theme.background} {theme.foreground}",
            "dialog frame.label": f"bg:{theme.accent} {theme.selected_fg}",
            "button": f"bg:{theme.button_bg} {theme.button_fg}",
            "button.focused": f"bg:{theme.button_focus_bg} {theme.button_focus_fg}",
            "radio-selected": f"bg:{theme.selected_bg} {theme.selected_fg}",
            "desc": f"{theme.muted}",
            "help": f"{theme.muted}",
            "recommend": f"{theme.accent} italic",
            "warn": f"bold {theme.warning}",
            "info": f"{theme.info}",
        }
    )

    kb = KeyBindings()

    @kb.add("escape")
    @kb.add("c-c")
    def _(event) -> None:  # type: ignore
        _do_cancel()

    @kb.add("up")
    @kb.add("k")
    def _(event) -> None:  # type: ignore
        nonlocal selected_index
        selected_index = (selected_index - 1) % len(labels)
        app.invalidate()

    @kb.add("down")
    @kb.add("j")
    def _(event) -> None:  # type: ignore
        nonlocal selected_index
        selected_index = (selected_index + 1) % len(labels)
        app.invalidate()

    # number keys jump and select
    for d in "123456789":
        @kb.add(d)
        def _(event, d=d):  # type: ignore
            nonlocal selected_index
            n = int(d)
            if 1 <= n <= len(labels):
                selected_index = n - 1
                app.invalidate()
                _do_ok()

    @kb.add("enter")
    def _(event) -> None:  # type: ignore
        _do_ok()

    app = Application(
        layout=Layout(dialog),
        key_bindings=kb,
        mouse_support=True,
        full_screen=True,
        style=style,
    )
    selected_value = app.run()
    if selected_value is None:
        return None
    idx = int(selected_value)
    return idx
