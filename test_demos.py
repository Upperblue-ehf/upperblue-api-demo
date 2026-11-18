import os
import unittest
from datetime import date
from unittest.mock import MagicMock, patch

from api import get
from seismic import distance_km, fetch_day
from tides import fetch_tides

DAY = date(2026, 11, 17)


class SeismicTests(unittest.TestCase):
    def test_distance_in_kilometres(self):
        self.assertAlmostEqual(
            distance_km({"lat": 65, "lon": -20}, {"lat": 65, "lon": -19}), 47, delta=0.1
        )

    @patch("seismic.get")
    def test_pagination_and_map_bounds(self, request):
        row = {
            "event_time": "2026-11-17T12:00:00Z",
            "longitude": "-19",
            "latitude": "64",
            "magnitude": None,
        }

        def volcano(name, lon, lat):
            return {"geometry": {"coordinates": [lon, lat]}, "properties": {"name": name}}

        request.side_effect = [
            {"features": [volcano("Askja", -16.8, 65), volcano("Beerenberg", -8.1, 71.1)]},
            {"data": [row], "total": 2},
            {"data": [dict(row, magnitude="1.5")], "total": 2},
        ]
        sample = fetch_day(DAY)
        self.assertEqual([v["name"] for v in sample["volcanoes"]], ["Askja"])
        self.assertEqual([q["magnitude"] for q in sample["quakes"]], [None, 1.5])
        self.assertEqual(request.call_args.kwargs["offset"], 1)


class TideTests(unittest.TestCase):
    def setUp(self):
        self.site = {
            "provider_id": "reykjavik",
            "site_approved": True,
            "tide_site_id": "site-1",
            "name_is": "Reykjavík",
            "coverage_start": "2026-01-01",
            "coverage_end": "2026-12-31",
            "source_revision": "2026",
            "vertical_reference": "0 íslenskra sjókorta",
        }

    @patch("tides.get")
    def test_site_lookup_and_exclusive_end(self, request):
        event = {"valid_time": "2026-11-17T05:14:00Z", "event_type": "low", "height_m": 1.6}
        request.side_effect = [
            {"features": [{"properties": self.site}]},
            {"availability": "available", "data": [event]},
        ]
        self.assertEqual(fetch_tides(DAY)["events"][0]["height"], 1.6)
        request.assert_called_with(
            "ocean/tides/sites/site-1/events",
            start_time="2026-11-17T00:00:00Z",
            end_time="2026-11-20T00:00:00Z",
            source_version="2026",
        )

    @patch("tides.get")
    def test_three_days_must_fit_the_edition(self, request):
        request.return_value = {"features": [{"properties": self.site}]}
        with self.assertRaisesRegex(ValueError, "covers all three days"):
            fetch_tides(date(2026, 12, 30))
        request.assert_called_once()


class ClientTests(unittest.TestCase):
    @patch("api.requests.get")
    @patch("api.load_dotenv")
    @patch.dict(os.environ, {"UPPERBLUE_API_KEY": ""})
    def test_missing_key_stops_before_request(self, dotenv, request):
        with self.assertRaisesRegex(ValueError, "UPPERBLUE_API_KEY"):
            get("geodynamics/quakes")
        request.assert_not_called()

    @patch("api.requests.get")
    @patch.dict(os.environ, {"UPPERBLUE_API_KEY": "test-only"})
    def test_rate_limit_and_private_header(self, request):
        request.return_value.__enter__.return_value = MagicMock(
            status_code=429, headers={"Retry-After": "10"}
        )
        with self.assertRaisesRegex(ValueError, "Retry-After: 10"):
            get("geodynamics/quakes", limit=1)
        request.assert_called_once_with(
            "https://api.upperblue.com/geodynamics/quakes",
            params={"limit": 1},
            headers={"X-API-Key": "test-only"},
            timeout=(5, 30),
            allow_redirects=False,
        )
