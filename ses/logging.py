from datetime import datetime


def log(message: str = "", *, end: str = "\n", flush: bool = False) -> None:
    """Timestamp script-owned log lines so hangs show exactly where time went."""
    prefix = datetime.now().strftime("[%H:%M:%S]")
    print(f"{prefix} {message}", end=end, flush=flush)
