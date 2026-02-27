from typing import Literal, NotRequired, TypedDict

SUPPORTED_FILTERS = ("drawtext", "pad")
FiltersLiteral = Literal["drawtext", "pad"]


class GeneralFilterSettings(TypedDict):
    enable: NotRequired[str]


# TODO: explanation of these args, better sortin
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


class Pad(GeneralFilterSettings):
    width: NotRequired[str]
    height: NotRequired[str]
    color: NotRequired[str]
    x: NotRequired[int]
    y: NotRequired[int]


class Filters(TypedDict):
    drawtext: Drawtext
    pad: Pad


def filtermap(filter: FiltersLiteral) -> type[GeneralFilterSettings]:
    match filter:
        case "drawtext":
            return Drawtext
        case "pad":
            return Pad
