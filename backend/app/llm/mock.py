class MockLLMProvider:
    """Return predefined responses without calling an LLM."""

    async def generate(self, prompt: str) -> str:
        return "Mock Provider 응답입니다. 실제 LLM은 호출하지 않았습니다."

    async def aclose(self) -> None:
        pass