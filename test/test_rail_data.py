import json
import math
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class RailDataTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = (ROOT / "rail-data.js").read_text(encoding="utf-8")
        cls.data = json.loads(source.removeprefix("const railData = ").removesuffix(";\n"))

    def test_all_station_communes_have_all_requested_years(self):
        stations = self.data["stations"]
        self.assertEqual(len(stations), 8)
        codes = {station["code"] for station in stations}
        self.assertEqual(len(codes), 7)
        self.assertEqual(
            {station["name"] for station in stations if station["code"] == "30171"},
            {"Molières-sur-Cèze", "Gammal"},
        )
        for code in codes:
            self.assertEqual(set(self.data["rates"][code]), {"2013", "2015", "2020", "2023"})
            for rate in self.data["rates"][code].values():
                self.assertGreaterEqual(rate, 0)
                self.assertLessEqual(rate, 100)

    def test_railway_passes_near_each_station(self):
        route = self.data["route"]
        for station in self.data["stations"]:
            lat, lon = station["position"]
            distance_km = min(
                math.hypot((lat - point[0]) * 111.2, (lon - point[1]) * 80)
                for point in route
            )
            self.assertLess(distance_km, 0.3, station["name"])

    def test_rate_examples_match_insee(self):
        self.assertEqual(self.data["rates"]["30007"]["2015"], 24.7)
        self.assertEqual(self.data["rates"]["30171"]["2020"], 31.2)
        self.assertEqual(self.data["rates"]["30227"]["2023"], 26.1)


if __name__ == "__main__":
    unittest.main()
