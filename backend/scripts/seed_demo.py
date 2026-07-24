"""Seed a public demo team with fictional players and matches.

Run from the backend directory after migrations:
    uv run python scripts/seed_demo.py
"""
from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone

from sqlalchemy import select

import app.models  # noqa: F401 - register SQLAlchemy models
import app.models.team_ranking  # noqa: F401 - register ExternalTeam for match FK
from app.core.database import AsyncSessionLocal
from app.core.security import get_password_hash
from app.models.match import TeamSettings
from app.models.membership import PlayerTeamMembership
from app.models.player import Player, PlayerStatus, UserRole
from app.models.team import Team
from app.models.user import User
from app.schemas.match import EventCreate, MatchCreate, MatchPlayerEntry
from app.services.match_service import create_match


DEMO_TEAM_NAME = "demo_mix"
DEMO_PASSWORD = "Demo@123456"

DEMO_PLAYERS = [
    ("demo_owner", "Demo Captain", "F", UserRole.owner),
    ("demo_admin", "Demo Analyst", "M", UserRole.admin),
    ("demo_ace", "River Chen", "F", UserRole.member),
    ("demo_handler", "Kai Lin", "M", UserRole.member),
    ("demo_cutter", "Nova Zhang", "F", UserRole.member),
    ("demo_mark", "Orion Wu", "M", UserRole.member),
    ("demo_deep", "Mika Sun", "F", UserRole.member),
    ("demo_guard", "Leo Tang", "M", UserRole.member),
    ("demo_rookie", "Tao He", "M", UserRole.member),
    ("demo_spark", "Iris Zhou", "F", UserRole.member),
]


def entry(player_id: int, goals: int | None = None, assists: int | None = None,
          defenses: int | None = None, turnovers: int | None = None) -> MatchPlayerEntry:
    return MatchPlayerEntry(
        player_id=player_id,
        goals=goals,
        assists=assists,
        defenses=defenses,
        turnovers=turnovers,
    )


async def ensure_demo_team() -> None:
    async with AsyncSessionLocal() as db:
        existing = await db.execute(select(Team).where(Team.name == DEMO_TEAM_NAME))
        if existing.scalar_one_or_none() is not None:
            print(f"Demo team '{DEMO_TEAM_NAME}' already exists; skipping seed.")
            return

        now = datetime.now(timezone.utc)
        password_hash = get_password_hash(DEMO_PASSWORD)

        team = Team(name=DEMO_TEAM_NAME, is_active=True, is_approved=True)
        db.add(team)
        await db.flush()

        users: dict[str, User] = {}
        players: dict[str, Player] = {}

        owner_username, owner_name, owner_gender, owner_role = DEMO_PLAYERS[0]
        owner_user = User(
            username=owner_username,
            email=f"{owner_username}@example.invalid",
            password_hash=password_hash,
            default_team_id=team.id,
        )
        db.add(owner_user)
        await db.flush()
        owner_player = Player(
            user_id=owner_user.id,
            team_id=team.id,
            username=owner_username,
            email=owner_user.email,
            password_hash=password_hash,
            display_name=owner_name,
            gender=owner_gender,
            role=owner_role,
            status=PlayerStatus.active,
            approved_at=now,
        )
        db.add(owner_player)
        await db.flush()
        users[owner_username] = owner_user
        players[owner_username] = owner_player

        db.add(
            PlayerTeamMembership(
                player_id=owner_player.id,
                team_id=team.id,
                role=owner_role,
                status=PlayerStatus.active,
                approved_at=now,
                approved_by=owner_player.id,
            )
        )
        db.add(TeamSettings(team_id=team.id, updated_by=owner_player.id))

        for username, display_name, gender, role in DEMO_PLAYERS[1:]:
            user = User(
                username=username,
                email=f"{username}@example.invalid",
                password_hash=password_hash,
                default_team_id=team.id,
            )
            db.add(user)
            await db.flush()
            player = Player(
                user_id=user.id,
                team_id=team.id,
                username=username,
                email=user.email,
                password_hash=password_hash,
                display_name=display_name,
                gender=gender,
                role=role,
                status=PlayerStatus.active,
                approved_at=now,
                approved_by=owner_player.id,
            )
            db.add(player)
            await db.flush()
            db.add(
                PlayerTeamMembership(
                    player_id=player.id,
                    team_id=team.id,
                    role=role,
                    status=PlayerStatus.active,
                    approved_at=now,
                    approved_by=owner_player.id,
                )
            )
            users[username] = user
            players[username] = player

        await db.commit()

    await seed_matches()
    print("Seeded demo data.")
    print(f"Team: {DEMO_TEAM_NAME}")
    print(f"Login: demo_owner / {DEMO_PASSWORD}")
    print("Also try: demo_admin, demo_ace, demo_handler with the same password.")


async def seed_matches() -> None:
    async with AsyncSessionLocal() as db:
        rows = await db.execute(select(Player).where(Player.team.has(name=DEMO_TEAM_NAME)))
        players = {p.username: p for p in rows.scalars()}
        owner = players["demo_owner"]
        team_id = owner.team_id
        assert team_id is not None

        p = {name: player.id for name, player in players.items()}

        matches = [
            MatchCreate(
                match_date=date(2026, 1, 10),
                match_type="internal",
                score_us=9,
                score_them=7,
                data_level=1,
                team_a=[
                    entry(p["demo_owner"]), entry(p["demo_ace"]), entry(p["demo_cutter"]),
                    entry(p["demo_guard"]), entry(p["demo_spark"]),
                ],
                team_b=[
                    entry(p["demo_admin"]), entry(p["demo_handler"]), entry(p["demo_mark"]),
                    entry(p["demo_deep"]), entry(p["demo_rookie"]),
                ],
                notes="Demo Level 1 internal match: score-only rating.",
            ),
            MatchCreate(
                match_date=date(2026, 1, 17),
                match_type="internal",
                score_us=11,
                score_them=8,
                data_level=2,
                team_a=[
                    entry(p["demo_ace"], 4, 2), entry(p["demo_handler"], 2, 4),
                    entry(p["demo_cutter"], 3, 1), entry(p["demo_mark"], 1, 2),
                    entry(p["demo_spark"], 1, 1),
                ],
                team_b=[
                    entry(p["demo_owner"], 2, 3), entry(p["demo_admin"], 2, 2),
                    entry(p["demo_guard"], 1, 2), entry(p["demo_deep"], 2, 1),
                    entry(p["demo_rookie"], 1, 0),
                ],
                events=[
                    EventCreate(event_type="goal", team_side="A", player_id=p["demo_ace"], assist_player_id=p["demo_handler"]),
                    EventCreate(event_type="goal", team_side="A", player_id=p["demo_cutter"], assist_player_id=p["demo_ace"]),
                    EventCreate(event_type="goal", team_side="B", player_id=p["demo_owner"], assist_player_id=p["demo_admin"]),
                ],
                notes="Demo Level 2 internal match: goals and assists affect weights.",
            ),
            MatchCreate(
                match_date=date(2026, 1, 24),
                match_type="internal",
                score_us=10,
                score_them=10,
                data_level=3,
                team_a=[
                    entry(p["demo_owner"], 2, 3, 1, 1), entry(p["demo_handler"], 2, 4, 0, 1),
                    entry(p["demo_deep"], 3, 0, 2, 2), entry(p["demo_guard"], 1, 1, 4, 1),
                    entry(p["demo_rookie"], 2, 0, 1, 2),
                ],
                team_b=[
                    entry(p["demo_admin"], 1, 5, 1, 0), entry(p["demo_ace"], 4, 1, 2, 1),
                    entry(p["demo_cutter"], 2, 1, 1, 1), entry(p["demo_mark"], 2, 1, 3, 2),
                    entry(p["demo_spark"], 1, 2, 0, 1),
                ],
                events=[
                    EventCreate(event_type="goal", team_side="A", player_id=p["demo_deep"], assist_player_id=p["demo_handler"]),
                    EventCreate(event_type="defense", team_side="A", player_id=p["demo_guard"]),
                    EventCreate(event_type="turnover", team_side="B", player_id=p["demo_mark"]),
                ],
                notes="Demo Level 3 draw: goals, assists, defenses and turnovers are present.",
            ),
            MatchCreate(
                match_date=date(2026, 2, 1),
                match_type="external",
                score_us=13,
                score_them=9,
                data_level=1,
                opponent_strength=7,
                team_a=[
                    entry(p["demo_owner"]), entry(p["demo_ace"]), entry(p["demo_handler"]),
                    entry(p["demo_cutter"]), entry(p["demo_mark"]), entry(p["demo_deep"]),
                    entry(p["demo_guard"]),
                ],
                team_b=[],
                notes="Demo external match: virtual opponent strength 7.",
            ),
            MatchCreate(
                match_date=date(2026, 2, 8),
                match_type="external",
                score_us=12,
                score_them=14,
                data_level=3,
                opponent_strength=9,
                team_a=[
                    entry(p["demo_owner"], 1, 3, 1, 1), entry(p["demo_admin"], 2, 3, 0, 2),
                    entry(p["demo_ace"], 4, 1, 2, 1), entry(p["demo_handler"], 2, 4, 1, 2),
                    entry(p["demo_cutter"], 2, 1, 1, 1), entry(p["demo_mark"], 1, 0, 3, 1),
                    entry(p["demo_deep"], 0, 0, 2, 1),
                ],
                team_b=[],
                events=[
                    EventCreate(event_type="goal", team_side="A", player_id=p["demo_ace"], assist_player_id=p["demo_handler"], is_break=True),
                    EventCreate(event_type="defense", team_side="A", player_id=p["demo_mark"]),
                    EventCreate(event_type="turnover", team_side="A", player_id=p["demo_admin"]),
                ],
                notes="Demo external loss: strong virtual opponent, full stats.",
            ),
            MatchCreate(
                match_date=date(2026, 2, 15),
                match_type="internal",
                score_us=13,
                score_them=11,
                data_level=3,
                team_a=[
                    entry(p["demo_admin"], 1, 5, 2, 0), entry(p["demo_ace"], 5, 1, 2, 1),
                    entry(p["demo_guard"], 1, 1, 5, 1), entry(p["demo_rookie"], 3, 0, 1, 2),
                    entry(p["demo_spark"], 3, 2, 0, 1),
                ],
                team_b=[
                    entry(p["demo_owner"], 2, 3, 2, 1), entry(p["demo_handler"], 2, 5, 0, 2),
                    entry(p["demo_cutter"], 3, 1, 1, 2), entry(p["demo_mark"], 2, 0, 4, 1),
                    entry(p["demo_deep"], 2, 1, 2, 2),
                ],
                events=[
                    EventCreate(event_type="goal", team_side="A", player_id=p["demo_ace"], assist_player_id=p["demo_admin"]),
                    EventCreate(event_type="goal", team_side="A", player_id=p["demo_spark"], assist_player_id=p["demo_admin"]),
                    EventCreate(event_type="defense", team_side="A", player_id=p["demo_guard"]),
                ],
                notes="Demo Level 3 internal match: chemistry pairs have repeated events.",
            ),
        ]

        for body in matches:
            await create_match(db, body, created_by_id=owner.id, team_id=team_id, auto_approve=True)


def main() -> None:
    asyncio.run(ensure_demo_team())


if __name__ == "__main__":
    main()
