import os
import time
import subprocess
import psutil
import logging
from urllib.parse import urlparse
import glob

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("surveillance.log"),
        logging.StreamHandler()
    ]
)
import time
import logging
import subprocess
import psutil
import glob
import os
from urllib.parse import urlparse

file_path = "actif.txt"
CHECK_INTERVAL = 60  # Vérification toutes les 60 secondes
MAX_PROCESS_DURATION = 30 * 60  # Durée max d'un enregistrement
process_mapping = {}

def lire_liens():
    try:
        with open(file_path, "r") as f:
            return [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        logging.error(f"Le fichier {file_path} est introuvable.")
        return []


def enregistrer_live(username):
    try:
        cmd = f"python3 main.py -user {username} -output ./movies"
        process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Attente pour une réponse rapide
        output, err = process.communicate(timeout=20)

        # Analyse des résultats si aucun timeout n'a eu lieu
        if b"Started recording" in output:
            process_mapping[username] = {
                "pid": process.pid,
                "start_time": time.time()
            }
            logging.info(f"Live enregistrement pour {username} a commencé (PID: {process.pid}).")
        elif b"The user is not hosting a live stream" in err:
            liens = lire_liens()
            lien = f"https://www.tiktok.com/@{username}"
            if lien in liens:
                liens.remove(lien)
                ecrire_liens(liens)
            logging.info(f"{username} n'est pas en direct, lien supprimé de {file_path}.")
        else:
            logging.warning(f"Résultat inconnu pour {username}.")
            logging.warning(f"{err}.")
            logging.warning(f"{output}.")
    
    except subprocess.TimeoutExpired:
        # Considérer comme un enregistrement en cours si un timeout se produit
        process_mapping[username] = {
            "pid": process.pid,
            "start_time": time.time()
        }
        logging.info(f"Timeout lors de l'enregistrement pour {username},--> actif (PID: {process.pid}).")
    
    except Exception as e:
        # Gérer d'autres exceptions
        logging.error(f"Erreur lors du lancement de l'enregistrement pour {username} : {e}")


def ecrire_liens(liens):
    try:
        with open(file_path, "w") as f:
            f.writelines([l + "\n" for l in liens])
    except Exception as e:
        logging.error(f"Erreur lors de l'écriture dans {file_path} : {e}")

def est_url_valide(url):
    parsed = urlparse(url)
    return bool(parsed.netloc) and bool(parsed.scheme)


def verifier_process_enregistrement(username):
    process_info = process_mapping.get(username)
    if process_info:
        pid = process_info["pid"]
        start_time = process_info["start_time"]
        try:
            if psutil.pid_exists(pid):
                process = psutil.Process(pid)

                # Vérifier l'utilisation des ressources
                memory_info = process.memory_info()
                cpu_usage = process.cpu_percent(interval=1)  # CPU usage sur 1 seconde

                """logging.info(
                    f"{username} - PID: {pid}, Mémoire: {memory_info.rss / (1024 * 1024):.2f} MB, "
                    f"CPU: {cpu_usage:.2f}%."
                )"""

                # Vérifier si un fichier correspondant existe
                pattern = f"/app/movies/TK_{username}_*_flv.mp4"
                fichiers_matches = glob.glob(pattern)
                if fichiers_matches:
                    # Trouver le fichier avec la modification la plus récente
                    fichier_recent = max(fichiers_matches, key=os.path.getmtime)
                    derniere_modification = os.path.getmtime(fichier_recent)
                    temps_ecoule = time.time() - derniere_modification

                    if temps_ecoule > 10:  # Plus de 10 secondes sans modification
                        logging.warning(
                            f"Le fichier {fichier_recent} n'a pas été modifié depuis {temps_ecoule:.2f} secondes. "
                            f"Arrêt du processus {username}."
                        )
                        process.terminate()
                        process_mapping.pop(username, None)
                        return False
                else:
                    logging.warning(f"Aucun fichier correspondant pour {username} trouvé dans /app/movies. Arrêt du processus.")
                    process.terminate()
                    process_mapping.pop(username, None)
                    return False

                # Vérifier la durée maximale
                elapsed_time = time.time() - start_time
                if elapsed_time > MAX_PROCESS_DURATION:
                    logging.warning(f"Arrêt du processus {username} (PID: {pid}) après {elapsed_time / 60:.2f} minutes.")
                    process.terminate()
                    process_mapping.pop(username, None)
                    return False

                """logging.info(f"{username} déjà en enregistrement PID: {pid}, durée: {elapsed_time / 60:.2f} minutes.")"""
                return True
        except psutil.NoSuchProcess:
            logging.error(f"Le processus {username} (PID: {pid}) n'existe plus.")
        except Exception as e:
            logging.error(f"Erreur lors de la vérification du processus {username} (PID: {pid}): {e}")
    
    # Nettoyer les informations de processus si non valides
    process_mapping.pop(username, None)
    return False


def surveiller():
    while True:
        liens = lire_liens()
        if not liens:
            logging.info("Aucun lien actif trouvé.")
        for url in liens:
            if est_url_valide(url):
                username = url.split("@")[1]
                if not verifier_process_enregistrement(username):
                    enregistrer_live(username)
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    surveiller()

