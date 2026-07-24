"""match_service 关键分支单测：data_level 自动判定"""

from app.schemas.match import MatchPlayerEntry
from app.services.match_service import detect_data_level


def _entry(pid: int, goals=None, assists=None, defenses=None) -> MatchPlayerEntry:
    return MatchPlayerEntry(
        player_id=pid,
        goals=goals,
        assists=assists,
        defenses=defenses,
    )


def test_detect_level_forced_zero():
    entries = [_entry(1, goals=1, assists=1, defenses=1)]
    assert detect_data_level(entries, requested_level=0) == 0


def test_detect_level_full_data_respects_requested_cap():
    entries = [
        _entry(1, goals=1, assists=1, defenses=1),
        _entry(2, goals=0, assists=1, defenses=0),
    ]
    assert detect_data_level(entries, requested_level=3) == 3
    assert detect_data_level(entries, requested_level=2) == 2
    assert detect_data_level(entries, requested_level=1) == 1


def test_detect_level_goals_assists_only_to_level2():
    entries = [
        _entry(1, goals=2, assists=1, defenses=None),
        _entry(2, goals=1, assists=0, defenses=None),
    ]
    assert detect_data_level(entries, requested_level=3) == 2


def test_detect_level_missing_assists_falls_back_to_level1():
    entries = [
        _entry(1, goals=2, assists=None, defenses=1),
        _entry(2, goals=1, assists=0, defenses=0),
    ]
    assert detect_data_level(entries, requested_level=3) == 1
    assert detect_data_level(entries, requested_level=2) == 1
