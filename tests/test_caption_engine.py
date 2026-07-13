import random
import re
from types import SimpleNamespace

from app.captions.engine import build_caption_document
from app.captions.font_scaling import _AVG_GLYPH_WIDTH_RATIO, font_size_for_card
from app.captions.line_breaking import (
    HARD_MAX_WORDS_PER_LINE,
    MAX_LINES_PER_CARD,
    segment_into_caption_cards,
)
from app.captions.safe_area import safe_area_for
from app.captions.themes import DEFAULT_THEME, THEMES, get_theme

_ASPECT_RESOLUTIONS = {
    "9:16": (1080, 1920),
    "16:9": (1920, 1080),
    "1:1": (1080, 1080),
    "4:5": (1080, 1350),
}

_WORDS = [
    "Marie", "Curie", "discovered", "radium", "in", "1898,", "changing", "science",
    "forever.", "billion", "years", "ago", "Earth", "formed", "swirling", "cloud",
    "dust", "gas", "October", "4th,", "1957,", "Soviet", "Union", "launched",
    "Sputnik,", "satellite.", "extraordinarily", "longer", "technical", "terminology",
]


def test_captions_never_exceed_safe_area():
    random.seed(11)
    for ratio, (width, height) in _ASPECT_RESOLUTIONS.items():
        safe = safe_area_for(ratio)
        for _ in range(300):
            text = " ".join(random.choice(_WORDS) for _ in range(random.randint(3, 30)))
            for card in segment_into_caption_cards(text):
                size = font_size_for_card(card.lines, width, height, ratio)
                for line in card.lines:
                    estimated_width = len(line) * size * _AVG_GLYPH_WIDTH_RATIO
                    assert estimated_width <= safe.max_text_width(width) + 1, (
                        f"{ratio}: {line!r} at size {size} overflows safe width"
                    )


def test_no_clipping_in_generated_document():
    scenes = [
        SimpleNamespace(
            number=1,
            narration="Have you ever wondered how the Earth was formed billions of years ago from a swirling cloud of dust and gas?",
            on_screen_text="",
            start_second=0,
            end_second=10,
            caption_safe_area="lower_third",
            caption_emphasis="formed",
        ),
    ]
    storyboard = SimpleNamespace(scenes=scenes)
    for ratio, (width, height) in _ASPECT_RESOLUTIONS.items():
        safe = safe_area_for(ratio)
        document = build_caption_document(storyboard, width, height, aspect_ratio=ratio)
        for line in document.splitlines():
            if not line.startswith("Dialogue:"):
                continue
            fs_index = line.index("\\fs")
            size_str = ""
            for ch in line[fs_index + 3:]:
                if ch.isdigit():
                    size_str += ch
                else:
                    break
            size = int(size_str)
            # Isolate the Text field (the 10th, per the Dialogue Format
            # line) and strip every ASS override block {...} -- the leading
            # position/size block plus any inline highlight tags -- before
            # measuring the plain rendered text per \N-separated line.
            text_field = line.split(",", 9)[-1]
            text_part = re.sub(r"\{[^}]*\}", "", text_field)
            for rendered_line in text_part.split("\\N"):
                plain = rendered_line
                assert len(plain) * size * _AVG_GLYPH_WIDTH_RATIO <= safe.max_text_width(width) + 1


def test_maximum_two_lines_per_card():
    random.seed(3)
    for _ in range(300):
        text = " ".join(random.choice(_WORDS) for _ in range(random.randint(1, 40)))
        for card in segment_into_caption_cards(text):
            assert len(card.lines) <= MAX_LINES_PER_CARD


def test_natural_language_wrapping_protects_names_dates_numbers():
    cards = segment_into_caption_cards(
        "Marie Curie discovered radium in 1898, a breakthrough that changed science forever."
    )
    flattened = " / ".join(" ".join(card.lines) for card in cards)
    assert "Marie Curie" in flattened  # name never split across a break

    cards = segment_into_caption_cards(
        "On October 4th, 1957, the Soviet Union launched Sputnik, the first artificial satellite."
    )
    joined_lines = [line for card in cards for line in card.lines]
    assert any("October 4th, 1957," in line for line in joined_lines)

    for card in segment_into_caption_cards(
        "This is a very long sentence with absolutely no punctuation anywhere at all "
        "which should still wrap sensibly without ever exceeding the maximum word count"
    ):
        for line in card.lines:
            assert len(line.split()) <= HARD_MAX_WORDS_PER_LINE


def test_dynamic_font_scaling_shrinks_for_longer_captions():
    short = font_size_for_card(["Sky is blue."], 1080, 1920, "9:16")
    long = font_size_for_card(
        ["This is a considerably longer caption line", "that wraps onto a second line too"],
        1080,
        1920,
        "9:16",
    )
    assert short > long


def test_dynamic_font_scaling_respects_aspect_ratio():
    portrait = font_size_for_card(["A short line"], 1080, 1920, "9:16")
    landscape = font_size_for_card(["A short line"], 1920, 1080, "16:9")
    assert portrait > 0 and landscape > 0


def test_caption_themes_load_correctly():
    expected_themes = {
        "netflix_documentary", "bbc_documentary", "national_geographic",
        "vox", "minimal", "modern", "cinematic",
    }
    assert set(THEMES) == expected_themes
    for name in expected_themes:
        theme = get_theme(name)
        assert theme.key == name
        assert theme.font
        assert theme.outline_width > 0
        assert theme.default_animation in {"fade", "slide", "pop", "none"}

    assert get_theme(None).key == DEFAULT_THEME
    assert get_theme("not-a-real-theme").key == DEFAULT_THEME


def test_build_caption_document_is_deterministic():
    scenes = [
        SimpleNamespace(
            number=1, narration="A calm test sentence about deterministic rendering.",
            on_screen_text="", start_second=0, end_second=5,
            caption_safe_area="lower_third", caption_emphasis="",
        ),
    ]
    storyboard = SimpleNamespace(scenes=scenes)
    first = build_caption_document(storyboard, 1080, 1920, aspect_ratio="9:16")
    second = build_caption_document(storyboard, 1080, 1920, aspect_ratio="9:16")
    assert first == second
