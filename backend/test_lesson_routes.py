from routes.lessons import router


def test_manifest_route_is_registered_before_topic_route():
    paths = [getattr(route, "path", "") for route in router.routes]

    assert paths.index("/api/lessons/{topic_id}/manifest") < paths.index("/api/lessons/{topic_id}")
