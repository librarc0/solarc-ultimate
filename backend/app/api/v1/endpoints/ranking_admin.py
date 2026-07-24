"""排行榜管理员接口（独立 JWT，与 Player 体系隔离）"""
import json
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import verify_password
from app.models.team_ranking import (
    ExternalTeam,
    RankingAdmin,
    RankingApiKey,
    RankingUploadBatch,
    RankingSeason,
    TournamentRecord,
)
from app.schemas.team_ranking import (
    ApiKeyCreated,
    ApiKeyOut,
    RankingAdminToken,
    UploadBatchOut,
    UploadResult,
    RankingsExportPayload,
    SeasonCreate,
    SeasonOut,
    SeasonUpdate,
)
from app.services.ranking_service import generate_api_key, process_rankings_payload, get_latest_season_id

router = APIRouter()

_RANKING_ADMIN_AUD = "ranking_admin"
_oauth2 = OAuth2PasswordBearer(tokenUrl="/api/v1/ranking-admin/login")


# ────────────────────────────────────────
# JWT 辅助
# ────────────────────────────────────────

def _create_ranking_admin_token(admin_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=12)
    payload = {
        "sub": str(admin_id),
        "aud": _RANKING_ADMIN_AUD,
        "exp": expire,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


async def _get_current_ranking_admin(
    token: str = Depends(_oauth2),
    db: AsyncSession = Depends(get_db),
) -> RankingAdmin:
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无效的排行榜管理员令牌",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=["HS256"],
            audience=_RANKING_ADMIN_AUD,
        )
        admin_id = int(payload.get("sub", 0))
    except (JWTError, ValueError):
        raise credentials_exc

    result = await db.execute(select(RankingAdmin).where(RankingAdmin.id == admin_id))
    admin = result.scalar_one_or_none()
    if not admin:
        raise credentials_exc
    return admin


# ────────────────────────────────────────
# 登录
# ────────────────────────────────────────

@router.post("/login", response_model=RankingAdminToken)
async def ranking_admin_login(
    username: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(RankingAdmin).where(RankingAdmin.username == username)
    )
    admin = result.scalar_one_or_none()
    if not admin or not verify_password(password, admin.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )
    token = _create_ranking_admin_token(admin.id)
    return RankingAdminToken(access_token=token)


@router.get("/profile")
async def ranking_admin_profile(
    admin: RankingAdmin = Depends(_get_current_ranking_admin),
):
    return {"id": admin.id, "username": admin.username, "created_at": admin.created_at}


# ────────────────────────────────────────
# 赛季管理
# ────────────────────────────────────────

@router.get("/seasons", response_model=list[SeasonOut])
async def list_seasons_admin(
    admin: RankingAdmin = Depends(_get_current_ranking_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(RankingSeason).order_by(
            RankingSeason.year.desc(), RankingSeason.created_at.desc()
        )
    )
    return [SeasonOut.model_validate(s) for s in result.scalars().all()]


@router.post("/seasons", response_model=SeasonOut, status_code=201)
async def create_season(
    data: SeasonCreate,
    admin: RankingAdmin = Depends(_get_current_ranking_admin),
    db: AsyncSession = Depends(get_db),
):
    season = RankingSeason(
        name=data.name,
        year=data.year,
        start_date=data.start_date,
        end_date=data.end_date,
        description=data.description,
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    db.add(season)
    await db.commit()
    await db.refresh(season)
    return SeasonOut.model_validate(season)


@router.patch("/seasons/{season_id}", response_model=SeasonOut)
async def update_season(
    season_id: int,
    data: SeasonUpdate,
    admin: RankingAdmin = Depends(_get_current_ranking_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(RankingSeason).where(RankingSeason.id == season_id))
    season = result.scalar_one_or_none()
    if not season:
        raise HTTPException(status_code=404, detail="赛季不存在")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(season, field, value)
    await db.commit()
    await db.refresh(season)
    return SeasonOut.model_validate(season)


@router.delete("/seasons/{season_id}", status_code=204)
async def delete_season(
    season_id: int,
    admin: RankingAdmin = Depends(_get_current_ranking_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(RankingSeason).where(RankingSeason.id == season_id))
    season = result.scalar_one_or_none()
    if not season:
        raise HTTPException(status_code=404, detail="赛季不存在")

    # 显式按层次删除，全部加 synchronize_session=False 确保 SQL 语句一定执行，
    # 不依赖 ORM 内存对象跟踪，也不依赖 SQLite PRAGMA CASCADE。
    # 删除顺序：TournamentRecord（按 batch_id）
    #         → TournamentRecord（按 team_id，兜底清理孤儿记录）
    #         → ExternalTeam → RankingUploadBatch → RankingSeason
    await db.execute(
        delete(TournamentRecord).where(
            TournamentRecord.batch_id.in_(
                select(RankingUploadBatch.id).where(RankingUploadBatch.season_id == season_id)
            )
        ).execution_options(synchronize_session=False)
    )
    await db.execute(
        delete(TournamentRecord).where(
            TournamentRecord.team_id.in_(
                select(ExternalTeam.id).where(ExternalTeam.season_id == season_id)
            )
        ).execution_options(synchronize_session=False)
    )
    await db.execute(
        delete(ExternalTeam)
        .where(ExternalTeam.season_id == season_id)
        .execution_options(synchronize_session=False)
    )
    await db.execute(
        delete(RankingUploadBatch)
        .where(RankingUploadBatch.season_id == season_id)
        .execution_options(synchronize_session=False)
    )
    await db.delete(season)
    await db.commit()


# ────────────────────────────────────────
# 数据上传
# ────────────────────────────────────────

@router.post("/upload", response_model=UploadResult)
async def upload_rankings(
    file: UploadFile = File(..., description="JSON 格式的排行榜导出文件"),
    season_id: Optional[int] = Form(None, description="目标赛季 ID，不传默认最新赛季"),
    notes: Optional[str] = Form(None),
    auto_create_season: bool = Form(False, description="True=从 JSON 元信息自动查找/创建赛季"),
    admin: RankingAdmin = Depends(_get_current_ranking_admin),
    db: AsyncSession = Depends(get_db),
):
    """上传排行榜 JSON 文件到指定赛季"""
    if not file.filename or not file.filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="请上传 .json 格式文件")

    content = await file.read()
    try:
        text = content.decode('utf-8-sig')
        data = json.loads(text)
        payload = RankingsExportPayload.model_validate(data)
    except (json.JSONDecodeError, Exception) as e:
        raise HTTPException(status_code=422, detail=f"JSON 解析失败：{e}")

    # auto_create_season：从 JSON 的 season 元信息自动查找/创建赛季
    if auto_create_season and season_id is None and payload.season is not None:
        meta = payload.season
        existing_season = (await db.execute(
            select(RankingSeason).where(
                RankingSeason.year == meta.year,
                RankingSeason.name == meta.name,
            )
        )).scalar_one_or_none()
        if existing_season:
            season_id = existing_season.id
        else:
            new_season = RankingSeason(name=meta.name, year=meta.year, is_active=True)
            db.add(new_season)
            await db.flush()
            season_id = new_season.id

    # 未通过 auto_create_season 确定赛季时，回落到手动指定或最新赛季
    if season_id is None:
        season_id = await get_latest_season_id(db)
    if season_id is None:
        raise HTTPException(status_code=400, detail="尚未创建任何赛季，请先在赛季管理中新建赛季或勾选「自动建立赛季」")

    # 验证赛季存在
    res = await db.execute(select(RankingSeason).where(RankingSeason.id == season_id))
    if not res.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="赛季不存在")

    return await process_rankings_payload(db, payload, source="upload", season_id=season_id, notes=notes)


# ────────────────────────────────────────
# 批次管理
# ────────────────────────────────────────

@router.get("/batches", response_model=list[UploadBatchOut])
async def list_batches(
    season_id: Optional[int] = None,
    admin: RankingAdmin = Depends(_get_current_ranking_admin),
    db: AsyncSession = Depends(get_db),
):
    q = select(RankingUploadBatch).order_by(RankingUploadBatch.uploaded_at.desc())
    if season_id is not None:
        q = q.where(RankingUploadBatch.season_id == season_id)
    result = await db.execute(q)
    return [UploadBatchOut.model_validate(b) for b in result.scalars().all()]


@router.post("/batches/{batch_id}/restore", response_model=UploadResult)
async def restore_batch(
    batch_id: int,
    admin: RankingAdmin = Depends(_get_current_ranking_admin),
    db: AsyncSession = Depends(get_db),
):
    """从历史批次恢复排行榜数据（需要批次包含原始 JSON）"""
    result = await db.execute(
        select(RankingUploadBatch).where(RankingUploadBatch.id == batch_id)
    )
    batch = result.scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=404, detail="批次不存在")
    if not batch.raw_payload:
        raise HTTPException(status_code=422, detail="该批次无原始数据，无法恢复（仅新格式批次支持恢复）")

    data = json.loads(batch.raw_payload)
    payload = RankingsExportPayload.model_validate(data)
    return await process_rankings_payload(
        db,
        payload,
        source="restore",
        season_id=batch.season_id,
        notes=f"恢复自批次 #{batch_id}（{batch.uploaded_at.strftime('%m-%d %H:%M')}）",
    )


@router.delete("/batches/{batch_id}", status_code=204)
async def delete_batch(
    batch_id: int,
    admin: RankingAdmin = Depends(_get_current_ranking_admin),
    db: AsyncSession = Depends(get_db),
):
    """删除一个批次（同时删除关联的 tournament_records，并按该赛季剩余 records 重算排名）"""
    result = await db.execute(
        select(RankingUploadBatch).where(RankingUploadBatch.id == batch_id)
    )
    batch = result.scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=404, detail="批次不存在")

    season_id = batch.season_id
    await db.delete(batch)

    # 重建该赛季 ExternalTeam
    await db.execute(delete(ExternalTeam).where(ExternalTeam.season_id == season_id))

    remaining = await db.execute(
        select(TournamentRecord)
        .join(RankingUploadBatch, TournamentRecord.batch_id == RankingUploadBatch.id)
        .where(RankingUploadBatch.season_id == season_id)
        .order_by(TournamentRecord.batch_id.desc())
    )
    records = remaining.scalars().all()

    if records:
        from collections import defaultdict
        team_map: dict[str, list[TournamentRecord]] = defaultdict(list)
        for r in records:
            team_map[r.team_name].append(r)

        for name, recs in team_map.items():
            wins = sum(r.wins for r in recs)
            losses = sum(r.losses for r in recs)
            draws = sum(r.draws for r in recs)
            forfeits = sum(r.forfeits for r in recs)
            total_games = sum(r.total_games for r in recs)
            points_scored = sum(r.points_scored for r in recs)
            points_conceded = sum(r.points_conceded for r in recs)
            total_score = round(sum(r.computed_score for r in recs), 2)
            avg_score = round(total_score / len(recs), 2) if recs else 0.0

            team = ExternalTeam(
                season_id=season_id,
                name=name,
                rank=0, prev_rank=0, rank_change=0,
                total_score=total_score, avg_score=avg_score,
                tournament_count=len(recs),
                wins=wins, losses=losses, draws=draws, forfeits=forfeits,
                total_games=total_games,
                win_rate=round(wins / total_games, 3) if total_games > 0 else 0.0,
                points_scored=points_scored,
                points_conceded=points_conceded,
                net_points=points_scored - points_conceded,
            )
            db.add(team)

        await db.flush()
        all_teams = await db.execute(
            select(ExternalTeam)
            .where(ExternalTeam.season_id == season_id)
            .order_by(ExternalTeam.total_score.desc())
        )
        for idx, t in enumerate(all_teams.scalars().all(), start=1):
            t.rank = idx

    await db.commit()


# ────────────────────────────────────────
# API Key 管理
# ────────────────────────────────────────

@router.get("/api-keys", response_model=list[ApiKeyOut])
async def list_api_keys(
    admin: RankingAdmin = Depends(_get_current_ranking_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(RankingApiKey).order_by(RankingApiKey.created_at.desc())
    )
    keys = result.scalars().all()
    # 拼接赛季名
    season_ids = {k.season_id for k in keys if k.season_id}
    season_map: dict[int, str] = {}
    if season_ids:
        sres = await db.execute(select(RankingSeason).where(RankingSeason.id.in_(season_ids)))
        for s in sres.scalars().all():
            season_map[s.id] = f"{s.year} · {s.name}"
    out_list = []
    for k in keys:
        d = ApiKeyOut.model_validate(k).model_dump()
        d["season_name"] = season_map.get(k.season_id) if k.season_id else None
        out_list.append(ApiKeyOut(**d))
    return out_list


@router.post("/api-keys", response_model=ApiKeyCreated, status_code=201)
async def create_api_key(
    name: str = Form(..., description="Key 的备注名称"),
    season_id: Optional[int] = Form(None, description="绑定的赛季 ID，不传则不限制赛季"),
    admin: RankingAdmin = Depends(_get_current_ranking_admin),
    db: AsyncSession = Depends(get_db),
):
    """生成新 API Key（完整 key 只返回一次，请妥善保存）"""
    # 验证 season_id
    season_name: Optional[str] = None
    if season_id is not None:
        res = await db.execute(select(RankingSeason).where(RankingSeason.id == season_id))
        season = res.scalar_one_or_none()
        if not season:
            raise HTTPException(status_code=404, detail="赛季不存在")
        season_name = f"{season.year} · {season.name}"

    full_key, prefix, key_hash = generate_api_key()
    key_record = RankingApiKey(
        name=name,
        key_prefix=prefix,
        key_hash=key_hash,
        is_active=True,
        season_id=season_id,
    )
    db.add(key_record)
    await db.commit()
    await db.refresh(key_record)
    out = ApiKeyOut.model_validate(key_record)
    out_dict = out.model_dump()
    out_dict["season_name"] = season_name
    return ApiKeyCreated(**out_dict, full_key=full_key)


@router.delete("/api-keys/{key_id}", status_code=204)
async def revoke_api_key(
    key_id: int,
    admin: RankingAdmin = Depends(_get_current_ranking_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(RankingApiKey).where(RankingApiKey.id == key_id)
    )
    key_record = result.scalar_one_or_none()
    if not key_record:
        raise HTTPException(status_code=404, detail="Key 不存在")
    key_record.is_active = False
    await db.commit()
