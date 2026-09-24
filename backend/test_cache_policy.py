import unittest

from cache_policy import PRIVATE_NO_STORE, PRIVATE_READ_CACHE, api_cache_control


class ApiCachePolicyTests(unittest.TestCase):
    def test_hot_read_endpoints_are_private_short_cache(self):
        self.assertEqual(api_cache_control("GET", "/api/lessons/2/manifest"), PRIVATE_READ_CACHE)
        self.assertEqual(api_cache_control("GET", "/api/subjects/1/outline"), PRIVATE_READ_CACHE)
        self.assertEqual(api_cache_control("GET", "/api/sections/3/topics"), PRIVATE_READ_CACHE)
        self.assertEqual(api_cache_control("GET", "/api/curriculum/students/7/map"), PRIVATE_READ_CACHE)

    def test_mutations_and_auth_like_reads_are_no_store(self):
        self.assertEqual(api_cache_control("POST", "/api/progress"), PRIVATE_NO_STORE)
        self.assertEqual(api_cache_control("GET", "/api/auth/me"), PRIVATE_NO_STORE)

    def test_non_api_paths_are_left_to_static_server(self):
        self.assertIsNone(api_cache_control("GET", "/assets/index.js"))


if __name__ == "__main__":
    unittest.main()
