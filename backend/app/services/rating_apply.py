"""Rating apply orchestration: compute, persist, and update chemistry."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.match import (
    EventType,
    Match,
    MatchEvent,
    MatchPlayer,
    PlayerChemistry,
    RatingHistory,
    TeamSettings,
)
from app.models.player import Player
from app.rating_engine.chemistry import calc_chemistry_v2
from app.rating_engine.engine import MatchData, PlayerRatingInput, RatingEngine, conservative_score
from app.services.rating_adjustments import (
    compute_total_bonus,
    compute_turnover_penalty,
    resolve_adjustment_coefficients,
)
from app.services.rating_settings import build_engine_settings


async def apply_ratings(
    db: AsyncSession,
    match: Match,
    operated_by: int,
    participants: list[MatchPlayer] | None = None,
    reason: str = "match_result",
) -> None:
    """
    调用 RatingEngine，将结果写回 MatchPlayer 和 Player，并追加 RatingHistory。

    participants: 可直接传入，避免触发 lazy-load。
    """
    if participants is None:
        parts_result = await db.execute(
            select(MatchPlayer).where(MatchPlayer.match_id == match.id)
        )
        participants = list(parts_result.scalars())

    ts_result = await db.execute(
        select(TeamSettings)
        .where(TeamSettings.team_id == match.team_id)
        .order_by(TeamSettings.id.desc())
        .limit(1)
    )
    ts = ts_result.scalar_one_or_none()
    settings = build_engine_settings(ts)
    engine = RatingEngine(settings)

    participant_ids = [p.player_id for p in participants]
    players_result = await db.execute(
        select(Player).where(Player.id.in_(participant_ids)).with_for_update()
    )
    player_map: dict[int, Player] = {p.id: p for p in players_result.scalars()}

    team_a_inputs = []
    team_b_inputs = []
    for mp in participants:
        p = player_map[mp.player_id]
        inp = PlayerRatingInput(
            player_id=p.id,
            mu=p.mu,
            sigma=p.sigma,
            goals=mp.goals,
            assists=mp.assists,
            defenses=mp.defenses,
        )
        if mp.team_side.value == "A":
            team_a_inputs.append(inp)
        else:
            team_b_inputs.append(inp)

    match_data = MatchData(
        team_a=team_a_inputs,
        team_b=team_b_inputs,
        team_a_score=match.team_a_score,
        team_b_score=match.team_b_score,
        data_level=match.data_level,
    )

    if match.match_type.value == "internal":
        outputs = engine.calculate_internal(match_data)
    else:
        strength = match.opponent_strength or 5
        cal_mu = getattr(match, 'opponent_calibrated_mu', None)
        cal_sigma = getattr(match, 'opponent_calibrated_sigma', None)
        outputs = engine.calculate_external(
            match_data, strength,
            calibrated_mu=cal_mu,
            calibrated_sigma=cal_sigma,
        )

    if not outputs:
        return

    output_map = {o.player_id: o for o in outputs}
    side_map = {mp.player_id: mp.team_side.value for mp in participants}

    if match.team_a_score > match.team_b_score:
        winner_side = "A"
    elif match.team_b_score > match.team_a_score:
        winner_side = "B"
    else:
        winner_side = None

    universe_point_players: set[int] = set()
    if abs(match.team_a_score - match.team_b_score) == 1:
        uni_result = await db.execute(
            select(MatchEvent).where(
                MatchEvent.match_id == match.id,
                MatchEvent.event_type == EventType.goal,
                MatchEvent.is_universe_point == True,  # noqa: E712
                MatchEvent.player_id.isnot(None),
            )
        )
        for ue in uni_result.scalars():
            if ue.player_id:
                universe_point_players.add(ue.player_id)

    dline_ev_count: dict[int, int] = {}
    if match.match_type.value == "external":
        dline_goal_result = await db.execute(
            select(MatchEvent).where(
                MatchEvent.match_id == match.id,
                MatchEvent.event_type == EventType.goal,
                MatchEvent.is_break == True,  # noqa: E712
                MatchEvent.player_id.isnot(None),
            )
        )
        for ev in dline_goal_result.scalars():
            if ev.player_id:
                dline_ev_count[ev.player_id] = dline_ev_count.get(ev.player_id, 0) + 1
            if ev.assist_player_id:
                dline_ev_count[ev.assist_player_id] = (
                    dline_ev_count.get(ev.assist_player_id, 0) + 1
                )

        dline_def_result = await db.execute(
            select(MatchEvent).where(
                MatchEvent.match_id == match.id,
                MatchEvent.event_type == EventType.defense,
                MatchEvent.player_id.isnot(None),
            )
        )
        for ev in dline_def_result.scalars():
            if ev.player_id:
                dline_ev_count[ev.player_id] = dline_ev_count.get(ev.player_id, 0) + 1

    to_ev_result = await db.execute(
        select(MatchEvent).where(
            MatchEvent.match_id == match.id,
            MatchEvent.event_type == EventType.turnover,
            MatchEvent.player_id.isnot(None),
        )
    )
    to_count: dict[int, int] = {}
    for te in to_ev_result.scalars():
        if te.player_id:
            to_count[te.player_id] = to_count.get(te.player_id, 0) + 1

    adjustment_coefficients = resolve_adjustment_coefficients(ts)

    for mp in participants:
        out = output_map.get(mp.player_id)
        if not out:
            continue
        p = player_map[mp.player_id]
        side = side_map[mp.player_id]

        total_bonus = compute_total_bonus(
            player_id=p.id,
            universe_point_players=universe_point_players,
            dline_event_count=dline_ev_count,
            coefficients=adjustment_coefficients,
        )

        n_to = to_count.get(p.id, 0) if to_count else (mp.turnovers or 0)
        to_penalty_mu = compute_turnover_penalty(
            turnover_count=n_to,
            coefficients=adjustment_coefficients,
        )

        final_mu = out.mu_after + total_bonus - to_penalty_mu
        final_sigma = out.sigma_after
        final_conservative = conservative_score(final_mu, final_sigma)

        mp.mu_after = final_mu
        mp.sigma_after = final_sigma
        mp.is_winner = (winner_side is not None and side == winner_side)

        # 自动计算正负值（得分差），并嵌入 match_player
        score_diff = (
            (match.team_a_score - match.team_b_score)
            if side == "A"
            else (match.team_b_score - match.team_a_score)
        )
        mp.plus_minus = score_diff

        p.mu = final_mu
        p.sigma = final_sigma
        p.conservative_rating = final_conservative
        p.total_matches += 1
        if mp.is_winner:
            p.total_wins += 1
        if mp.goals:
            p.total_goals += mp.goals
        if mp.assists:
            p.total_assists += mp.assists
        if mp.defenses:
            p.total_defenses += mp.defenses
        p.total_plus_minus += score_diff
        if mp.turnovers:
            p.total_turnovers += mp.turnovers


        rh = RatingHistory(
            player_id=p.id,
            match_id=match.id,
            mu_before=out.mu_before,
            sigma_before=out.sigma_before,
            mu_after=final_mu,
            sigma_after=final_sigma,
            conservative_before=out.conservative_before,
            conservative_after=final_conservative,
            delta_mu=out.delta_mu + total_bonus - to_penalty_mu,
            reason=reason,
            operated_by=operated_by,
        )
        db.add(rh)

    await db.flush()
    await _apply_chemistry(db, match, participants, winner_side, ts)


async def _apply_chemistry(
    db: AsyncSession,
    match: Match,
    participants: list[MatchPlayer],
    winner_side: str | None,
    ts: TeamSettings | None = None,
) -> None:
    events_result = await db.execute(
        select(MatchEvent).where(
            MatchEvent.match_id == match.id,
            MatchEvent.event_type == EventType.goal,
            MatchEvent.assist_player_id.is_not(None),
        )
    )
    events = list(events_result.scalars())

    combo_map: dict[tuple[int, int], int] = {}
    for e in events:
        if e.player_id and e.assist_player_id:
            key = (min(e.player_id, e.assist_player_id), max(e.player_id, e.assist_player_id))
            combo_map[key] = combo_map.get(key, 0) + 1

    team_a_ids = [mp.player_id for mp in participants if mp.team_side.value == "A"]
    team_b_ids = [mp.player_id for mp in participants if mp.team_side.value == "B"]

    def _pairs(team_ids: list[int]) -> set[tuple[int, int]]:
        pairs: set[tuple[int, int]] = set()
        for i in range(len(team_ids)):
            for j in range(i + 1, len(team_ids)):
                a = min(team_ids[i], team_ids[j])
                b = max(team_ids[i], team_ids[j])
                pairs.add((a, b))
        return pairs

    all_pairs = _pairs(team_a_ids) | _pairs(team_b_ids)
    if all_pairs:
        existing_result = await db.execute(
            select(PlayerChemistry).where(
                PlayerChemistry.team_id == match.team_id,
                tuple_(PlayerChemistry.player_a_id, PlayerChemistry.player_b_id).in_(list(all_pairs)),
            )
        )
        chem_map: dict[tuple[int, int], PlayerChemistry] = {
            (c.player_a_id, c.player_b_id): c for c in existing_result.scalars()
        }
    else:
        chem_map = {}

    chem_w1 = ts.chemistry_win_weight if ts else 0.7
    chem_w2 = ts.chemistry_combo_weight if ts else 0.3
    chem_decay = getattr(ts, 'chemistry_decay_constant', 8.0) if ts else 8.0
    now = datetime.now(timezone.utc)

    for team_ids, is_winner in [
        (team_a_ids, winner_side == "A"),
        (team_b_ids, winner_side == "B"),
    ]:
        for i in range(len(team_ids)):
            for j in range(i + 1, len(team_ids)):
                a = min(team_ids[i], team_ids[j])
                b = max(team_ids[i], team_ids[j])
                pair_key = (a, b)

                chem = chem_map.get(pair_key)
                if chem is None:
                    chem = PlayerChemistry(
                        player_a_id=a,
                        player_b_id=b,
                        team_id=match.team_id,
                        co_matches=0,
                        co_wins=0,
                        combo_count=0,
                        chemistry_score=0.0,
                        expected_win_rate=0.5,
                        synergy_score=0.0,
                    )
                    db.add(chem)
                    chem_map[pair_key] = chem

                chem.co_matches += 1
                if is_winner:
                    chem.co_wins += 1
                chem.combo_count += combo_map.get(pair_key, 0)

                # v2: expected_win_rate 暂用 0.5 基准，后续可接入 predict_win
                existing_ewr = getattr(chem, 'expected_win_rate', 0.5) or 0.5
                score, synergy = calc_chemistry_v2(
                    chem.co_matches,
                    chem.co_wins,
                    chem.combo_count,
                    expected_win_rate=existing_ewr,
                    w1=chem_w1,
                    w2=chem_w2,
                    decay_constant=chem_decay,
                )
                chem.chemistry_score = score
                chem.synergy_score = synergy
                chem.updated_at = now

    await db.flush()
