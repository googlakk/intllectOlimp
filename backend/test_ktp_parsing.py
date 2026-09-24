import unittest

from ktp.extract import Extraction
from ktp.parsing import KtpParseError, MAX_UPLOAD_BYTES, parse_ktp_draft


def extraction(tables=None):
    return Extraction(
        source_kind="docx",
        header_text="",
        tables=tables if tables is not None else [[["Номер", "Тема"], ["1", "Сложение"]]],
    )


class KtpParsingServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_parse_ktp_draft_attaches_source_and_stats(self):
        async def mapper(_extraction):
            return {
                "subject_name": "Математика",
                "sections": [
                    {"name": "A", "topics": [
                        {"name": "Тема 1", "learning_objectives": "Цель", "confidence": "high"},
                        {"name": "Тема 2", "learning_objectives": "", "confidence": "low"},
                    ]},
                    {"name": "B", "topics": []},
                ],
            }

        draft = await parse_ktp_draft(
            filename="plan.docx",
            data=b"fake",
            extractor=lambda _data, _filename: extraction(),
            mapper=mapper,
        )

        self.assertEqual(draft["source"], {
            "filename": "plan.docx",
            "kind": "docx",
            "table_count": 1,
            "row_count": 2,
        })
        self.assertEqual(draft["stats"], {
            "section_count": 2,
            "topic_count": 2,
            "low_confidence_count": 1,
            "with_objectives": 1,
        })

    async def test_rejects_unsupported_file_type(self):
        with self.assertRaises(KtpParseError) as rejected:
            await parse_ktp_draft(filename="plan.csv", data=b"x")

        self.assertEqual(rejected.exception.status_code, 422)
        self.assertIn(".xlsx", rejected.exception.detail)

    async def test_rejects_empty_file(self):
        with self.assertRaises(KtpParseError) as rejected:
            await parse_ktp_draft(filename="plan.docx", data=b"")

        self.assertEqual(rejected.exception.status_code, 422)
        self.assertEqual(rejected.exception.detail, "Файл пустой")

    async def test_rejects_too_large_file_before_extracting(self):
        called = False

        def extractor(_data, _filename):
            nonlocal called
            called = True
            return extraction()

        with self.assertRaises(KtpParseError) as rejected:
            await parse_ktp_draft(
                filename="plan.pdf",
                data=b"x" * (MAX_UPLOAD_BYTES + 1),
                extractor=extractor,
            )

        self.assertEqual(rejected.exception.status_code, 413)
        self.assertFalse(called)

    async def test_reports_unreadable_file_as_validation_error(self):
        def extractor(_data, _filename):
            raise ValueError("битый архив")

        with self.assertRaises(KtpParseError) as rejected:
            await parse_ktp_draft(
                filename="plan.docx",
                data=b"x",
                extractor=extractor,
            )

        self.assertEqual(rejected.exception.status_code, 422)
        self.assertIn("битый архив", rejected.exception.detail)

    async def test_reports_missing_tables(self):
        with self.assertRaises(KtpParseError) as rejected:
            await parse_ktp_draft(
                filename="plan.pdf",
                data=b"x",
                extractor=lambda _data, _filename: extraction(tables=[]),
            )

        self.assertEqual(rejected.exception.status_code, 422)
        self.assertIn("не найдено таблиц", rejected.exception.detail)

    async def test_reports_mapper_runtime_error_as_provider_error(self):
        async def mapper(_extraction):
            raise RuntimeError("модель недоступна")

        with self.assertRaises(KtpParseError) as rejected:
            await parse_ktp_draft(
                filename="plan.docx",
                data=b"x",
                extractor=lambda _data, _filename: extraction(),
                mapper=mapper,
            )

        self.assertEqual(rejected.exception.status_code, 502)
        self.assertEqual(rejected.exception.detail, "модель недоступна")


if __name__ == "__main__":
    unittest.main()
