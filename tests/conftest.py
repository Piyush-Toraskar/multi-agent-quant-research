import pytest
from app.config import Settings
from app.database.queries import Repository
from app.schemas import ResearchRequest
from app.tools.market_data import fetch_prices

@pytest.fixture
def settings(tmp_path):
    return Settings(_env_file=None, data_dir=tmp_path, database_url='sqlite:///' + (tmp_path/'test.db').as_posix(),
                    agent_mode='demo', workflow_engine='native', tool_transport='local')

@pytest.fixture
def request_data():
    return ResearchRequest().model_dump(mode='json')

@pytest.fixture
def dataset(settings, request_data):
    return fetch_prices(settings, request_data)

@pytest.fixture
def repository(settings):
    r=Repository(settings)
    yield r
    r.close()
