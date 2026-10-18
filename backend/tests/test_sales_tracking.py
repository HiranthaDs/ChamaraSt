import unittest
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from pydantic import ValidationError

from backend.app.features.sales_tracking.models import LocationPoint
from backend.app.features.sales_tracking.service import distance_m, validate_point_order


class SalesTrackingTests(unittest.TestCase):
    def test_distance_uses_haversine_meters(self):
        a = {"latitude": 0, "longitude": 0}
        b = {"latitude": 0, "longitude": 1}
        self.assertAlmostEqual(distance_m(a, b), 111_195, delta=150)

    def test_coordinates_are_range_checked(self):
        with self.assertRaises(ValidationError):
            LocationPoint(latitude=91, longitude=0, accuracy_m=5,
                          client_timestamp=datetime.now(timezone.utc), sequence_number=1)

    def test_naive_timestamp_is_rejected(self):
        point = {"latitude": 6, "longitude": 79, "accuracy_m": 5,
                 "client_timestamp": datetime.now(), "sequence_number": 1}
        with self.assertRaises(HTTPException) as error:
            validate_point_order(None, point)
        self.assertEqual(error.exception.status_code, 422)

    def test_duplicate_sequence_is_rejected(self):
        now = datetime.now(timezone.utc)
        previous = {"latitude": 6, "longitude": 79, "sequence_number": 9,
                    "client_timestamp": now - timedelta(seconds=5)}
        point = {"latitude": 6, "longitude": 79, "sequence_number": 9,
                 "client_timestamp": now}
        with self.assertRaises(HTTPException) as error:
            validate_point_order(previous, point)
        self.assertEqual(error.exception.status_code, 409)

    def test_impossible_jump_is_rejected(self):
        now = datetime.now(timezone.utc)
        previous = {"latitude": 0, "longitude": 0, "sequence_number": 1,
                    "client_timestamp": now - timedelta(seconds=2)}
        point = {"latitude": 1, "longitude": 1, "sequence_number": 2,
                 "client_timestamp": now}
        with self.assertRaises(HTTPException) as error:
            validate_point_order(previous, point)
        self.assertEqual(error.exception.status_code, 422)


if __name__ == "__main__":
    unittest.main()
