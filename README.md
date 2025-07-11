# 🤖 Discord Community Bot

**Entwickelt von [Mando Developing](https://flimando.com/)**

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Discord.py](https://img.shields.io/badge/Discord.py-2.3.3+-green.svg)](https://discordpy.readthedocs.io/)
[![License](https://img.shields.io/badge/License-CC%20BY--NC%204.0-red.svg)](https://creativecommons.org/licenses/by-nc/4.0/)
[![Version](https://img.shields.io/badge/Version-0.1.0-orange.svg)](https://github.com/flimando/discord-community-bot)
[![Website](https://img.shields.io/badge/Website-flimando.com-blue.svg)](https://bot.flimando.com/)

Ein **modularer** Discord Bot für Community-Server mit erweiterten Features wie Ticket-System, Level-System, Counter und Unix-Tools.

## 📋 Extensions

### 🎫 Ticket-System
- Vollautomatisches Ticket-System mit Kategorien
- Konfigurierbare Ticket-Einstellungen pro Server
- Support für verschiedene Ticket-Typen
- Automatische Archivierung und Löschung

### 📊 Level-System
- XP-basiertes Level-System
- Server-isolierte Level-Daten
- Konfigurierbare XP-Gewinnung
- Level-Up Benachrichtigungen

### 🔢 Counter-System
- Automatische Nachrichten-Zähler
- Konfigurierbare Counter-Kanäle
- Real-time Updates

### 🛠️ Unix-Tools
- Erweiterte Utility-Funktionen
- Server-Management Tools
- Moderations-Hilfsmittel

## 🚀 Installation

### Voraussetzungen
- Python (3.8+, empfohlen 3.13)
- Discord Bot Token
- Discord Application ID

### Setup

1. **Repository klonen**
```bash
git clone https://github.com/your-repo/basic-bot-comm.git
cd basic-bot-comm
```

2. **Dependencies installieren**
```bash
pip install -r requirements.txt
```

3. **Umgebungsvariablen konfigurieren**
(du brauchst nur TEST_ Variablen, wenn du einen Production und einen Beta Bot hast.)
Erstelle eine `.env` Datei im Root-Verzeichnis:
```env
BOT_TOKEN=your_discord_bot_token
BOT_TEST_TOKEN=your_test_bot_token
APPLICATION_ID=your_application_id
TEST_APPLICATION_ID=your_test_application_id
```

4. **Bot starten**
```bash
python starter.py
```

## ⚙️ Konfiguration

### Bot-Einstellungen (`config.py`)
```python
BOT_CONFIG = {
    "beta": False,                    # Beta-Modus
    "prefix": ".",                    # Command-Prefix
    "bot_version": "0.1.0",          # Bot-Version
    "state_version": "Stable Build", # Build-Status
    "status": "spielt mit den Leuten" # Bot-Status
}
```

### Extension-System
Der Bot lädt automatisch alle Python-Dateien aus dem `Extensions/` Ordner:
- `Ticket.py` - Ticket-System
- `level.py` - Level-System  
- `counter.py` - Counter-System
- `unix.py` - Utility-Tools

## 📁 Projektstruktur

```
basic-bot-comm/
├── starter.py              # Hauptstartdatei
├── config.py              # Bot-Konfiguration
├── functions.py           # Hilfsfunktionen
├── requirements.txt       # Python-Dependencies
├── data.json             # Bot-Daten
├── Extensions/           # Bot-Module
│   ├── Ticket.py        # Ticket-System
│   ├── level.py         # Level-System
│   ├── counter.py       # Counter-System
│   └── unix.py          # Utility-Tools
├── data/                 # Konfigurationsdaten
│   └── ticket_configs/   # Ticket-Konfigurationen
└── logs/                 # Log-Dateien
    └── bot.log          # Bot-Logs
```

## 🔧 Entwicklung

### Logging
Der Bot verwendet ein umfassendes Logging-System:
- Rotierende Log-Dateien (max. 2MB, 3 Backups)
- Console und File-Output
- Detaillierte Fehlerprotokollierung

### Extension-Entwicklung
Neue Module können einfach hinzugefügt werden:
1. Erstelle eine neue `.py` Datei im `Extensions/` Ordner
2. Implementiere die Discord.py Extension-Struktur
3. Der Bot lädt sie automatisch beim Start

## 📝 Lizenz

**Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)**

Diese Lizenz erlaubt:
- ✅ Kopieren und Verbreiten des Materials
- ✅ Anpassen und Weiterentwickeln
- ✅ Attribution (Nennung des Urhebers)

**NICHT erlaubt:**
- ❌ Kommerzielle Nutzung
- ❌ Geld verdienen mit dem Code
- ❌ Verkauf oder kommerzielle Verbreitung

### Attribution
Bei Verwendung bitte folgendes angeben:
```
Entwickelt von Mando Developing (https://flimando.com/)
Discord Community Bot - CC BY-NC 4.0
```

---

**Entwickelt mit ❤️ von Mando Developing**
