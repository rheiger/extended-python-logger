from extended_python_logger import (
    ALWAYS,
    NEVER,
    NOTICE,
    TRACE,
    configure_logging,
    get_logger,
)


def main() -> None:
    configure_logging(
        console_level="NOTICE",
        file_level="TRACE",
        console_format="DETAILED",
        file_format="EXTENDED",
    )

    logger = get_logger(__name__)

    logger.log(ALWAYS, "ALWAYS: this should always be emitted")
    logger.trace("TRACE: very verbose")
    logger.debug("DEBUG detail")
    logger.info("INFO message")
    logger.notice("NOTICE: important but not a warning")
    logger.warning("WARNING")
    logger.error("ERROR")

    # NEVER is ring-buffer only
    logger.log(NEVER, "NEVER: ring-buffer only message")

    try:
        1 / 0
    except ZeroDivisionError:
        logger.exception("Handled exception with stack trace")

    # Uncomment to simulate unhandled exception and ring-buffer dump
    # raise RuntimeError("Boom")


if __name__ == "__main__":
    main()
