# Mock GPIO for container environments where RPi.GPIO is not available
class MockGPIO:
    BCM = "BCM"
    IN = "IN"
    OUT = "OUT"
    HIGH = 1
    LOW = 0
    PUD_UP = "PUD_UP"
    PUD_DOWN = "PUD_DOWN"
    
    @staticmethod
    def setmode(mode):
        pass
    
    @staticmethod
    def setup(pin, mode, pull_up_down=None):
        pass
    
    @staticmethod
    def output(pin, value):
        pass
    
    @staticmethod
    def input(pin):
        return 0
    
    @staticmethod
    def cleanup():
        pass

"""
Provide GPIO bindings with a detection flag. If RPi.GPIO is unavailable,
we expose a lightweight mock and set GPIO_IS_MOCK=True so callers can
decide to switch to demo/synthetic behavior automatically.
"""

# Try to import RPi.GPIO, fall back to mock
try:
    import RPi.GPIO as _RPIGPIO  # type: ignore
    GPIO = _RPIGPIO
    GPIO_IS_MOCK = False
except ImportError:
    GPIO = MockGPIO()
    GPIO_IS_MOCK = True
