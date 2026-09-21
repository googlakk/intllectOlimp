import unittest

from errors import ApplicationError


class ApplicationErrorTests(unittest.TestCase):
    def test_exposes_http_mapping_fields_and_stringifies_detail(self):
        detail = {"message": "Нужно подтвердить предупреждения"}

        error = ApplicationError(status_code=422, detail=detail)

        self.assertEqual(error.status_code, 422)
        self.assertEqual(error.detail, detail)
        self.assertEqual(str(error), str(detail))


if __name__ == "__main__":
    unittest.main()
