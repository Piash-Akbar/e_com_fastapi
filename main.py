# /home/1.Study/1.ecom_fastapi/bazarghat/main.py

from fastapi import FastAPI, Request, HTTPException, status, BackgroundTasks # Added BackgroundTasks
from tortoise.contrib.fastapi import register_tortoise
from models import * # Imports User, Business, Product, and pydantic models
# Removed 'uvicorn' import as it's not needed when running via `uvicorn main:app`
from authentication import verify_token, get_password_hash # Assuming authentication.py exists

# Signals
from tortoise.signals import post_save
from typing import List, Optional, Type
from tortoise import BaseDBAsyncClient

# Response classes
from fastapi.responses import HTMLResponse

# Templates
from fastapi.templating import Jinja2Templates

# Email utility
from email_utils import send_verification_email # Import the specific function


app = FastAPI()


# Initialize Jinja2Templates
templates = Jinja2Templates(directory="templates")


# --- Tortoise-ORM Signal Handlers ---

@post_save(User)
async def create_business_and_send_verification_email( # Renamed for clarity
    sender: Type[User],
    instance: User,
    created: bool,
    using_db: "Optional[BaseDBAsyncClient]",
    update_fields: List[str]
) -> None:
    """
    Tortoise-ORM signal handler that runs after a User is saved.
    If a new user is created, it creates a corresponding business
    and sends a verification email.
    """
    if created:
        # Create a business for the new user
        business_obj = await Business.create(businessname=instance.username, owner=instance)
        # Convert to pydantic model (optional, but good for consistent data structure)
        # Note: This line might not be strictly necessary if you're just creating,
        # not immediately returning or processing the pydantic representation.
        await business_pydantic.from_tortoise_orm(business_obj)

        # Send verification email for the new user
        # Signals run within the app's event loop, so awaiting directly here is fine.
        await send_verification_email(email_to=instance.email, instance=instance)


# --- API Endpoints ---

@app.post("/users/", status_code=status.HTTP_201_CREATED) # Add status code for creation
async def create_user(user: user_pydantic_in, background_tasks: BackgroundTasks):
    """
    Registers a new user and sends a verification email in the background.
    """
    user_info = user.dict(exclude_unset=True)
    user_info["password"] = get_password_hash(user_info["password"])
    
    # Check if user with email or username already exists to provide better feedback
    existing_user = await User.get_or_none(email=user_info["email"])
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists."
        )
    existing_user = await User.get_or_none(username=user_info["username"])
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this username already exists."
        )

    user_obj = await User.create(**user_info)
    new_user = await user_pydantic_out.from_tortoise_orm(user_obj) # Use user_pydantic_out for response

    # Add email sending to background tasks for non-blocking execution
    background_tasks.add_task(send_verification_email, email_to=new_user.email, instance=user_obj)

    return {
        "status" : "success",
        "data" : f"Thanks for choosing {new_user.username}, check your email to verify your account"
    }


@app.get("/verify/{token}", response_class=HTMLResponse)
async def verify_user(request: Request, token: str):
    """
    Verifies a user's account using a token from the verification email.
    """
    # Assuming verify_token decodes the token and returns the User object or None/raises error
    user = await verify_token(token) # Your verify_token needs to retrieve the user from DB

    if user and not user.is_verified:
        user.is_verified = True
        await user.save()
        # Return a success HTML page
        return templates.TemplateResponse(
            "verify.html",
            {"request": request, "username": user.username, "message": "Account verified successfully!"}
        )
    elif user and user.is_verified:
        # User is already verified
        return templates.TemplateResponse(
            "verify.html",
            {"request": request, "username": user.username, "message": "Account already verified."}
        )
    
    # If user is None (token invalid/expired) or other issues
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials or token is invalid/expired.",
        headers={"WWW-Authenticate": "Bearer"},
    )


@app.get("/")
async def root():
    """
    Basic root endpoint.
    """
    return {"message": "Hello World"}


# --- Tortoise-ORM Initialization ---

register_tortoise(
    app,
    db_url="sqlite://db.sqlite3",
    modules={"models": ["models"]}, # Assumes models.py is in the same directory
    generate_schemas=True, # Will create tables if they don't exist
    add_exception_handlers=True,
)