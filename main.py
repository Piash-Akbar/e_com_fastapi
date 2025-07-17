# Organized FastAPI App with Tags and Routers
from fastapi import FastAPI, Request, HTTPException, status, BackgroundTasks, Depends, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from tortoise.contrib.fastapi import register_tortoise
from tortoise.signals import post_save
from tortoise import BaseDBAsyncClient
from typing import List, Optional, Type

from PIL import Image
import os
import secrets

from models import *
from authentication import verify_token, get_password_hash, token_generator
from email_utils import send_verification_email

app = FastAPI(
    title="E-Commerce API",
    description="API for authentication, product management, and business operations",
    version="1.0.0",
    openapi_tags=[
        {"name": "Authentication", "description": "User registration, login, and verification."},
        {"name": "Business", "description": "Manage business profiles and ownership."},
        {"name": "Products", "description": "CRUD operations for products."},
        {"name": "Uploads", "description": "Image uploads for profile and products."},
        {"name": "Users", "description": "Admin-level user queries."},
    ]
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

# Auth scheme
oauth_to_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Templates
templates = Jinja2Templates(directory="templates")

@app.post("/token", tags=["Authentication"])
async def generate_token(form_data: OAuth2PasswordRequestForm = Depends()):
    token = await token_generator(form_data.username, form_data.password)
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

@app.post("/users/", tags=["Authentication"])
async def create_user(user: user_pydantic_in, background_tasks: BackgroundTasks):
    user_info = user.dict(exclude_unset=True)
    user_info["password"] = get_password_hash(user_info["password"])

    if await User.get_or_none(email=user_info["email"]):
        raise HTTPException(status_code=409, detail="User with this email already exists.")
    if await User.get_or_none(username=user_info["username"]):
        raise HTTPException(status_code=409, detail="User with this username already exists.")

    user_obj = await User.create(**user_info)
    new_user = await user_pydantic_out.from_tortoise_orm(user_obj)

    background_tasks.add_task(send_verification_email, email_to=new_user.email, instance=user_obj)
    return {"status": "success", "data": f"Thanks for choosing {new_user.username}, check your email to verify your account"}

@app.get("/verify/{token}", response_class=HTMLResponse, tags=["Authentication"])
async def verify_user(request: Request, token: str):
    user = await verify_token(token)
    if user and not user.is_verified:
        user.is_verified = True
        await user.save()
        return templates.TemplateResponse("verify.html", {"request": request, "username": user.username, "message": "Account verified successfully!"})
    elif user and user.is_verified:
        return templates.TemplateResponse("verify.html", {"request": request, "username": user.username, "message": "Account already verified."})
    raise HTTPException(status_code=401, detail="Invalid or expired token.")

@app.post("/user/me", tags=["Authentication"])
async def user_login(user=Depends(get_current_user)):
    business = await Business.get_or_none(owner=user)
    logo = business.logo
    logo_path = f"https://e-com-fastapi.onrender.com/static/images/business/{logo}"
    user_data = await user_pydantic_out.from_tortoise_orm(user)
    return {
        "status": "success",
        "data": {
            "user": user_data,
            "email": user.email,
            "verified": user.is_verified,
            "joined_on": user.join_data.strftime("%B %d, %Y"),
            "logo": logo_path
        }
    }

@app.post("/uploadfiles/profile", tags=["Uploads"])
async def upload_image(file: UploadFile = File(...), current_user: User = Depends(get_current_user)):
    FILE_PATH = "static/images/business"
    extension = file.filename.split(".")[-1]
    if extension not in ["jpg", "jpeg", "png", "gif"]:
        raise HTTPException(status_code=400, detail="Invalid file type")

    token_name_img = secrets.token_hex(10) + "." + extension
    generated_img_name = f"{FILE_PATH}/{token_name_img}"
    with open(generated_img_name, "wb") as f:
        f.write(await file.read())

    img = Image.open(generated_img_name).resize((400, 400))
    img.save(generated_img_name)

    business = await Business.get_or_none(owner=current_user)
    if await business.owner != current_user:
        raise HTTPException(status_code=400, detail="You are not the owner of this business")

    business.logo = token_name_img
    await business.save()

    return {
        "status": "success",
        "filename": f"https://e-com-fastapi.onrender.com/static/images/business/{token_name_img}",
        "message": "Image uploaded successfully"
    }

@app.post("/uploadfiles/product/{product_id}", tags=["Uploads"])
async def upload_product_image(product_id: int, file: UploadFile = File(...), current_user: User = Depends(get_current_user)):
    FILE_PATH = "static/images/products"
    extension = file.filename.split(".")[-1]
    if extension not in ["jpg", "jpeg", "png", "gif"]:
        raise HTTPException(status_code=400, detail="Invalid file type")

    token_name_img = secrets.token_hex(10) + "." + extension
    generated_img_name = f"{FILE_PATH}/{token_name_img}"
    with open(generated_img_name, "wb") as f:
        f.write(await file.read())

    img = Image.open(generated_img_name).resize((400, 400))
    img.save(generated_img_name)

    product = await Product.get(id=product_id).prefetch_related("business")
    if (await product.business).owner.id != current_user.id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    product.product_image = token_name_img
    await product.save(update_fields=["product_image"])

    return {
        "status": "success",
        "filename": f"https://e-com-fastapi.onrender.com/static/images/products/{token_name_img}",
        "message": "Image uploaded successfully"
    }

@app.post("/products/", tags=["Products"])
async def create_product(product: product_pydantic_in, current_user: User = Depends(get_current_user)):
    product = product.dict(exclude_unset=True)
    business = await Business.get_or_none(owner=current_user)
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    product['percentage_discount'] = round((product['new_price'] / product['original_price']) * 100) if product['original_price'] > 0 else 0
    product_obj = await Product.create(**product, business=business)
    return {"status": "success", "data": await product_pydantic.from_tortoise_orm(product_obj)}

@app.get("/products/", tags=["Products"])
async def get_products():
    return {"status": "success", "data": await product_pydantic.from_queryset(Product.all())}

@app.get("/products/{product_id}", tags=["Products"])
async def get_product(product_id: int):
    product = await Product.get_or_none(id=product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    business = await product.business
    owner = await business.owner
    return {
        "status": "success",
        "data": {
            "product_details": await product_pydantic.from_queryset_single(Product.get(id=product_id)),
            "business_details": {
                "business_name": business.businessname,
                "owner_name": owner.username,
                "city": business.city,
                "region": business.region,
                "description": business.business_description,
                "logo": f"https://e-com-fastapi.onrender.com/static/images/business/{business.logo}",
                "email": owner.email,
                "joined_on": owner.join_data.strftime("%B %d, %Y")
            }
        }
    }

@app.delete("/products/{product_id}", tags=["Products"])
async def delete_product(product_id: int, current_user: User = Depends(get_current_user)):
    product = await Product.get_or_none(id=product_id)
    if await (await product.business).owner != current_user:
        raise HTTPException(status_code=403, detail="Unauthorized")
    await product.delete()
    return {"status": "success", "message": f"Product {product_id} deleted successfully"}

@app.put("/products/{product_id}", tags=["Products"])
async def update_product(product_id: int, product: product_pydantic_in, current_user: User = Depends(get_current_user)):
    product_data = product.dict(exclude_unset=True)
    business = await Business.get_or_none(owner=current_user)
    product_in_db = await Product.get_or_none(id=product_id).prefetch_related("business")

    if not product_in_db or product_in_db.business_id != business.id:
        raise HTTPException(status_code=403, detail="Unauthorized")

    if 'original_price' in product_data and 'new_price' in product_data:
        product_data['percentage_discount'] = round((product_data['new_price'] / product_data['original_price']) * 100)

    await Product.filter(id=product_id).update(**product_data)
    return {"status": "success", "data": await product_pydantic.from_tortoise_orm(await Product.get(id=product_id))}

@app.get("/business/", tags=["Business"])
async def get_businesses():
    return {"status": "success", "data": await business_pydantic.from_queryset(Business.all())}

@app.delete("/business/{business_id}", tags=["Business"])
async def delete_business(business_id: int, current_user: User = Depends(get_current_user)):
    business = await Business.get_or_none(id=business_id)
    if not business or business.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Unauthorized")
    await business.delete()
    return {"status": "success", "message": f"Business {business_id} deleted successfully"}

@app.put("/business/{business_id}", tags=["Business"])
async def update_business(business_id: int, business: business_pydantic_in, current_user: User = Depends(get_current_user)):
    data = business.dict(exclude_unset=True)
    biz = await Business.get_or_none(id=business_id)
    if not biz or biz.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Unauthorized")
    await Business.filter(id=business_id).update(**data)
    return {"status": "success", "data": await business_pydantic.from_tortoise_orm(await Business.get(id=business_id))}

@app.get("/", tags=["Root"])
async def root():
    return {"message": "Hello World"}

@app.get("/users/", tags=["Users"])
async def get_users():
    return {"status": "success", "data": await user_pydantic.from_queryset(User.all())}

@post_save(User)
async def create_business_and_send_verification_email(sender: Type[User], instance: User, created: bool, using_db: Optional[BaseDBAsyncClient], update_fields: List[str]) -> None:
    if created:
        business_obj = await Business.create(businessname=instance.username, owner=instance)
        await business_pydantic.from_tortoise_orm(business_obj)
        await send_verification_email(email_to=instance.email, instance=instance)

register_tortoise(
    app,
    db_url="sqlite://db.sqlite3",
    modules={"models": ["models"]},
    generate_schemas=True,
    add_exception_handlers=True,
)


