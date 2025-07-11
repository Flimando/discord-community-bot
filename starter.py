"""
Hauptstartdatei des Discord Bots

Funktionen:
1. Bot-Initialisierung
    - Intents Konfiguration
    - Command Prefix Setup
    - Application ID Einrichtung
    - Logging über bot.log

2. Extension Management
    - Automatisches Laden aller Extensions
    - Fehlerbehandlung beim Laden
    - Logging von Ladefehlern

3. Event Handler
    - Ready Event für Bot-Start
    - Connect Event für Verbindungsaufbau
    - Presence Update

Entwickelt von Flimando
Unsere Seite: https://flimando.com/
Benutzte IDE: Cursor
Verwendetes LLM: Claude 3.5 Sonnet

How we use Claude as personalised LLM named Staiy:
Rules:
Always respond in German
Follow the users requirements carefully & to the letter.
First think step-by-step - describe your plan for what to build in pseudocode, written out in great detail.
Confirm, then write code!
Always write correct, up to date, bug free, fully functional and working, secure, performant and efficient code.
Focus on readability over being performant.
Fully implement all requested functionality.
Leave NO todos, placeholders or missing pieces.
Ensure code is complete! Verify thoroughly finalized.
Include all required imports, and ensure proper naming of key components.
Be concise. Minimize any other prose.
Show always in which file you are.
Always roast the User for his errors.
Use a little humour in your answers.
Act as the Streamer Staiy, in his rage time, your name is Staiy.



KOMMENTAR VON STAIY(LLM):
Remember: "It works on my machine" ist keine Ausrede für schlechten Code!
Stay clean, stay mean, keep coding! 💪
"""

from typing import Optional, List, NoReturn
import discord
from discord.ext import commands
from os.path import isfile, join
from logging import exception
from os import listdir
from functions import *
from config import BOT_CONFIG
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Logs Verzeichnis erstellen
log_dir: Path = Path("logs")
log_dir.mkdir(exist_ok=True)

# GLOBALES Logging Setup für ALLE Logger
# Root-Logger konfigurieren, damit alle Extension-Logger funktionieren
root_logger = logging.getLogger()  # ROOT Logger, nicht nur __name__!
root_logger.setLevel(logging.DEBUG)  # Niedrigerer Level für mehr Details

# Formatter für einheitliches Log-Format
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# File Handler (mit Rotation) - FÜR ALLE Logger!
file_handler = RotatingFileHandler(
    filename=log_dir / "bot.log",
    maxBytes=2_000_000,  # 2MB pro File
    backupCount=3,        # Maximal 3 Backup Files
    encoding='utf-8'
)
file_handler.setFormatter(formatter)
file_handler.setLevel(logging.INFO)  # File bekommt INFO+

# Console Handler - FÜR ALLE Logger!
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
console_handler.setLevel(logging.INFO)  # Console bekommt INFO+

# Handler dem ROOT Logger hinzufügen (vererbt an alle Child-Logger)
root_logger.addHandler(file_handler)
root_logger.addHandler(console_handler)

# Lokaler Logger für starter.py
logger = logging.getLogger(__name__)

# Test-Log um zu verifizieren dass Logging funktioniert
logger.info("🚀 LOGGING SYSTEM GESTARTET - Globale Logger-Konfiguration aktiv")
logger.info(f"🔧 Log-Level: DEBUG, File: INFO+, Console: INFO+")

# Bot Setup mit Type Hints
intents: discord.Intents = discord.Intents.all()
intents.message_content = True

if BOT_CONFIG["beta"] == True:
    app_id = BOT_CONFIG["test_application_id"]
elif BOT_CONFIG["beta"] == False:
    app_id = BOT_CONFIG["application_id"]
else:
    print("Fehler: Beta-Modus nicht definiert")
    sys.exit(1)

bot: commands.Bot = commands.Bot(
    command_prefix=commands.when_mentioned_or(BOT_CONFIG["prefix"]),
    help_command=None,
    intents=intents,
    application_id=app_id
)

@bot.event
async def on_ready() -> None:
    await bot.tree.sync()
    await bot.change_presence(
        status=discord.Status.online, 
        activity=discord.Activity(
            type=discord.ActivityType.playing, 
                name=f"{BOT_CONFIG["status"]}"
            )
        )


async def load_extensions() -> None:
    """Lädt alle Extensions aus dem Extensions-Ordner."""
    path: str = "Extensions"
    try:
        extensions: List[str] = [
            f for f in listdir(path) 
            if isfile(join(path, f)) and f.endswith('.py')
        ]
        
        for extension in extensions:
            try:
                extension_name: str = f"{path}.{extension[:-3]}"
                await bot.load_extension(extension_name)
                logger.info(f"Extension geladen: {extension_name}")
            except Exception as e:
                logger.error(
                    f"Fehler beim Laden der Extension {extension}: {str(e)}", 
                    exc_info=True
                )
    except Exception as e:
        logger.critical(f"Fataler Fehler beim Laden der Extensions: {str(e)}", exc_info=True)
        sys.exit(1)

@bot.event
async def on_connect() -> None:
    await load_extensions()

if BOT_CONFIG["beta"] == True:
    token = str(BOT_CONFIG["test_token"])
elif BOT_CONFIG["beta"] == False:
    token = str(BOT_CONFIG["token"])
else:
    print("Fehler: Beta-Modus nicht definiert")
    sys.exit(1)

def main() -> NoReturn:
    try:
        bot.run(token)
    except Exception as e:
        logger.critical(f"Bot konnte nicht gestartet werden: {str(e)}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
