import pytest

from app.agent.analyzer import FailureAnalyzer
from app.llm.models import LLMResponse, LLMUsage


class FakeLLM:
    async def complete(self, messages, tools=None, temperature=None, response_format=None, **kwargs):
        return LLMResponse(
            content='{"root_cause":"missing endpoint","affected_files":["main.py"],"proposed_fix":"add /health","confidence":0.9}',
            usage=LLMUsage(),
        )


@pytest.mark.asyncio
async def test_failure_analyzer():
    diagnosis = await FailureAnalyzer(FakeLLM()).diagnose("add health", "FAILED test_health", "", "app code")
    assert diagnosis.root_cause == "missing endpoint"
    assert diagnosis.affected_files == ["main.py"]
    assert diagnosis.confidence == 0.9
