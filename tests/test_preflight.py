from magazine.preflight import _effective_image_ppi


def test_cover_ppi_uses_the_rendered_monument_placement():
    assert round(_effective_image_ppi((1054, 1492), (250, 250)), 1) == 303.6
