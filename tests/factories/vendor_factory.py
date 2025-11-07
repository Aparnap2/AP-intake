"""
Factory for generating Vendor test data.
"""

import factory
from datetime import datetime, timedelta
from faker import Faker

from app.models.vendor import Vendor

fake = Faker()


class VendorFactory(factory.Factory):
    """Factory for generating Vendor model instances."""

    class Meta:
        model = Vendor
        sqlalchemy_session_persistence = "flush"

    # Basic vendor information
    name = factory.Faker('company')
    tax_id = factory.LazyAttribute(lambda _: fake.ssn())
    currency = factory.Iterator(['USD', 'EUR', 'GBP', 'CAD'])

    # Financial information
    credit_limit = factory.Faker('pydecimal', left_digits=5, right_digits=2, positive=True)
    payment_terms = factory.Iterator(['NET30', 'NET45', 'NET60', 'COD'])

    # Status
    active = True
    status = factory.LazyAttribute(lambda obj: 'active' if obj.active else 'inactive')

    # Contact information
    email = factory.Faker('company_email')
    phone = factory.Faker('phone_number')
    website = factory.Faker('url')

    # Address information
    address_line1 = factory.Faker('street_address')
    address_line2 = factory.LazyAttribute(lambda _: fake.secondary_address() if fake.boolean() else None)
    city = factory.Faker('city')
    state = factory.Faker('state')
    postal_code = factory.Faker('postalcode')
    country = factory.Faker('country')

    # Metadata
    created_at = factory.LazyFunction(datetime.utcnow)
    updated_at = factory.LazyFunction(datetime.utcnow)


class InactiveVendorFactory(VendorFactory):
    """Factory for generating inactive vendors."""

    active = False
    status = 'inactive'
    updated_at = factory.LazyFunction(
        lambda: datetime.utcnow() - timedelta(days=30)
    )


class HighCreditVendorFactory(VendorFactory):
    """Factory for generating vendors with high credit limits."""

    credit_limit = factory.Faker('pydecimal', left_digits=7, right_digits=2, positive=True)
    payment_terms = 'NET60'


class InternationalVendorFactory(VendorFactory):
    """Factory for generating international vendors."""

    country = factory.Iterator(['UK', 'Germany', 'France', 'Japan', 'Australia'])
    currency = factory.LazyAttribute(
        lambda obj: {
            'UK': 'GBP',
            'Germany': 'EUR',
            'France': 'EUR',
            'Japan': 'JPY',
            'Australia': 'AUD'
        }.get(obj.country, 'USD')
    )