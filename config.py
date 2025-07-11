"""
Zentrale Konfigurationsdatei für den Discord Bot

Enthält:
1. Bot-Grundeinstellungen: BOT_CONFIG
    - Token, Prefix, Application ID
    - Beta-Modus Konfiguration
    - Zugriff über die .env Datei

2. Farbkonfiguration: COLORS
    - Vordefinierte Farben für Embeds
"""

import discord, os
from functools import wraps
from dotenv import load_dotenv
from typing import Final

load_dotenv()

def check_env_vars():
    required = ["BOT_TOKEN", "APPLICATION_ID"]
    missing = [var for var in required if not os.getenv(var)]
    if missing:
        raise EnvironmentError(f"Fehlende Umgebungsvariablen: {', '.join(missing)}")

check_env_vars()

# Bot Grundeinstellungen
BOT_CONFIG = {
    "beta": False, #If the bot is in beta mode, no function till this point
    "prefix": ".", #Mostly unnused because of the slash commands
    "token": str(os.getenv("BOT_TOKEN")), #Token of the bot
    "test_token": str(os.getenv("BOT_TEST_TOKEN")), #Token of the bot for testing
    "application_id": int(os.getenv("APPLICATION_ID")), #ID of the bot
    "test_application_id": int(os.getenv("TEST_APPLICATION_ID")), #ID of the bot for testing
    "FILEPATH": "/data.json", #Path to the data file
    "BACKUP_PATH": "/backup/", #Path to the backup folder
    "bot_version": "0.1.0",
    "state_version": "Stable Build",
    "status": "spielt mit den Leuten",
    "data": {
        "levels": {}           # Level-System (server-isoliert)
    }
}

BLACKLIST = {
    "users": [],
    "guilds": []
}

DEVELOPER_IDS = [
    796687533114523648, #Flimanda
    898905676980559933 #Darcci
]
# Farben
COLORS = {
    "violet": 0x9966cc,
    "red": 0xff0000,      # discord.Color.red()
    "green": 0x00ff00,    # discord.Color.green()
    "blue": 0x0099ff,     # discord.Color.blue()
    "orange": 0xff6600,   # discord.Color.orange()
    "yellow": 0xffff00,   # discord.Color.yellow()
    "purple": 0x9933ff,   # discord.Color.purple()
    "pink": 0xff69b4      # discord.Color.pink()
}