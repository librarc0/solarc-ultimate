# Demo Data

Run the demo seed from `backend/`:

```bash
uv run alembic upgrade head
uv run python scripts/seed_demo.py
```

The seed creates one fictional team, `demo_mix`, with ten fictional players and
six approved matches. It covers:

- Internal score-only match, Level 1.
- Internal goals/assists match, Level 2.
- Internal full-stat matches, Level 3.
- External virtual-opponent matches with different opponent strengths.
- Repeated assist combinations for chemistry ranking examples.

Demo login:

| Username | Password | Role |
| --- | --- | --- |
| `demo_owner` | `Demo@123456` | Owner |
| `demo_admin` | `Demo@123456` | Admin |
| `demo_ace` | `Demo@123456` | Member |
| `demo_handler` | `Demo@123456` | Member |

All demo emails use the reserved `example.invalid` domain.
