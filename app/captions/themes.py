from __future__ import annotations

"""Caption style presets ("themes").

Each theme is a bundle of ASS-renderable style choices -- font, outline
(stroke), shadow, base text color, highlight color, letter spacing, and a
default animation -- so switching the visual language of the subtitles
never requires touching the line-breaking, timing, or positioning logic.
"""

from dataclasses import dataclass

# ASS colours are &HAABBGGRR (alpha-blue-green-red, hex, alpha 00=opaque).
_WHITE = "&H00FFFFFF"
_NEAR_BLACK = "&H00101010"
_SOFT_BLACK_SHADOW = "&H80000000"


@dataclass(frozen=True)
class CaptionTheme:
    key: str
    label: str
    font: str
    bold: bool
    base_color: str
    highlight_color: str
    outline_color: str
    outline_width: float
    shadow: float
    back_color: str
    letter_spacing: float
    default_animation: str


THEMES: dict[str, CaptionTheme] = {
    "netflix_documentary": CaptionTheme(
        key="netflix_documentary",
        label="Netflix Documentary",
        font="Arial",
        bold=True,
        base_color=_WHITE,
        highlight_color="&H00E8B862",  # warm gold
        outline_color=_NEAR_BLACK,
        outline_width=3.0,
        shadow=3.0,
        back_color=_SOFT_BLACK_SHADOW,
        letter_spacing=0.0,
        default_animation="fade",
    ),
    "bbc_documentary": CaptionTheme(
        key="bbc_documentary",
        label="BBC Documentary",
        font="Georgia",
        bold=False,
        base_color=_WHITE,
        highlight_color="&H00D9D9D9",  # restrained near-white
        outline_color=_NEAR_BLACK,
        outline_width=2.2,
        shadow=1.5,
        back_color="&HA0000000",
        letter_spacing=0.0,
        default_animation="fade",
    ),
    "national_geographic": CaptionTheme(
        key="national_geographic",
        label="National Geographic",
        font="Arial Black",
        bold=True,
        base_color=_WHITE,
        highlight_color="&H0000D8FF",  # signature Nat Geo yellow (BGR)
        outline_color="&H00000000",
        outline_width=3.4,
        shadow=2.0,
        back_color=_SOFT_BLACK_SHADOW,
        letter_spacing=1.0,
        default_animation="fade",
    ),
    "vox": CaptionTheme(
        key="vox",
        label="Vox",
        font="Verdana",
        bold=True,
        base_color=_WHITE,
        highlight_color="&H001ED6FF",  # bright orange-yellow (BGR)
        outline_color=_NEAR_BLACK,
        outline_width=2.6,
        shadow=1.0,
        back_color="&H70000000",
        letter_spacing=0.5,
        default_animation="pop",
    ),
    "minimal": CaptionTheme(
        key="minimal",
        label="Minimal",
        font="Segoe UI",
        bold=False,
        base_color=_WHITE,
        highlight_color="&H00E0E0E0",
        outline_color=_NEAR_BLACK,
        outline_width=1.6,
        shadow=0.6,
        back_color="&H50000000",
        letter_spacing=0.0,
        default_animation="fade",
    ),
    "modern": CaptionTheme(
        key="modern",
        label="Modern",
        font="Segoe UI Semibold",
        bold=True,
        base_color=_WHITE,
        highlight_color="&H00FF6EC7",  # vivid magenta-pink (BGR)
        outline_color=_NEAR_BLACK,
        outline_width=2.4,
        shadow=1.2,
        back_color="&H60000000",
        letter_spacing=0.5,
        default_animation="slide",
    ),
    "cinematic": CaptionTheme(
        key="cinematic",
        label="Cinematic",
        font="Georgia",
        bold=True,
        base_color=_WHITE,
        highlight_color="&H0048B4E8",  # amber (BGR)
        outline_color="&H00000000",
        outline_width=3.2,
        shadow=3.5,
        back_color="&HA0000000",
        letter_spacing=2.0,
        default_animation="fade",
    ),
}

DEFAULT_THEME = "netflix_documentary"


def get_theme(name: str | None) -> CaptionTheme:
    return THEMES.get(name or DEFAULT_THEME, THEMES[DEFAULT_THEME])
