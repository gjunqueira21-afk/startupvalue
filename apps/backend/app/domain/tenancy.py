from dataclasses import dataclass

from app.db.models import Role


class AuthorizationError(PermissionError):
    pass


@dataclass(frozen=True)
class ActorContext:
    user_id: str
    workspace_id: str
    role: Role

    def require(self, *allowed: Role) -> None:
        if self.role not in allowed:
            raise AuthorizationError("action_not_allowed")


def require_same_workspace(actor: ActorContext, resource_workspace_id: str) -> None:
    if actor.workspace_id != resource_workspace_id:
        raise AuthorizationError("resource_not_found")

