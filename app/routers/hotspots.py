"""首页热点路由"""
from fastapi import APIRouter

from app.services.hotspot_service import HotspotResponse, get_all_hotspots

router = APIRouter(prefix="/hotspots", tags=["首页热点"])


@router.get("/", response_model=HotspotResponse, summary="获取首页热点")
async def list_hotspots():
    return await get_all_hotspots()
