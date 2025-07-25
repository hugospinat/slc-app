import os

from slc_app.utils.settings import BASE_STORAGE_DIR


def save_file(content: bytes, subdirectory: str, filename: str) -> str:
    """
    Sauvegarde un fichier binaire dans un répertoire donné.

    Args:
        content (bytes): Contenu binaire du fichier.
        subdirectory (str): Sous-répertoire où sauvegarder le fichier (relatif à BASE_STORAGE_DIR).
        filename (str): Nom du fichier.

    Returns:
        str: Chemin complet du fichier sauvegardé.
    """
    # Construire le chemin complet du répertoire
    directory = os.path.join(BASE_STORAGE_DIR, subdirectory)
    os.makedirs(directory, exist_ok=True)

    # Construire le chemin complet du fichier
    filepath = os.path.join(directory, filename)

    # Sauvegarder le contenu dans le fichier
    with open(filepath, "wb") as f:
        f.write(content)

    return filepath
