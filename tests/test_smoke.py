import laptop.config as c


def test_config_constants():
    for n in ("SERIAL_PORT", "BAUD", "CAMERA_INDEX", "FRAME_W", "FRAME_H", "PLATE_SIZE_MM",
              "PLATE_CORNERS_PX", "HSV_LOW", "HSV_HIGH", "POSITION_RATE_HZ", "QUEUE_SIZE"):
        assert hasattr(c, n), n
    assert c.BAUD == 115200 and (c.FRAME_W, c.FRAME_H) == (640, 480)


def test_import_contracts():
    import contracts  # noqa: F401
