"""
Separate process for handling display updates to prevent blocking the main process.
Uses multiprocessing.Queue for communication with the main process.
"""
import os
import signal
import time
import multiprocessing as mp
from typing import Optional, Dict, Any
import logging

from .display_serial import DisplaySerial

logger = logging.getLogger(__name__)

class DisplayProcess:
    def __init__(self, config: Dict[str, Any]):
        """Initialize display process with configuration."""
        self.config = config
        self.display: Optional[DisplaySerial] = None
        self._process: Optional[mp.Process] = None
        self._queue: Optional[mp.Queue] = None
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
                self._queue.put_nowait(("config", config))
            except Exception as e:
                logger.warning(f"Failed to send config to display process: {e}"

    @classmethod
    def _run(cls, config: Dict[str, Any], queue: mp.Queue, stop_event: mp.Event) -> None:
        """Main process loop for handling display updates."""
        # Set up process
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        logger = logging.getLogger("display-process")
        
        display = None
        last_value: Optional[float] = None
        
        try:
            # Initialize display
            display = DisplaySerial(
                port=config.get("serial_port"),
                baudrate=config.get("baudrate", 9600),
                databits=config.get("databits", 7),
                parity=config.get("parity", "E"),
                stopbits=config.get("stopbits", 1),
                dp=config.get("dp", 2),
                unit=config.get("unit", "kg"),
                address=config.get("address"),
            )
            
            logger.info("Display process started")
            
            # Main loop
            while not stop_event.is_set():
                try:
                    # Process messages with timeout to allow checking stop_event
                    try:
                        msg_type, data = queue.get(timeout=0.1)
                        if msg_type == "weight":
                            last_value = data
                        elif msg_type == "config":
                            display.update_config(
                                port=data.get("serial_port"),
                                baudrate=data.get("baudrate"),
                                databits=data.get("databits"),
                                parity=data.get("parity"),
                                stopbits=data.get("stopbits"),
                                dp=data.get("dp"),
                                unit=data.get("unit"),
                                address=data.get("address"),
                            )
                    except mp.queues.Empty:
                        pass  # No message, continue
                    
                    # Update display if we have a value
                    if last_value is not None:
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
                
                except Exception as e:
                    logger.error(f"Error in display process: {e}", exc_info=True)
                    time.sleep(1)  # Prevent tight loop on errors
        
        except Exception as e:
            logger.critical(f"Fatal error in display process: {e}", exc_info=True)
        finally:
            if display:
                try:
                    display.close()
                except:
                    pass
            logger.info("Display process exiting")
