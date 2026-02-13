from typing import Literal, NotRequired, TypedDict, TypeVar

SUPPORTED_FILTERS = ("drawtext",)
FiltersLiteral = Literal["drawtext"]


class GeneralFilterSettings(TypedDict):
    enable: NotRequired[str]


class Drawtext(GeneralFilterSettings):
    fontfile: str
    text: str
    x: NotRequired[int]
    y: NotRequired[int]
    fontsize: NotRequired[int]
    fontcolor: NotRequired[str]
    box: NotRequired[bool]
    boxborderw: NotRequired[str]
    boxw: NotRequired[int]
    boxh: NotRequired[int]
    boxcolor: NotRequired[str]
    line_spacing: NotRequired[int]
    text_align: NotRequired[Literal["T", "M", "B", "L", "C", "R"]]
    y_align: NotRequired[Literal["text", "baseline", "font"]]
    borderw: NotRequired[int]
    bordercolor: NotRequired[str]
    shadowcolor: NotRequired[str]
    shadowx: NotRequired[int]
    shadowy: NotRequired[int]


class Filters(TypedDict):
    drawtext: Drawtext


T = TypeVar("T", bound=Drawtext)


def filtermap(filter: FiltersLiteral) -> type[Drawtext]:
    match filter:
        case "drawtext":
            return Drawtext
