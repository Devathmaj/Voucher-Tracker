from sqlalchemy.ext.asyncio import AsyncSession
from typing import Generic, TypeVar, Type
from voucherbot.models.base import Base

ModelType = TypeVar("ModelType", bound=Base)

class BaseService(Generic[ModelType]):
    def __init__(self, model: Type[ModelType], session: AsyncSession):
        self.model = model
        self.session = session
