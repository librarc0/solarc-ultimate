"""ChemistryCalculator 单元测试"""
import math

from app.rating_engine.chemistry import (
    ChemistryCalculator,
    MatchRecord,
    calc_chemistry_score,
    CHEM_W1,
    CHEM_W2,
)


def _make_record(
    a_ids: list[int],
    b_ids: list[int],
    a_won: bool = True,
    combos: dict[tuple[int, int], int] | None = None,
) -> MatchRecord:
    return MatchRecord(
        team_a_player_ids=a_ids,
        team_b_player_ids=b_ids,
        team_a_won=a_won,
        combos=combos or {},
    )


def _confidence(co_matches: int) -> float:
    return 1.0 - 1.0 / math.sqrt(co_matches + 1)


# ---------------------------------------------------------------------------
# 基础场景
# ---------------------------------------------------------------------------


def test_below_min_co_matches_excluded_from_ranking():
    """不足 3 场共同参赛的搭档，get_score 返回 0，且不出现在 get_all_qualified"""
    calc = ChemistryCalculator()
    for _ in range(2):
        calc.update(_make_record([1, 2], [3, 4], a_won=True))

    assert calc.get_score(1, 2) == 0.0
    assert calc.get_all_qualified() == []


def test_exactly_min_co_matches_included():
    """恰好 3 场时应出现在排行榜"""
    calc = ChemistryCalculator()
    for _ in range(3):
        calc.update(_make_record([1, 2], [3, 4], a_won=True))

    assert calc.get_score(1, 2) > 0.0
    qualified = calc.get_all_qualified()
    assert any(q.player_a_id == 1 and q.player_b_id == 2 for q in qualified)


def test_chemistry_score_formula():
    """验证化学值公式：(win_rate * W1 + combo_rate * W2) * confidence"""
    calc = ChemistryCalculator()
    # 4 场全赢，无配合
    for _ in range(4):
        calc.update(_make_record([1, 2], [3, 4], a_won=True))

    score = calc.get_score(1, 2)
    # win_rate=1.0, combo_rate=0.0, co_matches=4
    expected = (1.0 * CHEM_W1 + 0.0 * CHEM_W2) * _confidence(4)
    assert abs(score - expected) < 1e-9


def test_high_win_rate_pair_beats_low_win_rate_pair():
    """同样场次下，胜率更高的搭档化学值更高"""
    calc = ChemistryCalculator()
    # 搭档 (1,2)：3 场全赢
    for _ in range(3):
        calc.update(_make_record([1, 2], [3, 4], a_won=True))
    # 搭档 (3,4)：3 场全输
    for _ in range(3):
        calc.update(_make_record([1, 2], [3, 4], a_won=True))  # 3,4 仍在 b 队输

    score_12 = calc.get_score(1, 2)
    score_34 = calc.get_score(3, 4)
    assert score_12 > score_34


def test_symmetry():
    """get_score(A, B) == get_score(B, A)"""
    calc = ChemistryCalculator()
    for _ in range(3):
        calc.update(_make_record([10, 20], [30, 40], a_won=True))

    assert calc.get_score(10, 20) == calc.get_score(20, 10)


def test_co_matches_accumulate_bidirectionally():
    """混合胜负记录下，co_matches 累计双向"""
    calc = ChemistryCalculator()
    calc.update(_make_record([1, 2], [3, 4], a_won=True))   # 1,2 赢
    calc.update(_make_record([1, 2], [3, 4], a_won=False))  # 1,2 输
    calc.update(_make_record([1, 2], [3, 4], a_won=True))   # 1,2 赢

    # 3 场，2 赢，无配合
    score = calc.get_score(1, 2)
    expected = ((2 / 3) * CHEM_W1 + 0.0 * CHEM_W2) * _confidence(3)
    assert abs(score - expected) < 1e-9


def test_update_returns_correct_stats():
    """update() 返回的 ChemistryUpdate 包含正确的统计数据和 combo_count"""
    calc = ChemistryCalculator()
    result = calc.update(_make_record([1, 2, 3], [4, 5], a_won=True))

    # team_a 有 3 对: (1,2), (1,3), (2,3)；team_b 有 1 对: (4,5)
    pair_ids = {(r.player_a_id, r.player_b_id) for r in result}
    assert (1, 2) in pair_ids
    assert (1, 3) in pair_ids
    assert (2, 3) in pair_ids
    assert (4, 5) in pair_ids

    for r in result:
        assert r.combo_count == 0  # 无配合数据
        if r.player_a_id in (1, 2, 3) and r.player_b_id in (1, 2, 3):
            assert r.co_wins == 1  # team_a 赢了
        else:
            assert r.co_wins == 0  # team_b 输了


def test_single_player_team_no_pairs():
    """单人队没有搭档，update 返回空列表（单侧）"""
    calc = ChemistryCalculator()
    result = calc.update(_make_record([1], [2], a_won=True))
    # 两队各 1 人，均无组合对
    assert result == []


def test_get_all_qualified_sorted_by_score():
    """get_all_qualified 按化学值降序排列"""
    calc = ChemistryCalculator()
    # (1,2) 3 场全赢 → 高分
    for _ in range(3):
        calc.update(_make_record([1, 2], [3, 4], a_won=True))
    # (3,4) 3 场全输 → 0分
    for _ in range(3):
        calc.update(_make_record([1, 2], [3, 4], a_won=True))  # 3,4 仍输

    qualified = calc.get_all_qualified()
    scores = [q.chemistry_score for q in qualified]
    assert scores == sorted(scores, reverse=True)


# ---------------------------------------------------------------------------
# Combo 配合测试
# ---------------------------------------------------------------------------


def test_combo_increases_chemistry_score():
    """有配合的搭档比无配合同等胜率更高分"""
    calc_no_combo = ChemistryCalculator()
    calc_with_combo = ChemistryCalculator()

    for _ in range(3):
        calc_no_combo.update(_make_record([1, 2], [3, 4], a_won=True))
        calc_with_combo.update(
            _make_record([1, 2], [3, 4], a_won=True, combos={(1, 2): 2})
        )

    score_no = calc_no_combo.get_score(1, 2)
    score_with = calc_with_combo.get_score(1, 2)
    assert score_with > score_no


def test_combo_count_accumulates():
    """combo_count 在多场比赛中累计"""
    calc = ChemistryCalculator()
    calc.update(_make_record([1, 2], [3, 4], a_won=True, combos={(1, 2): 1}))
    calc.update(_make_record([1, 2], [3, 4], a_won=True, combos={(1, 2): 3}))
    calc.update(_make_record([1, 2], [3, 4], a_won=True, combos={}))

    qualified = calc.get_all_qualified()
    pair = next(q for q in qualified if q.player_a_id == 1 and q.player_b_id == 2)
    assert pair.combo_count == 4  # 1 + 3 + 0


def test_combo_rate_capped_at_1():
    """combo_rate 不超过 1.0（防止异常值拉爆分数）"""
    # 3 场每场 10 次配合 → combo_rate = 10/3 > 1, 应被截断到 1.0
    score = calc_chemistry_score(co_matches=3, co_wins=3, combo_count=30)
    # win_rate=1.0, combo_rate=min(10.0,1.0)=1.0
    expected = (1.0 * CHEM_W1 + 1.0 * CHEM_W2) * _confidence(3)
    assert abs(score - expected) < 1e-9


def test_combo_only_counted_for_same_team():
    """跨队配合（A射B助，但B在对方队）不应影响 combo_count"""
    calc = ChemistryCalculator()
    # 玩家1在A队，玩家3在B队 — 他们没有搭档关系
    for _ in range(3):
        calc.update(
            _make_record([1, 2], [3, 4], a_won=True, combos={(1, 3): 5})
        )
    # (1,3) 配合 key 存在，但他们不是同队 — 当 update() 处理 team_a 的 (1,2) 对时，
    # 只查 combos.get((1,2), 0)，所以 (1,3) 配合不会影响 (1,2) 的 combo_count
    pair_12 = next(
        (q for q in calc.get_all_qualified() if q.player_a_id == 1 and q.player_b_id == 2),
        None,
    )
    assert pair_12 is not None
    assert pair_12.combo_count == 0  # (1,3) 的配合不计入 (1,2)
