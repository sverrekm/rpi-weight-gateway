"""
Separate process for handling display updates to prevent blocking the main process.
Uses multiprocessing.Queue for communication with the main process.
"""
import os
import signal
import time
import multiprocessing as mp
from typing import Optional, Dict, Any, Tuple, Union
import logging

from .display_serial import DisplaySerial

logger = logging.getLogger(__name__)

class DisplayProcess:
    def __init__(self, config: Dict[str, Any]):
        """Initialize display process with configuration."""
        self.config = config
        self.display: Optional[DisplaySerial] = None
        self._process = None
        self._queue = None
        self._stop_event = mp.Event()

    def start(self) -> None:
        """Start the display process."""
        if self._process and self._process.is_alive():
            return

        self._queue = mp.Queue()
        self._stop_event.clear()
        self._process = mp.Process(
            target=self._run,
            args=(self.config, self._queue, self._stop_event),
            daemon=True,
            name="display-process"
        )
        self._process.start()
        logger.info("Started display process")

    def stop(self) -> None:
        """Stop the display process."""
        if not self._process or not self._process.is_alive():
            return

        logger.info("Stopping display process...")
        self._stop_event.set()
        self._process.join(timeout=2.0)
        if self._process.is_alive():
            logger.warning("Force terminating display process")
            self._process.terminate()
            self._process.join(timeout=1.0)
        
        if self._queue:
            self._queue.close()
            self._queue = None
        
        logger.info("Display process stopped")

    def update_display(self, grams: float) -> None:
        """Send weight update to display process."""
        if self._queue and not self._stop_event.is_set():
            try:
                self._queue.put_nowait(("weight", grams))
            except Exception as e:
                logger.warning(f"Failed to send weight to display process: {e}")

    def update_config(self, config: Dict[str, Any]) -> None:
        """Update display configuration."""
        if self._queue and not self._stop_event.is_set():
            try:
                # Ensure unit is always lowercase for consistency
                if 'unit' in config:
                    config['unit'] = config['unit'].lower()
                self._queue.put_nowait(("config", config))
            except Exception as e:
                logger.warning(f"Failed to send config to display process: {e}")

    @classmethod
    def _run(cls, config: Dict[str, Any], queue: 'mp.Queue', stop_event: Any) -> None:
        """Main process loop for handling display updates."""
        # Set up process
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        logger = logging.getLogger("display-process")
        
        display = None
        last_value: Optional[float] = None
        current_config = config.copy()
        
        try:
            # Initialize display
            display = DisplaySerial(
                port=current_config.get("serial_port"),
                baudrate=current_config.get("baudrate", 9600),
                databits=current_config.get("databits", 7),
                parity=current_config.get("parity", "E"),
                stopbits=current_config.get("stopbits", 1),
                dp=current_config.get("dp", 2),
                unit=current_config.get("unit", "kg"),
                address=current_config.get("address"),
            )
            
            logger.info("Display process started")
            
            # Main loop
            while not stop_event.is_set():
                try:
                    # Process messages with timeout to allow checking stop_event
                    try:
                        msg: Tuple[str, Any] = queue.get(timeout=0.1)
                        msg_type, data = msg
                        if msg_type == "weight":
                            last_value = data
                            if display:
                                display.send(data)
                        elif msg_type == "config":
                            # Update the current configuration
                            current_config.update(data)
                            logger.info(f"Received config update: {current_config}")
                            if display:
                                try:
                                    display.update_config(
                                        port=current_config.get("serial_port"),
                                        baudrate=current_config.get("baudrate", 9600),
                                        databits=current_config.get("databits", 7),
                                        parity=current_config.get("parity", "E"),
                                        stopbits=current_config.get("stopbits", 1),
                                        dp=current_config.get("dp", 2),
                                        unit=current_config.get("unit", "kg").lower(),
                                        address=current_config.get("address"),
                                    )
                                    logger.info(f"Display config updated: unit={current_config.get('unit', 'kg')}")
                                    # Resend last value with new unit
                                    if last_value is not None:
                                        try:
                                            display.send(last_value)
                                        except Exception as e:
                                            logger.error(f"Failed to update display with new unit: {e}")
                                except Exception as e:
                                    logger.error(f"Failed to update display config: {e}", exc_info=True)
                    except mp.queues.Empty:
                        pass  # No message, continue
                    
                    # Periodically resend last value to keep display updated
                    if last_value is not None and (time.time() % 5) < 0.1:  # ~every 5 seconds
                        if display and last_value is not None:
                            try:
                                display.send(last_value)
                            except Exception as e:
                                logger.warning(f"Display update failed: {e}")
                                # Reinitialize display on error
                                try:
                                    display.close()
                                    time.sleep(0.5)
                                except:
                                    pass
                
                except mp.queues.Empty:
                    pass  # No message, continue
                except Exception as e:
                    logger.error(f"Error in display process: {e}", exc_info=True)
                    time.sleep(1)  # Prevent tight loop on errors
        
        except Exception as e:
            logger.critical(f"Fatal error in display process: {e}", exc_info=True)
        finally:
            if display:
                try:
                    display.close()
                except Exception:
                    pass
            logger.info("Display process exiting")
