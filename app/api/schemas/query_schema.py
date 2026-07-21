from pydantic import BaseModel


class QuerySchema(BaseModel):
    query: str
    user_id: str = "anonymous"
    session_id: str | None = None
