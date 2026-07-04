import uuid
from datetime import datetime, timezone

import factory
from async_factory_boy.factory.sqlalchemy import AsyncSQLAlchemyFactory

from app.core.models_registry import post_models
from tests.users.factories import UserFactory


class PostContentFactory(factory.Factory):
    class Meta:
        model = dict

    id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    title = factory.Faker("sentence", nb_words=5)
    slug = factory.Faker("slug")
    content = factory.Faker("paragraph", nb_sentences=5)


class PostFactory(AsyncSQLAlchemyFactory):
    class Meta:
        model = post_models.Post

    # id = factory.Sequence(lambda n: n + 1)
    title = factory.Sequence(lambda n: f"Test Post {n}")

    # FIX 3: Ensure body has a value
    content = PostContentFactory()

    status = "draft"

    # FIX 4: Ensure owner is created (which sets user_id)
    owner = factory.SubFactory(UserFactory)

    slug = factory.Faker("slug")
    summary = factory.Faker("paragraph", nb_sentences=5)

    created_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))
    updated_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))
