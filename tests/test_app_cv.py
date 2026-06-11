import numpy as np

from app import optimize_black_and_white, order_points


def test_order_points_returns_consistent_corners() -> None:
    points = np.array([[100, 200], [20, 10], [200, 20], [220, 210]], dtype="float32")

    ordered = order_points(points)

    assert ordered.tolist() == [[20.0, 10.0], [200.0, 20.0], [220.0, 210.0], [100.0, 200.0]]


def test_optimize_black_and_white_returns_binary_image() -> None:
    image = np.full((220, 320, 3), 255, dtype=np.uint8)
    image[70:150, 80:240] = 30

    output = optimize_black_and_white(image)

    assert output.ndim == 2
    assert set(np.unique(output)).issubset({0, 255})
