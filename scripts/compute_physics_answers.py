"""Compute the reference answers for the physics items in Study 2.

Boiling points use the International Standard Atmosphere for pressure at
altitude and the Antoine equation for water. Run with: python scripts/compute_physics_answers.py
"""

import math


def isa_pressure_kpa(altitude_m: float) -> float:
    """Pressure in the ISA troposphere (valid below 11 km)."""
    return 101.325 * (1 - 2.25577e-5 * altitude_m) ** 5.25588


def water_boiling_point_c(pressure_kpa: float) -> float:
    """Antoine equation for water; coefficients switch at 100 °C."""
    mmhg = pressure_kpa * 7.50062
    if pressure_kpa <= 101.325:
        a, b, c = 8.07131, 1730.63, 233.426
    else:
        a, b, c = 8.14019, 1810.94, 244.485
    return b / (a - math.log10(mmhg)) - c


def speed_of_sound(temperature_k: float) -> float:
    return math.sqrt(1.4 * 287.05 * temperature_k)


if __name__ == "__main__":
    for name, altitude in [
        ("Aconcagua", 6961),
        ("Denali", 6190),
        ("Kilimanjaro", 5895),
        ("Elbrus", 5642),
        ("Mont Blanc", 4806),
        ("La Paz", 3640),
    ]:
        print(f"{name:12s} {altitude:5d} m  {water_boiling_point_c(isa_pressure_kpa(altitude)):.1f} °C")
    print(f"Pressure cooker (1 bar gauge)  {water_boiling_point_c(101.325 + 100):.1f} °C")
    print(f"Speed of sound at 11 km        {speed_of_sound(216.65):.1f} m/s")
