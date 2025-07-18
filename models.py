from email.policy import default
from tortoise import Model,fields
from tortoise.contrib.pydantic import pydantic_model_creator
from pydantic import BaseModel
from datetime import datetime



class User(Model):
    id = fields.IntField(pk=True, index=True)
    username = fields.CharField(max_length=200, unique=True, null=False)
    email = fields.CharField(max_length=255, unique=True, null=False)
    password = fields.CharField(max_length=255, null=False)
    is_verified = fields.BooleanField(default=False)
    join_data = fields.DatetimeField(default=datetime.now())


class Business(Model):
    id = fields.IntField(pk=True, index=True)
    businessname = fields.CharField(max_length=200, unique=True, null=False)
    city = fields.CharField(max_length=255, null=False, default="unspecified")
    region = fields.CharField(max_length=255, null=False, default="unspecified")
    business_description = fields.TextField(null=True)
    logo = fields.CharField(max_length=255, null=False, default="default.jpg")
    owner = fields.ForeignKeyField("models.User", related_name="businesses")

class Product(Model):
    id = fields.IntField(pk=True, index=True)
    product_name = fields.CharField(max_length=200, index=True, null=False)
    category = fields.CharField(max_length=255, index=True, default="unspecified")
    original_price = fields.DecimalField(max_digits=10, decimal_places=2, null=False)
    new_price = fields.DecimalField(max_digits=10, decimal_places=2)
    percentage_discount = fields.IntField()
    offer_expires = fields.DatetimeField(default=datetime.now())
    product_image = fields.CharField(max_length=255, null=False, default="productDefault.jpg")
    business = fields.ForeignKeyField("models.Business", related_name="products")
    date_published = fields.DatetimeField(default=datetime.now())

user_pydantic = pydantic_model_creator(User, name="User", exclude=("is_verified",))
user_pydantic_in = pydantic_model_creator(User, name="UserIn", exclude_readonly=True,exclude=("is_verified","join_data"))
user_pydantic_out = pydantic_model_creator(User, name="UserOut", exclude=("password",))


business_pydantic = pydantic_model_creator(Business, name="Business")
business_pydantic_in = pydantic_model_creator(Business, name="BusinessIn", exclude=("logo","id"))


product_pydantic = pydantic_model_creator(Product, name="Product")
product_pydantic_in = pydantic_model_creator(Product, name="ProductIn", exclude=("percentage_discount", "id", "product_image","date_published"))

