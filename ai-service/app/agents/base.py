from abc import ABC, abstractmethod
from typing import Generic, TypeVar
from app.models.agent_base import AgentOutput

InputT = TypeVar("InputT")
OutputT = TypeVar("OutputT", bound=AgentOutput)


class BaseAgent(ABC, Generic[InputT, OutputT]):
    def __init__(self, name: str):
        self.name = name
    
    @abstractmethod
    async def run(self, input_data: InputT) -> OutputT:
        pass
    
    @abstractmethod
    def get_system_prompt(self) -> str:
        pass
    
    def get_output_schema(self) -> dict:
        return AgentOutput.model_json_schema()