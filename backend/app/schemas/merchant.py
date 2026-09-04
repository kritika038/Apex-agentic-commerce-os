from pydantic import BaseModel
from typing import Optional, Dict

class MerchantBase(BaseModel):
    name: str
    domain: str

class MerchantCreate(MerchantBase):
    pass

class MerchantResponse(MerchantBase):
    id: str
    is_active: bool
    settings: Dict

    class Config:
        from_attributes = True
