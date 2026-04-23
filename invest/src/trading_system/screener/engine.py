from dataclasses import dataclass, field
from enum import Enum

import pandas as pd


class LogicOperator(str, Enum):
    AND = "AND"
    OR = "OR"


@dataclass
class ScreenCondition:
    name: str
    field: str
    operator: str
    value: float | int | str | tuple
    logic: LogicOperator = LogicOperator.AND

    def evaluate(self, df: pd.DataFrame) -> pd.Series:
        if self.field not in df.columns:
            return pd.Series(False, index=df.index)

        col = df[self.field]

        if self.operator == ">":
            return col > self.value
        elif self.operator == ">=":
            return col >= self.value
        elif self.operator == "<":
            return col < self.value
        elif self.operator == "<=":
            return col <= self.value
        elif self.operator == "==":
            return col == self.value
        elif self.operator == "!=":
            return col != self.value
        elif self.operator == "between" and isinstance(self.value, tuple):
            return (col >= self.value[0]) & (col <= self.value[1])
        elif self.operator == "not_between" and isinstance(self.value, tuple):
            return (col < self.value[0]) | (col > self.value[1])
        elif self.operator == "in" and isinstance(self.value, (list, tuple)):
            return col.isin(self.value)
        return pd.Series(False, index=df.index)


@dataclass
class ScreenResult:
    symbol: str
    name: str = ""
    score: float = 0.0
    passed_conditions: list[str] = field(default_factory=list)
    details: dict = field(default_factory=dict)


class StockScreener:
    def __init__(self):
        self._conditions: list[ScreenCondition] = []

    def add_condition(self, condition: ScreenCondition) -> "StockScreener":
        self._conditions.append(condition)
        return self

    def add_conditions(self, conditions: list[ScreenCondition]) -> "StockScreener":
        self._conditions.extend(conditions)
        return self

    def clear_conditions(self) -> "StockScreener":
        self._conditions = []
        return self

    @property
    def conditions(self) -> list[ScreenCondition]:
        return list(self._conditions)

    def screen(self, stock_data: pd.DataFrame) -> list[ScreenResult]:
        if stock_data.empty or not self._conditions:
            return []

        df = stock_data.copy()
        symbol_col = "symbol" if "symbol" in df.columns else df.columns[0]
        name_col = "name" if "name" in df.columns else None

        and_masks = []
        or_masks = []
        condition_names = {}

        for cond in self._conditions:
            mask = cond.evaluate(df)
            condition_names[cond.name] = mask
            if cond.logic == LogicOperator.AND:
                and_masks.append(mask)
            else:
                or_masks.append(mask)

        if and_masks and or_masks:
            and_result = pd.concat(and_masks, axis=1).all(axis=1)
            or_result = pd.concat(or_masks, axis=1).any(axis=1)
            final_mask = and_result & or_result
        elif and_masks:
            final_mask = pd.concat(and_masks, axis=1).all(axis=1)
        elif or_masks:
            final_mask = pd.concat(or_masks, axis=1).any(axis=1)
        else:
            final_mask = pd.Series(True, index=df.index)

        passed = df[final_mask]
        results = []
        for idx, row in passed.iterrows():
            passed_conds = []
            for cond in self._conditions:
                if cond.name in condition_names and condition_names[cond.name].get(idx, False):
                    passed_conds.append(cond.name)

            symbol = str(row.get(symbol_col, idx))
            name = str(row.get(name_col, "")) if name_col else ""
            score = len(passed_conds) / max(len(self._conditions), 1)

            results.append(ScreenResult(
                symbol=symbol,
                name=name,
                score=round(score, 4),
                passed_conditions=passed_conds,
                details={col: row[col] for col in df.columns if col not in [symbol_col, name_col]},
            ))

        results.sort(key=lambda x: x.score, reverse=True)
        return results
