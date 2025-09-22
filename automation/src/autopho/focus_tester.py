#!/usr/bin/env python3
"""
Focus Position Tester for Telescope Setup
Determines optimal focus positions for each filter using HFR analysis
"""

import os
import sys
import yaml
import logging
import argparse
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import numpy as np

# Import your drivers - adjust paths for your structure
sys.path.append(str(Path(__file__).parent.parent / 'src' / 'autopho'))
from devices.drivers.alpaca_focuser import AlpacaFocuserDriver, AlpacaFocuserError
from devices.camera import CameraManager, CameraError
from devices.drivers.alpaca_filterwheel import AlpacaFilterWheelDriver, AlpacaFilterWheelError
from config.loader import ConfigLoader

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class FocusTester:
    def __init__(self, config_file: str = "focus_test_config.yaml"):
        # Load focus test config
        self.config = self.load_focus_config(config_file)
        
        # Load main config using your ConfigLoader
        self.config_loader = ConfigLoader('config')
        self.config_loader.load_all_configs()
        
        # Initialize hardware drivers
        self.focuser = AlpacaFocuserDriver()
        self.camera_manager = CameraManager()
        self.filter_wheel = AlpacaFilterWheelDriver()
        
        # Test results storage
        self.results = {}
        self.test_data = []
        
        # Create results directory
        self.results_dir = Path(self.config['logging']['results_dir'])
        self.results_dir.mkdir(exist_ok=True)
    
    def load_focus_config(self, filename: str) -> Dict:
        """Load focus test specific configuration"""
        try:
            with open(filename, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Failed to load focus config {filename}: {e}")
            sys.exit(1)
    
    def connect_hardware(self) -> bool:
        """Connect to all hardware components"""
        logger.info("Connecting to hardware...")
        
        # Get device configs using your ConfigLoader
        focuser_config = self.config_loader.get_config('devices')['focuser']
        filter_config = self.config_loader.get_filter_wheel_config()
        camera_configs = self.config_loader.get_camera_configs()
        
        # Connect focuser
        if not self.focuser.connect(focuser_config):
            logger.error("Failed to connect to focuser")
            return False
        
        # Connect filter wheel
        if not self.filter_wheel.connect(filter_config):
            logger.error("Failed to connect to filter wheel")
            return False
        
        # Discover and connect cameras
        if not self.camera_manager.discover_cameras(camera_configs):
            logger.error("Failed to discover cameras")
            return False
            
        if not self.camera_manager.connect_all_cameras():
            logger.error("Failed to connect cameras")
            return False
            
        logger.info("All hardware connected successfully")
        return True
    
    def disconnect_hardware(self):
        """Safely disconnect all hardware"""
        logger.info("Disconnecting hardware...")
        try:
            self.camera_manager.shutdown_all_coolers()
            self.camera_manager.disconnect_all_cameras()
            self.filter_wheel.disconnect()
            self.focuser.disconnect()
        except Exception as e:
            logger.warning(f"Error during disconnect: {e}")
    
    def calculate_hfr(self, image: np.ndarray) -> Optional[float]:
        """
        Calculate Half Flux Radius (HFR) from image
        Simple implementation focusing on brightest stars
        """
        try:
            # Basic star detection - find bright pixels
            threshold = self.config['test_settings']['image_analysis']['min_star_brightness']
            bright_pixels = image > threshold
            
            if not np.any(bright_pixels):
                logger.warning("No bright stars found in image")
                return None
            
            # Find connected components (stars)
            from scipy import ndimage
            labeled, num_features = ndimage.label(bright_pixels)
            
            if num_features == 0:
                logger.warning("No star features detected")
                return None
            
            # Analyze up to N brightest stars
            max_stars = self.config['test_settings']['image_analysis']['max_stars_to_analyze']
            star_hfrs = []
            
            for star_id in range(1, min(num_features + 1, max_stars + 1)):
                star_mask = labeled == star_id
                star_pixels = image[star_mask]
                
                if len(star_pixels) < 5:  # Skip very small detections
                    continue
                
                # Find centroid
                y_coords, x_coords = np.where(star_mask)
                total_flux = np.sum(star_pixels)
                
                if total_flux <= 0:
                    continue
                    
                centroid_x = np.sum(x_coords * star_pixels) / total_flux
                centroid_y = np.sum(y_coords * star_pixels) / total_flux
                
                # Calculate distances from centroid
                distances = np.sqrt((x_coords - centroid_x)**2 + (y_coords - centroid_y)**2)
                
                # Sort by distance and find half-flux radius
                sorted_indices = np.argsort(distances)
                sorted_flux = star_pixels[sorted_indices]
                cumulative_flux = np.cumsum(sorted_flux)
                half_flux = total_flux / 2
                
                # Find radius containing half the flux
                half_flux_index = np.where(cumulative_flux >= half_flux)[0]
                if len(half_flux_index) > 0:
                    hfr = distances[sorted_indices[half_flux_index[0]]]
                    star_hfrs.append(hfr)
            
            if not star_hfrs:
                logger.warning("No valid stars found for HFR calculation")
                return None
                
            # Return median HFR of detected stars
            median_hfr = np.median(star_hfrs)
            logger.debug(f"Calculated HFR: {median_hfr:.2f} (from {len(star_hfrs)} stars)")
            return median_hfr
            
        except Exception as e:
            logger.error(f"HFR calculation failed: {e}")
            return None
    
    def capture_and_measure(self, camera_role: str, focus_position: int) -> Optional[float]:
        """Capture image at focus position and return HFR measurement"""
        try:
            # Move focuser to position
            if not self.focuser.move_to_position(focus_position):
                logger.error(f"Failed to move focuser to {focus_position}")
                return None
                
            # Wait for settle
            settle_time = self.config['test_settings']['exposure']['settle_time']
            time.sleep(settle_time)
            
            # Get camera
            camera = self.camera_manager.get_camera(camera_role)
            if not camera or not camera.connected:
                logger.error(f"Camera {camera_role} not available")
                return None
            
            # Capture image
            exposure_time = self.config['test_settings']['exposure']['time']
            image = camera.capture_image(exposure_time)
            
            if image is None:
                logger.error("Failed to capture image")
                return None
            
            # Calculate HFR
            hfr = self.calculate_hfr(image)
            
            if hfr is not None:
                logger.info(f"Focus {focus_position}: HFR = {hfr:.2f}")
            else:
                logger.warning(f"Focus {focus_position}: HFR calculation failed")
                
            return hfr
            
        except Exception as e:
            logger.error(f"Capture and measure failed: {e}")
            return None
    
    def run_focus_sweep(self, filter_code: str) -> Optional[int]:
        """Run complete focus sweep for a filter"""
        logger.info(f"Starting focus test for filter {filter_code}")
        
        # Get camera role and initial position
        camera_role = self.config['camera_mapping'][filter_code]
        initial_pos = self.config['initial_positions'][filter_code]
        
        if initial_pos is None:
            logger.error(f"No initial position defined for filter {filter_code}")
            return None
        
        # Change to correct filter (skip for spectro)
        if filter_code != 'spectro':
            logger.info(f"Changing to filter {filter_code}")
            if not self.filter_wheel.change_filter(filter_code):
                logger.error(f"Failed to change to filter {filter_code}")
                return None
        
        test_results = []
        
        # Coarse sweep
        logger.info("Running coarse focus sweep...")
        coarse_range = self.config['test_settings']['coarse_sweep']['range']
        coarse_step = self.config['test_settings']['coarse_sweep']['step_size']
        
        coarse_positions = range(
            initial_pos - coarse_range,
            initial_pos + coarse_range + 1,
            coarse_step
        )
        
        best_hfr = float('inf')
        best_position = initial_pos
        
        for pos in coarse_positions:
            hfr = self.capture_and_measure(camera_role, pos)
            if hfr is not None:
                test_results.append((pos, hfr))
                if hfr < best_hfr:
                    best_hfr = hfr
                    best_position = pos
        
        if not test_results:
            logger.error("No valid measurements in coarse sweep")
            return None
            
        logger.info(f"Coarse sweep complete. Best position: {best_position} (HFR: {best_hfr:.2f})")
        
        # Fine sweep around best position
        logger.info("Running fine focus sweep...")
        fine_range = self.config['test_settings']['fine_sweep']['range']
        fine_step = self.config['test_settings']['fine_sweep']['step_size']
        
        fine_positions = range(
            best_position - fine_range,
            best_position + fine_range + 1,
            fine_step
        )
        
        for pos in fine_positions:
            hfr = self.capture_and_measure(camera_role, pos)
            if hfr is not None:
                test_results.append((pos, hfr))
                if hfr < best_hfr:
                    best_hfr = hfr
                    best_position = pos
        
        # Store results
        self.results[filter_code] = {
            'optimal_position': best_position,
            'optimal_hfr': best_hfr,
            'camera_used': camera_role,
            'test_data': test_results
        }
        
        logger.info(f"Focus test complete for {filter_code}:")
        logger.info(f"  Optimal position: {best_position}")
        logger.info(f"  Best HFR: {best_hfr:.2f}")
        
        return best_position
    
    def save_results(self):
        """Save test results to files"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save summary results
        summary_file = self.results_dir / f"focus_results_{timestamp}.yaml"
        summary_data = {
            'test_timestamp': timestamp,
            'results': {}
        }
        
        for filter_code, data in self.results.items():
            summary_data['results'][filter_code] = {
                'optimal_position': data['optimal_position'],
                'optimal_hfr': data['optimal_hfr'],
                'camera_used': data['camera_used']
            }
        
        with open(summary_file, 'w') as f:
            yaml.dump(summary_data, f, default_flow_style=False)
        
        logger.info(f"Results saved to {summary_file}")
        
        # Save detailed data if requested
        if self.config['logging']['detailed_log']:
            detail_file = self.results_dir / f"focus_details_{timestamp}.yaml"
            with open(detail_file, 'w') as f:
                yaml.dump(self.results, f, default_flow_style=False)
            logger.info(f"Detailed results saved to {detail_file}")
    
    def test_filter(self, filter_code: str) -> bool:
        """Test focus for a single filter"""
        try:
            if filter_code not in self.config['camera_mapping']:
                logger.error(f"Unknown filter code: {filter_code}")
                return False
            
            optimal_pos = self.run_focus_sweep(filter_code)
            return optimal_pos is not None
            
        except Exception as e:
            logger.error(f"Filter test failed: {e}")
            return False

def main():
    parser = argparse.ArgumentParser(description="Focus Position Tester")
    parser.add_argument('--filter', '-f', required=True,
                       help='Filter code to test (L, B, V, R, C, I, H, spectro)')
    parser.add_argument('--config', default='config/focus_test_config.yaml',
                       help='Focus test configuration file')
    
    args = parser.parse_args()
    
    tester = FocusTester(args.config)
    
    try:
        # Connect to hardware
        if not tester.connect_hardware():
            logger.error("Hardware connection failed")
            return 1
        
        # Run focus test
        success = tester.test_filter(args.filter.upper())
        
        if success:
            tester.save_results()
            logger.info(f"Focus test completed successfully for filter {args.filter}")
            return 0
        else:
            logger.error(f"Focus test failed for filter {args.filter}")
            return 1
            
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 1
    finally:
        tester.disconnect_hardware()

if __name__ == "__main__":
    sys.exit(main())