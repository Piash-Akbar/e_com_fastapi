# /home/1.Study/1.ecom_fastapi/bazarghat/main.py
from fileinput import filename
from fastapi import FastAPI, Request, HTTPException, status, BackgroundTasks, Depends # Added BackgroundTasks
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

#Authentication
from authentication import *
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer

#image upload
from fastapi import UploadFile, File, Form
import secrets
from fastapi.staticfiles import StaticFiles
from PIL import Image





app = FastAPI()


oauth_to_scheme = OAuth2PasswordBearer(tokenUrl="token")

#Static Files setup config
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.post("/token")
async def generate_token(form_data: OAuth2PasswordRequestForm = Depends()):
    token = await token_generator(form_data.username, form_data.password)##Eikhane ektu dekha dorkar
    return {"access_token": token, "token_type": "bearer"}

async def get_current_user(token: str = Depends(oauth_to_scheme)) -> User:
    try:
        payload = jwt.decode(token, config_credentials["SECRET_KEY"], algorithms=["HS256"])
        user = await User.get(id=payload.get("id"))
        return user
    except:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )



@app.post("/user/me")
async def user_login(user=Depends(get_current_user)):
    business = await Business.get_or_none(owner=user)
    logo = business.logo
    logo_path = f"http://127.0.0.1:8000/static/images/business/{logo}"
    user_data = await user_pydantic_out.from_tortoise_orm(user)
    return {
        "status": "success",
        "data": {
            "user": user_data,
            "email": user.email,
            "verified": user.is_verified,
            "joined_on": user.join_data.strftime("%B %d, %Y"),
            "logo": logo_path
        },
    }


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

@app.post("/uploadfiles/profile")
async def upload_image(file: UploadFile = File(...), current_user: User = Depends(get_current_user)):
    
    FILE_PATH = "static/images/business"
    filename = file.filename

    extension = filename.split(".")[-1]
    
    if extension not in ["jpg", "jpeg", "png", "gif"]:
        raise HTTPException(status_code=400, detail="Invalid file type")
    
    token_name_img = secrets.token_hex(10) + "." + extension
    generated_img_name = FILE_PATH + "/" + token_name_img
    file_content = await file.read()
    with open(generated_img_name, "wb") as f:
        f.write(file_content)

    #Pillow
    img = Image.open(generated_img_name)
    img = img.resize((400, 400))
    img.save(generated_img_name)
    
    f.close()

    business = await Business.get_or_none(owner=current_user)
    owner = await business.owner

    if owner == current_user:
        business.logo = token_name_img
        await business.save()
    else:
        raise HTTPException(status_code=400, detail="You are not the owner of this business")

    file_url = f"http://127.0.0.1:8000/static/images/business/{token_name_img}"
    return {
        "status": "success","filename": file_url,
        "message": "Image uploaded successfully"
        } 

@app.post("/uploadfiles/product/{product_id}")
async def upload_product_image(
    product_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    FILE_PATH = "static/images/products"
    filename = file.filename

    extension = filename.split(".")[-1]
    if extension not in ["jpg", "jpeg", "png", "gif"]:
        raise HTTPException(status_code=400, detail="Invalid file type")

    token_name_img = secrets.token_hex(10) + "." + extension
    generated_img_name = f"{FILE_PATH}/{token_name_img}"

    file_content = await file.read()
    with open(generated_img_name, "wb") as f:
        f.write(file_content)

    # Pillow
    img = Image.open(generated_img_name)
    img = img.resize((400, 400))
    img.save(generated_img_name)

    # Fetch product and validate ownership
    product = await Product.get_or_none(id=product_id).prefetch_related("business")

    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    business = await product.business  # only use await if it's a relation
    if not business:
        raise HTTPException(status_code=404, detail="Business not found for this product")

    owner = await business.owner
    if owner.id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to update this product"
        )

    # Save image reference
    product.product_image = token_name_img
    await product.save()

    file_url = f"http://127.0.0.1:8000/static/images/products/{token_name_img}"
    return {
        "status": "success",
        "filename": file_url,
        "message": "Image uploaded successfully"
    }


#CRUD Operations
@app.post("/products/")
async def create_product(product: product_pydantic_in, current_user: User = Depends(get_current_user)):
    product = product.dict(exclude_unset=True)

    # Retrieve business associated with the current user
    business = await Business.get_or_none(owner=current_user)
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    # Avoid division by zero
    if product['original_price'] > 0:
        product['percentage_discount'] = round((product['new_price'] / product['original_price']) * 100)
    else:
        product['percentage_discount'] = 0

    # Create product and assign the correct business object
    product_obj = await Product.create(**product, business=business)
    product_obj = await product_pydantic.from_tortoise_orm(product_obj)

    return {"status": "success", "data": product_obj}


#Get all products
@app.get("/products/")
async def get_products():
    response = await product_pydantic.from_queryset(Product.all())
    return {"status": "success", "data": response}

#Get a specific product
@app.get("/products/{product_id}")
async def get_product(product_id: int):
    product = await Product.get_or_none(id=product_id)
    business = await product.business
    owner = await business.owner
    response = await product_pydantic.from_queryset_single(Product.get(id=product_id))
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return {
        "status": "success",
        "data": {
            "product_details": response,
            "business_details": {
                "business_name": business.businessname,
                "owner_name": owner.username,
                "city": business.city,
                "region": business.region,
                "description": business.business_description,
                "logo": f"http://127.0.0.1:8000/static/images/business/{business.logo}",
                "email": owner.email,
                "joined_on": owner.join_data.strftime("%B %d, %Y")
            }
        }
    }

#delete a product
@app.delete("/products/{product_id}")
async def delete_product(product_id: int, current_user: User = Depends(get_current_user)):
    product = await Product.get_or_none(id=product_id)
    business = await product.business
    owner = await business.owner

    if current_user == owner:
        await product.delete()
        return {"status": "success", "message": f"Product {product_id} deleted successfully"}
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not authorized to delete this product")
    





# --- Tortoise-ORM Initialization ---

register_tortoise(
    app,
    db_url="sqlite://db.sqlite3",
    modules={"models": ["models"]}, # Assumes models.py is in the same directory
    generate_schemas=True, # Will create tables if they don't exist
    add_exception_handlers=True,
)