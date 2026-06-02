import logging
import sys
import os

# Aggiungo la cartella poller al path per importare Database
sys.path.append(os.path.join(os.getcwd(), 'poller'))

from db import Database

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
log = logging.getLogger(__name__)

def backfill():
    db_path = os.path.join(os.getcwd(), 'data', 'leapmotor_mate.db')
    if not os.path.exists(db_path):
        log.error(f"Database non trovato in: {db_path}")
        return
    
    db = Database(db_path)
    
    # Cerchiamo tutti i trip_id che hanno punti senza altitudine
    trips = db._conn.execute(
        "SELECT DISTINCT trip_id FROM trip_positions WHERE altitude IS NULL"
    ).fetchall()
    
    if not trips:
        log.info("Nessun viaggio da aggiornare. Tutti i punti hanno già la quota.")
        return

    log.info(f"Trovati {len(trips)} viaggi da aggiornare con dati altimetrici.")
    
    for row in trips:
        trip_id = row['trip_id']
        try:
            db.fetch_trip_elevations(trip_id)
        except Exception as e:
            log.error(f"Errore durante il recupero per il viaggio #{trip_id}: {e}")

    log.info("Operazione completata!")

if __name__ == "__main__":
    backfill()
