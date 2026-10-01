from pathlib import Path
from typing import Literal
from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[1]

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / '.env', extra='ignore', case_sensitive=False)
    data_dir: Path = ROOT / 'data' / 'runtime'
    database_url: str = ''
    agent_mode: Literal['demo', 'llm'] = 'demo'
    workflow_engine: Literal['auto', 'native', 'langgraph'] = 'auto'
    tool_transport: Literal['mcp', 'local'] = 'mcp'
    mcp_implementation: Literal['builtin', 'sdk'] = 'builtin'
    llm_base_url: str = 'https://api.openai.com/v1'
    llm_model: str = ''
    llm_api_key: SecretStr = SecretStr('')
    openai_api_key: SecretStr = SecretStr('')
    llm_timeout_seconds: float = Field(90, ge=1, le=300)
    tool_timeout_seconds: float = Field(90, ge=1, le=300)
    max_agent_turns: int = Field(4, ge=1, le=8)
    max_revisions: int = Field(1, ge=0, le=2)
    max_workers: int = Field(2, ge=1, le=4)
    max_pending_runs: int = Field(8, ge=1, le=32)
    llm_input_usd_per_million: float | None = Field(None, ge=0)
    llm_output_usd_per_million: float | None = Field(None, ge=0)

    @model_validator(mode='after')
    def resolve_paths(self):
        self.data_dir = self.data_dir.expanduser().resolve()
        if not self.database_url:
            self.database_url = 'sqlite:///' + (self.data_dir / 'research.db').as_posix()
        return self

    @property
    def api_key(self):
        return self.llm_api_key.get_secret_value() or self.openai_api_key.get_secret_value()

    def prepare(self):
        for path in [self.data_dir, self.data_dir / 'snapshots', self.data_dir / 'artifacts']:
            path.mkdir(parents=True, exist_ok=True)

    def child_env(self):
        # The numerical/MCP subprocesses do not receive LLM credentials.
        return {'DATA_DIR': str(self.data_dir), 'DATABASE_URL': self.database_url,
                'MCP_IMPLEMENTATION': self.mcp_implementation}
