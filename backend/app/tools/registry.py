from typing import Callable, Dict, Any, List, Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session

class ToolDefinition(BaseModel):
    name: str
    description: str
    parameters: Dict[str, Any]
    required_permission: str
    side_effect: bool = False
    output_schema: Optional[Dict[str, Any]] = None
    authorization_requirement: str = "PUBLIC"

class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, Callable] = {}
        self._definitions: Dict[str, ToolDefinition] = {}

    def register(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        required_permission: str,
        side_effect: bool = False,
        output_schema: Optional[Dict[str, Any]] = None,
        authorization_requirement: Optional[str] = None
    ):
        def decorator(func: Callable):
            self._tools[name] = func
            self._definitions[name] = ToolDefinition(
                name=name,
                description=description,
                parameters=parameters,
                required_permission=required_permission,
                side_effect=side_effect,
                output_schema=output_schema,
                authorization_requirement=authorization_requirement or required_permission
            )
            return func
        return decorator

    def get_tool(self, name: str) -> Optional[Callable]:
        return self._tools.get(name)

    def get_definition(self, name: str) -> Optional[ToolDefinition]:
        return self._definitions.get(name)

    def list_all_tools(self) -> List[ToolDefinition]:
        return list(self._definitions.values())

    def get_all_definitions_for_llm(self) -> List[Dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": d.name,
                    "description": d.description,
                    "parameters": d.parameters
                }
            } for d in self._definitions.values()
        ]

    def verify_permission(
        self,
        tool_name: str,
        agent_permissions: Optional[List[str]] = None,
        db: Optional[Session] = None,
        agent_id: Optional[str] = None,
        agent_name: Optional[str] = "Agent"
    ) -> Optional[Dict[str, Any]]:
        """
        Verifies if an agent has permission to execute a tool.
        Returns None if authorized, or a structured permission failure dict if denied.
        """
        definition = self.get_definition(tool_name)
        if not definition:
            return {"error": "TOOL_NOT_FOUND", "message": f"Tool '{tool_name}' is not registered."}

        required_perm = definition.required_permission
        
        # Check permissions from DB if db and agent_id provided
        if db and agent_id:
            from app.database.models.agent import Agent
            agent_record = db.query(Agent).filter(Agent.id == agent_id, Agent.status == "active").first()
            if agent_record:
                granted = agent_record.permission_names
                if required_perm not in granted:
                    return {
                        "error": "PERMISSION_DENIED",
                        "agent": agent_record.name,
                        "required_permission": required_perm
                    }
                return None

        # Check in-memory permissions list if provided
        if agent_permissions is not None:
            if required_perm not in agent_permissions:
                return {
                    "error": "PERMISSION_DENIED",
                    "agent": agent_name,
                    "required_permission": required_perm
                }
            return None

        return {
            "error": "PERMISSION_DENIED",
            "agent": agent_name,
            "required_permission": required_perm
        }

tool_registry = ToolRegistry()
