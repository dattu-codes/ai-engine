from pydantic import BaseModel
from typing import Dict, Optional

class CreateGraphRequest(BaseModel):
    preset: Optional[str] = None
    graph_def: Optional[Dict] = None

class RunGraphRequest(BaseModel):
    graph_id: str
    initial_state: Dict
