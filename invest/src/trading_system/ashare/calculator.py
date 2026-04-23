from dataclasses import dataclass
from enum import Enum


class BoardType(str, Enum):
    MAIN = "main"
    GEM = "gem"
    STAR = "star"
    ST = "st"
    BSE = "bse"


@dataclass
class LimitPrice:
    upper_limit: float
    lower_limit: float
    board_type: BoardType


BOARD_LIMIT_PCT = {
    BoardType.MAIN: 0.10,
    BoardType.GEM: 0.20,
    BoardType.STAR: 0.20,
    BoardType.ST: 0.05,
    BoardType.BSE: 0.30,
}


def calc_limit_price(prev_close: float, board_type: BoardType = BoardType.MAIN) -> LimitPrice:
    if prev_close <= 0:
        raise ValueError(f"prev_close must be positive, got {prev_close}")

    limit_pct = BOARD_LIMIT_PCT[board_type]
    raw_upper = prev_close * (1 + limit_pct)
    raw_lower = prev_close * (1 - limit_pct)

    upper_limit = round(round(raw_upper * 100) / 100, 2)
    lower_limit = round(round(raw_lower * 100) / 100, 2)

    return LimitPrice(
        upper_limit=upper_limit,
        lower_limit=lower_limit,
        board_type=board_type,
    )


def clamp_price(
    price: float,
    prev_close: float,
    board_type: BoardType = BoardType.MAIN,
) -> float:
    limit = calc_limit_price(prev_close, board_type)
    return max(limit.lower_limit, min(limit.upper_limit, price))


def is_within_limit(
    price: float,
    prev_close: float,
    board_type: BoardType = BoardType.MAIN,
) -> bool:
    limit = calc_limit_price(prev_close, board_type)
    return limit.lower_limit <= price <= limit.upper_limit


def detect_board_type(symbol: str, name: str = "") -> BoardType:
    if not symbol:
        return BoardType.MAIN

    if name.upper().startswith("ST") or "*ST" in name.upper() or "ST" in name.upper():
        return BoardType.ST

    if symbol.startswith("688"):
        return BoardType.STAR

    if symbol.startswith("300") or symbol.startswith("301"):
        return BoardType.GEM

    if symbol.startswith("8") or symbol.startswith("4"):
        return BoardType.BSE

    return BoardType.MAIN
