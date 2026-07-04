from datetime import datetime, timedelta, timezone

import factory
from async_factory_boy.factory.sqlalchemy import AsyncSQLAlchemyFactory

from app.auth.models import RefreshToken
from tests.users.factories import UserFactory


class RefreshTokenFactory(AsyncSQLAlchemyFactory):
    class Meta:
        model = RefreshToken

    # Create the User relationship
    user = factory.SubFactory(UserFactory)

    # Generate a random hex string to simulate a SHA256 hash
    token_hash = factory.Faker("sha256")

    created_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))
    expires_at = factory.LazyFunction(
        lambda: datetime.now(timezone.utc) + timedelta(days=7)
    )

    revoked_at = None
    revocation_reason = None
    replaced_by_token_hash = None

    ip_address = factory.Faker("ipv4")
    user_agent = factory.Faker("user_agent")

    # --- Traits ---

    class Params:
        revoked = factory.Trait(
            revoked_at=factory.LazyFunction(lambda: datetime.now(timezone.utc)),
            revocation_reason="manual_test_revoke",
        )

        expired = factory.Trait(
            created_at=factory.LazyFunction(
                lambda: datetime.now(timezone.utc) - timedelta(days=10)
            ),
            expires_at=factory.LazyFunction(
                lambda: datetime.now(timezone.utc) - timedelta(days=1)
            ),
        )
