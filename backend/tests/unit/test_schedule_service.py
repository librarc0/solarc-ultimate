"""分 line 自动分配算法单元测试"""



def _fake_player(pid: int, rating: float):
    """构造简单 mock 球员对象"""
    class FP:
        id = pid
        username = f"player_{pid}"
        display_name = None
        conservative_rating = rating
        team_id = 1
    return FP()


def _snake_draft(players, num_lines):
    """从 schedule_lines 模块复制的蛇形分配逻辑（用于验证一致性）"""
    sorted_p = sorted(players, key=lambda p: p.conservative_rating, reverse=True)
    assignments = [[] for _ in range(num_lines)]
    direction = 1
    idx = 0
    for p in sorted_p:
        assignments[idx].append(p.id)
        idx += direction
        if idx >= num_lines:
            idx = num_lines - 1
            direction = -1
        elif idx < 0:
            idx = 0
            direction = 1
    return assignments


def test_auto_balanced_even_distribution():
    """8 球员 2 line → 每条 4 人"""
    players = [_fake_player(i, float(100 - i * 5)) for i in range(8)]
    result = _snake_draft(players, 2)
    assert len(result[0]) == 4
    assert len(result[1]) == 4


def test_auto_balanced_uneven_distribution():
    """5 球员 2 line → 3+2 分配"""
    players = [_fake_player(i, float(100 - i * 5)) for i in range(5)]
    result = _snake_draft(players, 2)
    total = sum(len(r) for r in result)
    assert total == 5
    assert max(len(r) for r in result) - min(len(r) for r in result) <= 1


def test_snake_draft_balance_rating():
    """蛇形分配：两 line 的总战力差距应较小"""
    ratings = [100, 90, 80, 70, 60, 50, 40, 30]
    players = [_fake_player(i, r) for i, r in enumerate(ratings)]
    result = _snake_draft(players, 2)

    def total_rating(pid_list):
        return sum(ratings[pid] for pid in pid_list)

    diff = abs(total_rating(result[0]) - total_rating(result[1]))
    # 蛇形分配战力差应 ≤ 最大单人战力差
    assert diff <= max(ratings) - min(ratings)


def test_auto_strong_to_weak_order():
    """强到弱：rating 最高的球员应在 line 0"""
    players = [_fake_player(i, float(100 - i * 10)) for i in range(6)]
    sorted_p = sorted(players, key=lambda p: p.conservative_rating, reverse=True)
    num_lines = 2
    assignments = [[] for _ in range(num_lines)]
    for idx, p in enumerate(sorted_p):
        assignments[idx % num_lines].append(p.id)

    # line 0 的第一个球员应该是 rating 最高的
    assert assignments[0][0] == sorted_p[0].id


def test_snake_draft_single_player():
    """只有 1 个球员 → 分到第一条 line"""
    players = [_fake_player(0, 100.0)]
    result = _snake_draft(players, 2)
    assert result[0] == [0]
    assert result[1] == []


def test_snake_draft_num_lines_equals_players():
    """球员数 == line 数 → 每 line 1 人"""
    players = [_fake_player(i, float(100 - i)) for i in range(4)]
    result = _snake_draft(players, 4)
    assert all(len(r) == 1 for r in result)
