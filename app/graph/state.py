from typing import TypedDict

class ResearchState(TypedDict, total=False):
    request: dict
    engine: str
    plan: dict
    history: dict
    data: dict
    analysis: dict
    backtest: dict
    risk: dict
    verification: dict
    report: str
    execution_delay: int
    revisions: int
    revision_note: str
