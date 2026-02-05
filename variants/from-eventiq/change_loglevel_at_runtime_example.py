from enhanced_logging import change_log_level, get_logger

logger = get_logger('my_app.feature')

# Initially, the level might be INFO
logger.debug("This message will not appear.")

# Now, let's change it
change_log_level("DEBUG", logger_name='my_app.feature')
logger.info("Log level for 'my_app.feature' was changed to DEBUG.")
logger.debug("This message will now appear!")