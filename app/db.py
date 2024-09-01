import logging

from sqlalchemy import Column, Integer, String, ForeignKey, Enum as SqlEnum, select, update
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base, relationship, selectinload

from models import Status

logger = logging.getLogger(__name__)

DATABASE_URL = "sqlite+aiosqlite:///./test.db"

engine = create_async_engine(DATABASE_URL, echo=True, future=True)

Base = declarative_base()

# create tables
async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async_session = sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession
)

class Task(Base):
    __tablename__ = 'tasks'

    task_id = Column(Integer, primary_key=True, index=True)
    request_id = Column(String, index=True)
    total_images = Column(Integer, default=0, index=True)
    processed_images = Column(Integer, default=0, index=True)
    webhook_url = Column(String)

    products = relationship("Product", back_populates="task", cascade="all, delete-orphan")

    @classmethod
    async def fetch_by_request_id(cls, request_id: str):
        async with async_session() as session:  # Ensure async_session is defined
            result = await session.execute(select(cls).filter_by(request_id=request_id))
            return result.scalar_one_or_none()

    async def increment_processed_images(self, session: AsyncSession):
        async with session.begin():
            await session.execute(
                update(Task).
                where(Task.task_id == self.task_id).
                values(processed_images=Task.processed_images + 1)
            )
            result = await session.execute(select(Task).filter_by(task_id=self.task_id))
            return result.scalar_one_or_none()

    @classmethod
    async def is_complete(cls, request_id: str):
        async with async_session() as session:
            result = await session.execute(select(Task).filter_by(request_id=request_id))
            task = result.scalar_one_or_none()
            return task.processed_images == task.total_images


class Product(Base):
    __tablename__ = 'products'

    product_id = Column(Integer, primary_key=True, index=True)
    serial_num = Column(Integer)
    product_name = Column(String)
    request_id = Column(String, ForeignKey('tasks.request_id'))

    task = relationship("Task", back_populates="products")
    images = relationship("Image", back_populates="product", cascade="all, delete-orphan")

    @classmethod
    async def fetch_all_data_by_request_id(cls, request_id: str):
        async with async_session() as session:
            query = (
                select(Product)
                .options(selectinload(Product.images))  # Eager load images relationship
                .filter(Product.request_id == request_id)
            )

            result = await session.execute(query)
            return result.scalars().all()

class Image(Base):
    __tablename__ = 'images'

    image_id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey('products.product_id'))
    input_url = Column(String)
    output_url = Column(String)
    status = Column(SqlEnum(Status))

    product = relationship("Product", back_populates="images")

    @classmethod
    async def fetch_by_id(cls, image_id: int):
        async with async_session() as session:
            result = await session.execute(select(cls).filter_by(image_id=image_id))
            return result.scalar_one_or_none()

    async def set_complete(self, session: AsyncSession, output_url: str):
        async with session.begin():
            stmt = (
                update(Image)
                .where(Image.image_id == self.image_id)
                .values(output_url=output_url, status=Status.Complete)
            )
            await session.execute(stmt)


async def create_request(task: Task, session: AsyncSession, **kwargs):
    async with session.begin():
        try:
            product = Product(
                serial_num=kwargs['serial_num'],
                product_name=kwargs['product_name'],
                request_id=task.request_id,
            )
            session.add(product)

            await session.flush()

            image_urls = kwargs['input_image_urls'].split(',')

            for image_url in image_urls:
                image = Image(
                    product_id=product.product_id,
                    input_url=image_url,
                    status=Status.Processing,
                )
                session.add(image)

            task.total_images += len(image_urls)
        except Exception as e:
            raise e
async def fetch_images_by_request_id(request_id: str):
    async with async_session() as session:
        async with session.begin():
            # Fetch products associated with the given request ID
            result = await session.execute(
                select(Image)
                .join(Product)
                .join(Task)
                .where(Task.request_id == request_id)
            )
            images = result.scalars().all()
            return images
