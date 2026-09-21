import unittest

from fastapi import HTTPException

from errors import ApplicationError
from routes.http_errors import raise_http_error


class HttpErrorAdapterTests(unittest.TestCase):
    def test_application_error_is_translated_to_http_exception(self):
        detail = {"message": "Ошибка домена"}

        with self.assertRaises(HTTPException) as rejected:
            raise_http_error(ApplicationError(status_code=409, detail=detail))

        self.assertEqual(rejected.exception.status_code, 409)
        self.assertEqual(rejected.exception.detail, detail)


if __name__ == "__main__":
    unittest.main()
