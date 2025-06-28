
from passlib.context import CryptContext
from dotenv import dotenv_values
import jwt
from models import User
from fastapi import status
from fastapi.exceptions import HTTPException

# Load environment variables
config_credentials = dotenv_values(".env")


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

async def verify_token(token: str):
    try:
        payload = jwt.decode(token, config_credentials["SECRET_KEY"],algorithms= ["HS256"])
        user = await User.get(id=payload.get("id"))
        
    except:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    return user


async def authenticate_user(username: str, password: str):
    user = await User.get_or_none(username=username)

    if user and verify_password(password, user.password):
        return user

    return None

async def token_generator(username: str, password: str):
    user = await authenticate_user(username, password)

    if user:
        return jwt.encode({"id": user.id}, config_credentials["SECRET_KEY"], algorithm="HS256")

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect username or password",
        headers={"WWW-Authenticate": "Bearer"},
    ) 

    