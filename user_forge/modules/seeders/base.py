from abc import ABC, abstractmethod
from typing import List, Dict, Any
from user_forge.core.models import Persona, Account

class BaseSeeder(ABC):
    """
    Base class for seeding personas directly into databases or auth APIs.
    """
    def __init__(self, project_id: str, **kwargs):
        self.project_id = project_id
        self.config = kwargs

    @abstractmethod
    def seed_personas(self, personas: List[Persona]) -> List[Account]:
        """
        Takes a list of Personas, inserts them into target database/provider,
        and returns Account representations with execution status.
        """
        pass
