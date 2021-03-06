from unittest import TestCase
from mock import Mock, patch
import elasticsearch
import yaml
import curator
# Get test variables and constants from a single source
from . import testvars as testvars

class TestIndexListClientAndInit(TestCase):
    def test_init_bad_client(self):
        client = 'not a real client'
        self.assertRaises(TypeError, curator.IndexList, client)
    def test_init_get_indices_exception(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_two
        client.indices.get_settings.side_effect = testvars.fake_fail
        self.assertRaises(curator.FailedExecution, curator.IndexList, client)
    def test_init(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_two
        client.cluster.state.return_value = testvars.clu_state_two
        client.indices.stats.return_value = testvars.stats_two
        il = curator.IndexList(client)
        self.assertEqual(
            testvars.stats_two['indices']['index-2016.03.03']['total']['store']['size_in_bytes'],
            il.index_info['index-2016.03.03']['size_in_bytes']
        )
        self.assertEqual(
            testvars.clu_state_two['metadata']['indices']['index-2016.03.04']['state'],
            il.index_info['index-2016.03.04']['state']
        )
        self.assertEqual(['index-2016.03.03','index-2016.03.04'], sorted(il.indices))
    def test_for_closed_index(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_2_closed
        client.cluster.state.return_value = testvars.cs_two_closed
        client.indices.stats.return_value = testvars.stats_two
        il = curator.IndexList(client)
        self.assertEqual('close', il.index_info['index-2016.03.03']['state'])
    def test_skip_index_without_creation_date(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_two_no_cd
        client.cluster.state.return_value = testvars.clu_state_two_no_cd
        client.indices.stats.return_value = testvars.stats_two
        il = curator.IndexList(client)
        self.assertEqual(['index-2016.03.03'], sorted(il.indices))
class TestIndexListOtherMethods(TestCase):
    def test_empty_list(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_two
        client.cluster.state.return_value = testvars.clu_state_two
        client.indices.stats.return_value = testvars.stats_two
        il = curator.IndexList(client)
        self.assertEqual(2, len(il.indices))
        il.indices = []
        self.assertRaises(curator.NoIndices, il.empty_list_check)
    def test_get_segmentcount(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_one
        client.cluster.state.return_value = testvars.clu_state_one
        client.indices.stats.return_value = testvars.stats_one
        client.indices.segments.return_value = testvars.shards
        il = curator.IndexList(client)
        il._get_segmentcounts()
        self.assertEqual(71, il.index_info[testvars.named_index]['segments'])

class TestIndexListAgeFilterName(TestCase):
    def test_get_name_based_ages_match(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_two
        client.cluster.state.return_value = testvars.clu_state_two
        client.indices.stats.return_value = testvars.stats_two
        il = curator.IndexList(client)
        il._get_name_based_ages('%Y.%m.%d')
        self.assertEqual(1456963200,il.index_info['index-2016.03.03']['age']['name'])
    def test_get_name_based_ages_no_match(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_two
        client.cluster.state.return_value = testvars.clu_state_two
        client.indices.stats.return_value = testvars.stats_two
        nomatch = curator.IndexList(client)
        nomatch._get_name_based_ages('%Y-%m-%d')
        self.assertEqual(
            curator.fix_epoch(
                testvars.settings_two['index-2016.03.03']['settings']['index']['creation_date']
            ),
            nomatch.index_info['index-2016.03.03']['age']['creation_date']
        )

class TestIndexListAgeFilterStatsAPI(TestCase):
    def test_get_field_stats_dates_success(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_two
        client.cluster.state.return_value = testvars.clu_state_two
        client.indices.stats.return_value = testvars.stats_two
        il = curator.IndexList(client)
        client.field_stats.return_value = testvars.fieldstats_two
        il._get_field_stats_dates(field='timestamp')
        self.assertEqual(
            curator.fix_epoch(
                testvars.fieldstats_two['indices']['index-2016.03.04']['fields']['timestamp']['min_value']
            ),
            il.index_info['index-2016.03.04']['age']['min_value']
        )
    def test_get_field_stats_dates_negative(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_two
        client.cluster.state.return_value = testvars.clu_state_two
        client.indices.stats.return_value = testvars.stats_two
        il = curator.IndexList(client)
        client.field_stats.return_value = testvars.fieldstats_two
        il._get_field_stats_dates(field='timestamp')
        self.assertNotIn('not_an_index_name', list(il.index_info.keys()))
    def test_get_field_stats_dates_field_not_found(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_two
        client.cluster.state.return_value = testvars.clu_state_two
        client.indices.stats.return_value = testvars.stats_two
        client.field_stats.return_value = testvars.fieldstats_two
        il = curator.IndexList(client)
        self.assertRaises(
            curator.ActionError, il._get_field_stats_dates, field='not_in_index')

class TestIndexListRegexFilters(TestCase):
    def test_filter_by_regex_prefix(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_two
        client.cluster.state.return_value = testvars.clu_state_two
        client.indices.stats.return_value = testvars.stats_two
        il = curator.IndexList(client)
        self.assertEqual(
            [u'index-2016.03.03', u'index-2016.03.04'],
            sorted(il.indices)
        )
        il.filter_by_regex(kind='prefix', value='ind')
        self.assertEqual(
            [u'index-2016.03.03', u'index-2016.03.04'],
            sorted(il.indices)
        )
        il.filter_by_regex(kind='prefix', value='ind', exclude=True)
        self.assertEqual([], il.indices)
    def test_filter_by_regex_timestring(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_two
        client.cluster.state.return_value = testvars.clu_state_two
        client.indices.stats.return_value = testvars.stats_two
        il = curator.IndexList(client)
        self.assertEqual(
            [u'index-2016.03.03', u'index-2016.03.04'],
            sorted(il.indices)
        )
        il.filter_by_regex(kind='timestring', value='%Y.%m.%d')
        self.assertEqual(
            [u'index-2016.03.03', u'index-2016.03.04'],
            sorted(il.indices)
        )
        il.filter_by_regex(kind='timestring', value='%Y.%m.%d', exclude=True)
        self.assertEqual([], il.indices)
    def test_filter_by_regex_no_match_exclude(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_two
        client.cluster.state.return_value = testvars.clu_state_two
        client.indices.stats.return_value = testvars.stats_two
        il = curator.IndexList(client)
        self.assertEqual(
            [u'index-2016.03.03', u'index-2016.03.04'],
            sorted(il.indices)
        )
        il.filter_by_regex(kind='prefix', value='invalid', exclude=True)
        # self.assertEqual([], il.indices)
        self.assertEqual(
            [u'index-2016.03.03', u'index-2016.03.04'],
            sorted(il.indices)
        )
    def test_filter_by_regex_no_value(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_two
        client.cluster.state.return_value = testvars.clu_state_two
        client.indices.stats.return_value = testvars.stats_two
        il = curator.IndexList(client)
        self.assertEqual(
            [u'index-2016.03.03', u'index-2016.03.04'],
            sorted(il.indices)
        )
        self.assertRaises(ValueError, il.filter_by_regex, kind='prefix', value=None)
        self.assertEqual(
            [u'index-2016.03.03', u'index-2016.03.04'],
            sorted(il.indices)
        )
        il.filter_by_regex(kind='prefix', value=0)
        self.assertEqual([], il.indices)
    def test_filter_by_regex_bad_kind(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_two
        client.cluster.state.return_value = testvars.clu_state_two
        client.indices.stats.return_value = testvars.stats_two
        il = curator.IndexList(client)
        self.assertEqual(
            [u'index-2016.03.03', u'index-2016.03.04'],
            sorted(il.indices)
        )
        self.assertRaises(ValueError, il.filter_by_regex, kind='invalid', value=None)

class TestIndexListFilterByAge(TestCase):
    def test_missing_direction(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_two
        client.cluster.state.return_value = testvars.clu_state_two
        client.indices.stats.return_value = testvars.stats_two
        il = curator.IndexList(client)
        self.assertRaises(curator.MissingArgument,
            il.filter_by_age, unit='days', unit_count=1
        )
    def test_bad_direction(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_two
        client.cluster.state.return_value = testvars.clu_state_two
        client.indices.stats.return_value = testvars.stats_two
        il = curator.IndexList(client)
        self.assertRaises(ValueError, il.filter_by_age, unit='days',
            unit_count=1, direction="invalid"
        )
    def test_name_no_timestring(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_two
        client.cluster.state.return_value = testvars.clu_state_two
        client.indices.stats.return_value = testvars.stats_two
        il = curator.IndexList(client)
        self.assertRaises(curator.MissingArgument,
            il.filter_by_age,
            source='name', unit='days', unit_count=1, direction='older'
        )
    def test_name_older_than_now(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_two
        client.cluster.state.return_value = testvars.clu_state_two
        client.indices.stats.return_value = testvars.stats_two
        il = curator.IndexList(client)
        il.filter_by_age(source='name', direction='older',
            timestring='%Y.%m.%d', unit='days', unit_count=1
        )
        self.assertEqual(
            ['index-2016.03.03','index-2016.03.04'], sorted(il.indices)
        )
    def test_name_older_than_now_exclude(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_two
        client.cluster.state.return_value = testvars.clu_state_two
        client.indices.stats.return_value = testvars.stats_two
        il = curator.IndexList(client)
        il.filter_by_age(source='name', direction='older',
            timestring='%Y.%m.%d', unit='days', unit_count=1, exclude=True
        )
        self.assertEqual(
            [], sorted(il.indices)
        )
    def test_name_younger_than_now(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_two
        client.cluster.state.return_value = testvars.clu_state_two
        client.indices.stats.return_value = testvars.stats_two
        il = curator.IndexList(client)
        il.filter_by_age(source='name', direction='younger',
            timestring='%Y.%m.%d', unit='days', unit_count=1
        )
        self.assertEqual([], sorted(il.indices))
    def test_name_younger_than_now_exclude(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_two
        client.cluster.state.return_value = testvars.clu_state_two
        client.indices.stats.return_value = testvars.stats_two
        il = curator.IndexList(client)
        il.filter_by_age(source='name', direction='younger',
            timestring='%Y.%m.%d', unit='days', unit_count=1, exclude=True
        )
        self.assertEqual(
            ['index-2016.03.03','index-2016.03.04'], sorted(il.indices))
    def test_name_younger_than_past_date(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_two
        client.cluster.state.return_value = testvars.clu_state_two
        client.indices.stats.return_value = testvars.stats_two
        il = curator.IndexList(client)
        il.filter_by_age(source='name', direction='younger',
            timestring='%Y.%m.%d', unit='seconds', unit_count=0,
            epoch=1457049599
        )
        self.assertEqual(['index-2016.03.04'], sorted(il.indices))
    def test_name_older_than_past_date(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_two
        client.cluster.state.return_value = testvars.clu_state_two
        client.indices.stats.return_value = testvars.stats_two
        il = curator.IndexList(client)
        il.filter_by_age(source='name', direction='older',
            timestring='%Y.%m.%d', unit='seconds', unit_count=0,
            epoch=1456963201
        )
        self.assertEqual(['index-2016.03.03'], sorted(il.indices))
    def test_creation_date_older_than_now(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_two
        client.cluster.state.return_value = testvars.clu_state_two
        client.indices.stats.return_value = testvars.stats_two
        il = curator.IndexList(client)
        il.filter_by_age(source='creation_date', direction='older', unit='days',
            unit_count=1
        )
        self.assertEqual(
            ['index-2016.03.03','index-2016.03.04'], sorted(il.indices)
        )
    def test_creation_date_older_than_now_raises(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_two
        client.cluster.state.return_value = testvars.clu_state_two
        client.indices.stats.return_value = testvars.stats_two
        il = curator.IndexList(client)
        il.index_info['index-2016.03.03']['age'].pop('creation_date')
        il.index_info['index-2016.03.04']['age'].pop('creation_date')
        il.filter_by_age(
            source='creation_date', direction='older', unit='days', unit_count=1
        )
        self.assertEqual([], il.indices)
    def test_creation_date_younger_than_now(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_two
        client.cluster.state.return_value = testvars.clu_state_two
        client.indices.stats.return_value = testvars.stats_two
        il = curator.IndexList(client)
        il.filter_by_age(source='creation_date', direction='younger',
            unit='days', unit_count=1
        )
        self.assertEqual([], sorted(il.indices))
    def test_creation_date_younger_than_now_raises(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_two
        client.cluster.state.return_value = testvars.clu_state_two
        client.indices.stats.return_value = testvars.stats_two
        il = curator.IndexList(client)
        il.index_info['index-2016.03.03']['age'].pop('creation_date')
        il.index_info['index-2016.03.04']['age'].pop('creation_date')
        il.filter_by_age(
            source='creation_date', direction='younger', unit='days',
            unit_count=1
        )
        self.assertEqual([], il.indices)
    def test_creation_date_younger_than_past_date(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_two
        client.cluster.state.return_value = testvars.clu_state_two
        client.indices.stats.return_value = testvars.stats_two
        il = curator.IndexList(client)
        il.filter_by_age(source='creation_date', direction='younger',
            unit='seconds', unit_count=0, epoch=1457049599
        )
        self.assertEqual(['index-2016.03.04'], sorted(il.indices))
    def test_creation_date_older_than_past_date(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_two
        client.cluster.state.return_value = testvars.clu_state_two
        client.indices.stats.return_value = testvars.stats_two
        il = curator.IndexList(client)
        il.filter_by_age(source='creation_date', direction='older',
            unit='seconds', unit_count=0, epoch=1456963201
        )
        self.assertEqual(['index-2016.03.03'], sorted(il.indices))
    def test_field_stats_missing_field(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_two
        client.cluster.state.return_value = testvars.clu_state_two
        client.indices.stats.return_value = testvars.stats_two
        il = curator.IndexList(client)
        self.assertRaises(curator.MissingArgument, il.filter_by_age,
            source='field_stats', direction='older', unit='days', unit_count=1
        )
    def test_field_stats_invalid_stats_result(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_two
        client.cluster.state.return_value = testvars.clu_state_two
        client.indices.stats.return_value = testvars.stats_two
        il = curator.IndexList(client)
        self.assertRaises(ValueError, il.filter_by_age, field='timestamp',
            source='field_stats', direction='older', unit='days', unit_count=1,
            stats_result='invalid'
        )
    def test_field_stats_invalid_source(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_two
        client.cluster.state.return_value = testvars.clu_state_two
        client.indices.stats.return_value = testvars.stats_two
        il = curator.IndexList(client)
        self.assertRaises(ValueError, il.filter_by_age,
            source='invalid', direction='older', unit='days', unit_count=1
        )
    def test_field_stats_older_than_now(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_two
        client.cluster.state.return_value = testvars.clu_state_two
        client.indices.stats.return_value = testvars.stats_two
        client.field_stats.return_value = testvars.fieldstats_two
        il = curator.IndexList(client)
        il.filter_by_age(source='field_stats', direction='older',
            field='timestamp', unit='days', unit_count=1
        )
        self.assertEqual(
            ['index-2016.03.03','index-2016.03.04'], sorted(il.indices)
        )
    def test_field_stats_younger_than_now(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_two
        client.cluster.state.return_value = testvars.clu_state_two
        client.indices.stats.return_value = testvars.stats_two
        client.field_stats.return_value = testvars.fieldstats_two
        il = curator.IndexList(client)
        il.filter_by_age(source='field_stats', direction='younger',
            field='timestamp', unit='days', unit_count=1
        )
        self.assertEqual([], sorted(il.indices))
    def test_field_stats_younger_than_past_date(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_two
        client.cluster.state.return_value = testvars.clu_state_two
        client.indices.stats.return_value = testvars.stats_two
        client.field_stats.return_value = testvars.fieldstats_two
        il = curator.IndexList(client)
        il.filter_by_age(source='field_stats', direction='younger',
            field='timestamp', unit='seconds', unit_count=0, epoch=1457049599
        )
        self.assertEqual(['index-2016.03.04'], sorted(il.indices))
    def test_field_stats_older_than_past_date(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_two
        client.cluster.state.return_value = testvars.clu_state_two
        client.indices.stats.return_value = testvars.stats_two
        client.field_stats.return_value = testvars.fieldstats_two
        il = curator.IndexList(client)
        il.filter_by_age(source='field_stats', direction='older',
            field='timestamp', unit='seconds', unit_count=0, epoch=1456963207
        )
        self.assertEqual(['index-2016.03.03'], sorted(il.indices))
    def test_field_stats_older_than_now_max(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_two
        client.cluster.state.return_value = testvars.clu_state_two
        client.indices.stats.return_value = testvars.stats_two
        client.field_stats.return_value = testvars.fieldstats_two
        il = curator.IndexList(client)
        il.filter_by_age(source='field_stats', direction='older',
            field='timestamp', stats_result='max_value', unit='days', unit_count=0
        )
        self.assertEqual(
            ['index-2016.03.03','index-2016.03.04'], sorted(il.indices)
        )
    def test_field_stats_younger_than_now_max(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_two
        client.cluster.state.return_value = testvars.clu_state_two
        client.indices.stats.return_value = testvars.stats_two
        client.field_stats.return_value = testvars.fieldstats_two
        il = curator.IndexList(client)
        il.filter_by_age(source='field_stats', direction='younger',
            field='timestamp', stats_result='max_value', unit='days', unit_count=0
        )
        self.assertEqual([], sorted(il.indices))
    def test_field_stats_younger_than_past_date_max(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_two
        client.cluster.state.return_value = testvars.clu_state_two
        client.indices.stats.return_value = testvars.stats_two
        client.field_stats.return_value = testvars.fieldstats_two
        il = curator.IndexList(client)
        il.filter_by_age(source='field_stats', direction='younger',
            field='timestamp', stats_result='max_value', unit='seconds',
            unit_count=0, epoch=1457135998
        )
        self.assertEqual(['index-2016.03.04'], sorted(il.indices))
    def test_field_stats_older_than_past_date_max(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_two
        client.cluster.state.return_value = testvars.clu_state_two
        client.indices.stats.return_value = testvars.stats_two
        client.field_stats.return_value = testvars.fieldstats_two
        il = curator.IndexList(client)
        il.filter_by_age(source='field_stats', direction='older',
            field='timestamp', stats_result='max_value', unit='seconds',
            unit_count=0, epoch=1457049600
        )
        self.assertEqual(['index-2016.03.03'], sorted(il.indices))

class TestIndexListFilterBySpace(TestCase):
    def test_missing_disk_space_value(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_two
        client.cluster.state.return_value = testvars.clu_state_two
        client.indices.stats.return_value = testvars.stats_two
        client.field_stats.return_value = testvars.fieldstats_two
        il = curator.IndexList(client)
        self.assertRaises(curator.MissingArgument, il.filter_by_space)
    def test_filter_result_by_name(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_two
        client.cluster.state.return_value = testvars.clu_state_two
        client.indices.stats.return_value = testvars.stats_two
        client.field_stats.return_value = testvars.fieldstats_two
        il = curator.IndexList(client)
        il.filter_by_space(disk_space=1.1)
        self.assertEqual(['index-2016.03.03'], il.indices)
    def test_filter_result_by_name_reverse_order(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_two
        client.cluster.state.return_value = testvars.clu_state_two
        client.indices.stats.return_value = testvars.stats_two
        client.field_stats.return_value = testvars.fieldstats_two
        il = curator.IndexList(client)
        il.filter_by_space(disk_space=1.1, reverse=False)
        self.assertEqual(['index-2016.03.04'], il.indices)
    def test_filter_result_by_name_exclude(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_two
        client.cluster.state.return_value = testvars.clu_state_two
        client.indices.stats.return_value = testvars.stats_two
        client.field_stats.return_value = testvars.fieldstats_two
        il = curator.IndexList(client)
        il.filter_by_space(disk_space=1.1, exclude=True)
        self.assertEqual(['index-2016.03.04'], il.indices)
    def test_filter_result_by_date_raise(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_four
        client.cluster.state.return_value = testvars.clu_state_four
        client.indices.stats.return_value = testvars.stats_four
        client.field_stats.return_value = testvars.fieldstats_four
        il = curator.IndexList(client)
        self.assertRaises(ValueError,
            il.filter_by_space, disk_space=2.1, use_age=True, source='invalid'
        )
    def test_filter_result_by_date_timestring_raise(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_four
        client.cluster.state.return_value = testvars.clu_state_four
        client.indices.stats.return_value = testvars.stats_four
        client.field_stats.return_value = testvars.fieldstats_four
        il = curator.IndexList(client)
        self.assertRaises(curator.MissingArgument,
            il.filter_by_space, disk_space=2.1, use_age=True, source='name'
        )
    def test_filter_result_by_date_timestring(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_four
        client.cluster.state.return_value = testvars.clu_state_four
        client.indices.stats.return_value = testvars.stats_four
        client.field_stats.return_value = testvars.fieldstats_four
        il = curator.IndexList(client)
        il.filter_by_space(
            disk_space=2.1, use_age=True,
            source='name', timestring='%Y.%m.%d'
        )
        self.assertEqual(['a-2016.03.03'], sorted(il.indices))
    def test_filter_result_by_date_non_matching_timestring(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_four
        client.cluster.state.return_value = testvars.clu_state_four
        client.indices.stats.return_value = testvars.stats_four
        client.field_stats.return_value = testvars.fieldstats_four
        il = curator.IndexList(client)
        il.filter_by_space(
            disk_space=2.1, use_age=True,
            source='name', timestring='%Y.%m.%d.%H'
        )
        self.assertEqual([], sorted(il.indices))
    def test_filter_result_by_date_field_stats_raise(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_four
        client.cluster.state.return_value = testvars.clu_state_four
        client.indices.stats.return_value = testvars.stats_four
        client.field_stats.return_value = testvars.fieldstats_four
        il = curator.IndexList(client)
        self.assertRaises(ValueError,
            il.filter_by_space, disk_space=2.1, use_age=True,
            source='min_value'
        )
    def test_filter_result_by_date_no_field_raise(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_four
        client.cluster.state.return_value = testvars.clu_state_four
        client.indices.stats.return_value = testvars.stats_four
        client.field_stats.return_value = testvars.fieldstats_four
        il = curator.IndexList(client)
        self.assertRaises(curator.MissingArgument,
            il.filter_by_space, disk_space=2.1, use_age=True,
            source='field_stats'
        )
    def test_filter_result_by_date_invalid_stats_result_raise(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_four
        client.cluster.state.return_value = testvars.clu_state_four
        client.indices.stats.return_value = testvars.stats_four
        client.field_stats.return_value = testvars.fieldstats_four
        il = curator.IndexList(client)
        self.assertRaises(ValueError,
            il.filter_by_space, disk_space=2.1, use_age=True,
            source='field_stats', field='timestamp', stats_result='invalid'
        )
    def test_filter_result_by_date_field_stats(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_four
        client.cluster.state.return_value = testvars.clu_state_four
        client.indices.stats.return_value = testvars.stats_four
        client.field_stats.return_value = testvars.fieldstats_four
        il = curator.IndexList(client)
        il.filter_by_space(
            disk_space=2.1, use_age=True,
            source='field_stats', field='timestamp'
        )
        self.assertEqual(['a-2016.03.03'], il.indices)
    def test_filter_result_by_creation_date(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_four
        client.cluster.state.return_value = testvars.clu_state_four
        client.indices.stats.return_value = testvars.stats_four
        client.field_stats.return_value = testvars.fieldstats_four
        il = curator.IndexList(client)
        il.filter_by_space(disk_space=2.1, use_age=True)
        self.assertEqual(['a-2016.03.03'], il.indices)

class TestIndexListFilterKibana(TestCase):
    def test_filter_kibana_positive(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_two
        client.cluster.state.return_value = testvars.clu_state_two
        client.indices.stats.return_value = testvars.stats_two
        client.field_stats.return_value = testvars.fieldstats_two
        il = curator.IndexList(client)
        # Establish the object per requirements, then overwrite
        il.indices = ['.kibana', '.marvel-kibana', 'kibana-int', '.marvel-es-data', 'dummy']
        il.filter_kibana()
        self.assertEqual(['dummy'], il.indices)
    def test_filter_kibana_positive_exclude(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_two
        client.cluster.state.return_value = testvars.clu_state_two
        client.indices.stats.return_value = testvars.stats_two
        client.field_stats.return_value = testvars.fieldstats_two
        il = curator.IndexList(client)
        # Establish the object per requirements, then overwrite
        kibana_indices = [
            '.kibana', '.marvel-kibana', 'kibana-int', '.marvel-es-data']
        il.indices = kibana_indices
        il.indices.append('dummy')
        il.filter_kibana(exclude=True)
        self.assertEqual(kibana_indices, il.indices)
    def test_filter_kibana_negative(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_two
        client.cluster.state.return_value = testvars.clu_state_two
        client.indices.stats.return_value = testvars.stats_two
        client.field_stats.return_value = testvars.fieldstats_two
        il = curator.IndexList(client)
        # Establish the object per requirements, then overwrite
        il.indices = ['kibana', 'marvel-kibana', 'cabana-int', 'marvel-es-data', 'dummy']
        il.filter_kibana()
        self.assertEqual(
            ['kibana', 'marvel-kibana', 'cabana-int', 'marvel-es-data', 'dummy'],
             il.indices
        )

class TestIndexListFilterForceMerged(TestCase):
    def test_filter_forcemerge_raise(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_one
        client.cluster.state.return_value = testvars.clu_state_one
        client.indices.stats.return_value = testvars.stats_one
        client.indices.segments.return_value = testvars.shards
        il = curator.IndexList(client)
        self.assertRaises(curator.MissingArgument, il.filter_forceMerged)
    def test_filter_forcemerge_positive(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_one
        client.cluster.state.return_value = testvars.clu_state_one
        client.indices.stats.return_value = testvars.stats_one
        client.indices.segments.return_value = testvars.shards
        il = curator.IndexList(client)
        il.filter_forceMerged(max_num_segments=2)
        self.assertEqual([testvars.named_index], il.indices)
    def test_filter_forcemerge_negative(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_one
        client.cluster.state.return_value = testvars.clu_state_one
        client.indices.stats.return_value = testvars.stats_one
        client.indices.segments.return_value = testvars.fm_shards
        il = curator.IndexList(client)
        il.filter_forceMerged(max_num_segments=2)
        self.assertEqual([], il.indices)

class TestIndexListFilterOpened(TestCase):
    def test_filter_opened(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_four
        client.cluster.state.return_value = testvars.clu_state_four
        client.indices.stats.return_value = testvars.stats_four
        client.field_stats.return_value = testvars.fieldstats_four
        il = curator.IndexList(client)
        il.filter_opened()
        self.assertEqual(['c-2016.03.05'], il.indices)

class TestIndexListFilterAllocated(TestCase):
    def test_missing_key(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_two
        client.cluster.state.return_value = testvars.clu_state_two
        client.indices.stats.return_value = testvars.stats_two
        il = curator.IndexList(client)
        self.assertRaises(
            curator.MissingArgument, il.filter_allocated, value='foo',
            allocation_type='invalid'
        )
    def test_missing_value(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_two
        client.cluster.state.return_value = testvars.clu_state_two
        client.indices.stats.return_value = testvars.stats_two
        il = curator.IndexList(client)
        self.assertRaises(
            curator.MissingArgument, il.filter_allocated, key='tag',
            allocation_type='invalid'
        )
    def test_invalid_allocation_type(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_two
        client.cluster.state.return_value = testvars.clu_state_two
        client.indices.stats.return_value = testvars.stats_two
        il = curator.IndexList(client)
        self.assertRaises(
            ValueError, il.filter_allocated, key='tag', value='foo',
            allocation_type='invalid'
        )
    def test_success(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_two
        client.cluster.state.return_value = testvars.clu_state_two
        client.indices.stats.return_value = testvars.stats_two
        il = curator.IndexList(client)
        il.filter_allocated(key='tag', value='foo', allocation_type='include')
        self.assertEqual(['index-2016.03.04'], il.indices)
    def test_invalid_tag(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_two
        client.cluster.state.return_value = testvars.clu_state_two
        client.indices.stats.return_value = testvars.stats_two
        il = curator.IndexList(client)
        il.filter_allocated(
            key='invalid', value='foo', allocation_type='include')
        self.assertEqual(
            ['index-2016.03.03','index-2016.03.04'], sorted(il.indices))

class TestIterateFiltersIndex(TestCase):
    def test_no_filters(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_four
        client.cluster.state.return_value = testvars.clu_state_four
        client.indices.stats.return_value = testvars.stats_four
        ilo = curator.IndexList(client)
        ilo.iterate_filters({})
        self.assertEqual(
            ['a-2016.03.03', 'b-2016.03.04', 'c-2016.03.05', 'd-2016.03.06'],
            sorted(ilo.indices)
        )
    def test_no_filtertype(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_four
        client.cluster.state.return_value = testvars.clu_state_four
        client.indices.stats.return_value = testvars.stats_four
        ilo = curator.IndexList(client)
        config = {'filters': [{'no_filtertype':'fail'}]}
        self.assertRaises(
            curator.ConfigurationError, ilo.iterate_filters, config)
    def test_invalid_filtertype(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_four
        client.cluster.state.return_value = testvars.clu_state_four
        client.indices.stats.return_value = testvars.stats_four
        ilo = curator.IndexList(client)
        config = {'filters': [{'filtertype':12345.6789}]}
        self.assertRaises(
            curator.ConfigurationError, ilo.iterate_filters, config)
    def test_pattern_filtertype(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_four
        client.cluster.state.return_value = testvars.clu_state_four
        client.indices.stats.return_value = testvars.stats_four
        ilo = curator.IndexList(client)
        config = yaml.load(testvars.pattern_ft)['actions'][1]
        ilo.iterate_filters(config)
        self.assertEqual(['a-2016.03.03'], ilo.indices)
    def test_age_filtertype(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_two
        client.cluster.state.return_value = testvars.clu_state_two
        client.indices.stats.return_value = testvars.stats_two
        ilo = curator.IndexList(client)
        config = yaml.load(testvars.age_ft)['actions'][1]
        ilo.iterate_filters(config)
        self.assertEqual(['index-2016.03.03'], ilo.indices)
    def test_space_filtertype(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_four
        client.cluster.state.return_value = testvars.clu_state_four
        client.indices.stats.return_value = testvars.stats_four
        client.field_stats.return_value = testvars.fieldstats_four
        ilo = curator.IndexList(client)
        config = yaml.load(testvars.space_ft)['actions'][1]
        ilo.iterate_filters(config)
        self.assertEqual(['a-2016.03.03'], ilo.indices)
    def test_forcemerge_filtertype(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_one
        client.cluster.state.return_value = testvars.clu_state_one
        client.indices.stats.return_value = testvars.stats_one
        client.indices.segments.return_value = testvars.shards
        ilo = curator.IndexList(client)
        config = yaml.load(testvars.forcemerge_ft)['actions'][1]
        ilo.iterate_filters(config)
        self.assertEqual([testvars.named_index], ilo.indices)
    def test_allocated_filtertype(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_two
        client.cluster.state.return_value = testvars.clu_state_two
        client.indices.stats.return_value = testvars.stats_two
        ilo = curator.IndexList(client)
        config = yaml.load(testvars.allocated_ft)['actions'][1]
        ilo.iterate_filters(config)
        self.assertEqual(['index-2016.03.04'], ilo.indices)
    def test_kibana_filtertype(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_two
        client.cluster.state.return_value = testvars.clu_state_two
        client.indices.stats.return_value = testvars.stats_two
        client.field_stats.return_value = testvars.fieldstats_two
        ilo = curator.IndexList(client)
        # Establish the object per requirements, then overwrite
        ilo.indices = [
            '.kibana', '.marvel-kibana', 'kibana-int', '.marvel-es-data',
            'dummy'
        ]
        config = yaml.load(testvars.kibana_ft)['actions'][1]
        ilo.iterate_filters(config)
        self.assertEqual(['dummy'], ilo.indices)
    def test_opened_filtertype(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_four
        client.cluster.state.return_value = testvars.clu_state_four
        client.indices.stats.return_value = testvars.stats_four
        client.field_stats.return_value = testvars.fieldstats_four
        ilo = curator.IndexList(client)
        config = yaml.load(testvars.opened_ft)['actions'][1]
        ilo.iterate_filters(config)
        self.assertEqual(['c-2016.03.05'], ilo.indices)
    def test_closed_filtertype(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_four
        client.cluster.state.return_value = testvars.clu_state_four
        client.indices.stats.return_value = testvars.stats_four
        client.field_stats.return_value = testvars.fieldstats_four
        ilo = curator.IndexList(client)
        config = yaml.load(testvars.closed_ft)['actions'][1]
        ilo.iterate_filters(config)
        self.assertEqual(
            ['a-2016.03.03','b-2016.03.04','d-2016.03.06'], sorted(ilo.indices))
    def test_none_filtertype(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_two
        client.cluster.state.return_value = testvars.clu_state_two
        client.indices.stats.return_value = testvars.stats_two
        ilo = curator.IndexList(client)
        config = yaml.load(testvars.none_ft)['actions'][1]
        ilo.iterate_filters(config)
        self.assertEqual(
            ['index-2016.03.03', 'index-2016.03.04'], sorted(ilo.indices))
    def test_unknown_filtertype_raises(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_two
        client.cluster.state.return_value = testvars.clu_state_two
        client.indices.stats.return_value = testvars.stats_two
        ilo = curator.IndexList(client)
        config = yaml.load(testvars.invalid_ft)['actions'][1]
        self.assertRaises(
            curator.ConfigurationError,
            ilo.iterate_filters, config
        )
class TestIndexListFilterAlias(TestCase):
    def test_raise(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_one
        client.cluster.state.return_value = testvars.clu_state_one
        client.indices.stats.return_value = testvars.stats_one
        il = curator.IndexList(client)
        self.assertRaises(curator.MissingArgument, il.filter_by_alias)
    def test_positive(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_two
        client.cluster.state.return_value = testvars.clu_state_two
        client.indices.stats.return_value = testvars.stats_two
        client.indices.get_alias.return_value = testvars.settings_2_get_aliases
        il = curator.IndexList(client)
        il.filter_by_alias(aliases=['my_alias'])
        self.assertEqual(
            sorted(list(testvars.settings_two.keys())), sorted(il.indices))
    def test_negative(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_two
        client.cluster.state.return_value = testvars.clu_state_two
        client.indices.stats.return_value = testvars.stats_two
        client.indices.get_alias.return_value = {}
        il = curator.IndexList(client)
        il.filter_by_alias(aliases=['not_my_alias'])
        self.assertEqual(
            sorted([]), sorted(il.indices))
    def test_get_alias_raises(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_two
        client.cluster.state.return_value = testvars.clu_state_two
        client.indices.stats.return_value = testvars.stats_two
        client.indices.get_alias.side_effect = testvars.get_alias_fail
        client.indices.get_alias.return_value = testvars.settings_2_get_aliases
        il = curator.IndexList(client)
        il.filter_by_alias(aliases=['my_alias'])
        self.assertEqual(
            sorted([]), sorted(il.indices))

class TestIndexListFilterCount(TestCase):
    def test_raise(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_one
        client.cluster.state.return_value = testvars.clu_state_one
        client.indices.stats.return_value = testvars.stats_one
        il = curator.IndexList(client)
        self.assertRaises(curator.MissingArgument, il.filter_by_count)
    def test_without_age(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_two
        client.cluster.state.return_value = testvars.clu_state_two
        client.indices.stats.return_value = testvars.stats_two
        client.indices.get_alias.return_value = testvars.settings_2_get_aliases
        il = curator.IndexList(client)
        il.filter_by_count(count=1)
        self.assertEqual([u'index-2016.03.03'], il.indices)
    def test_without_age_reversed(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_two
        client.cluster.state.return_value = testvars.clu_state_two
        client.indices.stats.return_value = testvars.stats_two
        client.indices.get_alias.return_value = testvars.settings_2_get_aliases
        il = curator.IndexList(client)
        il.filter_by_count(count=1, reverse=False)
        self.assertEqual([u'index-2016.03.04'], il.indices)
    def test_with_age(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_two
        client.cluster.state.return_value = testvars.clu_state_two
        client.indices.stats.return_value = testvars.stats_two
        client.indices.get_alias.return_value = testvars.settings_2_get_aliases
        il = curator.IndexList(client)
        il.filter_by_count(
            count=1, use_age=True, source='name', timestring='%Y.%m.%d'
        )
        self.assertEqual([u'index-2016.03.03'], il.indices)
    def test_with_age_creation_date(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_two
        client.cluster.state.return_value = testvars.clu_state_two
        client.indices.stats.return_value = testvars.stats_two
        client.indices.get_alias.return_value = testvars.settings_2_get_aliases
        il = curator.IndexList(client)
        il.filter_by_count(count=1, use_age=True)
        self.assertEqual([u'index-2016.03.03'], il.indices)
    def test_with_age_reversed(self):
        client = Mock()
        client.info.return_value = {'version': {'number': '5.0.0'} }
        client.indices.get_settings.return_value = testvars.settings_two
        client.cluster.state.return_value = testvars.clu_state_two
        client.indices.stats.return_value = testvars.stats_two
        client.indices.get_alias.return_value = testvars.settings_2_get_aliases
        il = curator.IndexList(client)
        il.filter_by_count(
            count=1, use_age=True, source='name', timestring='%Y.%m.%d',
            reverse=False
        )
        self.assertEqual([u'index-2016.03.04'], il.indices)
