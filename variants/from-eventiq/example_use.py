# In your main application file (e.g., app.py)
from enhanced_logging import get_logger

# Get a logger for the current module
# This will automatically configure logging on its first call
logger = get_logger(__name__)

def my_function():
    logger.info("Starting my_function.")
    # Use custom levels for more context
    logger.trace("This is a very detailed trace message.")
    for i in range(3):
        logger.debug(f"Processing item {i+1}...")
    logger.notice("All items have been processed successfully.")
    logger.warning("The function completed, but one value was unexpected.")

my_function()