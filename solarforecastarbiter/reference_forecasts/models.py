"""
Default processing functions for data from NOAA weather models.

All public functions in this module have the same signature.

The functions accept:

  * latitude : float
  * longitude : float
  * elevation : float
  * init_time : pd.Timestamp
      Full datetime of a model initialization
  * start : pd.Timestamp
  * end : pd.Timestamp
  * load_forecast : function
      A function that accepts the arguments above and returns the
      correct data. Enables users to supply their own data independently
      of the `solarforecastarbiter.io` module.

The functions return a tuple of:

  * ghi : pd.Series
  * dni : pd.Series
  * dhi : pd.Series
  * temp_air : pd.Series
  * wind_speed : pd.Series
  * resampler : function
      A function that resamples data to the appropriate frequency.
      This function is to be applied to all forecast variables after
      power is calculated.
  * solar_position_calculator : function
      A function that returns solar position at the ghi forecast times
      (after internal interpolation, before external resampling). The
      function will return results immediately if solar position is
      already known or will call a solar position calculation algorithm
      and then return.

Most of the model functions return forecast data interpolated to 5
minute frequency. Interpolation to 5 minutes reduces the errors
associated with solar position and irradiance to power models (these
models assume instantaneous inputs). Why 5 minutes? It's a round number
that produces about 10 data points per hour, so it's reasonable for hour
average calculations. It is expected that after calculating power, users
will apply the `resampler` function to both the weather and power
forecasts. These functions may be most useful if the user would like to
understand the performance of a NWP model with modest post-processing.

Several model functions return instantaneous data that is coincident
with the NWP model forecast time (15 minutes or hourly, depending on the
NWP model). The resamplers returned by these functions do not modify the
data (though they do define the frequency attribute of the data's
DatetimeIndex). These functions may most useful if the user would like
to understand the raw performance of a NWP model.

The functions in this module accept primitives (floats, strings, etc.)
rather than objects defined in :py:mod:`solarforecastarbiter.datamodel`
because we anticipate that these functions may be of more general use
and that functions that accept primitives may be easier to maintain in
the long run.
"""

from functools import partial

from solarforecastarbiter import pvmodel
from solarforecastarbiter.io.nwp import load_forecast
from solarforecastarbiter.reference_forecasts import forecast


def _resample_using_cloud_cover(latitude, longitude, elevation,
                                cloud_cover, temp_air, wind_speed):
    """
    Calculate all irradiance components from cloud cover.
    """
    # Interpolate cloud cover, temp, and wind to higher temporal resolution
    # because solar position and PV power calculations assume instantaneous
    # inputs. Why 5 minutes? It's a round number that produces order 10 data
    # points per hour, so it's reasonable for hour average calculations.
    interpolator = partial(forecast.interpolate, freq='5min')
    cloud_cover, temp_air, wind_speed = list(
        map(interpolator, (cloud_cover, temp_air, wind_speed)))
    solar_position = pvmodel.calculate_solar_position(
        latitude, longitude, elevation, cloud_cover.index)
    ghi, dni, dhi = forecast.cloud_cover_to_irradiance(
        latitude, longitude, elevation, cloud_cover,
        solar_position['apparent_zenith'], solar_position['zenith'])
    resampler = partial(forecast.resample, freq='1h')

    def solar_pos_calculator(): return solar_position

    return ghi, dni, dhi, temp_air, wind_speed, resampler, solar_pos_calculator


def _ghi_to_dni_dhi(latitude, longitude, elevation, ghi):
    """
    Calculate DNI, DHI from GHI and calculated solar position.
    """
    solar_position = pvmodel.calculate_solar_position(
        latitude, longitude, elevation, ghi.index)
    dni, dhi = pvmodel.complete_irradiance_components(
        ghi, solar_position['zenith'])

    def solar_pos_calculator(): return solar_position
    return dni, dhi, solar_pos_calculator


def hrrr_subhourly_to_subhourly_instantaneous(latitude, longitude, elevation,
                                              init_time, start, end,
                                              load_forecast=load_forecast):
    """
    Subhourly (15 min) instantantaneous HRRR forecast.
    GHI, DNI, DHI directly from model.
    Max forecast horizon 18 or 36 hours (0Z, 6Z, 12Z, 18Z).
    """
    ghi, dni, dhi, temp_air, wind_speed = load_forecast(
        latitude, longitude, init_time, start, end, 'hrrr_subhourly')
    # resampler takes 15 min instantaneous in, retuns 15 min instantaneous out
    # still want to call resample, rather than pass through lambda x: x
    # so that DatetimeIndex has well-defined freq attribute
    resampler = partial(forecast.resample, freq='15min')
    solar_pos_calculator = partial(
        pvmodel.calculate_solar_position, latitude, longitude, elevation,
        ghi.index)
    return ghi, dni, dhi, temp_air, wind_speed, resampler, solar_pos_calculator


def hrrr_subhourly_to_hourly_mean(latitude, longitude, elevation,
                                  init_time, start, end,
                                  load_forecast=load_forecast):
    """
    Hourly mean HRRR forecast.
    GHI, DNI, DHI directly from model, resampled.
    Max forecast horizon 18 or 36 hours (0Z, 6Z, 12Z, 18Z).
    """
    ghi, dni, dhi, temp_air, wind_speed = load_forecast(
        latitude, longitude, init_time, start, end, 'hrrr_subhourly')
    # interpolate irrad, temp, wind data to 5 min to
    # minimize weather to power errors.
    interpolator = partial(forecast.interpolate, freq='5min')
    ghi, dni, dhi, temp_air, wind_speed = list(
        map(interpolator, (ghi, dni, dhi, temp_air, wind_speed)))
    # user may weather (and optionally power) will eventually be resampled
    # to hourly average using resampler defined below
    resampler = partial(forecast.resample, freq='1h')
    solar_pos_calculator = partial(
        pvmodel.calculate_solar_position, latitude, longitude, elevation,
        ghi.index)
    return ghi, dni, dhi, temp_air, wind_speed, resampler, solar_pos_calculator


def rap_ghi_to_instantaneous(latitude, longitude, elevation,
                             init_time, start, end,
                             load_forecast=load_forecast):
    """
    Hourly instantantaneous RAP forecast.
    GHI directly from NWP model. DNI, DHI computed.
    Max forecast horizon 21 or 39 (3Z, 9Z, 15Z, 21Z) hours.
    """
    # dni and dhi not in RAP output available from g2sub service
    ghi, temp_air, wind_speed = load_forecast(
        latitude, longitude, init_time, start, end, 'rap',
        variables=('ghi', 'temp_air', 'wind_speed'))
    dni, dhi, solar_pos_calculator = _ghi_to_dni_dhi(
        latitude, longitude, elevation, ghi)
    # hourly instant in, hourly instant out
    resampler = partial(forecast.resample, freq='1h')
    return ghi, dni, dhi, temp_air, wind_speed, resampler, solar_pos_calculator


def rap_ghi_to_hourly_mean(latitude, longitude, elevation,
                           init_time, start, end,
                           load_forecast=load_forecast):
    """
    Take hourly RAP instantantaneous irradiance and convert it to hourly
    average forecasts.
    GHI directly from NWP model. DNI, DHI computed.
    Max forecast horizon 21 or 39 (3Z, 9Z, 15Z, 21Z) hours.
    """
    # dni and dhi not in RAP output available from g2sub service
    ghi, temp_air, wind_speed = load_forecast(
        latitude, longitude, init_time, start, end, 'rap',
        variables=('ghi', 'temp_air', 'wind_speed'))
    dni, dhi, solar_pos_calculator = _ghi_to_dni_dhi(
        latitude, longitude, elevation, ghi)
    interpolator = partial(forecast.interpolate, freq='5min')
    ghi, dni, dhi, temp_air, wind_speed = list(
        map(interpolator, (ghi, dni, dhi, temp_air, wind_speed)))
    resampler = partial(forecast.resample, freq='1h')
    return ghi, dni, dhi, temp_air, wind_speed, resampler, solar_pos_calculator


def rap_cloud_cover_to_hourly_mean(latitude, longitude, elevation,
                                   init_time, start, end,
                                   load_forecast=load_forecast):
    """
    Take hourly RAP instantantaneous cloud cover and convert it to
    hourly average forecasts.
    GHI from NWP model cloud cover. DNI, DHI computed.
    Max forecast horizon 21 or 39 (3Z, 9Z, 15Z, 21Z) hours.
    """
    cloud_cover, temp_air, wind_speed = load_forecast(
        latitude, longitude, init_time, start, end, 'rap',
        variables=('cloud_cover', 'temp_air', 'wind_speed'))
    return _resample_using_cloud_cover(latitude, longitude, elevation,
                                       cloud_cover, temp_air, wind_speed)


def gfs_quarter_deg_3hour_to_hourly_mean(latitude, longitude, elevation,
                                         init_time, start, end,
                                         load_forecast=load_forecast):
    """
    Take 3 hr GFS and convert it to hourly average data.
    GHI from NWP model cloud cover. DNI, DHI computed.
    Max forecast horizon 240 hours.
    """
    cloud_cover, temp_air, wind_speed = load_forecast(
        latitude, longitude, init_time, start, end, 'gfs_3h')
    cloud_cover = forecast.unmix_intervals(cloud_cover)
    return _resample_using_cloud_cover(latitude, longitude, elevation,
                                       cloud_cover, temp_air, wind_speed)


def gfs_quarter_deg_hourly_to_hourly_mean(latitude, longitude, elevation,
                                          init_time, start, end,
                                          load_forecast=load_forecast):
    """
    Take 1 hr GFS and convert it to hourly average data.
    GHI from NWP model cloud cover. DNI, DHI computed.
    Max forecast horizon 120 hours.
    """
    cloud_cover, temp_air, wind_speed = load_forecast(
        latitude, longitude, init_time, start, end, 'gfs_1h')
    cloud_cover = forecast.unmix_intervals(cloud_cover)
    return _resample_using_cloud_cover(latitude, longitude, elevation,
                                       cloud_cover, temp_air, wind_speed)


def gfs_quarter_deg_to_hourly_mean(latitude, longitude, elevation,
                                   init_time, start, end,
                                   load_forecast=load_forecast):
    """
    Hourly average forecasts derived from GFS 1-3 hr frequency output.
    GHI directly from NWP model. DNI, DHI computed.
    Max forecast horizon 240 hours.
    """
    # this function is supposed to be able to handle the switch from
    # hourly to 3 hourly output.
    # unclear if this should call gfs_quarter_deg_hourly_to_hourly_mean
    # and then gfs_quarter_deg_3hour_to_hourly_mean or if it should
    # do everything here. defer until after storage implementation is
    # more clear.
    raise NotImplementedError


def nam_12km_hourly_to_hourly_instantaneous(latitude, longitude, elevation,
                                            init_time, start, end,
                                            load_forecast=load_forecast):
    """
    Hourly instantantaneous forecast.
    GHI directly from NWP model. DNI, DHI computed.
    Max forecast horizon 36 hours.
    """
    ghi, temp_air, wind_speed = load_forecast(
        latitude, longitude, init_time, start, end, 'nam')
    dni, dhi, solar_pos_calculator = _ghi_to_dni_dhi(
        latitude, longitude, elevation, ghi)
    # hourly instant in, hourly instant out
    resampler = partial(forecast.resample, freq='1h')
    return ghi, dni, dhi, temp_air, wind_speed, resampler, solar_pos_calculator


def nam_12km_cloud_cover_to_hourly_mean(latitude, longitude, elevation,
                                        init_time, start, end,
                                        load_forecast=load_forecast):
    """
    Hourly average forecast.
    GHI from NWP model cloud cover. DNI, DHI computed.
    Max forecast horizon 72 hours.
    """
    cloud_cover, temp_air, wind_speed = load_forecast(
        latitude, longitude, init_time, start, end, 'nam',
        variables=('cloud_cover', 'temp_air', 'wind_speed'))
    return _resample_using_cloud_cover(latitude, longitude, elevation,
                                       cloud_cover, temp_air, wind_speed)