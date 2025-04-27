# app/logging_config.py
import logging

def setup_logging():
    # コンソール出力向けのシンプルなロガー設定
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )