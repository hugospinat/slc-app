import logging

# Configuration du logging global pour l'application SLC

# Format commun
formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

# Handler pour les logs de succès/info/debug
success_handler = logging.FileHandler("success.log", encoding="utf-8")
success_handler.setLevel(logging.INFO)
success_handler.setFormatter(formatter)

# Handler pour les logs d'erreur
error_handler = logging.FileHandler("errors.log", encoding="utf-8")
error_handler.setLevel(logging.ERROR)
error_handler.setFormatter(formatter)

# Logger racine
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)

# Ajout des handlers si pas déjà présents
if not any(
    isinstance(h, logging.FileHandler) and h.baseFilename.endswith("success.log")
    for h in root_logger.handlers
):
    root_logger.addHandler(success_handler)
if not any(
    isinstance(h, logging.FileHandler) and h.baseFilename.endswith("errors.log")
    for h in root_logger.handlers
):
    root_logger.addHandler(error_handler)
