import subprocess
import json
import os
import time
import argparse
import logging
from datetime import datetime

# Setup Logging
log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_file = os.path.join(log_dir, f"bulk_offboard_{timestamp}.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("bulk_offboard")

# 1. The Cleaned Target List (37 Unique Accounts)
TARGETS = [
    {"first": "Antonio", "last": "Fedele", "email": "a.fedele-LDO@boom.aero"},
    {"first": "Agostino", "last": "Luise", "email": "a.luise-LDO@boom.aero"},
    {"first": "Almerigo", "last": "Pantalone", "email": "a.pantalone-LDO@boom.aero"},
    {"first": "Alfredo", "last": "Ricciardi", "email": "a.ricciardi-LDO@boom.aero"},
    {"first": "Aniello", "last": "Smarrazzo", "email": "a.smarrazzo-LDO@boom.aero"},
    {"first": "Angelo", "last": "Sportelli", "email": "a.sportelli-LDO@boom.aero"},
    {"first": "Cedric", "last": "Puigdengolas", "email": "c.puigdengolas-LIS@boom.aero"},
    {"first": "Ferdinando", "last": "Caramiello", "email": "f.caramiello-LDO@boom.aero"},
    {"first": "Francesco", "last": "Ingegno", "email": "f.ingegno-LDO@boom.aero"},
    {"first": "Gioacchino", "last": "Carlone", "email": "g.carlone-LDO@boom.aero"},
    {"first": "Giulio", "last": "De Maria", "email": "g.demaria-LDO@boom.aero"},
    {"first": "Giuseppe", "last": "Di Meo", "email": "g.dimeo-LDO@boom.aero"},
    {"first": "Giovanni", "last": "Di Somma", "email": "g.disomma-LDO@boom.aero"},
    {"first": "Giovanni", "last": "Gente", "email": "g.gente-LDO@boom.aero"},
    {"first": "Gaetano", "last": "Ricciardi", "email": "g.ricciardi-LDO@boom.aero"},
    {"first": "Ilaria", "last": "Blasi", "email": "i.blasi-LDO@boom.aero"},
    {"first": "Iker", "last": "Pradovaso", "email": "i.pradovaso-ANN@boom.aero"},
    {"first": "Iker", "last": "Zalbide Padura", "email": "i.zalbide-ANN@boom.aero"},
    {"first": "Jeremy", "last": "Granier", "email": "j.granier-LIS@boom.aero"},
    {"first": "Jose Ignacio", "last": "Izar De La Fuente", "email": "j.izardelafuente-ANN@boom.aero"},
    {"first": "Jerome", "last": "Sisquet", "email": "j.sisquet-LIS@boom.aero"},
    {"first": "Luis Angel", "last": "Alejo", "email": "l.alejo-ANN@boom.aero"},
    {"first": "Luca", "last": "Angelino", "email": "l.angelino-LDO@boom.aero"},
    {"first": "Luca", "last": "Coppola", "email": "l.coppola-LDO@boom.aero"},
    {"first": "Luca", "last": "Monopoli", "email": "l.monopoli-LDO@boom.aero"},
    {"first": "Lorenza", "last": "Nola", "email": "l.nola-LDO@boom.aero"},
    {"first": "Nicolas", "last": "Boulous", "email": "n.boulous-LIS@boom.aero"},
    {"first": "Nicola", "last": "Capasso", "email": "n.capasso-LDO@boom.aero"},
    {"first": "Paolo", "last": "Ambrico", "email": "p.ambrico-LDO@boom.aero"},
    {"first": "Pasquale", "last": "Francabandiera", "email": "p.francabandiera-LDO@boom.aero"},
    {"first": "Pasquale", "last": "Gambardella", "email": "p.gambardella-LDO@boom.aero"},
    {"first": "Ruben", "last": "Elices Vidriales", "email": "r.elices-ANN@boom.aero"},
    {"first": "Ruggero", "last": "Grafiti", "email": "r.grafiti-LDO@boom.aero"},
    {"first": "Vincenzo", "last": "Volpara", "email": "v.volpara-LDO@boom.aero"},
    {"first": "Xabier", "last": "Aia Lopez de Foronda", "email": "x.aia-ANN@boom.aero"},
    {"first": "Xavier", "last": "Devos", "email": "x.devos-LIS@boom.aero"},
    {"first": "Yoann", "last": "Julou", "email": "y.julou-LIS@boom.aero"}
]

WORKFLOW = "servus/workflows/offboard_us.yaml"
TEMP_PROFILE = "temp_offboard_profile.json"

def run_offboarding(dry_run=True, limit=None):
    mode = "DRY RUN" if dry_run else "LIVE EXECUTION"
    logger.info(f"🚀 Starting Bulk Offboard sequence for {len(TARGETS)} users.")
    logger.info(f"👉 Mode: {mode}")
    
    if limit:
        logger.info(f"👉 Limit: Processing only first {limit} users.")
        targets_to_process = TARGETS[:limit]
    else:
        targets_to_process = TARGETS

    for i, user in enumerate(targets_to_process, 1):
        logger.info(f"[{i}/{len(targets_to_process)}] Processing: {user['first']} {user['last']} <{user['email']}>...")
        
        # 1. Create temporary profile JSON
        profile_data = {
            "first_name": user["first"],
            "last_name": user["last"],
            "work_email": user["email"],
            "department": "Supplier/Contractor",
            "title": "External",
            "employment_type": "Contractor",
            "start_date": "2020-01-01", # Dummy dates for schema validation
            "manager": "unknown" 
        }
        
        with open(TEMP_PROFILE, "w") as f:
            json.dump(profile_data, f)
            
        # 2. Build Command
        cmd = [
            "python3", "-m", "servus", "offboard",
            "--workflow", WORKFLOW,
            "--profile", TEMP_PROFILE
        ]
        
        if dry_run:
            cmd.append("--dry-run")
            
        # 3. Execute SERVUS
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                logger.info("   ✅ Success")
                # logger.debug(result.stdout) 
            else:
                logger.error("   ❌ Failed")
                logger.error(result.stderr)
        except Exception as e:
            logger.error(f"   ❌ Exception: {e}")
            
        logger.info("-" * 40)
        time.sleep(1) # Polite pause

    # Cleanup
    if os.path.exists(TEMP_PROFILE):
        os.remove(TEMP_PROFILE)
    logger.info("\n🏁 Bulk Sequence Complete.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bulk Offboard Suppliers")
    parser.add_argument("--live", action="store_true", help="Run in LIVE mode (default is DRY RUN)")
    parser.add_argument("--limit", type=int, help="Limit number of users to process (e.g. 1 for testing)")
    
    args = parser.parse_args()
    
    # Default is dry_run=True, so if --live is passed, dry_run=False
    run_offboarding(dry_run=not args.live, limit=args.limit)