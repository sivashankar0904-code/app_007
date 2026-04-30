"""
Agent endpoints — triggered internally by Django or Redis Stream consumer.
"""
from fastapi import APIRouter

router = APIRouter(tags=["agents"])

@router.post("/run")
async def run_agent(payload: dict):
    # TODO: implement agentic workflow
    return {"status": "queued", "payload": payload}
