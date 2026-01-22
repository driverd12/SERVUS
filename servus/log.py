import logging, os, sys
from datetime import datetime

def setup_logger(run_id: str) -> logging.Logger:
    logger = logging.getLogger("servus")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    os.makedirs("logs", exist_ok=True)
    log_path = os.path.join("logs", f"servus_{run_id}.log")
    fmt = logging.Formatter("[%(asctime)s] %(levelname)s %(message)s")
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setFormatter(fmt)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(sh)
    return logger
