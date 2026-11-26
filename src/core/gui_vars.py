from typing import Any, TypedDict

from core import filters


class Value:
    def __init__(self, value: str | int | bool) -> None:
        self._value: Any = value

    def get(self) -> Any:
        return self._value

    def set(self, value: Any) -> None:
        self._value = value


class DefaultVarDict(TypedDict):
    default: str | int | bool
    var: Value


class GuiVars:
    settings: dict[str, dict[str, DefaultVarDict]]

    def __init__(self) -> None:
        self.settings = {
            "general": {
                "file": {"default": "Double click here or Drag & drop file ...", "var": Value("")},
                "normalize_audio": {"default": True, "var": Value(True)},
                "force_reencoding_video": {"default": False, "var": Value(False)},
                "selected_encoder_video": {"default": "libx265", "var": Value("libx265")},
            },
            "crop": {
                "crop_enabled": {"default": True, "var": Value(True)},
                "width": {"default": 0, "var": Value(0)},
                "height": {"default": 0, "var": Value(0)},
                "original_width": {"default": 0, "var": Value(0)},
                "original_height": {"default": 0, "var": Value(0)},
                "left_top_x": {"default": 0, "var": Value(0)},
                "left_top_y": {"default": 0, "var": Value(0)},
                "original_left_top_x": {"default": 0, "var": Value(0)},
                "original_left_top_y": {"default": 0, "var": Value(0)},
            },
            "trim": {
                "trim_enabled": {"default": True, "var": Value(True)},
                "hh_start": {"default": 0, "var": Value(0)},
                "mm_start": {"default": 0, "var": Value(0)},
                "ss_start": {"default": 0, "var": Value(0)},
                "ms_start": {"default": 0, "var": Value(0)},
                "hh_end": {"default": 0, "var": Value(0)},
                "mm_end": {"default": 0, "var": Value(0)},
                "ss_end": {"default": 0, "var": Value(0)},
                "ms_end": {"default": 0, "var": Value(0)},
                "original_hh_end": {"default": 0, "var": Value(0)},
                "original_mm_end": {"default": 0, "var": Value(0)},
                "original_ss_end": {"default": 0, "var": Value(0)},
                "original_ms_end": {"default": 0, "var": Value(0)},
            },
            "videofilters": {"selected": {"default": "", "var": Value("")}},
            "libx264": {
                "crf": {"default": 23, "var": Value(23)},
                "preset": {"default": "medium", "var": Value("medium")},
                "tune": {"default": "DEFAULT", "var": Value("DEFAULT")},
            },
            "libx265": {
                "crf": {"default": 28, "var": Value(28)},
                "preset": {"default": "medium", "var": Value("medium")},
                "tune": {"default": "DEFAULT", "var": Value("DEFAULT")},
            },
        }
        self.video_filter_args: list[tuple[filters.FiltersLiteral, dict[str, str]]] = []

    def reset_settings_to_default(self) -> None:
        for section in self.settings.values():
            for option in section.values():
                option["var"].set(option["default"])
        self.video_filter_args = []
