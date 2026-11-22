"""Ejecutar explícitamente un trabajador local o del entorno elegido."""

import argparse
import logging
import time

from app.core.config import settings
from app.db.session import SessionLocal

from .images import clean_one
from .imports import process_chunk
from .mail import dispatch_one

logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("tarea", choices=("lotes", "limpieza", "correo"))
    parser.add_argument("--continuo", action="store_true")
    args = parser.parse_args()
    if not settings.administracion_habilitada:
        parser.error("La administración debe estar habilitada")
    fn = {"lotes": process_chunk, "limpieza": clean_one, "correo": dispatch_one}[
        args.tarea
    ]
    while True:
        try:
            with SessionLocal() as db:
                worked = fn(db)
        except Exception as error:
            if not args.continuo:
                raise
            logger.error("Trabajador %s: %s", args.tarea, type(error).__name__)
            time.sleep(10)
            continue
        if not args.continuo:
            break
        if not worked:
            time.sleep(5)


if __name__ == "__main__":
    main()
