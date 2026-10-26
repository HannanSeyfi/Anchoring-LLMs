"""Compute the true answers that question set v2 derives by calculation.

- Great-circle distances between cities (haversine, mean Earth radius 6,371 km), from the
  city coordinates in English Wikipedia (checked 2026-10-26).
- Boiling points of water at altitude: International Standard Atmosphere and the Antoine
  equation, as in scripts/compute_physics_answers.py, from Wikipedia elevations.
- Speed of sound in gases at 20 °C: ideal gas, c = sqrt(gamma * R * T / M).

Run with: python scripts/compute_answers_v2.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from compute_physics_answers import isa_pressure_kpa, water_boiling_point_c  # noqa: E402

EARTH_RADIUS_KM = 6371.0

# Latitude, longitude (degrees) from each city's Wikipedia article.
CITIES = {
    "Tehran": (35.6889, 51.3897), "Reykjavík": (64.1458, -21.9425),
    "Lisbon": (38.7253, -9.15), "Novosibirsk": (55.05, 82.95),
    "Nairobi": (-1.2864, 36.8172), "Oslo": (59.9133, 10.7389),
    "Lima": (-12.06, -77.0375), "Cape Town": (-33.9253, 18.4239),
    "Perth": (-32.0, 115.9), "Johannesburg": (-26.2044, 28.0456),
    "Anchorage": (61.2167, -149.8936), "Honolulu": (21.3, -157.85),
    "Ulaanbaatar": (47.9219, 106.9153), "Cairo": (30.0444, 31.2358),
    "Quito": (-0.22, -78.5125), "Madrid": (40.4169, -3.7033),
    "Wellington": (-41.2889, 174.7772), "Santiago": (-33.4375, -70.65),
    "Helsinki": (60.1708, 24.9375), "Baku": (40.3756, 49.8325),
    "Tashkent": (41.3111, 69.2797), "Dakar": (14.6928, -17.4467),
    "Kathmandu": (27.71, 85.32),
}

PAIRS = [
    ("Tehran", "Reykjavík"), ("Lisbon", "Novosibirsk"), ("Nairobi", "Oslo"), ("Lima", "Cape Town"),
    ("Perth", "Johannesburg"), ("Anchorage", "Honolulu"), ("Ulaanbaatar", "Cairo"),
    ("Quito", "Madrid"), ("Wellington", "Santiago"), ("Helsinki", "Baku"), ("Tashkent", "Dakar"),
    ("Kathmandu", "Nairobi"),
]

# Elevation in metres from each place's Wikipedia article.
ALTITUDES = {
    "Ojos del Salado (summit)": 6893, "Mount Logan (summit)": 5959,
    "Pico de Orizaba (summit)": 5636, "Mount Damavand (summit)": 5610,
    "La Rinconada, Peru": 5100, "Potosí, Bolivia": 4067, "Lhasa": 3656, "Cusco": 3399,
}

R_GAS = 8.314462618  # J/(mol K)
# Ratio of heat capacities and molar mass (kg/mol) near room temperature.
GASES = {
    "argon": (5 / 3, 0.039948), "neon": (5 / 3, 0.020180), "krypton": (5 / 3, 0.083798),
    "xenon": (5 / 3, 0.131293), "methane": (1.304, 0.016043), "carbon dioxide": (1.289, 0.044009),
}


def great_circle_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2)
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(h))


def sound_speed(gamma: float, molar_mass: float, temperature_k: float = 293.15) -> float:
    return math.sqrt(gamma * R_GAS * temperature_k / molar_mass)


def main() -> None:
    print("Great-circle distances")
    for a, b in PAIRS:
        print(f"  {a} - {b}: {great_circle_km(CITIES[a], CITIES[b]):,.0f} km")
    print("Boiling point of water")
    for place, alt in ALTITUDES.items():
        print(f"  {place} ({alt} m): {water_boiling_point_c(isa_pressure_kpa(alt)):.1f} °C")
    print("Speed of sound at 20 °C")
    for gas, (gamma, m) in GASES.items():
        print(f"  {gas}: {sound_speed(gamma, m):.0f} m/s")


if __name__ == "__main__":
    main()
