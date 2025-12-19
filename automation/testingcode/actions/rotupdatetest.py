"""
Simple test script for rotator flip logic
Tests: safety rejection, flip trigger, and 180° flip execution
Test 1 and 2 are simulated (no actual rotator movement)
Test 3 will perform real 180° rotator flip but will ask for confirmation before proceeding (you can skip this)
"""

import sys
import logging
from pathlib import Path
from rich.logging import RichHandler
import time

sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from autopho.config.loader import ConfigLoader
from autopho.devices.drivers.alpaca_rotator import AlpacaRotatorDriver

def setup_logging():
    """Set up simple console logging"""
    console_handler = RichHandler(rich_tracebacks=True, markup=True, show_path=True)
    console_handler.setFormatter(logging.Formatter("%(message)s"))
    console_handler.setLevel(logging.DEBUG)
    
    logging.basicConfig(level=logging.DEBUG, handlers=[console_handler])
    logging.getLogger('urllib3.connectionpool').setLevel(logging.INFO)
    return logging.getLogger(__name__)

def test_safety_rejection(rotator_driver, logger):
    """Test that moves within emergency margin are rejected"""
    logger.info("\n" + "="*60)
    logger.info("TEST 1: SAFETY REJECTION (Emergency Margin)")
    logger.info("="*60)
    
    current_pos = rotator_driver.get_position()
    logger.info(f"Current position: {current_pos:.2f}°")
    logger.info(f"Min limit: {rotator_driver.min_limit}°")
    logger.info(f"Emergency margin: 0.5°")
    logger.info(f"Safety rejection should occur at: {rotator_driver.min_limit + 0.5}° = 94.5°")
    
    # Try to move to 94.4° (should be rejected - within 0.5° of 94.0°)
    test_position = 94.4
    logger.info(f"\nAttempting move to {test_position}° (should be REJECTED)...")
    
    is_safe, msg = rotator_driver.check_position_safety(test_position)
    if not is_safe:
        logger.info(f"✓ PASS: Move rejected as expected")
        logger.info(f"  Reason: {msg}")
    else:
        logger.error(f"✗ FAIL: Move was not rejected (safety margin too small?)")
    
    # Try to move to 95.0° (should be accepted - outside 0.5° margin)
    test_position = 95.0
    logger.info(f"\nAttempting move to {test_position}° (should be ACCEPTED)...")
    
    is_safe, msg = rotator_driver.check_position_safety(test_position)
    if is_safe:
        logger.info(f"✓ PASS: Move accepted as expected")
        logger.info(f"  Status: {msg}")
    else:
        logger.error(f"✗ FAIL: Move was rejected (emergency margin too large?)")
        logger.error(f"  Reason: {msg}")

def test_flip_trigger(rotator_driver, logger):
    """Test that flip triggers at correct margin"""
    logger.info("\n" + "="*60)
    logger.info("TEST 2: FLIP TRIGGER (Flip Margin)")
    logger.info("="*60)
    
    if not hasattr(rotator_driver, 'field_tracker'):
        logger.error("Field tracker not initialized - skipping flip trigger test")
        return False
    
    tracker = rotator_driver.field_tracker
    logger.info(f"Min limit: {rotator_driver.min_limit}°")
    logger.info(f"Flip margin: 1.25°")
    logger.info(f"Flip should trigger at: {rotator_driver.min_limit + 1.25}° = 95.25°")
    
    # Move rotator to test positions and check if flip triggers
    test_positions = [
        (98.0, False, "well above flip trigger"),
        (96.0, False, "just above flip trigger"),
        (95.5, False, "approaching flip trigger"),
        (95.2, True, "AT flip trigger point"),
        (95.0, True, "PAST flip trigger point")
    ]
    
    for pos, should_trigger, description in test_positions:
        logger.info(f"\nTesting position {pos}° ({description})...")
        
        # Manually set rotator position for testing (simulate being at that position)
        logger.debug(f"  Simulating rotator at {pos}°")
        
        # Temporarily override get_position to return test value
        original_get_pos = rotator_driver.get_position
        rotator_driver.get_position = lambda: pos
        
        flip_needed = tracker.check_wrap_needed()
        
        # Restore original method
        rotator_driver.get_position = original_get_pos
        
        if flip_needed == should_trigger:
            logger.info(f"  ✓ PASS: Flip trigger = {flip_needed} (expected {should_trigger})")
        else:
            logger.error(f"  ✗ FAIL: Flip trigger = {flip_needed} (expected {should_trigger})")
    
    return True

def test_actual_flip(rotator_driver, logger):
    """Test actual 180° flip execution"""
    logger.info("\n" + "="*60)
    logger.info("TEST 3: ACTUAL 180° FLIP EXECUTION")
    logger.info("="*60)
    
    if not hasattr(rotator_driver, 'field_tracker'):
        logger.error("Field tracker not initialized - cannot test flip")
        return False
    
    current_pos = rotator_driver.get_position()
    logger.info(f"Current position: {current_pos:.2f}°")
    
    # Ask user if they want to proceed
    logger.warning("\nThis will move the rotator ~180°!")
    response = input("Proceed with actual flip test? (yes/no): ").strip().lower()
    
    if response != 'yes':
        logger.info("Flip test skipped by user")
        return False
    
    logger.info("\nExecuting 180° flip...")
    logger.info(f"Expected new position: ~{(current_pos + 180) % 360:.1f}°")
    
    tracker = rotator_driver.field_tracker
    success = tracker._execute_180_flip()
    
    final_pos = rotator_driver.get_position()
    
    if success:
        logger.info(f"✓ Flip completed successfully")
        logger.info(f"  Start: {current_pos:.2f}°")
        logger.info(f"  End: {final_pos:.2f}°")
        logger.info(f"  Delta: {abs(final_pos - current_pos):.2f}°")
        
        # Check if it's approximately 180°
        delta = abs(final_pos - current_pos)
        if 170 < delta < 190:
            logger.info(f"  ✓ PASS: Delta is approximately 180°")
        else:
            logger.warning(f"  ⚠ WARNING: Delta is not close to 180°")
    else:
        logger.error(f"✗ Flip failed")
    
    return success

def main():
    logger = setup_logging()
    
    logger.info("="*60)
    logger.info("ROTATOR FLIP LOGIC TEST SCRIPT")
    logger.info("="*60)
    
    rotator_driver = None
    
    try:
        # Load config
        logger.info("\nLoading configuration...")
        config_loader = ConfigLoader("config")
        config_loader.load_all_configs()
        
        # Connect to rotator
        logger.info("Connecting to rotator...")
        rotator_driver = AlpacaRotatorDriver()
        rotator_config = config_loader.get_rotator_config()
        
        if not rotator_driver.connect(rotator_config):
            logger.error("Failed to connect to rotator")
            return 1
        
        rot_info = rotator_driver.get_rotator_info()
        logger.info(f"Connected: {rot_info.get('name', 'Unknown')}")
        logger.info(f"Position: {rot_info.get('position_deg', 0):.2f}°")
        logger.info(f"Limits: [{rotator_driver.min_limit}°, {rotator_driver.max_limit}°]")
        
        # Initialize field rotation (needed for flip logic)
        logger.info("\nInitializing field rotation tracker...")
        observatory_config = config_loader.get_config('observatory')
        field_rotation_config = config_loader.get_config('field_rotation')
        
        if rotator_driver.initialize_field_rotation(observatory_config, field_rotation_config):
            logger.info("Field rotation tracker initialized")
        else:
            logger.error("Failed to initialize field rotation tracker")
            return 1
        
        # Set a dummy target (needed for field tracker)
        logger.info("Setting dummy target (for field tracker)...")
        rotator_driver.set_tracking_target(ra_hours=4.0, dec_deg=-38.0)
        
        # Run tests
        test_safety_rejection(rotator_driver, logger)
        time.sleep(1)
        
        test_flip_trigger(rotator_driver, logger)
        time.sleep(1)
        
        test_actual_flip(rotator_driver, logger)
        
        logger.info("\n" + "="*60)
        logger.info("TESTS COMPLETE")
        logger.info("="*60)
        
        return 0
        
    except KeyboardInterrupt:
        logger.info("\nTest interrupted by user")
        return 0
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        return 1
    finally:
        if rotator_driver:
            logger.info("\nDisconnecting rotator...")
            rotator_driver.disconnect()

if __name__ == '__main__':
    sys.exit(main())
