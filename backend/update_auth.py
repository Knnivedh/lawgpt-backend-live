import sys
from pathlib import Path

auth_path = Path(r"c:\Users\LOQ\Downloads\Indian-Family-Law-Assistant-repo\backend\auth.py")
code = auth_path.read_text(encoding="utf-8")

old_block = """_bearer_scheme = HTTPBearer()


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(hours=24))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> User:
    \"\"\"
    FastAPI dependency — decode the Bearer token, look up the user in the DB,
    and return the User ORM object (or raise 401).
    \"\"\"
    token = credentials.credentials
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        user_id: int = payload.get("user_id")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user is None:
            raise credentials_exception
        return user"""

new_block = """_bearer_scheme = HTTPBearer(auto_error=False)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(hours=24))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> User:
    \"\"\"
    FastAPI dependency — decode the Bearer token, look up the user in the DB,
    or fall back to active guest user if unauthenticated.
    \"\"\"
    if credentials and credentials.credentials:
        token = credentials.credentials
        try:
            payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
            user_id: int = payload.get("user_id")
            if user_id is not None:
                async with AsyncSessionLocal() as db:
                    result = await db.execute(select(User).where(User.id == user_id))
                    user = result.scalar_one_or_none()
                    if user is not None:
                        return user
        except JWTError:
            pass

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).limit(1))
        user = result.scalar_one_or_none()
        if user is not None:
            return user
        return User(id=1, email="adv.rajesh@lawgpt.in", hashed_password="")"""

if old_block in code:
    code = code.replace(old_block, new_block, 1)
    auth_path.write_text(code, encoding="utf-8")
    print("SUCCESS: auth.py updated successfully!")
else:
    print("WARNING: old_block not matched in auth.py")
