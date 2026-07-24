"""化学值计算器 — 追踪球员搭档协作表现"""
from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class ChemistryUpdate:
    player_a_id: int
    player_b_id: int
    co_matches: int
    co_wins: int
    combo_count: int
    chemistry_score: float
    expected_win_rate: float = 0.0
    synergy_score: float = 0.0


@dataclass
class _PairStat:
    co_matches: int = 0
    co_wins: int = 0
    combo_count: int = 0  # 互相配合得分次数（A 射门 B 助攻，或 B 射门 A 助攻）


@dataclass
class MatchRecord:
    """传入 ChemistryCalculator.update() 所需的比赛摘要"""
    team_a_player_ids: list[int]
    team_b_player_ids: list[int]
    team_a_won: bool  # True 代表 team_a 获胜，False 代表 team_b 获胜或平局
    # 预计算的搭档配合次数：key=(min_id, max_id), value=本场配合次数
    combos: dict[tuple[int, int], int] = field(default_factory=dict)


# 化学值公式权重（默认常量，可被 TeamSettings 覆盖）
CHEM_W1 = 0.7  # 胜率权重
CHEM_W2 = 0.3  # 配合率权重
CHEM_DECAY_CONSTANT = 8.0  # v2 置信衰减常数（约 8 场达到 63% 置信）


def calc_chemistry_score(
    co_matches: int,
    co_wins: int,
    combo_count: int,
    w1: float = CHEM_W1,
    w2: float = CHEM_W2,
) -> float:
    """
    化学值公式 v1（保留兼容）：
        chemistry_score = (胜率 × w1 + 配合率 × w2) × 置信因子

    胜率 = co_wins / co_matches
    配合率 = combo_count / co_matches（每场平均配合次数，归一化后截断到 1.0）
    置信因子 = 1 - 1/sqrt(co_matches + 1)（场次越多，置信度越高）
    """
    if co_matches == 0:
        return 0.0
    win_rate = co_wins / co_matches
    combo_rate = min(combo_count / co_matches, 1.0)
    confidence = 1.0 - 1.0 / math.sqrt(co_matches + 1)
    return (win_rate * w1 + combo_rate * w2) * confidence


def calc_chemistry_v2(
    co_matches: int,
    co_wins: int,
    combo_count: int,
    expected_win_rate: float = 0.5,
    w1: float = CHEM_W1,
    w2: float = CHEM_W2,
    decay_constant: float = CHEM_DECAY_CONSTANT,
) -> tuple[float, float]:
    """
    化学值公式 v2 — Win Above Expected:

        synergy = actual_win_rate - expected_win_rate
        combo_rate = min(combo_count / co_matches, 1.0)
        confidence = 1 - exp(-co_matches / decay_constant)
        chemistry_v2 = max(0, synergy * w1 + combo_rate * w2) * confidence

    返回 (chemistry_score, synergy_score)。
    expected_win_rate 由调用方通过 OpenSkill predict_win 计算提供。
    """
    if co_matches == 0:
        return 0.0, 0.0
    actual_win_rate = co_wins / co_matches
    synergy = actual_win_rate - expected_win_rate
    combo_rate = min(combo_count / co_matches, 1.0)
    confidence = 1.0 - math.exp(-co_matches / decay_constant)
    raw = synergy * w1 + combo_rate * w2
    score = max(0.0, raw) * confidence
    return score, synergy


class ChemistryCalculator:
    """
    计算球员搭档化学值（内存版，用于单元测试和离线计算）。

    只有共同参赛 >= MIN_CO_MATCHES 场的搭档才计入排名。
    线上 DB 写入请使用 rating_service.apply_chemistry()。
    """

    MIN_CO_MATCHES = 3

    def __init__(self) -> None:
        # key: (min_id, max_id) → _PairStat
        self._stats: dict[tuple[int, int], _PairStat] = {}

    @staticmethod
    def _key(a: int, b: int) -> tuple[int, int]:
        return (min(a, b), max(a, b))

    def update(self, record: MatchRecord) -> list[ChemistryUpdate]:
        """
        处理一场比赛，更新所有同队搭档的统计数据。

        返回本场涉及的所有搭档的最新 ChemistryUpdate 列表。
        """
        results: list[ChemistryUpdate] = []

        for team_ids, is_winner in [
            (record.team_a_player_ids, record.team_a_won),
            (record.team_b_player_ids, not record.team_a_won),
        ]:
            pairs = _get_pairs(team_ids)
            for a, b in pairs:
                key = self._key(a, b)
                stat = self._stats.setdefault(key, _PairStat())
                stat.co_matches += 1
                if is_winner:
                    stat.co_wins += 1
                stat.combo_count += record.combos.get(key, 0)
                results.append(
                    ChemistryUpdate(
                        player_a_id=key[0],
                        player_b_id=key[1],
                        co_matches=stat.co_matches,
                        co_wins=stat.co_wins,
                        combo_count=stat.combo_count,
                        chemistry_score=calc_chemistry_score(stat.co_matches, stat.co_wins, stat.combo_count),
                    )
                )

        return results

    def get_score(self, player_a_id: int, player_b_id: int) -> float:
        """获取两名球员当前化学值（不足 MIN_CO_MATCHES 返回 0）"""
        key = self._key(player_a_id, player_b_id)
        stat = self._stats.get(key)
        if stat is None or stat.co_matches < self.MIN_CO_MATCHES:
            return 0.0
        return calc_chemistry_score(stat.co_matches, stat.co_wins, stat.combo_count)

    def get_all_qualified(self) -> list[ChemistryUpdate]:
        """返回所有满足 MIN_CO_MATCHES 条件的搭档列表（按化学值降序）"""
        results = []
        for (a, b), stat in self._stats.items():
            if stat.co_matches >= self.MIN_CO_MATCHES:
                results.append(
                    ChemistryUpdate(
                        player_a_id=a,
                        player_b_id=b,
                        co_matches=stat.co_matches,
                        co_wins=stat.co_wins,
                        combo_count=stat.combo_count,
                        chemistry_score=calc_chemistry_score(stat.co_matches, stat.co_wins, stat.combo_count),
                    )
                )
        results.sort(key=lambda x: x.chemistry_score, reverse=True)
        return results


def _get_pairs(player_ids: list[int]) -> list[tuple[int, int]]:
    """生成列表中所有不重复的两两组合（顺序不重要）"""
    pairs = []
    for i in range(len(player_ids)):
        for j in range(i + 1, len(player_ids)):
            pairs.append((player_ids[i], player_ids[j]))
    return pairs
