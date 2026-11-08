"""Roll up additive sufficient statistics; mirror M2 finalize() definitions."""
import math

RATIOS = {
    "cancel_rate": ("cancelled", "flights"), "divert_rate": ("diverted", "flights"),
    "otp_operated": ("on_time", "arr_n"), "otp_scheduled": ("on_time", "flights"),
    "delay15_rate": ("delayed15", "arr_n"), "severe60_rate": ("delayed60", "arr_n"),
    "avg_arr_delay_net": ("sum_arr_delay", "arr_n"),
    "avg_arr_delay_pos": ("sum_arr_delay_pos", "arr_n"),
    "avg_delay_when_late": ("sum_arr_delay_late", "delayed15"),
    "dep_delay15_rate": ("dep_delayed15", "dep_n"),
    "avg_dep_delay_pos": ("sum_dep_delay_pos", "dep_n"),
    "avg_air_gain": ("sum_air_gain", "gain_n"),
}
ADDITIVE = sorted({x for pair in RATIOS.values() for x in pair})


def ratio(numerator, denominator):
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def summarize(rows):
    rows = list(rows)
    if not rows:
        return {}
    result = {}
    for field in ADDITIVE:
        values = [r[field] for r in rows if r.get(field) is not None]
        result[field] = math.fsum(values) if values else None
    for field, (numerator, denominator) in RATIOS.items():
        result[field] = ratio(result[numerator], result[denominator])
    penalty = sum(weight * (result[field] or 0) for field, weight in [
        ("delay15_rate", .50), ("severe60_rate", .20),
        ("cancel_rate", .25), ("divert_rate", .05)])
    result["reliability_score"] = max(0., min(100., 100 * (1 - penalty)))
    return result
