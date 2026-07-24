# Rating Engine

`app.rating_engine` is the reusable core of SolArc-Ultimate. It is intentionally
implemented with plain dataclasses and does not depend on FastAPI, SQLAlchemy, or
the product database.

## Minimal Usage

```python
from app.rating_engine.engine import MatchData, PlayerRatingInput, RatingEngine

match = MatchData(
    team_a=[
        PlayerRatingInput(player_id=1, mu=25.0, sigma=8.333, goals=4, assists=2),
        PlayerRatingInput(player_id=2, mu=25.0, sigma=8.333, goals=2, assists=4),
    ],
    team_b=[
        PlayerRatingInput(player_id=3, mu=25.0, sigma=8.333, goals=3, assists=1),
        PlayerRatingInput(player_id=4, mu=25.0, sigma=8.333, goals=1, assists=3),
    ],
    team_a_score=6,
    team_b_score=4,
    data_level=2,
)

results = RatingEngine().calculate_internal(match)
```

## CLI Example

From `backend/`:

```bash
uv run python scripts/rating_cli.py examples/rating_match.json
```

The output is a JSON list containing each player's `mu_before`, `sigma_before`,
`mu_after`, `sigma_after`, conservative score, and `delta_mu`.

## Model Notes

SolArc-Ultimate uses the MIT-licensed `openskill` package and the
`PlackettLuce` model. Public documentation should describe this as an
OpenSkill / Weng-Lin style rating system. Do not describe it as a Microsoft
TrueSkill implementation.
