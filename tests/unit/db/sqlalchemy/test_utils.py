# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright (c) 2013 Boris Pavlovic (boris@pavlovic.me).
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import sqlalchemy
from sqlalchemy.dialects import mysql
from sqlalchemy import Boolean, Index, Integer, DateTime, String
from sqlalchemy import MetaData, Table, Column
from sqlalchemy.engine import reflection
from sqlalchemy.sql import select
from sqlalchemy.types import UserDefinedType, NullType

from openstack.common.db.sqlalchemy import utils
from openstack.common import exception
from tests.unit.db.sqlalchemy import test_migrations
from tests import utils as testutils


class CustomType(UserDefinedType):
    """Dummy column type for testing unsupported types."""
    def get_col_spec(self):
        return "CustomType"


class FakeModel(object):
    def __init__(self, values):
        self.values = values

    def __getattr__(self, name):
        try:
            value = self.values[name]
        except KeyError:
            raise AttributeError(name)
        return value

    def __getitem__(self, key):
        if key in self.values:
            return self.values[key]
        else:
            raise NotImplementedError()

    def __repr__(self):
        return '<FakeModel: %s>' % self.values


class TestPaginateQuery(testutils.BaseTestCase):
    def setUp(self):
        super(TestPaginateQuery, self).setUp()
        self.query = self.mox.CreateMockAnything()
        self.mox.StubOutWithMock(sqlalchemy, 'asc')
        self.mox.StubOutWithMock(sqlalchemy, 'desc')
        self.marker = FakeModel({
            'user_id': 'user',
            'project_id': 'p',
            'snapshot_id': 's',
        })
        self.model = FakeModel({
            'user_id': 'user',
            'project_id': 'project',
            'snapshot_id': 'snapshot',
        })

    def test_paginate_query_no_pagination_no_sort_dirs(self):
        sqlalchemy.asc('user').AndReturn('asc_3')
        self.query.order_by('asc_3').AndReturn(self.query)
        sqlalchemy.asc('project').AndReturn('asc_2')
        self.query.order_by('asc_2').AndReturn(self.query)
        sqlalchemy.asc('snapshot').AndReturn('asc_1')
        self.query.order_by('asc_1').AndReturn(self.query)
        self.query.limit(5).AndReturn(self.query)
        self.mox.ReplayAll()
        utils.paginate_query(self.query, self.model, 5,
                             ['user_id', 'project_id', 'snapshot_id'])

    def test_paginate_query_no_pagination(self):
        sqlalchemy.asc('user').AndReturn('asc')
        self.query.order_by('asc').AndReturn(self.query)
        sqlalchemy.desc('project').AndReturn('desc')
        self.query.order_by('desc').AndReturn(self.query)
        self.query.limit(5).AndReturn(self.query)
        self.mox.ReplayAll()
        utils.paginate_query(self.query, self.model, 5,
                             ['user_id', 'project_id'],
                             sort_dirs=['asc', 'desc'])

    def test_paginate_query_attribute_error(self):
        sqlalchemy.asc('user').AndReturn('asc')
        self.query.order_by('asc').AndReturn(self.query)
        self.mox.ReplayAll()
        self.assertRaises(utils.InvalidSortKey,
                          utils.paginate_query, self.query,
                          self.model, 5, ['user_id', 'non-existent key'])

    def test_paginate_query_assertion_error(self):
        self.mox.ReplayAll()
        self.assertRaises(AssertionError,
                          utils.paginate_query, self.query,
                          self.model, 5, ['user_id'],
                          marker=self.marker,
                          sort_dir='asc', sort_dirs=['asc'])

    def test_paginate_query_assertion_error_2(self):
        self.mox.ReplayAll()
        self.assertRaises(AssertionError,
                          utils.paginate_query, self.query,
                          self.model, 5, ['user_id'],
                          marker=self.marker,
                          sort_dir=None, sort_dirs=['asc', 'desk'])

    def test_paginate_query(self):
        sqlalchemy.asc('user').AndReturn('asc_1')
        self.query.order_by('asc_1').AndReturn(self.query)
        sqlalchemy.desc('project').AndReturn('desc_1')
        self.query.order_by('desc_1').AndReturn(self.query)
        self.mox.StubOutWithMock(sqlalchemy.sql, 'and_')
        sqlalchemy.sql.and_(False).AndReturn('some_crit')
        sqlalchemy.sql.and_(True, False).AndReturn('another_crit')
        self.mox.StubOutWithMock(sqlalchemy.sql, 'or_')
        sqlalchemy.sql.or_('some_crit', 'another_crit').AndReturn('some_f')
        self.query.filter('some_f').AndReturn(self.query)
        self.query.limit(5).AndReturn(self.query)
        self.mox.ReplayAll()
        utils.paginate_query(self.query, self.model, 5,
                             ['user_id', 'project_id'],
                             marker=self.marker,
                             sort_dirs=['asc', 'desc'])

    def test_paginate_query_value_error(self):
        sqlalchemy.asc('user').AndReturn('asc_1')
        self.query.order_by('asc_1').AndReturn(self.query)
        self.mox.ReplayAll()
        self.assertRaises(ValueError, utils.paginate_query,
                          self.query, self.model, 5, ['user_id', 'project_id'],
                          marker=self.marker, sort_dirs=['asc', 'mixed'])


class TestMigrationUtils(test_migrations.BaseMigrationTestCase):
    """Class for testing utils that are used in db migrations."""

    def _populate_db_for_drop_duplicate_entries(self, engine, meta,
                                                table_name):
        values = [
            {'id': 11, 'a': 3, 'b': 10, 'c': 'abcdef'},
            {'id': 12, 'a': 5, 'b': 10, 'c': 'abcdef'},
            {'id': 13, 'a': 6, 'b': 10, 'c': 'abcdef'},
            {'id': 14, 'a': 7, 'b': 10, 'c': 'abcdef'},
            {'id': 21, 'a': 1, 'b': 20, 'c': 'aa'},
            {'id': 31, 'a': 1, 'b': 20, 'c': 'bb'},
            {'id': 41, 'a': 1, 'b': 30, 'c': 'aef'},
            {'id': 42, 'a': 2, 'b': 30, 'c': 'aef'},
            {'id': 43, 'a': 3, 'b': 30, 'c': 'aef'}
        ]

        test_table = Table(table_name, meta,
                           Column('id', Integer, primary_key=True,
                                  nullable=False),
                           Column('a', Integer),
                           Column('b', Integer),
                           Column('c', String(255)),
                           Column('deleted', Integer, default=0),
                           Column('deleted_at', DateTime),
                           Column('updated_at', DateTime))

        test_table.create()
        engine.execute(test_table.insert(), values)
        return test_table, values

    def test_drop_old_duplicate_entries_from_table(self):
        table_name = "__test_tmp_table__"

        for key, engine in self.engines.items():
            meta = MetaData()
            meta.bind = engine
            test_table, values = self._populate_db_for_drop_duplicate_entries(
                engine, meta, table_name)
            utils.drop_old_duplicate_entries_from_table(
                engine, table_name, False, 'b', 'c')

            uniq_values = set()
            expected_ids = []
            for value in sorted(values, key=lambda x: x['id'], reverse=True):
                uniq_value = (('b', value['b']), ('c', value['c']))
                if uniq_value in uniq_values:
                    continue
                uniq_values.add(uniq_value)
                expected_ids.append(value['id'])

            real_ids = [row[0] for row in
                        engine.execute(select([test_table.c.id])).fetchall()]

            self.assertEqual(len(real_ids), len(expected_ids))
            for id_ in expected_ids:
                self.assertTrue(id_ in real_ids)

    def test_drop_old_duplicate_entries_from_table_soft_delete(self):
        table_name = "__test_tmp_table__"

        for key, engine in self.engines.items():
            meta = MetaData()
            meta.bind = engine
            table, values = self._populate_db_for_drop_duplicate_entries(
                engine, meta, table_name)
            utils.drop_old_duplicate_entries_from_table(engine, table_name,
                                                        True, 'b', 'c')
            uniq_values = set()
            expected_values = []
            soft_deleted_values = []

            for value in sorted(values, key=lambda x: x['id'], reverse=True):
                uniq_value = (('b', value['b']), ('c', value['c']))
                if uniq_value in uniq_values:
                    soft_deleted_values.append(value)
                    continue
                uniq_values.add(uniq_value)
                expected_values.append(value)

            base_select = table.select()

            rows_select = base_select.where(table.c.deleted != table.c.id)
            row_ids = [row['id'] for row in
                       engine.execute(rows_select).fetchall()]
            self.assertEqual(len(row_ids), len(expected_values))
            for value in expected_values:
                self.assertTrue(value['id'] in row_ids)

            deleted_rows_select = base_select.where(
                table.c.deleted == table.c.id)
            deleted_rows_ids = [row['id'] for row in
                                engine.execute(deleted_rows_select).fetchall()]
            self.assertEqual(len(deleted_rows_ids),
                             len(values) - len(row_ids))
            for value in soft_deleted_values:
                self.assertTrue(value['id'] in deleted_rows_ids)

    def test_change_deleted_column_type_doesnt_drop_index(self):
        table_name = 'abc'
        for key, engine in self.engines.items():
            meta = MetaData(bind=engine)

            indexes = {
                'idx_a_deleted': ['a', 'deleted'],
                'idx_b_deleted': ['b', 'deleted'],
                'idx_a': ['a']
            }

            index_instances = [Index(name, *columns)
                               for name, columns in indexes.iteritems()]

            table = Table(table_name, meta,
                          Column('id', Integer, primary_key=True),
                          Column('a', String(255)),
                          Column('b', String(255)),
                          Column('deleted', Boolean),
                          *index_instances)
            table.create()
            utils.change_deleted_column_type_to_id_type(engine, table_name)
            utils.change_deleted_column_type_to_boolean(engine, table_name)

            insp = reflection.Inspector.from_engine(engine)
            real_indexes = insp.get_indexes(table_name)
            self.assertEqual(len(real_indexes), 3)
            for index in real_indexes:
                name = index['name']
                self.assertIn(name, indexes)
                self.assertEqual(set(index['column_names']),
                                 set(indexes[name]))

    def test_change_deleted_column_type_to_id_type_integer(self):
        table_name = 'abc'
        for key, engine in self.engines.items():
            meta = MetaData()
            meta.bind = engine
            table = Table(table_name, meta,
                          Column('id', Integer, primary_key=True),
                          Column('deleted', Boolean))
            table.create()
            utils.change_deleted_column_type_to_id_type(engine, table_name)

            table = utils.get_table(engine, table_name)
            self.assertTrue(isinstance(table.c.deleted.type, Integer))

    def test_change_deleted_column_type_to_id_type_string(self):
        table_name = 'abc'
        for key, engine in self.engines.items():
            meta = MetaData()
            meta.bind = engine
            table = Table(table_name, meta,
                          Column('id', String(255), primary_key=True),
                          Column('deleted', Boolean))
            table.create()
            utils.change_deleted_column_type_to_id_type(engine, table_name)

            table = utils.get_table(engine, table_name)
            self.assertTrue(isinstance(table.c.deleted.type, String))

    def test_change_deleted_column_type_to_id_type_custom(self):
        table_name = 'abc'
        engine = self.engines['sqlite']
        meta = MetaData()
        meta.bind = engine
        table = Table(table_name, meta,
                      Column('id', Integer, primary_key=True),
                      Column('foo', CustomType),
                      Column('deleted', Boolean))
        table.create()

        self.assertRaises(exception.OpenstackException,
                          utils.change_deleted_column_type_to_id_type,
                          engine, table_name)

        fooColumn = Column('foo', CustomType())
        utils.change_deleted_column_type_to_id_type(engine, table_name,
                                                    foo=fooColumn)

        table = utils.get_table(engine, table_name)
        # NOTE(boris-42): There is no way to check has foo type CustomType.
        #                 but sqlalchemy will set it to NullType.
        self.assertTrue(isinstance(table.c.foo.type, NullType))
        self.assertTrue(isinstance(table.c.deleted.type, Integer))

    def test_change_deleted_column_type_to_boolean(self):
        table_name = 'abc'
        for key, engine in self.engines.items():
            meta = MetaData()
            meta.bind = engine
            table = Table(table_name, meta,
                          Column('id', Integer, primary_key=True),
                          Column('deleted', Integer))
            table.create()

            utils.change_deleted_column_type_to_boolean(engine, table_name)

            table = utils.get_table(engine, table_name)
            expected_type = Boolean if key != "mysql" else mysql.TINYINT
            self.assertTrue(isinstance(table.c.deleted.type, expected_type))

    def test_change_deleted_column_type_to_boolean_type_custom(self):
        table_name = 'abc'
        engine = self.engines['sqlite']
        meta = MetaData()
        meta.bind = engine
        table = Table(table_name, meta,
                      Column('id', Integer, primary_key=True),
                      Column('foo', CustomType),
                      Column('deleted', Integer))
        table.create()

        self.assertRaises(exception.OpenstackException,
                          utils.change_deleted_column_type_to_boolean,
                          engine, table_name)

        fooColumn = Column('foo', CustomType())
        utils.change_deleted_column_type_to_boolean(engine, table_name,
                                                    foo=fooColumn)

        table = utils.get_table(engine, table_name)
        # NOTE(boris-42): There is no way to check has foo type CustomType.
        #                 but sqlalchemy will set it to NullType.
        self.assertTrue(isinstance(table.c.foo.type, NullType))
        self.assertTrue(isinstance(table.c.deleted.type, Boolean))
