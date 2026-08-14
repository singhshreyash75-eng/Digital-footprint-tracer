from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


from app.investigations.models import Investigation, Target  # noqa: E402,F401