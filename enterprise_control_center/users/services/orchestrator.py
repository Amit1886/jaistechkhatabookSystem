from typing import Any, Dict


def process_action(user_id: int, action: str) -> Dict[str, Any]:
    return {"user_id": user_id, "action": action, "status": "processed"}
