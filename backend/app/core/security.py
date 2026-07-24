from datetime import datetime, timezone, timedelta

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings

ALGORITHM = "HS256"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def create_access_token(
    subject: str | int,
    role: str,
    player_id: int | None = None,
) -> str:
    """生成 JWT。

    新格式：sub=user_id，player_id=当前激活 player id（可选）。
    旧版 token（无 player_id）仍可解码，但鉴权层会尝试从 user_id 解析默认 player。
    """
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload: dict = {"sub": str(subject), "role": role, "exp": expire}
    if player_id is not None:
        # player_id 表示当前激活的 player（切队后会更新为新队伍的 player）
        payload["player_id"] = str(player_id)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return {}
