"""
ranking_service.py
处理排行榜 JSON 的导入、存储和排名计算逻辑。
"""
import hashlib
import math
import secrets
from datetime import datetime, timezone

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.team_ranking import (
    ExternalTeam,
    RankingUploadBatch,
    RankingSeason,
    TournamentRecord,
    RankingApiKey,
)
from app.schemas.team_ranking import RankingsExportPayload, UploadResult


# ────────────────────────────────────────
# 积分映射到对手强度（外战录入用）
# ────────────────────────────────────────

def map_score_to_strength(score: float, min_score: float, max_score: float) -> float:
    """线性映射到 1.0–10.0，保留 1 位小数"""
    if max_score <= min_score:
        return 5.0
    strength = 1.0 + (score - min_score) / (max_score - min_score) * 9.0
    strength = max(1.0, min(10.0, strength))
    return round(strength, 1)


# ────────────────────────────────────────
# v2: 自适应校准（联动联盟排行榜）
# ────────────────────────────────────────

def calibrate_opponent(
    opponent_rank: int,
    total_teams: int,
    team_avg_mu: float,
    calibration_range: float = 20.0,
    base_sigma: float = 8.333,
    opponent_tournament_count: int = 0,
) -> tuple[float, float]:
    """
    自适应校准虚拟对手的 μ 和 σ。

    - percentile: 对手在联盟中的百分位排名（1=最强, 0=最弱）
    - calibrated_mu: 以本队平均 mu 为锚点，按百分位拉伸
    - calibrated_sigma: 对手参赛越多越确定

    返回 (calibrated_mu, calibrated_sigma)。
    """
    if total_teams <= 1:
        percentile = 0.5
    else:
        percentile = 1.0 - (opponent_rank - 1) / (total_teams - 1)

    calibrated_mu = team_avg_mu + (percentile - 0.5) * calibration_range
    calibrated_sigma = base_sigma / math.sqrt(1 + opponent_tournament_count / 5.0)

    return round(calibrated_mu, 4), round(calibrated_sigma, 4)


# ────────────────────────────────────────
# 赛季辅助函数
# ────────────────────────────────────────

async def get_latest_season_id(session: AsyncSession) -> int | None:
    """返回 created_at 最新的赛季 id；若无赛季返回 None"""
    result = await session.execute(
        select(RankingSeason).order_by(RankingSeason.created_at.desc()).limit(1)
    )
    season = result.scalar_one_or_none()
    return season.id if season else None


# ────────────────────────────────────────
# 主入口：处理上传数据
# ────────────────────────────────────────

async def process_rankings_payload(
    session: AsyncSession,
    payload: RankingsExportPayload,
    source: str,
    season_id: int,
    notes: str | None = None,
) -> UploadResult:
    """
    处理一次完整的排名上传/推送（针对指定赛季）：
    1. 创建 batch 记录
    2. 清空并重建该赛季的 ExternalTeam 和 TournamentRecord
    3. 更新排名变化（rank_change，与同赛季上次数据对比）
    """
    # 1. 先保存旧排名（只读同赛季数据）
    old_ranks: dict[str, int] = {}
    existing = await session.execute(
        select(ExternalTeam).where(ExternalTeam.season_id == season_id)
    )
    for team in existing.scalars():
        old_ranks[team.name] = team.rank

    # 2. 创建 batch
    batch = RankingUploadBatch(
        season_id=season_id,
        source=source,
        notes=notes,
        record_count=sum(len(r.tournaments) for r in payload.rankings),
        exported_at=payload.exportedAt,
        raw_payload=payload.model_dump_json(),
    )
    session.add(batch)
    await session.flush()  # 获取 batch.id

    # 3. 删除该赛季旧数据
    # 先显式删除 tournament_record（按 team_id），再删除 ExternalTeam。
    # 不依赖 ORM cascade 或 SQLite PRAGMA foreign_keys，避免孤儿数据。
    await session.execute(
        delete(TournamentRecord).where(
            TournamentRecord.team_id.in_(
                select(ExternalTeam.id).where(ExternalTeam.season_id == season_id)
            )
        ).execution_options(synchronize_session=False)
    )
    await session.execute(
        delete(ExternalTeam)
        .where(ExternalTeam.season_id == season_id)
        .execution_options(synchronize_session=False)
    )
    await session.flush()

    # 4. 写入新数据
    # 若 JSON 中没有 rank 字段，则按 totalScore 降序自动分配排名
    ranked_rankings = sorted(payload.rankings, key=lambda r: r.totalScore, reverse=True)
    for idx, item in enumerate(ranked_rankings):
        computed_rank: int = item.rank if item.rank is not None else (idx + 1)
        team = ExternalTeam(
            season_id=season_id,
            name=item.name,
            rank=computed_rank,
            prev_rank=old_ranks.get(item.name, 0),
            rank_change=old_ranks.get(item.name, computed_rank) - computed_rank
            if item.name in old_ranks else 0,
            total_score=round(item.totalScore, 2),
            avg_score=round(item.avgScore, 2),
            tournament_count=item.tournamentCount,
            wins=item.wins,
            losses=item.losses,
            draws=item.draws,
            forfeits=item.forfeits,
            total_games=item.totalGames,
            win_rate=round(item.winRate, 3),
            points_scored=item.pointsScored,
            points_conceded=item.pointsConceded,
            net_points=item.netPoints,
            province=item.province,
            city=item.city,
            last_updated=datetime.now(timezone.utc),
        )
        session.add(team)
        await session.flush()  # 获取 team.id

        for t in item.tournaments:
            record = TournamentRecord(
                batch_id=batch.id,
                team_id=team.id,
                team_name=item.name,
                tournament_name=t.tournamentName,
                level=t.level,
                month=t.month,
                wins=t.wins,
                losses=t.losses,
                draws=t.draws,
                forfeits=t.forfeits,
                total_games=t.totalGames,
                win_rate=round(t.winRate, 3),
                points_scored=t.pointsScored,
                points_conceded=t.pointsConceded,
                pool=t.pool,
                final_rank=t.rank,
                computed_score=round(t.score, 2),
            )
            session.add(record)

    await session.commit()

    # 5. 超出 10 条批次时，删除该赛季最旧的（每赛季最多保留 10 条）
    all_batches_result = await session.execute(
        select(RankingUploadBatch)
        .where(RankingUploadBatch.season_id == season_id)
        .order_by(RankingUploadBatch.uploaded_at.desc())
    )
    all_batches_list = all_batches_result.scalars().all()
    if len(all_batches_list) > 10:
        old_batch_ids = [b.id for b in all_batches_list[10:]]
        # 先显式删除关联的 tournament_record，再删除超出的 batch
        await session.execute(
            delete(TournamentRecord)
            .where(TournamentRecord.batch_id.in_(old_batch_ids))
            .execution_options(synchronize_session=False)
        )
        await session.execute(
            delete(RankingUploadBatch)
            .where(RankingUploadBatch.id.in_(old_batch_ids))
            .execution_options(synchronize_session=False)
        )
        await session.commit()

    # 查询赛季名称用于返回给前端
    season_row = (await session.execute(
        select(RankingSeason).where(RankingSeason.id == season_id)
    )).scalar_one_or_none()

    return UploadResult(
        teams_processed=len(payload.rankings),
        batch_id=batch.id,
        season_id=season_id,
        season_name=season_row.name if season_row else None,
        message="Rankings updated successfully",
    )


# ────────────────────────────────────────
# API Key 工具函数
# ────────────────────────────────────────

def generate_api_key() -> tuple[str, str, str]:
    """
    生成一个安全的 API Key。
    返回 (full_key, prefix, hash)
    full_key 格式：ep_<32位随机字符串>
    """
    random_part = secrets.token_urlsafe(32)
    full_key = f"ep_{random_part}"
    prefix = full_key[:8]  # "ep_" + 5位
    key_hash = hashlib.sha256(full_key.encode()).hexdigest()
    return full_key, prefix, key_hash


def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


async def verify_api_key(session: AsyncSession, raw_key: str) -> RankingApiKey | None:
    """验证 API Key，有效则更新 last_used_at 并返回记录，否则返回 None"""
    key_hash = hash_api_key(raw_key)
    result = await session.execute(
        select(RankingApiKey).where(
            RankingApiKey.key_hash == key_hash,
            RankingApiKey.is_active == True,  # noqa: E712
        )
    )
    key_record = result.scalar_one_or_none()
    if key_record:
        key_record.last_used_at = datetime.now(timezone.utc)
        await session.commit()
    return key_record
