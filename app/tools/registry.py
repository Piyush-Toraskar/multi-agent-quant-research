from dataclasses import dataclass
from typing import Callable
from pydantic import BaseModel
from app.schemas import FetchArgs, AnalysisArgs, BacktestArgs, ArtifactArgs, VerifyArgs, SearchArgs, GetRunArgs
from app.tools.market_data import fetch_prices
from app.tools.quant_tools import analyse_market, run_backtest, assess_risk
from app.tools.verification import verify_research
from app.database.queries import Repository

@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    group: str
    model: type[BaseModel]
    handler: Callable

    def schema(self):
        return {'name': self.name, 'description': self.description, 'inputSchema': self.model.model_json_schema()}

    def call(self, settings, arguments):
        validated = self.model.model_validate(arguments).model_dump(mode='json')
        return self.handler(settings, **validated)


def search_research(settings, query='', limit=5):
    repo = Repository(settings)
    try:
        return {'runs': repo.search(query, limit)}
    finally:
        repo.close()


def get_research(settings, run_id):
    repo = Repository(settings)
    try:
        row = repo.get(run_id)
        if row is None:
            raise ValueError('Research run not found')
        return row
    finally:
        repo.close()


def registry():
    tools = [
      Tool('fetch_prices', 'Load a validated immutable adjusted-close dataset. Demo is synthetic; live failures are errors.', 'market', FetchArgs, fetch_prices),
      Tool('analyse_market', 'Calculate descriptive returns, volatility, correlations, beta and trailing momentum from a dataset.', 'quant', AnalysisArgs, analyse_market),
      Tool('run_backtest', 'Run an approved long-only strategy with delayed executions, costs, benchmark and chronological holdout.', 'quant', BacktestArgs, run_backtest),
      Tool('assess_risk', 'Calculate historical tail risk, exposure, beta and an illustrative shock from a stored backtest.', 'quant', ArtifactArgs, assess_risk),
      Tool('verify_research', 'Run deterministic backtest validity checks, including a future-price perturbation test.', 'quant', VerifyArgs, verify_research),
      Tool('search_research', 'Search persisted research history using a parameterised, bounded SQL query.', 'database', SearchArgs, search_research),
      Tool('get_research', 'Read a previous persisted research run by its identifier.', 'database', GetRunArgs, get_research)]
    return {t.name: t for t in tools}
