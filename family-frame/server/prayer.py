# Prayer-time calculation, a faithful Python port of the batoulapps/adhan
# JavaScript library (v4.4.6) that the family-frame web app uses. Only the
# ISNA method, Shafi/Hanafi Asr, and the "Middle of the Night" high-latitude
# rule are needed here, but the astronomical core is ported in full so the
# numbers match the frame exactly.
#
# All returned times are naive UTC datetimes.

import math
from datetime import datetime, timedelta, timezone


# ---- MathUtils -----------------------------------------------------------

def degrees_to_radians(degrees):
    return degrees * math.pi / 180.0


def radians_to_degrees(radians):
    return radians * 180.0 / math.pi


def normalize_to_scale(num, maximum):
    return num - maximum * math.floor(num / maximum)


def unwind_angle(angle):
    return normalize_to_scale(angle, 360.0)


def quadrant_shift_angle(angle):
    if -180 <= angle <= 180:
        return angle
    return angle - 360 * round(angle / 360)


def js_round(x):
    # Math.round: rounds half away from zero on the integer, i.e. floor(x + 0.5)
    return math.floor(x + 0.5)


# ---- Date helpers --------------------------------------------------------

def date_by_adding_seconds(dt, seconds):
    return dt + timedelta(seconds=seconds)


def date_by_adding_minutes(dt, minutes):
    return date_by_adding_seconds(dt, minutes * 60)


def date_by_adding_days(dt, days):
    return dt + timedelta(days=days)


def is_leap_year(year):
    if year % 4 != 0:
        return False
    if year % 100 == 0 and year % 400 != 0:
        return False
    return True


def rounded_minute(dt, rounding="nearest"):
    seconds = dt.second
    if rounding == "up":
        offset = 60 - seconds
    elif rounding == "none":
        offset = 0
    else:  # nearest
        offset = 60 - seconds if seconds >= 30 else -seconds
    return date_by_adding_seconds(dt, offset)


# ---- Astronomical --------------------------------------------------------

def julian_day(year, month, day, hours=0):
    trunc = math.trunc
    Y = trunc(year if month > 2 else year - 1)
    M = trunc(month if month > 2 else month + 12)
    D = day + hours / 24
    A = trunc(Y / 100)
    B = trunc(2 - A + trunc(A / 4))
    i0 = trunc(365.25 * (Y + 4716))
    i1 = trunc(30.6001 * (M + 1))
    return i0 + i1 + D + B - 1524.5


def julian_century(jd):
    return (jd - 2451545.0) / 36525


def mean_solar_longitude(jc):
    T = jc
    term1 = 280.4664567
    term2 = 36000.76983 * T
    term3 = 0.0003032 * T ** 2
    return unwind_angle(term1 + term2 + term3)


def mean_lunar_longitude(jc):
    T = jc
    term1 = 218.3165
    term2 = 481267.8813 * T
    return unwind_angle(term1 + term2)


def ascending_lunar_node_longitude(jc):
    T = jc
    term1 = 125.04452
    term2 = 1934.136261 * T
    term3 = 0.0020708 * T ** 2
    term4 = T ** 3 / 450000
    return unwind_angle(term1 - term2 + term3 + term4)


def mean_solar_anomaly(jc):
    T = jc
    term1 = 357.52911
    term2 = 35999.05029 * T
    term3 = 0.0001537 * T ** 2
    return unwind_angle(term1 + term2 - term3)


def solar_equation_of_the_center(jc, mean_anomaly):
    T = jc
    Mrad = degrees_to_radians(mean_anomaly)
    term1 = (1.914602 - 0.004817 * T - 0.000014 * T ** 2) * math.sin(Mrad)
    term2 = (0.019993 - 0.000101 * T) * math.sin(2 * Mrad)
    term3 = 0.000289 * math.sin(3 * Mrad)
    return term1 + term2 + term3


def apparent_solar_longitude(jc, mean_longitude):
    T = jc
    L0 = mean_longitude
    longitude = L0 + solar_equation_of_the_center(T, mean_solar_anomaly(T))
    Omega = 125.04 - 1934.136 * T
    Lambda = longitude - 0.00569 - 0.00478 * math.sin(degrees_to_radians(Omega))
    return unwind_angle(Lambda)


def mean_obliquity_of_the_ecliptic(jc):
    T = jc
    term1 = 23.439291
    term2 = 0.013004167 * T
    term3 = 0.0000001639 * T ** 2
    term4 = 0.0000005036 * T ** 3
    return term1 - term2 - term3 + term4


def apparent_obliquity_of_the_ecliptic(jc, mean_obliquity):
    T = jc
    O = 125.04 - 1934.136 * T
    return mean_obliquity + 0.00256 * math.cos(degrees_to_radians(O))


def mean_sidereal_time(jc):
    T = jc
    JD = T * 36525 + 2451545.0
    term1 = 280.46061837
    term2 = 360.98564736629 * (JD - 2451545)
    term3 = 0.000387933 * T ** 2
    term4 = T ** 3 / 38710000
    return unwind_angle(term1 + term2 + term3 - term4)


def nutation_in_longitude(jc, solar_longitude, lunar_longitude, ascending_node):
    L0 = solar_longitude
    Lp = lunar_longitude
    Omega = ascending_node
    term1 = -17.2 / 3600 * math.sin(degrees_to_radians(Omega))
    term2 = 1.32 / 3600 * math.sin(2 * degrees_to_radians(L0))
    term3 = 0.23 / 3600 * math.sin(2 * degrees_to_radians(Lp))
    term4 = 0.21 / 3600 * math.sin(2 * degrees_to_radians(Omega))
    return term1 - term2 - term3 + term4


def nutation_in_obliquity(jc, solar_longitude, lunar_longitude, ascending_node):
    L0 = solar_longitude
    Lp = lunar_longitude
    Omega = ascending_node
    term1 = 9.2 / 3600 * math.cos(degrees_to_radians(Omega))
    term2 = 0.57 / 3600 * math.cos(2 * degrees_to_radians(L0))
    term3 = 0.1 / 3600 * math.cos(2 * degrees_to_radians(Lp))
    term4 = 0.09 / 3600 * math.cos(2 * degrees_to_radians(Omega))
    return term1 + term2 + term3 - term4


def altitude_of_celestial_body(observer_latitude, declination, local_hour_angle):
    Phi = observer_latitude
    delta = declination
    H = local_hour_angle
    term1 = math.sin(degrees_to_radians(Phi)) * math.sin(degrees_to_radians(delta))
    term2 = math.cos(degrees_to_radians(Phi)) * math.cos(degrees_to_radians(delta)) * math.cos(degrees_to_radians(H))
    return radians_to_degrees(math.asin(term1 + term2))


def approximate_transit(longitude, sidereal_time, right_ascension):
    L = longitude
    Theta0 = sidereal_time
    a2 = right_ascension
    Lw = L * -1
    m0 = normalize_to_scale((a2 + Lw - Theta0) / 360, 1)
    expected = normalize_to_scale((12.0 - L / 15.0) / 24.0, 1)
    if m0 - expected > 0.5:
        return m0 - 1.0
    if expected - m0 > 0.5:
        return m0 + 1.0
    return m0


def corrected_transit(approx_transit, longitude, sidereal_time, right_ascension,
                      previous_right_ascension, next_right_ascension):
    m0 = approx_transit
    L = longitude
    Theta0 = sidereal_time
    a2 = right_ascension
    a1 = previous_right_ascension
    a3 = next_right_ascension
    Lw = L * -1
    Theta = unwind_angle(Theta0 + 360.985647 * m0)
    a = unwind_angle(interpolate_angles(a2, a1, a3, m0))
    H = quadrant_shift_angle(Theta - Lw - a)
    dm = H / -360
    return (m0 + dm) * 24


def corrected_hour_angle(approx_transit, angle, coordinates, after_transit,
                         sidereal_time, right_ascension, prev_ra, next_ra,
                         declination, prev_decl, next_decl):
    m0 = approx_transit
    h0 = angle
    Theta0 = sidereal_time
    a2 = right_ascension
    a1 = prev_ra
    a3 = next_ra
    d2 = declination
    d1 = prev_decl
    d3 = next_decl
    lat = coordinates.latitude
    lon = coordinates.longitude
    Lw = lon * -1
    term1 = math.sin(degrees_to_radians(h0)) - math.sin(degrees_to_radians(lat)) * math.sin(degrees_to_radians(d2))
    term2 = math.cos(degrees_to_radians(lat)) * math.cos(degrees_to_radians(d2))
    H0 = radians_to_degrees(math.acos(term1 / term2))
    m = m0 + H0 / 360 if after_transit else m0 - H0 / 360
    Theta = unwind_angle(Theta0 + 360.985647 * m)
    a = unwind_angle(interpolate_angles(a2, a1, a3, m))
    delta = interpolate(d2, d1, d3, m)
    H = Theta - Lw - a
    h = altitude_of_celestial_body(lat, delta, H)
    term3 = h - h0
    term4 = 360 * math.cos(degrees_to_radians(delta)) * math.cos(degrees_to_radians(lat)) * math.sin(degrees_to_radians(H))
    dm = term3 / term4
    return (m + dm) * 24


def interpolate(y2, y1, y3, n):
    a = y2 - y1
    b = y3 - y2
    c = b - a
    return y2 + n / 2 * (a + b + n * c)


def interpolate_angles(y2, y1, y3, n):
    a = unwind_angle(y2 - y1)
    b = unwind_angle(y3 - y2)
    c = b - a
    return y2 + n / 2 * (a + b + n * c)


# ---- SolarCoordinates ----------------------------------------------------

class SolarCoordinates:
    def __init__(self, jd):
        T = julian_century(jd)
        L0 = mean_solar_longitude(T)
        Lp = mean_lunar_longitude(T)
        Omega = ascending_lunar_node_longitude(T)
        Lambda = degrees_to_radians(apparent_solar_longitude(T, L0))
        Theta0 = mean_sidereal_time(T)
        dPsi = nutation_in_longitude(T, L0, Lp, Omega)
        dEpsilon = nutation_in_obliquity(T, L0, Lp, Omega)
        Epsilon0 = mean_obliquity_of_the_ecliptic(T)
        EpsilonApparent = degrees_to_radians(apparent_obliquity_of_the_ecliptic(T, Epsilon0))
        self.declination = radians_to_degrees(math.asin(math.sin(EpsilonApparent) * math.sin(Lambda)))
        self.right_ascension = unwind_angle(radians_to_degrees(math.atan2(
            math.cos(EpsilonApparent) * math.sin(Lambda), math.cos(Lambda))))
        self.apparent_sidereal_time = Theta0 + dPsi * 3600 * math.cos(degrees_to_radians(Epsilon0 + dEpsilon)) / 3600


# ---- Coordinates ---------------------------------------------------------

class Coordinates:
    def __init__(self, latitude, longitude):
        self.latitude = latitude
        self.longitude = longitude


# ---- SolarTime -----------------------------------------------------------

class SolarTime:
    def __init__(self, date, coordinates):
        jd = julian_day(date.year, date.month, date.day, 0)
        self.observer = coordinates
        self.solar = SolarCoordinates(jd)
        self.prev_solar = SolarCoordinates(jd - 1)
        self.next_solar = SolarCoordinates(jd + 1)
        m0 = approximate_transit(coordinates.longitude, self.solar.apparent_sidereal_time,
                                 self.solar.right_ascension)
        solar_altitude = -50.0 / 60.0
        self.approx_transit = m0
        self.transit = corrected_transit(m0, coordinates.longitude, self.solar.apparent_sidereal_time,
                                         self.solar.right_ascension, self.prev_solar.right_ascension,
                                         self.next_solar.right_ascension)
        self.sunrise = corrected_hour_angle(m0, solar_altitude, coordinates, False,
                                            self.solar.apparent_sidereal_time, self.solar.right_ascension,
                                            self.prev_solar.right_ascension, self.next_solar.right_ascension,
                                            self.solar.declination, self.prev_solar.declination,
                                            self.next_solar.declination)
        self.sunset = corrected_hour_angle(m0, solar_altitude, coordinates, True,
                                           self.solar.apparent_sidereal_time, self.solar.right_ascension,
                                           self.prev_solar.right_ascension, self.next_solar.right_ascension,
                                           self.solar.declination, self.prev_solar.declination,
                                           self.next_solar.declination)

    def hour_angle(self, angle, after_transit):
        return corrected_hour_angle(self.approx_transit, angle, self.observer, after_transit,
                                    self.solar.apparent_sidereal_time, self.solar.right_ascension,
                                    self.prev_solar.right_ascension, self.next_solar.right_ascension,
                                    self.solar.declination, self.prev_solar.declination,
                                    self.next_solar.declination)

    def afternoon(self, shadow_length):
        tangent = abs(self.observer.latitude - self.solar.declination)
        inverse = shadow_length + math.tan(degrees_to_radians(tangent))
        angle = radians_to_degrees(math.atan(1.0 / inverse))
        return self.hour_angle(angle, True)


# ---- CalculationParameters (ISNA subset) ---------------------------------

class CalculationParameters:
    def __init__(self, madhab="shafi"):
        # ISNA: Fajr 15, Isha 15, Dhuhr +1 minute. High-latitude rule:
        # Middle of the Night. Polar-circle resolution: Unresolved.
        self.method = "NorthAmerica"
        self.fajr_angle = 15
        self.isha_angle = 15
        self.isha_interval = 0
        self.maghrib_angle = 0
        self.madhab = madhab  # "shafi" or "hanafi"
        self.adjustments = {"fajr": 0, "sunrise": 0, "dhuhr": 0, "asr": 0, "maghrib": 0, "isha": 0}
        self.method_adjustments = {"fajr": 0, "sunrise": 0, "dhuhr": 1, "asr": 0, "maghrib": 0, "isha": 0}
        self.rounding = "nearest"

    def shadow_length(self):
        return 2 if self.madhab == "hanafi" else 1

    def night_portions(self):
        # Middle of the Night
        return {"fajr": 0.5, "isha": 0.5}


# ---- PrayerTimes ---------------------------------------------------------

class PrayerTimes:
    def __init__(self, coordinates, date, params):
        solar_time = SolarTime(date, coordinates)
        dhuhr_time = _utc_time(solar_time.transit, date)
        sunrise_time = _utc_time(solar_time.sunrise, date)
        sunset_time = _utc_time(solar_time.sunset, date)

        tomorrow = date_by_adding_days(date, 1)
        tomorrow_solar_time = SolarTime(tomorrow, coordinates)

        asr_time = _utc_time(solar_time.afternoon(params.shadow_length()), date)
        tomorrow_sunrise = _utc_time(tomorrow_solar_time.sunrise, tomorrow)
        night = (tomorrow_sunrise - sunset_time).total_seconds()

        fajr_time = _utc_time(solar_time.hour_angle(-1 * params.fajr_angle, False), date)

        night_fraction = params.night_portions()["fajr"] * night
        safe_fajr = date_by_adding_seconds(sunrise_time, -night_fraction)
        if fajr_time is None or safe_fajr > fajr_time:
            fajr_time = safe_fajr

        if params.isha_interval > 0:
            isha_time = date_by_adding_minutes(sunset_time, params.isha_interval)
        else:
            isha_time = _utc_time(solar_time.hour_angle(-1 * params.isha_angle, True), date)
            night_fraction = params.night_portions()["isha"] * night
            safe_isha = date_by_adding_seconds(sunset_time, night_fraction)
            if isha_time is None or safe_isha < isha_time:
                isha_time = safe_isha

        maghrib_time = sunset_time

        def adjusted(name, dt):
            minutes = params.adjustments.get(name, 0) + params.method_adjustments.get(name, 0)
            return rounded_minute(date_by_adding_minutes(dt, minutes), params.rounding)

        self.fajr = adjusted("fajr", fajr_time)
        self.sunrise = adjusted("sunrise", sunrise_time)
        self.dhuhr = adjusted("dhuhr", dhuhr_time)
        self.asr = adjusted("asr", asr_time)
        self.sunset = rounded_minute(sunset_time, params.rounding)
        self.maghrib = adjusted("maghrib", maghrib_time)
        self.isha = adjusted("isha", isha_time)


def _utc_time(hours_fraction, date):
    # hours_fraction is a fraction of a day in universal time. Build a naive
    # UTC datetime, rolling into the next day when the fraction passes 24.
    base = datetime(date.year, date.month, date.day)
    return base + timedelta(seconds=math.floor(hours_fraction * 3600))


def compute_prayer_times(latitude, longitude, day, madhab="shafi"):
    """Return a dict of naive-UTC datetimes for the given local civil day."""
    coords = Coordinates(latitude, longitude)
    params = CalculationParameters(madhab)
    pt = PrayerTimes(coords, day, params)
    return {
        "fajr": pt.fajr, "sunrise": pt.sunrise, "dhuhr": pt.dhuhr,
        "asr": pt.asr, "maghrib": pt.maghrib, "isha": pt.isha,
    }


if __name__ == "__main__":
    d = datetime(2026, 10, 15)
    for k, v in compute_prayer_times(40.7128, -74.0060, d).items():
        print(k, v.strftime("%H:%M:%S"), "UTC")
