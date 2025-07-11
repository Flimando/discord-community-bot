"""
Zentrale Funktionsbibliothek für den Discord Bot

Diese Datei enthält alle grundlegenden Funktionen, die von verschiedenen
Bot-Komponenten verwendet werden. Sie ist in folgende Hauptbereiche unterteilt:

1. Datenbank-Setup und Grundfunktionen
    - Initialisierung der JSON-Datenbank
    - Lade- und Speicherfunktionen

2. Ticket-System Funktionen
    - Ticket-Verwaltung (Erstellen, Prüfen, Löschen)
    - Berechtigungsprüfungen

3. Shopping-System Funktionen
    - Einkaufslisten-Verwaltung
    - Embed-Erstellung

4. Todo-System Funktionen
    - Aufgabenlisten-Verwaltung
    - Embed-Erstellung

Wichtige Hinweise:
- Alle Daten werden in data.json gespeichert
- Automatische Backup-Erstellung bei Änderungen
- Thread-safe Datenbankzugriffe
"""

import json, os, discord
from config import BOT_CONFIG, COLORS
from discord.ext import commands
from threading import Lock
from datetime import datetime

# Globale Variablen
try:
    data = BOT_CONFIG["data"]
except Exception as e:
    print(f"Fehler beim Laden der Konfiguration: {e}")
    raise
FILEPATH = BOT_CONFIG["FILEPATH"]
BACKUP_PATH = BOT_CONFIG["BACKUP_PATH"]


_file_lock = Lock()  # Erstellt eine Sperre

# ====== DATENBANK-SETUP ======
if os.path.isfile("data.json"):
    with open("data.json", encoding="utf-8") as file:
        data = json.load(file)
        print("Loaded Database: Data")
else:
    data = {
        "levels": {},              # Level-System (server-isoliert)
        "moderation": {},          # Warning-System
        "shopping": {              # Shopping-System
            "Profiles": []
        },
        "todo": {                  # Todo-System
            "Profiles": []
        },
        "tickets": {},             # Ticket-System
        "welcome_system": {}       # Welcome-System
    }
    with open("data.json", "w") as file:
        json.dump(data, file, indent=4)
        print("Created Database: Data")

# ====== GRUNDLEGENDE FUNKTIONEN ======
def dump():
    """Speichert die aktuellen Daten in die JSON-Datei"""
    with _file_lock:
        try:
            with open("data.json", "w") as file:
                json.dump(data, file, indent=4)
        except IOError as e:
            print(f"Fehler beim Speichern: {e}")
            raise
        except Exception as e:
            print(f"Unerwarteter Fehler: {e}")
            raise

def lib():
    """Gibt die aktuelle Datenbank zurück"""
    return data


# Prüfe ob alle nötigen Keys existieren, falls nicht erstelle sie
required_keys = {
    "levels": {},
    "moderation": {},
    "shopping": {"Profiles": []},
    "todo": {"Profiles": []},
    "tickets": {},
    "welcome_system": {}
}

for key, default_value in required_keys.items():
    if key not in data:
        data[key] = default_value

        dump()


# ====== DISCORD.PY COG SETUP ======
class functions(commands.Cog):
    """Klasse für Discord.py Cog-System"""
    pass

def setup(bot):
    """Fügt den Cog zum Bot hinzu"""
    bot.add_cog(functions(bot))


# ====== SHOPPING-SYSTEM FUNKTIONEN ======
def save_shopping_list():
    #Speichert die Einkaufsliste
    dump()

def shopping_dump():
    #Speichert die Shopping-Daten
    dump()

def create_shopping_embed():
    #Erstellt ein Embed für die Einkaufsliste
    embed = discord.Embed(title="Einkaufsliste", color=COLORS["violet"], timestamp=get_timestamp())
    if "shopping" in data and "Profiles" in data["shopping"]:
        for i, item in enumerate(data["shopping"]["Profiles"]):
            embed.add_field(
                name=f"{i}. {item['task']}", 
                value=f"Hinzugefügt von: {item['author']}", 
                inline=False
            )
    else:
        embed.add_field(name="Leer", value="Keine Einträge vorhanden", inline=False)
    return embed

# ====== TODO-SYSTEM FUNKTIONEN ======
def save_todo_list():
    #Speichert die Todo-Liste
    dump()

def create_embed():
    #Erstellt ein Embed für die Todo-Liste
    embed = discord.Embed(title="Todo-Liste", color=COLORS["violet"], timestamp=get_timestamp())
    if "todo" in data and "Profiles" in data["todo"]:
        for i, item in enumerate(data["todo"]["Profiles"]):
            embed.add_field(
                name=f"{i}. {item['task']}", 
                value=f"Hinzugefügt von: {item['author']}", 
                inline=False
            )
    else:
        embed.add_field(name="Leer", value="Keine Einträge vorhanden", inline=False)
    return embed

def get_timestamp() -> datetime:
    #Gibt den aktuellen Timestamp zurück
    return datetime.now()
# ====== MODERATION-SYSTEM FUNKTIONEN ======
def add_warning(user_id, guild_id, reason = "Kein Grund angegeben"):
    #Fügt eine Warnung zu einem User hinzu
    if guild_id not in data["moderation"]:
        data["moderation"][guild_id] = {
            "warnings": {}
        }
    if user_id not in data["moderation"][guild_id]["warnings"]:
        data["moderation"][guild_id]["warnings"][user_id] = []
    data["moderation"][guild_id]["warnings"][user_id].append({
        "reason": reason,
        "timestamp": datetime.now().isoformat()
    })
    dump()
    return True

def get_warnings(user_id, guild_id):
    #Gibt alle Warnungen eines Users zurück
    if guild_id not in data["moderation"]:
        return []
    if user_id not in data["moderation"][guild_id]["warnings"]:
        return []
    return data["moderation"][guild_id]["warnings"][user_id]

def check_warnings(user_id, guild_id):
    #Prüft, ob ein User mehr als 3 Warnungen hat
    warnings = get_warnings(user_id, guild_id)
    if len(warnings) >= 3:
        return True
    return False

# ====== LEVEL-SYSTEM FUNKTIONEN ======
def setup_level_system(guild_id: str):
    #Richtet das Level-System für einen Server ein
    if guild_id not in data["levels"]:
        data["levels"][guild_id] = {
            "enabled": True,
            "announcement_channel": None,
            "xp_cooldown": 30,  # Sekunden
            "xp_range": [1, 15],  # Min-Max XP pro Nachricht
            "blocked_channels": [],  # Blockierte Channels für XP
            "users": {}
        }
        dump()
        return True
    return False

def init_level_system(guild_id: str, announcement_channel_id: str = None):
    """Initialisiert das Level-System für einen Server mit optionalem Announcement-Channel"""
    # Richte das Level-System ein
    setup_level_system(guild_id)
    
    # Setze Announcement-Channel falls angegeben
    if announcement_channel_id:
        set_announcement_channel(guild_id, announcement_channel_id)

def is_level_system_enabled(guild_id: str) -> bool:
    #Prüft ob das Level-System für einen Server aktiviert ist
    return guild_id in data["levels"] and data["levels"][guild_id]["enabled"]

def get_user_level_data(guild_id: str, user_id: str):
    #Gibt die Level-Daten eines Users zurück
    if guild_id not in data["levels"]:
        return None
    
    if user_id not in data["levels"][guild_id]["users"]:
        data["levels"][guild_id]["users"][user_id] = {
            "xp": 0,
            "level": 0,
            "messages": 0,
            "last_message_time": 0
        }
        dump()
    
    return data["levels"][guild_id]["users"][user_id]

def add_xp_to_user(guild_id: str, user_id: str, xp_amount: int):
    #Fügt XP einem User hinzu und gibt True zurück wenn Level-Up
    if not is_level_system_enabled(guild_id):
        return False
    
    user_data = get_user_level_data(guild_id, user_id)
    if not user_data:
        return False
    
    old_level = user_data["level"]
    user_data["xp"] += xp_amount
    user_data["messages"] += 1
    user_data["last_message_time"] = int(datetime.now().timestamp())
    
    # Level berechnen: Level = sqrt(XP/100)
    new_level = int((user_data["xp"] / 100) ** 0.5)
    user_data["level"] = new_level
    
    dump()
    
    # True wenn Level-Up
    return new_level > old_level

def get_leaderboard(guild_id: str, limit: int = 10):
    #Gibt die Top User eines Servers zurück
    if guild_id not in data["levels"]:
        return []
    
    users = data["levels"][guild_id]["users"]
    sorted_users = sorted(users.items(), key=lambda x: x[1]["xp"], reverse=True)
    return sorted_users[:limit]

def can_gain_xp(guild_id: str, user_id: str) -> bool:
    #Prüft ob ein User XP bekommen kann (Cooldown)
    if guild_id not in data["levels"]:
        return False
    
    if user_id not in data["levels"][guild_id]["users"]:
        return True
    
    user_data = data["levels"][guild_id]["users"][user_id]
    cooldown = data["levels"][guild_id]["xp_cooldown"]
    current_time = int(datetime.now().timestamp())
    
    return (current_time - user_data["last_message_time"]) >= cooldown

def get_xp_for_level(level: int) -> int:
    #Berechnet die benötigten XP für ein Level
    return int((level ** 2) * 100)

def get_progress_to_next_level(xp: int) -> tuple:
    #Gibt Fortschritt zum nächsten Level zurück (current_xp, needed_xp, percentage)
    current_level = int((xp / 100) ** 0.5)
    current_level_xp = get_xp_for_level(current_level)
    next_level_xp = get_xp_for_level(current_level + 1)
    
    xp_in_current_level = xp - current_level_xp
    xp_needed_for_next = next_level_xp - current_level_xp
    
    percentage = (xp_in_current_level / xp_needed_for_next) * 100 if xp_needed_for_next > 0 else 100
    
    return xp_in_current_level, xp_needed_for_next, percentage

def set_announcement_channel(guild_id: str, channel_id: str):
    #Setzt den Announcement-Channel für Level-Ups
    if guild_id not in data["levels"]:
        return False
    
    data["levels"][guild_id]["announcement_channel"] = channel_id
    dump()
    return True

def get_announcement_channel(guild_id: str):
    #Gibt den Announcement-Channel zurück
    if guild_id not in data["levels"]:
        return None
    return data["levels"][guild_id]["announcement_channel"]

def block_channel_for_xp(guild_id: str, channel_id: str) -> bool:
    #Blockiert einen Channel für XP-Gewinn
    if guild_id not in data["levels"]:
        return False
    
    if channel_id not in data["levels"][guild_id]["blocked_channels"]:
        data["levels"][guild_id]["blocked_channels"].append(channel_id)
        dump()
        return True
    return False

def unblock_channel_for_xp(guild_id: str, channel_id: str) -> bool:
    #Entblockiert einen Channel für XP-Gewinn
    if guild_id not in data["levels"]:
        return False
    
    if channel_id in data["levels"][guild_id]["blocked_channels"]:
        data["levels"][guild_id]["blocked_channels"].remove(channel_id)
        dump()
        return True
    return False

def is_channel_blocked(guild_id: str, channel_id: str) -> bool:
    #Prüft ob ein Channel für XP blockiert ist
    if guild_id not in data["levels"]:
        return False
    return channel_id in data["levels"][guild_id]["blocked_channels"]

def get_blocked_channels(guild_id: str) -> list:
    #Gibt alle blockierten Channels eines Servers zurück
    if guild_id not in data["levels"]:
        return []
    return data["levels"][guild_id]["blocked_channels"]

# ====== WELCOME-SYSTEM FUNKTIONEN ======
def setup_welcome_system(guild_id: str) -> bool:
    """Aktiviert das Welcome-System für einen Server und erstellt die Grundstruktur in der JSON"""
    if "welcome_system" not in data:
        data["welcome_system"] = {}
        
    if guild_id not in data["welcome_system"]:
        data["welcome_system"][guild_id] = {
            "enabled": True,
            "channel_id": None,
            "welcome_msg": "Willkommen {user} auf {server}! Du bist unser {count}. Mitglied!",
            "leave_msg": "Auf Wiedersehen {user}! Wir werden dich vermissen..."
        }
        dump()
        return True
    return False

def is_welcome_system_enabled(guild_id: str) -> bool:
    """Prüft ob das Welcome-System für einen Server aktiviert ist"""
    if "welcome_system" not in data or guild_id not in data["welcome_system"]:
        return False
    return data["welcome_system"][guild_id]["enabled"]

def set_welcome_channel(guild_id: str, channel_id: str) -> bool:
    """Setzt den Welcome-Channel für einen Server"""
    if "welcome_system" not in data or guild_id not in data["welcome_system"]:
        setup_welcome_system(guild_id)
    
    data["welcome_system"][guild_id]["channel_id"] = channel_id
    dump()
    return True

def get_welcome_channel(guild_id: str) -> str:
    """Gibt den Welcome-Channel eines Servers zurück"""
    if "welcome_system" not in data or guild_id not in data["welcome_system"]:
        return None
    return data["welcome_system"][guild_id]["channel_id"]

def set_welcome_message(guild_id: str, message: str) -> bool:
    """Setzt die Willkommensnachricht für einen Server"""
    if "welcome_system" not in data or guild_id not in data["welcome_system"]:
        setup_welcome_system(guild_id)
    
    data["welcome_system"][guild_id]["welcome_msg"] = message
    dump()
    return True

def get_welcome_message(guild_id: str) -> str:
    """Gibt die Willkommensnachricht eines Servers zurück"""
    if "welcome_system" not in data or guild_id not in data["welcome_system"]:
        return None
    return data["welcome_system"][guild_id]["welcome_msg"]

def set_leave_message(guild_id: str, message: str) -> bool:
    """Setzt die Abschiedsnachricht für einen Server"""
    if "welcome_system" not in data or guild_id not in data["welcome_system"]:
        setup_welcome_system(guild_id)
    
    data["welcome_system"][guild_id]["leave_msg"] = message 
    dump()
    return True

def get_leave_message(guild_id: str) -> str:
    """Gibt die Abschiedsnachricht eines Servers zurück"""
    if "welcome_system" not in data or guild_id not in data["welcome_system"]:
        return None
    return data["welcome_system"][guild_id]["leave_msg"]

def toggle_welcome_system(guild_id: str, enabled: bool) -> bool:
    """Aktiviert oder Deaktiviert das Welcome-System für einen Server"""
    if "welcome_system" not in data or guild_id not in data["welcome_system"]:
        setup_welcome_system(guild_id)
    
    data["welcome_system"][guild_id]["enabled"] = enabled
    dump()
    return True
# ====== TICKET-SYSTEM FUNKTIONEN ======
def create_ticket(channel_id: int, owner_id: int, guild_id: int, reason: str) -> bool:
    """Erstellt ein neues Ticket in der Datenbank"""
    if "tickets" not in data:
        data["tickets"] = {}
    if str(guild_id) not in data["tickets"]:
        data["tickets"][str(guild_id)] = {}
    
    data["tickets"][str(guild_id)][str(channel_id)] = {
        "Owner_ID": owner_id,
        "Type": reason,
        "Created": datetime.now().isoformat(),
        "control_message_id": None  # Wird später gesetzt
    }
    dump()
    return True

def kill_ticket(channel_id: int, guild_id: int) -> bool:
    """Löscht ein Ticket aus der Datenbank"""
    if "tickets" not in data or str(guild_id) not in data["tickets"] or str(channel_id) not in data["tickets"][str(guild_id)]:
        return False
    
    del data["tickets"][str(guild_id)][str(channel_id)]
    dump()
    return True

def is_ticket(channel_id: int, guild_id: int) -> bool:
    """Prüft ob ein Channel ein Ticket ist"""
    return ("tickets" in data and 
            str(guild_id) in data["tickets"] and 
            str(channel_id) in data["tickets"][str(guild_id)])

def add_control_message_to_ticket(channel_id: int, guild_id: int, message_id: int) -> bool:
    """Fügt die Control-Message-ID zu einem bestehenden Ticket hinzu"""
    if not is_ticket(channel_id, guild_id):
        return False
    
    data["tickets"][str(guild_id)][str(channel_id)]["control_message_id"] = message_id
    dump()
    return True

def get_ticket_control_message_id(channel_id: int, guild_id: int) -> int:
    """Gibt die Control-Message-ID eines Tickets zurück"""
    if not is_ticket(channel_id, guild_id):
        return None
    return data["tickets"][str(guild_id)][str(channel_id)].get("control_message_id")

def ticket_check(user_id: int, channel_id: int, guild_id: int) -> bool:
    """Prüft ob ein User der Besitzer eines Tickets ist"""
    if not is_ticket(channel_id, guild_id):
        return False
    return data["tickets"][str(guild_id)][str(channel_id)]["Owner_ID"] == user_id

def cleanup_ghost_tickets(guild_id: int, bot) -> int:
    """Räumt Ghost-Tickets auf (Tickets deren Kanäle nicht mehr existieren)"""
    if "tickets" not in data or str(guild_id) not in data["tickets"]:
        return 0
    
    guild = bot.get_guild(guild_id)
    if not guild:
        return 0
    
    tickets_to_remove = []
    for channel_id, ticket_data in data["tickets"][str(guild_id)].items():
        channel = guild.get_channel(int(channel_id))
        if not channel:
            print(f"🧹 Ghost-Ticket gefunden: Channel {channel_id} existiert nicht mehr!")
            tickets_to_remove.append(channel_id)
    
    # Entferne Ghost-Tickets
    for channel_id in tickets_to_remove:
        del data["tickets"][str(guild_id)][channel_id]
        print(f"🗑️ Ghost-Ticket {channel_id} aus Datenbank entfernt")
    
    if tickets_to_remove:
        dump()  # Speichere Änderungen
        print(f"✅ {len(tickets_to_remove)} Ghost-Tickets für Guild {guild_id} aufgeräumt!")
    
    return len(tickets_to_remove)

def max_tickets(user_id: int, guild_id: int, bot=None) -> bool:
    """Prüft ob ein User die maximale Anzahl an Tickets erreicht hat"""
    if "tickets" not in data or str(guild_id) not in data["tickets"]:
        return True
    
    # Hole das Maximum aus der Guild-Config (Standard: 3)
    max_allowed = get_max_tickets_for_guild(guild_id)
    
    # Ghost-Ticket-Cleanup wenn Bot verfügbar ist
    if bot:
        cleanup_ghost_tickets(guild_id, bot)
        
    count = sum(1 for ticket in data["tickets"][str(guild_id)].values() 
                if ticket["Owner_ID"] == user_id)
    return count < max_allowed

def get_max_tickets_for_guild(guild_id: int) -> int:
    """Holt das Maximum an Tickets pro User aus der Guild-Config"""
    try:
        from pathlib import Path
        import json
        
        config_path = Path(f"data/ticket_configs/guild_{guild_id}.json")
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                return config.get('max_tickets_per_user', 3)
    except Exception as e:
        print(f"Fehler beim Laden der Ticket-Config für Guild {guild_id}: {e}")
    
    return 3  # Fallback



def get_ticket_owner(channel_id: int, guild_id: int) -> int:
    """Gibt die ID des Ticket-Besitzers zurück"""
    if not is_ticket(channel_id, guild_id):
        return None
    return data["tickets"][str(guild_id)][str(channel_id)]["Owner_ID"]

def get_ticket_data(channel_id: int, guild_id: int) -> dict:
    """Gibt alle Daten eines Tickets zurück"""
    if not is_ticket(channel_id, guild_id):
        return None
    return data["tickets"][str(guild_id)][str(channel_id)]

def setup_ticket_system(guild_id: int) -> bool:
    """Initialisiert das Ticket-System für einen Server"""
    if "tickets" not in data:
        data["tickets"] = {}
    if str(guild_id) not in data["tickets"]:
        data["tickets"][str(guild_id)] = {}
        dump()
        return True
    return False


