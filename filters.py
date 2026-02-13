from typing import NotRequired, TypedDict, Literal, TypeVar, Any

SUPPORTED_FILTERS = ("drawtext",)
FiltersLiteral = Literal["drawtext"]


class Drawtext(TypedDict):
    fontfile: str
    text: str
    x: NotRequired[int]
    y: NotRequired[int]
    fontsize: NotRequired[int]
    fontcolor: NotRequired[str]


class Filters(TypedDict):
    drawtext: Drawtext


T = TypeVar("T", bound=Drawtext)


def filtermap(filter: FiltersLiteral) -> type[Drawtext]:
    match filter:
        case "drawtext":
            return Drawtext
