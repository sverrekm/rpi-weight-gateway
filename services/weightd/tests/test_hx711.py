from app.hx711 import HX711Reader

def test_demo_mode_reads():
    r = HX711Reader(gpio_dout=5, gpio_sck=6, demo_mode=True)
    g1 = r.read_grams()
    g2 = r.read_grams()
    assert isinstance(g1, float)
    assert isinstance(g2, float)
    # Values should be finite and within a reasonable synthetic range
    assert -1000.0 < g1 < 10000.0
    assert -1000.0 < g2 < 10000.0
    r.close()
