#!/usr/bin/env python3
"""
Test script for finding correct GPIO pins for HX711 on Pi 3 Click Shield.
Tests various pin combinations to find working DOUT/SCK pairs.
"""

import RPi.GPIO as GPIO
import time
import sys

# Possible GPIO combinations based on Pi 3 Click Shield examples
GPIO_COMBINATIONS = [
    # From relay examples and signal relay examples
    {"name": "Socket 1 - Relay pins", "dout": 8, "sck": 18},
    {"name": "Socket 2 - Relay pins", "dout": 7, "sck": 17},
    {"name": "Socket 1 - Signal relay 1", "dout": 4, "sck": 5},
    {"name": "Socket 1 - Signal relay 2", "dout": 8, "sck": 18},
    {"name": "Socket 2 - Signal relay 1", "dout": 13, "sck": 12},
    {"name": "Socket 2 - Signal relay 2", "dout": 7, "sck": 17},
    
    # Original mappings we tried
    {"name": "Original Socket 1", "dout": 17, "sck": 11},
    {"name": "Original Socket 2", "dout": 27, "sck": 22},
    
    # Common mikroBUS mappings
    {"name": "Alt PWM/INT 1", "dout": 6, "sck": 18},
    {"name": "Alt PWM/INT 2", "dout": 26, "sck": 17},
    {"name": "Alt PWM/INT 3", "dout": 19, "sck": 13},
    {"name": "Alt PWM/INT 4", "dout": 16, "sck": 12},
    
    # Additional common GPIO pairs
    {"name": "Common pair 1", "dout": 23, "sck": 24},
    {"name": "Common pair 2", "dout": 20, "sck": 21},
    {"name": "Common pair 3", "dout": 9, "sck": 11},
    {"name": "Common pair 4", "dout": 25, "sck": 8},
]

def test_gpio_pair(dout_pin, sck_pin, test_name):
    """Test a specific GPIO pin pair for HX711 communication."""
    print(f"\n--- Testing {test_name}: DOUT={dout_pin}, SCK={sck_pin} ---")
    
    try:
        # Setup GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(dout_pin, GPIO.IN)
        GPIO.setup(sck_pin, GPIO.OUT)
        GPIO.output(sck_pin, False)
        
        # Check initial DOUT state
        initial_dout = GPIO.input(dout_pin)
        print(f"Initial DOUT: {initial_dout}")
        
        # Test SCK toggle response
        GPIO.output(sck_pin, True)
        time.sleep(0.001)
        dout_high = GPIO.input(dout_pin)
        GPIO.output(sck_pin, False)
        time.sleep(0.001)
        dout_low = GPIO.input(dout_pin)
        
        print(f"SCK toggle: HIGH->DOUT={dout_high}, LOW->DOUT={dout_low}")
        
        # Test HX711 data ready (DOUT should go LOW when ready)
        print("Waiting for DOUT to go LOW (data ready)...")
        start_time = time.time()
        timeout = 1.0  # 1 second timeout
        
        while GPIO.input(dout_pin) == 1:
            if time.time() - start_time > timeout:
                print("❌ TIMEOUT: DOUT never went LOW")
                return False
            time.sleep(0.01)
        
        ready_time = time.time() - start_time
        print(f"✅ DOUT went LOW after {ready_time:.3f}s - HX711 ready!")
        
        # Try to read 24-bit value
        count = 0
        for i in range(24):
            GPIO.output(sck_pin, True)
            count = (count << 1) | GPIO.input(dout_pin)
            GPIO.output(sck_pin, False)
        
        # Set gain 128 (one more pulse)
        GPIO.output(sck_pin, True)
        GPIO.output(sck_pin, False)
        
        # Convert to signed 24-bit
        if count & 0x800000:
            count |= ~0xFFFFFF
        
        print(f"✅ Raw 24-bit value: {count}")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    finally:
        try:
            GPIO.cleanup([dout_pin, sck_pin])
        except:
            pass

def main():
    """Test all GPIO combinations to find working HX711 connection."""
    print("🔍 Testing GPIO combinations for HX711 on Pi 3 Click Shield")
    print("=" * 60)
    
    working_combinations = []
    
    for combo in GPIO_COMBINATIONS:
        success = test_gpio_pair(combo["dout"], combo["sck"], combo["name"])
        if success:
            working_combinations.append(combo)
    
    print("\n" + "=" * 60)
    print("📋 RESULTS:")
    
    if working_combinations:
        print(f"✅ Found {len(working_combinations)} working combination(s):")
        for combo in working_combinations:
            print(f"   • {combo['name']}: DOUT={combo['dout']}, SCK={combo['sck']}")
        
        print(f"\n🎯 Recommended: Use the first working combination:")
        best = working_combinations[0]
        print(f"   DOUT = {best['dout']}")
        print(f"   SCK = {best['sck']}")
        
    else:
        print("❌ No working combinations found!")
        print("Possible issues:")
        print("   • Load Cell Click not properly seated in mikroBUS socket")
        print("   • JP1 not set to 5V on Load Cell Click")
        print("   • No power to Pi 3 Click Shield")
        print("   • Defective hardware")
    
    print("\n🔧 Next steps:")
    if working_combinations:
        best = working_combinations[0]
        print(f"1. Update UI config: DOUT={best['dout']}, SCK={best['sck']}")
        print("2. Test with actual load cell connected")
        print("3. Calibrate with known weight")
    else:
        print("1. Check hardware connections")
        print("2. Verify JP1 jumper on Load Cell Click is set to 5V")
        print("3. Try different mikroBUS socket")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⏹️  Test interrupted by user")
        GPIO.cleanup()
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        GPIO.cleanup()
        sys.exit(1)
