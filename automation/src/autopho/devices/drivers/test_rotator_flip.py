#!/usr/bin/env python3
"""
Simple test script for rotator flip mechanism
Run this in the same folder as alpaca_rotator.py

Test procedure:
1. Run this script
2. Manually move rotator to ~96° (close to but not triggering flip)
3. Then move to ~94° or lower to trigger flip mechanism
4. Observe if 180° flip executes correctly
"""

import time
import logging
from alpaca_rotator import AlpacaRotatorDriver

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s:%(lineno)d - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_test_config():
    """Create minimal config for testing"""
    return {
        'address': '127.0.0.1:11112',
        'device_number': 0,
        'mechanical_limits': {
            'min_deg': 94.0,
            'max_deg': 320.0
        },
        'limits': {
            'warning_margin_deg': 30.0,
            'emergency_margin_deg': 10.0
        },
        'settle_time': 1.0
    }

def create_field_rotation_config():
    """Create minimal field rotation config for testing"""
    return {
        'enabled': True,
        'tracking': {
            'update_rate_hz': 2.0,
            'move_threshold_deg': 0.1,
            'settle_time_sec': 0.1
        },
        'calibration': {
            'rotator_sign': 1,
            'mechanical_zero_deg': 0.0
        },
        'wrap_management': {
            'enabled': True,
            'flip_margin_deg': 5.0,  # Trigger flip when within 5° of limits
            'flip_timeout_duration': 90.0
        }
    }

def create_observatory_config():
    """Create minimal observatory config for testing"""
    return {
        'latitude': -27.7983683,    # Approximate - adjust for your location
        'longitude': 151.8547855,
        'altitude': 680.0
    }

def main():
    logger.info("="*60)
    logger.info("ROTATOR FLIP MECHANISM TEST")
    logger.info("="*60)
    
    rotator = None
    
    logging.getLogger('urllib3.connectionpool').setLevel(logging.INFO)
    
    try:
        # Initialize rotator
        logger.info("Initializing rotator driver...")
        rotator = AlpacaRotatorDriver()
        
        # Connect
        config = create_test_config()
        if not rotator.connect(config):
            logger.error("Failed to connect to rotator")
            return 1
        
        # Get initial status
        info = rotator.get_rotator_info()
        logger.info(f"Connected: {info['name']}")
        logger.info(f"Current position: {info['position_deg']:.3f}°")
        logger.info(f"Limits: {config['mechanical_limits']['min_deg']}° to {config['mechanical_limits']['max_deg']}°")
        logger.info(f"Flip margin: {create_field_rotation_config()['wrap_management']['flip_margin_deg']}°")
        
        # Initialize field rotation for flip testing
        logger.info("\nInitializing field rotation tracking...")
        obs_config = create_observatory_config()
        fr_config = create_field_rotation_config()
        
        if rotator.initialize_field_rotation(obs_config, fr_config):
            logger.info("Field rotation initialized successfully")
            
            # Set a dummy target (needed for field rotation calculations)
            logger.info("Setting dummy target coordinates...")
            rotator.set_tracking_target(12.0, -30.0)  # 12h RA, -30° Dec
            
            # Start tracking (this will monitor for flip conditions)
            logger.info("Starting field rotation tracking...")
            if rotator.start_field_tracking():
                logger.info("Tracking started - flip monitoring is now active")
            else:
                logger.error("Failed to start tracking")
                return 1
        else:
            logger.error("Failed to initialize field rotation")
            return 1
        
        logger.info("\n" + "="*60)
        logger.info("TEST READY - MANUAL CONTROL PHASE")
        logger.info("="*60)
        logger.info("Now manually move the rotator using your usual interface:")
        logger.info("1. Move to ~96° (should be safe, no flip)")
        logger.info("2. Then move to ~94° or lower (should trigger flip)")
        logger.info("3. Watch the logs for flip detection and execution")
        logger.info("4. Press Ctrl+C when done testing")
        logger.info("\nCurrent flip trigger zones:")
        logger.info(f"  Min trigger: < {94 + 5}° = {94 + 5}°")
        logger.info(f"  Max trigger: > {320 - 5}° = {320 - 5}°")
        
        # Monitor loop
        last_position = None
        check_interval = 2.0
        
        try:
            while True:
                current_pos = rotator.get_position()
                
                # Only log position changes to reduce spam
                if last_position is None or abs(current_pos - last_position) > 0.5:
                    status_info = rotator.get_rotator_info()
                    is_safe, safety_msg = rotator.check_position_safety(current_pos)
                    
                    logger.info(f"\nCurrent position: {current_pos:.3f}°")
                    logger.info(f"Safety status: {safety_msg}")
                    logger.info(f"Moving: {status_info.get('is_moving', 'unknown')}")
                    
                    # Check if we're in flip trigger zone
                    if hasattr(rotator, 'field_tracker'):
                        wrap_needed = rotator.field_tracker.check_wrap_needed()
                        logger.info(f"Flip needed: {wrap_needed}")
                    
                    last_position = current_pos
                
                time.sleep(check_interval)
                
        except KeyboardInterrupt:
            logger.info("\nTest interrupted by user")
            
    except Exception as e:
        logger.error(f"Test failed: {e}")
        logger.debug("Full traceback:", exc_info=True)
        return 1
        
    finally:
        if rotator:
            try:
                logger.info("Stopping field rotation tracking...")
                if hasattr(rotator, 'field_tracker'):
                    rotator.stop_field_tracking()
                
                logger.info("Disconnecting rotator...")
                rotator.disconnect()
                logger.info("Test cleanup complete")
            except Exception as e:
                logger.error(f"Cleanup error: {e}")
    
    logger.info("Test completed")
    return 0

if __name__ == '__main__':
    exit(main())