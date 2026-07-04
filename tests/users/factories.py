import factory
from async_factory_boy.factory.sqlalchemy import AsyncSQLAlchemyFactory

from app.auth import utils
from app.users import models


class UserFactory(AsyncSQLAlchemyFactory):
    class Meta:
        model = models.User

    id = factory.Sequence(lambda n: n + 1)
    username = factory.Sequence(lambda n: f"user_{n}")
    email = factory.Sequence(lambda n: f"user_{n}@example.com")

    # FIX 1: Add defaults for required fields!
    first_name = factory.Faker("first_name")  # Random name
    last_name = factory.Faker("last_name")  # Random name

    # FIX 2: Ensure password is hashed (as we discussed before)
    password = factory.LazyAttribute(
        lambda o: utils.get_password_hash("Test_password_$123")
    )

    status = models.UserStatus.ACTIVE
