import numpy as np
import pandas as pd
import pytest
from requests.exceptions import HTTPError


from solarforecastarbiter.datamodel import Site, Observation
from solarforecastarbiter.io.reference_observations import common
from solarforecastarbiter.io.reference_observations.tests.conftest import (
    expected_site,
    site_dicts,
    site_string_dicts,
    site_objects)


@pytest.fixture
def log(mocker):
    log = mocker.patch('solarforecastarbiter.io.reference_observations.'
                       'common.logger')
    return log


site_test_observation = Observation.from_dict({
    'name': 'site ghi',
    'variable': 'ghi',
    'interval_label': 'ending',
    'interval_value_type': 'interval_mean',
    'interval_length': 1,
    'site': site_objects[0],
    'uncertainty': 0,
    'extra_parameters': ('{"network": "ARM", "observation_interval_length": 1,'
                         '"network_api_id": "api_id", '
                         '"network_api_abbreviation": "siteghi"}')
})
invalid_params = {
    'name': 'site-invalid-jsonparams',
    'latitude': 3,
    'longitude': -3,
    'elevation': 6,
    'timezone': 'Etc/GMT+8',
    'extra_parameters': '{{ mon$stertruck',
}
no_params = {
    'name': 'site-invalid-jsonparams',
    'latitude': 3,
    'longitude': -3,
    'elevation': 6,
    'timezone': 'Etc/GMT+8',
}


def test_decode_extra_parameters():
    metadata = Site.from_dict(site_string_dicts[0])
    params = common.decode_extra_parameters(metadata)
    assert params['network'] == 'ARM'
    assert params['observation_interval_length'] == 1


@pytest.mark.parametrize('site', [
    (invalid_params),
    (no_params),
])
def test_decode_extra_parameters_error(site):
    with pytest.raises(ValueError):
        common.decode_extra_parameters(Site.from_dict(site))


@pytest.mark.parametrize('site,expected', [
    (site_objects[0], 'site'),
    (site_objects[1], 'site2'),
    (site_objects[2], 'site3'),
    (site_objects[3], 'site4'),
])
def test_site_name_no_network(site, expected):
    assert common.site_name_no_network(site) == expected


@pytest.mark.parametrize('name,expected', [
    ('{n}_(a)_/m\\_.e@_[1]-', 'n a m e 1')
])
def test_clean_name(name, expected):
    assert common.clean_name(name) == expected


bad_network = site_dicts()[0]
bad_network['extra_parameters']['network'] = 'BBQ DISCO'
bad_network = expected_site(bad_network)


@pytest.mark.parametrize('networks,site,expected', [
    (['ARM'], site_string_dicts[0], True),
    ('ARM', site_string_dicts[0], True),
    (['ARM', 'NREL MIDC'], site_string_dicts[1], False),
    (['NOAA SURFRAD', 'ARM'], site_string_dicts[3], False),
    (['NOAA SURFRAD', 'ARM'], bad_network, False),
    (['ARMS'], site_string_dicts[0], False),
])
def test_check_network(networks, site, expected):
    metadata = Site.from_dict(site)
    assert common.check_network(networks, metadata) == expected


@pytest.mark.parametrize('networks,expected', [
    (['ARM'], site_objects[:1]),
    ('ARM', site_objects[:1]),
    (['NOAA SURFRAD', 'NOAA SOLRAD'], site_objects[1:3])
])
def test_filter_by_network(networks, expected):
    assert common.filter_by_networks(site_objects, networks) == expected


@pytest.mark.parametrize('site,variable', [
    (site_objects[0], 'ghi'),
])
def test_create_observation(
        mock_api, site, variable, observation_objects_param):
    common.create_observation(mock_api, site, variable)
    mock_api.create_observation.assert_called()
    mock_api.create_observation.assert_called_with(
        observation_objects_param[0])


long_site_name = Site.from_dict({
    'name': 'ARM site with just abouts sixty four characters in its name oops',
    'latitude': 1,
    'longitude': 1,
    'elevation': 5,
    'timezone': 'Etc/GMT+8',
    'extra_parameters': ('{"network": "ARM", "network_api_abbreviation": '
                         '"site_abbrev", "network_api_id": "thing", '
                         '"observation_interval_length": 1}'),
})
observation_long_site_name = Observation.from_dict({
    'name': 'site_abbrev air_temperature',
    'variable': 'air_temperature',
    'interval_label': 'ending',
    'interval_value_type': 'interval_mean',
    'interval_length': 1,
    'site': long_site_name,
    'uncertainty': 0,
    'extra_parameters': ('{"network": "ARM", "network_api_abbreviation": '
                         '"site_abbrev", "network_api_id": "thing", '
                         '"observation_interval_length": 1}'),
})


@pytest.mark.parametrize('site,variable,expected', [
    (long_site_name, 'air_temperature', observation_long_site_name),
])
def test_create_observation_long_site(mock_api, site, variable, expected):
    common.create_observation(mock_api, site, variable)
    mock_api.create_observation.assert_called()
    mock_api.create_observation.assert_called_with(expected)


observation_with_extra_params = Observation.from_dict({
    'name': 'site ghi',
    'variable': 'ghi',
    'interval_label': 'ending',
    'interval_value_type': 'interval_mean',
    'interval_length': 5,
    'site': site_objects[0],
    'uncertainty': 0,
    'extra_parameters': '{"network": "", "observation_interval_length": 5}'
})
observation_params = {
    'network': '',
    'observation_interval_length': 5,
}


@pytest.mark.parametrize('site,variable,expected,extra_params', [
    (site_objects[0], 'ghi', observation_with_extra_params,
     observation_params),
])
def test_create_observation_extra_parameters(
        mock_api, site, variable, expected, extra_params):
    common.create_observation(mock_api, site, variable, extra_params)
    mock_api.create_observation.assert_called()
    mock_api.create_observation.assert_called_with(expected)


test_kwarg_observation = Observation.from_dict({
    'name': 'just observation',
    'variable': 'ghi',
    'interval_label': 'beginning',
    'interval_value_type': 'instantaneous',
    'interval_length': 1,
    'site': site_objects[0],
    'uncertainty': 2,
    'extra_parameters': ('{"network": "ARM", "network_api_id": "some_id", '
                         '"network_api_abbreviation": "abbrv", '
                         '"observation_interval_length": 1}')
})
obs_kwargs = {
    'interval_label': 'beginning',
    'name': 'just observation',
    'interval_value_type': 'instantaneous',
    'uncertainty': 2,
}


@pytest.mark.parametrize('site,variable,expected,kwargs', [
    (site_objects[0], 'ghi', test_kwarg_observation, obs_kwargs),
])
def test_create_observation_with_kwargs(
        mock_api, site, variable, expected, kwargs):
    common.create_observation(mock_api, site, variable, **kwargs)
    mock_api.create_observation.assert_called()
    mock_api.create_observation.assert_called_with(expected)


def test_post_observation_data_no_data(mock_api, log, start, end,):
    common.post_observation_data(
        mock_api, test_kwarg_observation,
        pd.DataFrame({'a': [1, 2, 3],
                      'b': ['a', 'b', 'c']}),
        start, end)
    log.error.assert_called()


def test_post_observation_data(mock_api, log, fake_ghi_data, start, end):
    common.post_observation_data(mock_api, site_test_observation,
                                 fake_ghi_data, start, end)

    args, _ = mock_api.post_observation_values.call_args
    # test observations never get assigned an id so the observation_id
    # argument should be an empty string
    assert args[0] == ''
    pd.testing.assert_frame_equal(
        args[1], fake_ghi_data.rename(columns={'ghi': 'value'}))


def test_post_observation_data_HTTPError(
        mock_api, log, fake_ghi_data, start, end):
    # mocking this error means that when the debugging logging call
    # fires, an AttributeError is thrown while looking for a response
    # but this also tests that we've followed the correct logic.
    mock_api.post_observation_values.side_effect = HTTPError
    with pytest.raises(AttributeError):
        common.post_observation_data(mock_api, site_test_observation,
                                     fake_ghi_data, start, end)
    log.error.assert_called()


def test_post_observation_data_all_nans(
        mock_api, log, fake_ghi_data, start, end):
    nan_data = fake_ghi_data.copy()
    nan_data['ghi'] = np.NaN
    ret = common.post_observation_data(mock_api, site_test_observation,
                                       nan_data, start, end)
    log.warning.assert_called()
    assert ret is None


@pytest.mark.parametrize('site', site_objects)
def test_update_site_observations(
        mock_api, mock_fetch, site, observation_objects_param, fake_ghi_data):
    start = pd.Timestamp('20190101T1205Z')
    end = pd.Timestamp('20190101T1225Z')
    common.update_site_observations(
        mock_api, mock_fetch, site, observation_objects_param, start, end)
    args, _ = mock_api.post_observation_values.call_args
    assert args[0] == ''
    pd.testing.assert_frame_equal(
        args[1], fake_ghi_data.rename(columns={'ghi': 'value'})[start:end])


def test_update_site_observations_no_data(
        mock_api, mocker, site_objects_param,
        observation_objects_param, log, start, end):
    fetch = mocker.MagicMock()
    fetch.return_value = pd.DataFrame()
    common.update_site_observations(
        mock_api, fetch, site_objects[1],
        observation_objects_param, start, end)

    mock_api.assert_not_called()
    log.warning.assert_called_once()