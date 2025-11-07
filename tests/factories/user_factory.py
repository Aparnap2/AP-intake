"""
Factory for generating User test data.
"""

import factory
from datetime import datetime, timedelta
from faker import Faker

fake = Faker()


class UserFactory(factory.Factory):
    """Factory for generating User model instances."""

    class Meta:
        model = dict  # Since User model might not be implemented yet

    # Basic user information
    id = factory.Faker('uuid4')
    username = factory.Faker('user_name')
    email = factory.Faker('email')
    full_name = factory.Faker('name')

    # Authentication
    password_hash = factory.Faker('sha256')
    is_active = True
    is_superuser = False

    # Roles and permissions
    roles = factory.LazyAttribute(lambda _: ['processor'])

    # Metadata
    created_at = factory.LazyFunction(datetime.utcnow)
    updated_at = factory.LazyFunction(datetime.utcnow)
    last_login = factory.LazyAttribute(
        lambda _: datetime.utcnow() - timedelta(hours=fake.random_int(1, 168))
    )


class AdminUserFactory(UserFactory):
    """Factory for generating admin users."""

    username = factory.LazyAttribute(lambda _: f"admin_{fake.user_name()}")
    email = factory.LazyAttribute(lambda _: f"admin_{fake.email()}")
    roles = ['admin', 'processor']
    is_superuser = True


class ReviewerUserFactory(UserFactory):
    """Factory for generating reviewer users."""

    username = factory.LazyAttribute(lambda _: f"reviewer_{fake.user_name()}")
    email = factory.LazyAttribute(lambda _: f"reviewer_{fake.email()}")
    roles = ['reviewer', 'processor']


class InactiveUserFactory(UserFactory):
    """Factory for generating inactive users."""

    is_active = False
    roles = []
    last_login = None


class SuperUserFactory(UserFactory):
    """Factory for generating superusers."""

    username = 'superadmin'
    email = 'superadmin@example.com'
    full_name = 'Super Administrator'
    roles = ['superadmin', 'admin', 'reviewer', 'processor']
    is_superuser = True