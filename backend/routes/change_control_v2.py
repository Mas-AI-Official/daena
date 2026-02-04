from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

class ChangeRequest(BaseModel):
    title: str
    description: str

@router.get("/")
def get_changes():
    return {"message": "Change Control V2"}
