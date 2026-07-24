"""外部平台通过 API Key 推送排行榜数据"""

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.core.database import get_db
from app.schemas.team_ranking import RankingsExportPayload, UploadResult
from app.services.ranking_service import process_rankings_payload, verify_api_key, get_latest_season_id

router = APIRouter()


@router.post("/rankings/push", response_model=UploadResult)
async def external_push_rankings(
    request: Request,
    x_api_key: str = Header(..., alias="X-API-Key", description="由管理员后台生成的 API Key"),
    season_id: Optional[int] = Query(None, description="目标赛季 ID，Key 已绑定赛季时可省略"),
    db: AsyncSession = Depends(get_db),
):
    """
    外部平台推送排行榜数据接口。
    Header: X-API-Key: <key>
    Body: 与 JSON 导出文件格式完全一致
    """
    key_record = await verify_api_key(db, x_api_key)
    if not key_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    # Key 的绑定赛季优先于查询参数
    resolved_season_id = key_record.season_id or season_id
    if resolved_season_id is None:
        resolved_season_id = await get_latest_season_id(db)
    if resolved_season_id is None:
        raise HTTPException(status_code=400, detail="尚未创建任何赛季")

    try:
        body = await request.json()
        payload = RankingsExportPayload.model_validate(body)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"请求体解析失败：{e}")

    return await process_rankings_payload(
        db, payload,
        source="api",
        season_id=resolved_season_id,
        notes=f"API push via key: {key_record.key_prefix}***",
    )
