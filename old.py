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

ARTISTES = [
    "https://www.tiktok.com/@milawoe1",
    "https://www.tiktok.com/@raoul.le.blanc274",
    "https://www.tiktok.com/@aristolebledardaklaaa",
    "https://www.tiktok.com/@hodakotv",
    "https://www.tiktok.com/@souklevivi_gemy",
    "https://www.tiktok.com/@eza_choco8",
    "https://www.tiktok.com/@journallalternativetogo",
    "https://www.tiktok.com/@pagbodjan",
    "https://www.tiktok.com/@ghettovi23",
    "https://www.tiktok.com/@togbevikpesse2",
    "https://www.tiktok.com/@sethloofficiel",
    "https://www.tiktok.com/@zaga_bambo",
]

CHECK_INTERVAL_PRIORITAIRE = 60  # Vérification des prioritaires toutes les 60 secondes
CHECK_INTERVAL_NON_PRIORITAIRE = 600  # Vérification des non-prioritaires toutes les 10 minutes
MAX_PROCESS_DURATION = 30 * 60  # Durée maximale pour un processus en secondes

process_mapping = {}
prioritaires = set()
non_prioritaires = set()

def est_url_valide(url):
    parsed = urlparse(url)
    return bool(parsed.netloc) and bool(parsed.scheme)

def enregistrer_live(username):
    url = f"https://www.tiktok.com/@{username}"
    try:
        cmd = f"python3 main.py -user {username} -output ./movies"
        process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Attente pour une réponse rapide
        output, err = process.communicate(timeout=20)

        # Analyse des résultats si aucun timeout n'a eu lieu
        if b"Started recording" in output:
            prioritaires.add(url)
            non_prioritaires.discard(url)
            process_mapping[username] = {
                "pid": process.pid,
                "start_time": time.time()
            }
            logging.info(f"Live enregistrement pour {username} a commencé (PID: {process.pid}).")
        elif b"The user is not hosting a live stream" in err:
            non_prioritaires.add(url)
            prioritaires.discard(url)
            logging.info(f"{username} n'est pas en direct. --> non-prioritaires.")
        else:
            prioritaires.add(url)
            non_prioritaires.discard(url)
            logging.warning(f"Résultat inconnu pour {username}.")
            logging.warning(f"{err}.")
            logging.warning(f"{output}.")
    
    except subprocess.TimeoutExpired:
        # Considérer comme un enregistrement en cours si un timeout se produit
        prioritaires.add(url)
        non_prioritaires.discard(url)
        process_mapping[username] = {
            "pid": process.pid,
            "start_time": time.time()
        }
        logging.info(f"Timeout lors de l'enregistrement pour {username},--> actif (PID: {process.pid}).")
    
    except Exception as e:
        # Gérer d'autres exceptions
        logging.error(f"Erreur lors du lancement de l'enregistrement pour {username} : {e}")

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

                logging.info(
                    f"{username} - PID: {pid}, Mémoire: {memory_info.rss / (1024 * 1024):.2f} MB, "
                    f"CPU: {cpu_usage:.2f}%."
                )

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

                logging.info(f"{username} déjà en enregistrement PID: {pid}, durée: {elapsed_time / 60:.2f} minutes.")
                return True
        except psutil.NoSuchProcess:
            logging.error(f"Le processus {username} (PID: {pid}) n'existe plus.")
        except Exception as e:
            logging.error(f"Erreur lors de la vérification du processus {username} (PID: {pid}): {e}")
    
    # Nettoyer les informations de processus si non valides
    process_mapping.pop(username, None)
    return False

def surveiller_artistes():
    dernier_verif_non_prioritaire = time.time()  # Dernière vérification des non-prioritaires
    tour = 1

    while True:
        logging.info(f"----Début d'un cycle de surveillance... Tour: {tour}--------------")

        # Vérification des artistes prioritaires (toutes les 1 minute)
        logging.info("Vérification des artistes prioritaires...")
        for url in list(prioritaires):  # Conversion en liste pour éviter les erreurs en cas de modification
            if not est_url_valide(url):
                logging.error(f"L'URL {url} n'est pas valide. Ignorée.")
                continue

            username = url.split("@")[1]
            if not verifier_process_enregistrement(username):
                enregistrer_live(username)
                time.sleep(20)  # Petite pause pour éviter les blocages d'API

        # Vérification des artistes non prioritaires (toutes les 10 minutes)
        temps_ecoule_non_prioritaire = time.time() - dernier_verif_non_prioritaire
        if temps_ecoule_non_prioritaire >= CHECK_INTERVAL_NON_PRIORITAIRE or tour == 1:
            logging.info("Vérification des artistes non prioritaires...")
            for url in list(non_prioritaires):
                if not est_url_valide(url):
                    logging.error(f"L'URL {url} n'est pas valide. Ignorée.")
                    continue

                username = url.split("@")[1]
                if not verifier_process_enregistrement(username):
                    enregistrer_live(username)
                    time.sleep(10)  # Petite pause pour éviter les blocages d'API
            dernier_verif_non_prioritaire = time.time()  # Mise à jour de la dernière vérification

        logging.info("Fin du cycle. Mise à jour des listes prioritaires et non prioritaires.")

        # Pause avant la prochaine vérification des prioritaires
        logging.info("Pause de 60 secondes avant la prochaine vérification des artistes prioritaires.")
        tour += 1
        time.sleep(CHECK_INTERVAL_PRIORITAIRE)
        logging.info(f"{CHECK_INTERVAL_PRIORITAIRE}.")

if __name__ == "__main__":
    # Initialisation des artistes dans les non-prioritaires
    non_prioritaires.update(ARTISTES)
    surveiller_artistes()
