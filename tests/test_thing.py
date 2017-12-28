from tests import TestCase

from auth.models import Country, Currency
from sqlalchemy.orm.base import object_mapper
from wtforms.ext.sqlalchemy.fields import identity_key


class TestThing(TestCase):
    def test_country(self):
        with self.app.test_request_context():
            c = Country.query.first()
            mapper = object_mapper(c)
            result = mapper.identity_key_from_instance(c)
            self.assertEqual((type(c), (c.id,)), result)
