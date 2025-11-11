"""
Unix-Befehle Extension für den Discord Bot

Funktionalitäten:
1. Clear Command
    - Löscht eine bestimmte Anzahl von Nachrichten
    - Verfügbar auf allen erlaubten Servern
    - Verzögertes Löschen zur Vermeidung von Rate Limits

2. Ban Command
    - Bannt einen Nutzer per Mention oder ID
    - Optionale Angabe eines Grundes
    - Nur für Admins/Moderatoren verfügbar
    - Logging des Vorgangs

3. Massenban Command
    - Bannt mehrere Nutzer gleichzeitig
    - IDs durch Kommas getrennt
    - Optionale Angabe eines Grundes
    - Ausführliche Erfolgs-/Fehlermeldungen

Sicherheitshinweise:
- Purge-Funktion sollte mit Bedacht verwendet werden
- Automatische Verzögerungen eingebaut
- Ephemeral Responses für bessere Übersicht
- Ban-Funktion nur für Berechtigte nutzbar
- Massenban nur für Administratoren
"""

from discord.ext import commands
import discord
import asyncio
from datetime import datetime, timedelta, timezone
import logging
from discord import app_commands
from functions import *
from config import COLORS, BOT_CONFIG, BLACKLIST, DEVELOPER_IDS
import json
import os
import re

# Logger Setup
logger = logging.getLogger(__name__)

prefix = BOT_CONFIG["prefix"]

class Unix(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        # Link-Erkennungsmuster
        self.link_patterns = [
            r'https?://[^\s]+',                    # HTTP/HTTPS Links
            r'www\.[^\s]+',                        # www Links
            r'[^\s]+\.[a-zA-Z]{2,}/?[^\s]*',       # Domain.tld Links
            r'discord\.gg/[^\s]+',                 # Discord Invites
            r'discord\.com/invite/[^\s]+',         # Discord Invites
            r'[^\s]+\.tk[^\s]*',                   # .tk Domains
            r'[^\s]+\.ml[^\s]*',                   # .ml Domains  
            r'[^\s]+\.cf[^\s]*',                   # .cf Domains
            r'[^\s]+\.ga[^\s]*',                   # .ga Domains
            r'bit\.ly/[^\s]+',                     # Bitly Links
            r'tinyurl\.com/[^\s]+',                # TinyURL Links
            r't\.co/[^\s]+',                       # Twitter Links
            r'youtu\.be/[^\s]+',                   # YouTube Short Links
            r'[^\s]+\.link[^\s]*',                 # .link Domains
        ]
        
        # Kompiliere Regex-Muster für bessere Performance
        self.compiled_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.link_patterns]

    def _contains_link(self, text: str) -> bool:
        """Prüft ob der Text Links enthält"""
        for pattern in self.compiled_patterns:
            if pattern.search(text):
                return True
        return False

    def _load_link_config(self) -> dict:
        """Lädt die Link-Schutz-Konfiguration"""
        try:
            # Erstelle config-Ordner falls nicht vorhanden
            if not os.path.exists('config'):
                os.makedirs('config')
                
            with open('config/link_protection.json', 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {
                "enabled_guilds": [],
                "exempt_channels": {},
                "exempt_users": {},
                "exempt_categories": {}
            }

    def _save_link_config(self, config: dict):
        """Speichert die Link-Schutz-Konfiguration"""
        try:
            if not os.path.exists('config'):
                os.makedirs('config')
            with open('config/link_protection.json', 'w') as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            logger.error(f"Fehler beim Speichern der Link-Konfiguration: {e}")

    @commands.Cog.listener()
    async def on_ready(self):
        print("Logged Succesfully In")

    @commands.Cog.listener()
    async def on_message(self, message):
        """Link-Schutz Event Handler"""
        # Ignore bot messages
        if message.author.bot:
            return
            
        # Ignore DMs
        if not message.guild:
            return
            
        # Ignore if no content
        if not message.content:
            return
            
        # Lade Link-Konfiguration
        config = self._load_link_config()
        guild_id = str(message.guild.id)
        
        # Prüfe ob Link-Schutz für diesen Server aktiviert ist
        if guild_id not in config["enabled_guilds"]:
            return
            
        # Prüfe Channel-Ausnahmen
        if guild_id in config["exempt_channels"]:
            if str(message.channel.id) in config["exempt_channels"][guild_id]:
                return
                
        # Prüfe User-Ausnahmen
        if guild_id in config["exempt_users"]:
            if str(message.author.id) in config["exempt_users"][guild_id]:
                return
        
        # Prüfe Kategorie-Ausnahmen
        try:
            # Prüfe ob Channel überhaupt eine Kategorie hat
            if message.channel.category:
                if guild_id in config["exempt_categories"]:
                    if str(message.channel.category.id) in config["exempt_categories"][guild_id]:
                        return
        except AttributeError:
            # Channel hat keine Kategorie (z.B. DM oder uncategorized channel)
            pass
        except KeyError:
            # exempt_categories existiert nicht für diese Guild oder den ganzen Key
            if "exempt_categories" not in config:
                config["exempt_categories"] = {}
            if guild_id not in config["exempt_categories"]:
                config["exempt_categories"][guild_id] = []
            self._save_link_config(config)
                
        # Prüfe Admin-Berechtigungen
        if message.author.guild_permissions.administrator:
            return
            
        # Prüfe Moderator-Berechtigungen
        if message.author.guild_permissions.manage_messages:
            return
            
        # Prüfe auf Links
        if self._contains_link(message.content):
            try:
                # Lösche die Nachricht
                await message.delete()
                
                # Sende Warnung
                warning_embed = discord.Embed(
                    title="🚫 Link blockiert!",
                    description=f"{message.author.mention}, Links sind in diesem Server nicht erlaubt!",
                    color=COLORS["red"],
                    timestamp=get_timestamp()
                )
                warning_embed.set_footer(text=f"User: {message.author.name} | Channel: #{message.channel.name}")
                
                # Sende Warnung und lösche nach 10 Sekunden
                warning_msg = await message.channel.send(embed=warning_embed)
                await asyncio.sleep(10)
                await warning_msg.delete()
                
                # Logging
                logger.info(f"Link blocked from {message.author.id} in {message.guild.id} | Content: {message.content[:100]}")
                
            except discord.Forbidden:
                logger.error(f"Keine Berechtigung zum Löschen von Links in {message.guild.id}")
            except Exception as e:
                logger.error(f"Fehler beim Link-Schutz: {e}")
    
    @app_commands.command(
        name="help",
        description="Zeigt die Hilfe an"
    )
    async def help(self, interaction: discord.Interaction):
        try:
            embed = discord.Embed(
                title="🤖 Bot-Hilfe - Alle Befehle", 
                description="**Hier sind alle verfügbaren Befehle, kategorisiert nach Funktionen:**\n\n"
                           "Nutze `/about` für Informationen über die Entwickler!", 
                color=COLORS["violet"], 
                timestamp=get_timestamp()
            )
            
            # Set Bot Avatar
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)
            
            # 🛠️ ALLGEMEINE BEFEHLE
            embed.add_field(
                name="🛠️ Allgemeine Befehle",
                value="`/help` - Zeigt diese Hilfe an\n"
                      "`/about` - Informationen über Bot & Entwickler\n"
                      "`/clear` - Löscht Nachrichten (1-100)\n"
                      "`/serverstats` - Detaillierte Server-Statistiken\n"
                      "`/memberinfo` - User-Informationen anzeigen\n"
                      "`/admin-setup` - Setup-Befehle für Admins\n"
                      "`/update` - Zeigt die neuesten Updates des Bots",
                inline=False
            )
            
            # 🔨 MODERATION
            embed.add_field(
                name="🔨 Moderation",
                value="`/ban` - Bannt einen User (per ID oder Mention)\n"
                      "`/massban` - Bannt mehrere User gleichzeitig (IDs)\n"
                      "`/kick` - Kickt einen User vom Server\n"
                      "`/unban` - Entbannt einen User (per ID)\n"
                      "`/mute` - Stummt einen User für bestimmte Zeit\n"
                      "`/unmute` - Entstummt einen User\n"
                      "`/warn` - Warnt einen User\n"
                      "`/warnings` - Zeigt alle Warnungen eines Users",
                inline=False
            )
            
            # 🐛 BUG SYSTEM
            embed.add_field(
                name="🐛 Bug System",
                value="`/bug-report` - Meldet einen Bug an die Entwickler\n"
                      "`/bug-list` - Zeigt aktuelle Bugs (nur Entwickler)",
                inline=False
            )
            
            # 💡 FEATURE SYSTEM
            embed.add_field(
                name="💡 Feature System",
                value="`/feature-request` - Meldet eine Feature-Anfrage an die Entwickler\n"
                      "`/feature-list` - Zeigt aktuelle Feature-Requests (nur Entwickler)",
                inline=False
            )
            
            # 🔗 LINK PROTECTION
            embed.add_field(
                name="🔗 Link Protection (Admin-Only)",
                value="`/disable-link` - Aktiviert/Deaktiviert Link-Schutz\n"
                      "`/link-channel-exempt` - Channel-Ausnahmen verwalten\n"
                      "`/link-user-exempt` - User-Ausnahmen verwalten\n"
                      "`/link-status` - Zeigt aktuellen Status & Ausnahmen",
                inline=False
            )
            
            # 🎮 LEVEL SYSTEM
            embed.add_field(
                name="🎮 Level System",
                value="`/setup-level` - Richtet das Level-System ein\n"
                      "`/level` - Zeigt dein aktuelles Level & XP\n"
                      "`/rank` - Zeigt Level eines anderen Users\n"
                      "`/leaderboard` - Top 10 Server-Rangliste\n"
                      "`/change-announcement` - Ändert Level-Up Channel\n"
                      "`/show-announcement` - Zeigt aktuellen Level-Up Channel",
                inline=False
            )
            
            # 🚫 CHANNEL MANAGEMENT
            embed.add_field(
                name="🚫 Channel Management (Level-System)",
                value="`/block-channel` - Blockiert einzelnen Channel für XP\n"
                      "`/unblock-channel` - Entblockiert einzelnen Channel\n"
                      "`/block-channels` - Blockiert mehrere Channels\n"
                      "`/unblock-channels` - Entblockiert mehrere Channels\n"
                      "`/block-all-except` - Blockiert alle außer bestimmte\n"
                      "`/list-blocked` - Zeigt alle blockierten Channels",
                inline=False
            )
            
            # 🎫 TICKET SYSTEM (User)
            embed.add_field(
                name="🎫 Ticket System (User-Commands)",
                value="`/close` - Schließt ein Ticket (nur in Ticket-Channels)\n"
                      "**Buttons:** Nutze das Panel für neue Tickets!",
                inline=False
            )
            
            # 🎫 TICKET MANAGEMENT (Admin)
            embed.add_field(
                name="🎫 Ticket Management (Admin-Only)",
                value="`/ticket-setup` - Erstellt ein Ticket-Panel mit Buttons\n"
                      "`/ticket-category-add` - Neue Custom-Kategorie erstellen\n"
                      "`/ticket-category-edit` - Kategorien bearbeiten\n"
                      "`/ticket-category-remove` - Kategorien löschen\n"
                      "`/ticket-category-list` - Alle Kategorien anzeigen\n"
                      "`/ticket-panel-refresh` - Panel nach Änderungen aktualisieren\n"
                      "`/ticket-settings` - Staff-Rollen, Log-Channel konfigurieren\n"
                      "`/ticket-config` - Aktuelle Konfiguration anzeigen",
                inline=False
            )
            
            # 🔧 TICKET UTILITIES (Admin)
            embed.add_field(
                name="🔧 Ticket Utilities (Admin-Only)",
                value="`/ticket-staff-remove` - Entfernt Staff-Rollen\n"
                      "`/ticket-panel-restore` - Panel-Views nach Neustart wiederherstellen\n"
                      "`/ticket-cleanup` - Ghost-Tickets aufräumen\n"
                      "`/ticket-debug-views` - Debug für persistente Views",
                inline=False
            )
            
            # 🔢 COUNTER GAME
            embed.add_field(
                name="🔢 Counter Game",
                value="`/setup-counter` - Richtet das Counter-Spiel ein\n"
                      "**Spielregeln:** Zählt von 1 aufwärts, kein User darf zweimal hintereinander!",
                inline=False
            )
            
            # 👋 WELCOME SYSTEM
            embed.add_field(
                name="👋 Welcome System",
                value="`/welcome_config` - Konfiguriert Willkommens-/Abschiedsnachrichten\n"
                      "**Platzhalter:** `{user}` `{server}` `{count}`",
                inline=False
            )
            
            # 💡 BERECHTIGUNGEN
            embed.add_field(
                name="💡 Wichtige Hinweise",
                value="**🔒 Admin-Commands:** Moderation, Level-Setup, Ticket-Management, Welcome-Config\n"
                      "**👥 User-Commands:** Level, Rank, Counter, Bug-Report\n"
                      "**🎫 Ticket-System:** Buttons im Panel nutzen (kein `/ticket` Command mehr!)\n"
                      "**📊 Info-Commands:** Help, About, Serverstats, Memberinfo\n\n"
                      "**Setup:** Nutze `/admin-setup` für detaillierte Anleitungen!",
                inline=False
            )
            
            # Footer
            embed.set_footer(
                text=f"Insgesamt {self._count_total_commands()} Commands verfügbar | Bot Version {BOT_CONFIG['bot_version']} ({BOT_CONFIG['state_version']})",
                icon_url=interaction.user.display_avatar.url
            )
            
            await interaction.response.send_message(embed=embed)
            logger.info(f"Help command used by {interaction.user.id} in guild {interaction.guild.id}")
            
        except Exception as e:
            logger.error(f"Error in help command: {e}")
            await interaction.response.send_message(
                "❌ Fehler beim Laden der Hilfe!",
                ephemeral=True
            )
    
    def _count_total_commands(self):
        """Zählt alle verfügbaren Commands"""
        return 49  # Unix(23) + Level(12) + Ticket(13) + Counter(1) = 49 Commands

    @app_commands.command(
        name="update",
        description="Zeige die neuesten Feuters des Bots"
    )
    async def update(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🔄 Neueste Updates",
            description="**Neueste Features des Bots:**",
            color=COLORS["green"],
            timestamp=get_timestamp()
        )
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.add_field(
            name="🔗 Link Protection",
            value="• Link-Schutz wurde hinzugefügt\n"
                  "• Link-Schutz kann nun deaktiviert/aktiviert werden\n"
                  "• Channel-Ausnahmen können hinzugefügt werden\n"
                  "• User-Ausnahmen können hinzugefügt werden\n"
                  "• Link-Schutz kann nun den aktuellen Status und Ausnahmen anzeigen\n"
                  "• Commands:\n" 
                  "`/disable-link [True/False]`\n"
                  "`/link-channel-exempt [Channel]`\n"
                  "`/link-user-exempt [User]`\n"
                  "`/link-status`",
            inline=False
        )
        embed.add_field(
            name="💡 Feature-request",
            value="• Feature-request wurde hinzugefügt\n"
                  "• Features die gewollt werden können nun gemeldet werden\n"
                  "• Commands:\n"
                  "`/feature-request [Feature]`",
            inline=False
        )
        embed.set_footer(
            text=f"Aktuelle Version: {BOT_CONFIG['bot_version']} ({BOT_CONFIG['state_version']})"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="about",
        description="Zeigt Informationen über die Entwickler und den Bot"
    )
    async def about(self, interaction: discord.Interaction):
        try:
            # Bot-Statistiken sammeln
            total_guilds = len(self.bot.guilds)
            total_users = sum(guild.member_count for guild in self.bot.guilds)
            total_channels = sum(len(guild.channels) for guild in self.bot.guilds)
            
            # Hauptembed
            embed = discord.Embed(
                title="🤖 Community Bot - About",
                description="**Ein professioneller Discord-Bot für Community-Management**\n\n"
                           "Entwickelt mit Leidenschaft und einer ordentlichen Portion Kaffee ☕",
                color=COLORS["green"],
                timestamp=get_timestamp()
            )
            
            # Bot-Avatar setzen
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)
            
            # Entwickler-Information
            embed.add_field(
                name="👨‍💻 Entwickler",
                value="**Flimando Development Team**\n"
                      "• **Lead Developer:** Mando\n"
                      "• **AI Assistant:** Staiy (Claude 3.5 Sonnet)\n"
                      "• **IDE:** Cursor\n"
                      "• **Website:** [flimando.com](https://flimando.com/)",
                inline=False
            )
            
            # Bot-Statistiken
            embed.add_field(
                name="📊 Bot-Statistiken",
                value=f"**Server:** {total_guilds:,}\n"
                      f"**Nutzer:** {total_users:,}\n"
                      f"**Channels:** {total_channels:,}\n"
                      f"**Ping:** {round(self.bot.latency * 1000)}ms",
                inline=True
            )
            
            # Technische Details
            embed.add_field(
                name="⚙️ Technologien",
                value="**Backend:** Python 3.13.4+\n"
                      "**Library:** discord.py 2.3.3\n"
                      "**Hosting:** [flimando.com](https://flimando.com/)\n",
                inline=True
            )
            
            # Features
            embed.add_field(
                name="🎯 Features",
                value="• **Moderation:** Ban, Kick, Mute, Warn\n"
                      "• **Level System:** XP & Leaderboards\n"
                      "• **Custom Ticket System:** Community-Kategorien & Buttons\n"
                      "• **Counter Game:** Zahlen-Spiel\n"
                      "• **Welcome System:** Begrüßungen\n"
                      "• **Server Stats:** Detaillierte Analysen",
                inline=False
            )
            
            # Kontakt & Links
            embed.add_field(
                name="🔗 Links & Kontakt",
                value=f"**Website:** [flimando.com](https://flimando.com/)\n"
                      f"**Version:** {BOT_CONFIG['bot_version']} ({BOT_CONFIG['state_version']})\n"
                      f"**Letzte Aktualisierung:** 08-07-2025 🚀",
                inline=False
            )
            
            # Footer
            embed.set_footer(
                text="Entwickelt mit ❤️ von Mando Development | Powered by Flimando Gamehosting",
                icon_url=interaction.user.display_avatar.url
            )
            
            await interaction.response.send_message(embed=embed)
            logger.info(f"About command used by {interaction.user.id} in guild {interaction.guild.id}")
            
        except Exception as e:
            logger.error(f"Error in about command: {e}")
            await interaction.response.send_message(
                "❌ Fehler beim Laden der About-Informationen!",
                ephemeral=True
            )

    @app_commands.command(
        name = "disable-link",
        description = "Deaktiviert/aktiviert den Link-Schutz"
    )
    @app_commands.describe(
        boolean = "True = aktivieren, False = deaktivieren"
    )
    @app_commands.default_permissions(administrator=True)
    async def disable_link(self, interaction: discord.Interaction, boolean: bool = None):
        if boolean is None:
            # Zeige aktuellen Status
            config = self._load_link_config()
            guild_id = str(interaction.guild.id)
            status = "aktiviert" if guild_id in config["enabled_guilds"] else "deaktiviert"
            
            embed = discord.Embed(
                title="🔗 Link-Schutz Status",
                description=f"**Aktueller Status:** {status}\n\n"
                           f"**Verwendung:** `/disable-link True/False`\n"
                           f"• `True` = Link-Schutz aktivieren\n"
                           f"• `False` = Link-Schutz deaktivieren",
                color=COLORS["blue"]
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
            
        config = self._load_link_config()
        guild_id = str(interaction.guild.id)
        
        if boolean:
            # Aktiviere Link-Schutz
            if guild_id not in config["enabled_guilds"]:
                config["enabled_guilds"].append(guild_id)
                
                # Initialisiere alle Listen falls sie nicht existieren
                if guild_id not in config["exempt_channels"]:
                    config["exempt_channels"][guild_id] = []
                if guild_id not in config["exempt_users"]:
                    config["exempt_users"][guild_id] = []
                if guild_id not in config["exempt_categories"]:
                    config["exempt_categories"][guild_id] = []
                
                self._save_link_config(config)
                
                embed = discord.Embed(
                    title="✅ Link-Schutz aktiviert!",
                    description="Links werden nun automatisch gelöscht.\n\n"
                               "**Ausnahmen:**\n"
                               "• Administratoren\n"
                               "• User mit `Nachrichten verwalten`\n"
                               "• Ausnahme-Channels (siehe `/link-channel-exempt`)\n"
                               "• Ausnahme-Kategorien (siehe `/link-category-exempt`)\n"
                               "• Ausnahme-User (siehe `/link-user-exempt`)",
                    color=COLORS["green"]
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                logger.info(f"Link protection enabled for guild {guild_id}")
            else:
                await interaction.response.send_message("Link-Schutz ist bereits aktiviert!", ephemeral=True)
        else:
            # Deaktiviere Link-Schutz
            if guild_id in config["enabled_guilds"]:
                config["enabled_guilds"].remove(guild_id)
                self._save_link_config(config)
                
                embed = discord.Embed(
                    title="❌ Link-Schutz deaktiviert!",
                    description="Links werden nicht mehr automatisch gelöscht.",
                    color=COLORS["red"]
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                logger.info(f"Link protection disabled for guild {guild_id}")
            else:
                await interaction.response.send_message("Link-Schutz ist bereits deaktiviert!", ephemeral=True)

    @app_commands.command(
        name="link-category-exempt",
        description="Fügt eine Kategorie als Ausnahme für den Link-Schutz hinzu oder entfernt ihn"
    )
    @app_commands.describe(
        category="Die Kategorie, der als Ausnahme hinzugefügt/entfernt werden soll",
        action="add = hinzufügen, remove = entfernen"
    )
    @app_commands.default_permissions(administrator=True)
    async def link_category_exempt(self, interaction: discord.Interaction, category: discord.CategoryChannel, action: str):
        if action.lower() not in ["add", "remove"]:
            await interaction.response.send_message("Aktion muss `add` oder `remove` sein!", ephemeral=True)
            return
        
        config = self._load_link_config()
        guild_id = str(interaction.guild.id)
        category_id = str(category.id)
        
        # Prüfe ob Link-Schutz aktiviert ist
        if guild_id not in config["enabled_guilds"]:
            await interaction.response.send_message("Link-Schutz ist nicht aktiviert! Nutze `/disable-link True`", ephemeral=True)
            return
        
        # Initialisiere Category-Liste falls nötig
        if guild_id not in config["exempt_categories"]:
            config["exempt_categories"][guild_id] = []
        
        if action.lower() == "add":
            if category_id not in config["exempt_categories"][guild_id]:
                config["exempt_categories"][guild_id].append(category_id)
                self._save_link_config(config)
                
                embed = discord.Embed(
                    title="✅ Kategorie-Ausnahme hinzugefügt!",
                    description=f"Kategorie {category.mention} ist nun vom Link-Schutz ausgenommen.",
                    color=COLORS["green"]
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                logger.info(f"Category {category_id} added to link protection exemptions for guild {guild_id}")
            else:
                await interaction.response.send_message(f"Kategorie {category.mention} ist bereits ausgenommen!", ephemeral=True)
        else:
            if category_id in config["exempt_categories"][guild_id]:
                config["exempt_categories"][guild_id].remove(category_id)
                self._save_link_config(config)
                
                embed = discord.Embed(
                    title="❌ Kategorie-Ausnahme entfernt!",
                    description=f"Kategorie {category.mention} ist nun wieder vom Link-Schutz betroffen.",
                    color=COLORS["red"]
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                logger.info(f"Category {category_id} removed from link protection exemptions for guild {guild_id}")
            else:
                await interaction.response.send_message(f"Kategorie {category.mention} ist nicht in den Ausnahmen!", ephemeral=True)
    @app_commands.command(
        name="link-channel-exempt",
        description="Fügt einen Channel als Ausnahme für den Link-Schutz hinzu oder entfernt ihn"
    )
    @app_commands.describe(
        channel="Der Channel, der als Ausnahme hinzugefügt/entfernt werden soll",
        action="add = hinzufügen, remove = entfernen"
    )
    @app_commands.default_permissions(administrator=True)
    async def link_channel_exempt(self, interaction: discord.Interaction, channel: discord.TextChannel, action: str):
        if action.lower() not in ["add", "remove"]:
            await interaction.response.send_message("Aktion muss `add` oder `remove` sein!", ephemeral=True)
            return
            
        config = self._load_link_config()
        guild_id = str(interaction.guild.id)
        channel_id = str(channel.id)
        
        # Prüfe ob Link-Schutz aktiviert ist
        if guild_id not in config["enabled_guilds"]:
            await interaction.response.send_message("Link-Schutz ist nicht aktiviert! Nutze `/disable-link True`", ephemeral=True)
            return
            
        # Initialisiere Channel-Liste falls nötig
        if guild_id not in config["exempt_channels"]:
            config["exempt_channels"][guild_id] = []
            
        if action.lower() == "add":
            if channel_id not in config["exempt_channels"][guild_id]:
                config["exempt_channels"][guild_id].append(channel_id)
                self._save_link_config(config)
                
                embed = discord.Embed(
                    title="✅ Channel-Ausnahme hinzugefügt!",
                    description=f"Channel {channel.mention} ist nun vom Link-Schutz ausgenommen.",
                    color=COLORS["green"]
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                logger.info(f"Channel {channel_id} added to link protection exemptions for guild {guild_id}")
            else:
                await interaction.response.send_message(f"Channel {channel.mention} ist bereits ausgenommen!", ephemeral=True)
        else:
            if channel_id in config["exempt_channels"][guild_id]:
                config["exempt_channels"][guild_id].remove(channel_id)
                self._save_link_config(config)
                
                embed = discord.Embed(
                    title="❌ Channel-Ausnahme entfernt!",
                    description=f"Channel {channel.mention} ist nun wieder vom Link-Schutz betroffen.",
                    color=COLORS["red"]
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                logger.info(f"Channel {channel_id} removed from link protection exemptions for guild {guild_id}")
            else:
                await interaction.response.send_message(f"Channel {channel.mention} ist nicht in den Ausnahmen!", ephemeral=True)

    @app_commands.command(
        name="link-user-exempt",
        description="Fügt einen User als Ausnahme für den Link-Schutz hinzu oder entfernt ihn"
    )
    @app_commands.describe(
        user="Der User, der als Ausnahme hinzugefügt/entfernt werden soll",
        action="add = hinzufügen, remove = entfernen"
    )
    @app_commands.default_permissions(administrator=True)
    async def link_user_exempt(self, interaction: discord.Interaction, user: discord.Member, action: str):
        if action.lower() not in ["add", "remove"]:
            await interaction.response.send_message("Aktion muss `add` oder `remove` sein!", ephemeral=True)
            return
            
        config = self._load_link_config()
        guild_id = str(interaction.guild.id)
        user_id = str(user.id)
        
        # Prüfe ob Link-Schutz aktiviert ist
        if guild_id not in config["enabled_guilds"]:
            await interaction.response.send_message("Link-Schutz ist nicht aktiviert! Nutze `/disable-link True`", ephemeral=True)
            return
            
        # Initialisiere User-Liste falls nötig
        if guild_id not in config["exempt_users"]:
            config["exempt_users"][guild_id] = []
            
        if action.lower() == "add":
            if user_id not in config["exempt_users"][guild_id]:
                config["exempt_users"][guild_id].append(user_id)
                self._save_link_config(config)
                
                embed = discord.Embed(
                    title="✅ User-Ausnahme hinzugefügt!",
                    description=f"User {user.mention} ist nun vom Link-Schutz ausgenommen.",
                    color=COLORS["green"]
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                logger.info(f"User {user_id} added to link protection exemptions for guild {guild_id}")
            else:
                await interaction.response.send_message(f"User {user.mention} ist bereits ausgenommen!", ephemeral=True)
        else:
            if user_id in config["exempt_users"][guild_id]:
                config["exempt_users"][guild_id].remove(user_id)
                self._save_link_config(config)
                
                embed = discord.Embed(
                    title="❌ User-Ausnahme entfernt!",
                    description=f"User {user.mention} ist nun wieder vom Link-Schutz betroffen.",
                    color=COLORS["red"]
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                logger.info(f"User {user_id} removed from link protection exemptions for guild {guild_id}")
            else:
                await interaction.response.send_message(f"User {user.mention} ist nicht in den Ausnahmen!", ephemeral=True)

    @app_commands.command(
        name="link-status",
        description="Zeigt den aktuellen Link-Schutz Status und alle Ausnahmen an"
    )
    @app_commands.default_permissions(administrator=True)
    async def link_status(self, interaction: discord.Interaction):
        config = self._load_link_config()
        guild_id = str(interaction.guild.id)
        
        if guild_id not in config["enabled_guilds"]:
            embed = discord.Embed(
                title="🔗 Link-Schutz Status",
                description="**Status:** ❌ Deaktiviert\n\nNutze `/disable-link True` um den Link-Schutz zu aktivieren.",
                color=COLORS["red"]
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
            
        exempt_channels = []
        exempt_users = []
        exempt_categories = []
        
        if guild_id in config["exempt_channels"]:
            for channel_id in config["exempt_channels"][guild_id]:
                channel = interaction.guild.get_channel(int(channel_id))
                if channel:
                    exempt_channels.append(channel.mention)
                    
        if guild_id in config["exempt_users"]:
            for user_id in config["exempt_users"][guild_id]:
                user = interaction.guild.get_member(int(user_id))
                if user:
                    exempt_users.append(user.mention)
        
        if guild_id in config["exempt_categories"]:
            for category_id in config["exempt_categories"][guild_id]:
                category = interaction.guild.get_channel(int(category_id))
                if category:
                    exempt_categories.append(category.mention)
                    
        embed = discord.Embed(
            title="🔗 Link-Schutz Status",
            description="**Status:** ✅ Aktiviert\n\nLinks werden automatisch gelöscht, außer von:",
            color=COLORS["green"]
        )
        
        # Automatische Ausnahmen
        embed.add_field(
            name="🔓 Automatische Ausnahmen",
            value="• Administratoren\n• User mit `Nachrichten verwalten`",
            inline=False
        )
        
        # Channel-Ausnahmen
        if exempt_channels:
            channels_text = "\n".join(exempt_channels[:10])
            if len(exempt_channels) > 10:
                channels_text += f"\n... und {len(exempt_channels) - 10} weitere"
            embed.add_field(
                name=f"📺 Ausnahme-Channels ({len(exempt_channels)})",
                value=channels_text,
                inline=False
            )
        else:
            embed.add_field(
                name="📺 Ausnahme-Channels",
                value="Keine",
                inline=False
            )
            
        # User-Ausnahmen
        if exempt_users:
            users_text = "\n".join(exempt_users[:10])
            if len(exempt_users) > 10:
                users_text += f"\n... und {len(exempt_users) - 10} weitere"
            embed.add_field(
                name=f"👥 Ausnahme-User ({len(exempt_users)})",
                value=users_text,
                inline=False
            )
        else:
            embed.add_field(
                name="👥 Ausnahme-User",
                value="Keine",
                inline=False
            )
        
        # Kategorie-Ausnahmen
        if exempt_categories:
            categories_text = "\n".join(exempt_categories[:10])
            if len(exempt_categories) > 10:
                categories_text += f"\n... und {len(exempt_categories) - 10} weitere"
            embed.add_field(
                name=f"📂 Ausnahme-Kategorien ({len(exempt_categories)})",
                value=categories_text,
                inline=False
            )
        else:
            embed.add_field(
                name="📂 Ausnahme-Kategorien",
                value="Keine",
                inline=False
            )
            
        embed.set_footer(text="Nutze /link-channel-exempt, /link-user-exempt und /link-category-exempt um Ausnahmen zu verwalten")
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
    @app_commands.command(
        name = "clear",
        description = "Löscht eine bestimmte Anzahl von Nachrichten"
    ) #Kann überall benutzt werden weil nicht extrem wichtig
    async def clear(self, interaction: discord.Interaction, amount: int):
        # Defer the response to avoid timeout
        await interaction.response.defer(ephemeral=True)
        
        # Warte kurz vor dem Purge
        await asyncio.sleep(1)
        
        try:
            # Führe Purge aus
            deleted = await interaction.channel.purge(limit=amount)
        
            # Warte nach dem Purge
            await asyncio.sleep(1)
            
            # Sende Bestätigung
            await interaction.followup.send(
                f"Die letzten {len(deleted)} Nachrichten wurden gelöscht",
                ephemeral=True
            )
            logger.info(f"Cleared {len(deleted)} messages in {interaction.channel.id} by {interaction.user.id}")
        except discord.Forbidden:
            await interaction.followup.send("❌ Ich habe keine Berechtigung, Nachrichten zu löschen!", ephemeral=True)
        except discord.HTTPException as e:
            logger.error(f"HTTP-Fehler beim Löschen von Nachrichten: {e}")
            await interaction.followup.send("❌ Fehler beim Löschen der Nachrichten!", ephemeral=True)
        except Exception as e:
            logger.error(f"Unerwarteter Fehler beim Löschen von Nachrichten: {e}")
            await interaction.followup.send("❌ Ein unerwarteter Fehler ist aufgetreten!", ephemeral=True)

    @app_commands.command(
        name = "bug-report",
        description = "Meldet einen Bug"
    )
    @app_commands.describe(
        bug = "Bitte beschreibe den Bug und wie wir ihn reproduzieren können. Wir werden uns darum kümmern"
    )
    async def bug_report(self, interaction: discord.Interaction, bug: str):
        if interaction.user.id in BLACKLIST["users"]:
            await interaction.response.send_message("Du bist in der Blacklist und kannst keine Bugs melden!", ephemeral=True)
            return
        if interaction.guild.id in BLACKLIST["guilds"]:
            await interaction.response.send_message("Dieser Server ist in der Blacklist und du kannst keine Bugs melden!", ephemeral=True)
            return
        
        
        embed = discord.Embed(
            title = "🐛 Bug Report",
            description = f"**Gemeldet von:** {interaction.user.mention}\n**Bug:** {bug}",
            color = COLORS["red"],
            timestamp = get_timestamp()
        )
        embed.set_footer(text=f"Danke für deine Hilfe! Wir werden uns darum kümmern.")
        await interaction.response.send_message(embed=embed, ephemeral=True)
        logger.info(f"Bug report used by {interaction.user.id} in guild {interaction.guild.id}")
        try:
            if os.path.exists("bug_reports.txt"):
                with open("bug_reports.txt", "a") as f:
                    f.write(f"Name: {interaction.user.name} - ID: {interaction.user.id} - Guild: {interaction.guild.name} - ID: {interaction.guild.id} - Bug: {bug}\n")
            else:
                with open("bug_reports.txt", "w") as f:
                    f.write("Bug Reports:\n")
                    f.write(f"Name: {interaction.user.name} - ID: {interaction.user.id} - Guild: {interaction.guild.name} - ID: {interaction.guild.id} - Bug: {bug}\n")
        except Exception as e:
            logger.error(f"Error writing bug report: {e}")
            await interaction.followup.send("❌ Fehler beim Melden des Bugs!", ephemeral=True)
    @app_commands.command(
        name = "bug-list",
        description = "Liste der aktuellen Bugs"
    )
    async def bug_list(self, interaction: discord.Interaction):
        if interaction.user.id not in DEVELOPER_IDS:
            await interaction.response.send_message("Du bist kein Entwickler und kannst keine Bugs sehen!", ephemeral=True)
            return
        if os.path.exists("bug_reports.txt"):
            with open("bug_reports.txt", "r") as f:
                bug_list = f.read()
            embed = discord.Embed(
                title = "🐛 Aktuelle Bugs",
                description = bug_list,
                color = COLORS["red"],
                timestamp = get_timestamp()
            )
            for line in bug_list.split("\n"):
                if line.strip() and "Name:" in line:
                    try:
                        name_part = line.split("Name:")[1].split(" - ")[0]
                        embed.add_field(name="Name", value=name_part, inline=False)
                    except (IndexError, ValueError):
                        # Skip malformed lines
                        continue
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message("Es gibt keine Bugs!", ephemeral=True)

    @app_commands.command(
        name = "feature-request",
        description = "Meldet eine Feature-Anfrage"
    )
    @app_commands.describe(
        feature = "Bitte beschreibe das gewünschte Feature und warum es nützlich wäre. Wir werden es prüfen!"
    )
    async def feature_request(self, interaction: discord.Interaction, feature: str):
        if interaction.user.id in BLACKLIST["users"]:
            await interaction.response.send_message("Du bist in der Blacklist und kannst keine Features anfragen!", ephemeral=True)
            return
        if interaction.guild.id in BLACKLIST["guilds"]:
            await interaction.response.send_message("Dieser Server ist in der Blacklist und du kannst keine Features anfragen!", ephemeral=True)
            return
        
        embed = discord.Embed(
            title = "💡 Feature Request",
            description = f"**Angefordert von:** {interaction.user.mention}\n**Feature:** {feature}",
            color = COLORS["green"],
            timestamp = get_timestamp()
        )
        embed.set_footer(text=f"Danke für deine Idee! Wir werden sie prüfen.")
        await interaction.response.send_message(embed=embed, ephemeral=True)
        logger.info(f"Feature request used by {interaction.user.id} in guild {interaction.guild.id}")
        try:
            if os.path.exists("feature_requests.txt"):
                with open("feature_requests.txt", "a") as f:
                    f.write(f"Name: {interaction.user.name} - ID: {interaction.user.id} - Guild: {interaction.guild.name} - ID: {interaction.guild.id} - Feature: {feature}\n")
            else:
                with open("feature_requests.txt", "w") as f:
                    f.write("Feature Requests:\n")
                    f.write(f"Name: {interaction.user.name} - ID: {interaction.user.id} - Guild: {interaction.guild.name} - ID: {interaction.guild.id} - Feature: {feature}\n")
        except Exception as e:
            logger.error(f"Error writing feature request: {e}")
            await interaction.followup.send("❌ Fehler beim Melden des Features!", ephemeral=True)

    @app_commands.command(
        name = "feature-list",
        description = "Liste der aktuellen Feature-Requests"
    )
    async def feature_list(self, interaction: discord.Interaction):
        if interaction.user.id not in DEVELOPER_IDS:
            await interaction.response.send_message("Du bist kein Entwickler und kannst keine Feature-Requests sehen!", ephemeral=True)
            return
        if os.path.exists("feature_requests.txt"):
            with open("feature_requests.txt", "r") as f:
                feature_list = f.read()
            embed = discord.Embed(
                title = "💡 Aktuelle Feature-Requests",
                description = feature_list,
                color = COLORS["green"],
                timestamp = get_timestamp()
            )
            for line in feature_list.split("\n"):
                if line.strip() and line.startswith("Name:"):
                    try:
                        name_part = line.split("Name:")[1].split(" - ")[0]
                        embed.add_field(name="Name", value=name_part, inline=False)
                    except (IndexError, ValueError):
                        # Skip malformed lines
                        continue
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message("Es gibt keine Feature-Requests!", ephemeral=True)


    @app_commands.command(
        name = "ban",
        description = "Bannt einen Nutzer vom Server (per Mention oder ID)"
    )
    @app_commands.describe(
        user_id="Die ID des zu bannenden Nutzers (falls kein Nutzer ausgewählt)",
        user="Der zu bannende Nutzer",
        grund="Der Grund für den Bann",
        löschen_tage="Anzahl der Tage, für die Nachrichten gelöscht werden sollen (0-7)"
    )
    @app_commands.default_permissions(ban_members=True)
    async def ban(self, interaction: discord.Interaction, user: discord.User = None, user_id: str = None, grund: str = "Kein Grund angegeben", löschen_tage: int = 0):
        # Überprüfe ob löschen_tage im gültigen Bereich ist
        if löschen_tage < 0 or löschen_tage > 7:
            await interaction.response.send_message("Die Anzahl der Tage muss zwischen 0 und 7 liegen!", ephemeral=True)
            return
            
        # Überprüfe ob User ODER user_id angegeben wurde
        if user is None and user_id is None:
            await interaction.response.send_message("Du musst entweder einen Nutzer auswählen oder eine Nutzer-ID angeben!", ephemeral=True)
            return
            
        # Wenn user_id angegeben wurde, versuche den Nutzer zu finden
        if user_id is not None:
            try:
                user_id_int = int(user_id)
                user = await self.bot.fetch_user(user_id_int)
            except (ValueError, discord.NotFound):
                await interaction.response.send_message(f"Konnte keinen Nutzer mit der ID {user_id} finden!", ephemeral=True)
                return
                
        # Überprüfe ob User der Bot selbst ist
        if user.id == self.bot.user.id:
            await interaction.response.send_message("Ich kann mich nicht selbst bannen! 😢", ephemeral=True)
            return
            
        # Überprüfe ob User der Server-Owner ist
        if user.id == interaction.guild.owner_id:
            await interaction.response.send_message("Ich kann den Server-Eigentümer nicht bannen!", ephemeral=True)
            return
            
        # Überprüfe ob User bereits gebannt ist
        try:
            ban_entry = await interaction.guild.fetch_ban(user)
            await interaction.response.send_message(f"Der Nutzer {user.name} (ID: {user.id}) ist bereits gebannt!", ephemeral=True)
            return
        except discord.NotFound:
            pass
            
        # Erstelle ein Embed für die Ban-Bestätigung
        ban_embed = discord.Embed(
            title="🔨 Ban ausgeführt",
            description=f"**Nutzer:** {user.name} (ID: {user.id})\n**Grund:** {grund}",
            color=COLORS["red"],
            timestamp=get_timestamp()
        )
        ban_embed.set_thumbnail(url=user.display_avatar.url)
        ban_embed.add_field(name="Gebannt von", value=interaction.user.mention, inline=False)
        
        # Ban ausführen
        try:
            await interaction.guild.ban(user, reason=f"Gebannt von {interaction.user.name}: {grund}", delete_message_days=löschen_tage)
            await interaction.response.send_message(embed=ban_embed)
            
            # Versuche dem Nutzer eine DM zu senden
            try:
                dm_embed = discord.Embed(
                    title=f"Du wurdest von {interaction.guild.name} gebannt",
                    description=f"**Grund:** {grund}",
                    color=COLORS["red"],
                    timestamp=get_timestamp()
                )
                await user.send(embed=dm_embed)
            except discord.Forbidden:
                # Nutzer hat DMs deaktiviert oder blockiert den Bot
                pass
                
        except discord.Forbidden:
            await interaction.response.send_message("Ich habe nicht die Berechtigung, diesen Nutzer zu bannen!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Fehler beim Bannen: {str(e)}", ephemeral=True)

    @app_commands.command(
        name = "massban",
        description = "Bannt mehrere Nutzer gleichzeitig (per IDs)"
    )
    @app_commands.describe(
        user_ids="Durch Komma getrennte Liste von Nutzer-IDs (z.B. 123456789,987654321)",
        grund="Der Grund für den Bann",
        löschen_tage="Anzahl der Tage, für die Nachrichten gelöscht werden sollen (0-7)"
    )
    @app_commands.default_permissions(administrator=True)
    async def massban(self, interaction: discord.Interaction, user_ids: str, grund: str = "Kein Grund angegeben", löschen_tage: int = 0):
        # Überprüfe Berechtigungen (nur für Admins)
        if not interaction.user.guild_permissions.administrator and not any(role.id == DISCORD_IDS["admin_role"] for role in interaction.user.roles):
            await interaction.response.send_message("Du benötigst Administrator-Rechte für den Massenban!", ephemeral=True)
            return
            
        # Überprüfe ob löschen_tage im gültigen Bereich ist
        if löschen_tage < 0 or löschen_tage > 7:
            await interaction.response.send_message("Die Anzahl der Tage muss zwischen 0 und 7 liegen!", ephemeral=True)
            return
            
        # Überprüfe, ob überhaupt IDs angegeben wurden
        if not user_ids or user_ids.strip() == "":
            await interaction.response.send_message("Du musst mindestens eine Nutzer-ID angeben!", ephemeral=True)
            return
            
        # Defer response für längere Verarbeitung
        await interaction.response.defer(ephemeral=False)
        
        # Splitte die IDs und entferne Leerzeichen
        id_list = [id.strip() for id in user_ids.split(",")]
        
        # Statistik-Tracking
        erfolgreiche_bans = []
        fehlgeschlagene_bans = []
        bereits_gebannt = []
        nicht_gefunden = []
        
        # Progress-Embed
        progress_embed = discord.Embed(
            title="⏳ Massenban wird ausgeführt...",
            description=f"Verarbeite {len(id_list)} Nutzer-IDs...",
            color=COLORS["orange"],
            timestamp=get_timestamp()
        )
        progress_message = await interaction.followup.send(embed=progress_embed)
        
        # Verarbeite jeden Nutzer
        for user_id in id_list:
            try:
                # Versuche die ID zu konvertieren
                user_id_int = int(user_id)
                
                # Versuche den Nutzer zu finden
                try:
                    user = await self.bot.fetch_user(user_id_int)
                    
                    # Überprüfe auf spezielle Fälle
                    if user.id == self.bot.user.id:
                        fehlgeschlagene_bans.append(f"{user.name} (ID: {user.id}) - Kann Bot nicht bannen")
                        continue
                        
                    if user.id == interaction.guild.owner_id:
                        fehlgeschlagene_bans.append(f"{user.name} (ID: {user.id}) - Kann Server-Owner nicht bannen")
                        continue
                    
                    # Überprüfe ob User bereits gebannt ist
                    try:
                        ban_entry = await interaction.guild.fetch_ban(user)
                        bereits_gebannt.append(f"{user.name} (ID: {user.id})")
                        continue
                    except discord.NotFound:
                        pass
                    
                    # Ban ausführen
                    await interaction.guild.ban(user, reason=f"Massenban von {interaction.user.name}: {grund}", delete_message_days=löschen_tage)
                    erfolgreiche_bans.append(f"{user.name} (ID: {user.id})")
                    
                    # Versuche dem Nutzer eine DM zu senden
                    try:
                        dm_embed = discord.Embed(
                            title=f"Du wurdest von {interaction.guild.name} gebannt",
                            description=f"**Grund:** {grund}",
                            color=COLORS["red"],
                            timestamp=get_timestamp()
                        )
                        await user.send(embed=dm_embed)
                    except:
                        pass
                    
                    # Kurze Pause um Rate Limits zu vermeiden
                    await asyncio.sleep(0.5)
                    
                except discord.NotFound:
                    nicht_gefunden.append(user_id)
                except Exception as e:
                    fehlgeschlagene_bans.append(f"ID: {user_id} - Fehler: {str(e)}")
                    
            except ValueError:
                nicht_gefunden.append(user_id)
                
        # Erstelle ein Embed für die Zusammenfassung
        result_embed = discord.Embed(
            title="🔨 Massenban abgeschlossen",
            description=f"**Grund:** {grund}\n**Durchgeführt von:** {interaction.user.mention}",
            color=COLORS["green"],
            timestamp=get_timestamp()
        )
        
        # Füge Statistiken hinzu
        result_embed.add_field(
            name=f"✅ Erfolgreich gebannt ({len(erfolgreiche_bans)})",
            value="\n".join(erfolgreiche_bans[:10]) + (f"\n... und {len(erfolgreiche_bans) - 10} weitere" if len(erfolgreiche_bans) > 10 else "") if erfolgreiche_bans else "Keine",
            inline=False
        )
        
        if bereits_gebannt:
            result_embed.add_field(
                name=f"⚠️ Bereits gebannt ({len(bereits_gebannt)})",
                value="\n".join(bereits_gebannt[:5]) + (f"\n... und {len(bereits_gebannt) - 5} weitere" if len(bereits_gebannt) > 5 else ""),
                inline=False
            )
            
        if nicht_gefunden:
            result_embed.add_field(
                name=f"❓ Nicht gefunden ({len(nicht_gefunden)})",
                value="\n".join(nicht_gefunden[:5]) + (f"\n... und {len(nicht_gefunden) - 5} weitere" if len(nicht_gefunden) > 5 else ""),
                inline=False
            )
            
        if fehlgeschlagene_bans:
            result_embed.add_field(
                name=f"❌ Fehlgeschlagen ({len(fehlgeschlagene_bans)})",
                value="\n".join(fehlgeschlagene_bans[:5]) + (f"\n... und {len(fehlgeschlagene_bans) - 5} weitere" if len(fehlgeschlagene_bans) > 5 else ""),
                inline=False
            )
            
        # Sende das finale Embed
        await progress_message.edit(embed=result_embed)
    @app_commands.command(
        name = "kick",
        description = "Kickt einen Nutzer vom Server (per Mention oder ID)"
    )
    @app_commands.describe(
        user_id="Die ID des zu kicken Nutzers (falls kein Nutzer ausgewählt)",
        user="Der zu kicken Nutzer",
        grund="Der Grund für den Kick",
    )
    @app_commands.default_permissions(kick_members=True)
    async def kick(self, interaction: discord.Interaction, user: discord.User = None, user_id: str = None, grund: str = "Kein Grund angegeben"):
        # Überprüfe ob User ODER user_id angegeben wurde
        if user is None and user_id is None:
            await interaction.response.send_message("Du musst entweder einen Nutzer auswählen oder eine Nutzer-ID angeben!", ephemeral=True)
            return

        # Wenn user_id angegeben wurde, versuche den Nutzer zu finden
        if user_id is not None:
            try:
                user_id_int = int(user_id)
                user = await self.bot.fetch_user(user_id_int)
            except (ValueError, discord.NotFound):
                await interaction.response.send_message(f"Konnte keinen Nutzer mit der ID {user_id} finden!", ephemeral=True)
                return
        await interaction.guild.kick(user, reason=f"Kicked von {interaction.user.name}: {grund}")
        await interaction.response.send_message(f"Der Nutzer {user.name} wurde erfolgreich gekickt!", ephemeral=True)
    @app_commands.command(
        name = "unban",
        description = "Entbannt einen Nutzer vom Server (per Mention oder ID)"
    )
    @app_commands.describe(
        user_id="Die ID des zu entbannenden Nutzers (falls kein Nutzer ausgewählt)",
        user="Der zu entbannende Nutzer",
        grund="Der Grund für die Entbanntung",
    )
    @app_commands.default_permissions(ban_members=True)
    async def unban(self, interaction: discord.Interaction, user: discord.User = None, user_id: str = None, grund: str = "Kein Grund angegeben"):
        # Überprüfe ob User ODER user_id angegeben wurde
        if user is None and user_id is None:
            await interaction.response.send_message("Du musst entweder einen Nutzer auswählen oder eine Nutzer-ID angeben!", ephemeral=True)
            return
            
        # Wenn user_id angegeben wurde, versuche den Nutzer zu finden
        if user_id is not None:
            try:
                user_id_int = int(user_id)
                user = await self.bot.fetch_user(user_id_int)
            except (ValueError, discord.NotFound):
                await interaction.response.send_message(f"Konnte keinen Nutzer mit der ID {user_id} finden!", ephemeral=True)
                return
                
        await interaction.guild.unban(user, reason=f"Entbannt von {interaction.user.name}: {grund}")
        await interaction.response.send_message(f"Der Nutzer {user.name} wurde erfolgreich entbannt!", ephemeral=True)
    @app_commands.command(
        name = "mute",
        description = "Stummt einen Nutzer für eine bestimmte Zeit (per Mention oder ID)"
    )
    @app_commands.describe(
        user_id="Die ID des zu stummsetzenden Nutzers (falls kein Nutzer ausgewählt)",
        user="Der zu stummsetzende Nutzer",
        time="Die Zeit, für die der Nutzer stumm geschaltet werden soll (in Sekunden)",
        grund="Der Grund für die Stummsetzung",
    )
    @app_commands.default_permissions(administrator=True)
    async def mute(self, interaction: discord.Interaction, user: discord.User = None, user_id: str = None, time: int = 0, grund: str = "Kein Grund angegeben"):
        # Überprüfe ob User ODER user_id angegeben wurde
        if user is None and user_id is None:
            await interaction.response.send_message("Du musst entweder einen Nutzer auswählen oder eine Nutzer-ID angeben!", ephemeral=True)
            return
        if time <= 0:
            await interaction.response.send_message("Die Zeit muss größer als 0 sein!", ephemeral=True)
            return
            
        # Wenn user_id angegeben wurde, versuche den Nutzer zu finden
        if user_id is not None:
            try:
                user_id_int = int(user_id)
                user = interaction.guild.get_member(user_id_int)
                if not user:
                    await interaction.response.send_message(f"Konnte keinen Nutzer mit der ID {user_id} auf diesem Server finden!", ephemeral=True)
                    return
            except ValueError:
                await interaction.response.send_message(f"Ungültige Nutzer-ID: {user_id}!", ephemeral=True)
                return
                
        await user.timeout(discord.utils.utcnow() + timedelta(seconds=time), reason=f"Stumm geschaltet von {interaction.user.name}: {grund}")
        await interaction.response.send_message(f"Der Nutzer {user.name} wurde erfolgreich für {time} Sekunden stumm geschaltet!", ephemeral=True)
    @app_commands.command(
        name = "unmute",
        description = "Entstummsetzt einen Nutzer (per Mention oder ID)"
    )
    @app_commands.describe(
        user_id="Die ID des zu entstummsetzenden Nutzers (falls kein Nutzer ausgewählt)",
        user="Der zu entstummsetzende Nutzer",
    )
    @app_commands.default_permissions(mute_members=True)
    async def unmute(self, interaction: discord.Interaction, user: discord.User = None, user_id: str = None):
        # Überprüfe ob User ODER user_id angegeben wurde
        if user is None and user_id is None:
            await interaction.response.send_message("Du musst entweder einen Nutzer auswählen oder eine Nutzer-ID angeben!", ephemeral=True)
            return
            
        # Wenn user_id angegeben wurde, versuche den Nutzer zu finden
        if user_id is not None:
            try:
                user_id_int = int(user_id)
                user = interaction.guild.get_member(user_id_int)
                if not user:
                    await interaction.response.send_message(f"Konnte keinen Nutzer mit der ID {user_id} auf diesem Server finden!", ephemeral=True)
                    return
            except ValueError:
                await interaction.response.send_message(f"Ungültige Nutzer-ID: {user_id}!", ephemeral=True)
                return
                
        await user.timeout(None, reason=f"Entstummt von {interaction.user.name}")
        await interaction.response.send_message(f"Der Nutzer {user.name} wurde erfolgreich entstummt!", ephemeral=True)
    @app_commands.command(
        name = "warn",
        description = "Warnt einen Nutzer (per Mention oder ID)"
    )
    @app_commands.describe(
        user_id="Die ID des zu warnenden Nutzers (falls kein Nutzer ausgewählt)",
        user="Der zu warnende Nutzer", 
        grund="Der Grund für die Warnung"
    )
    @app_commands.default_permissions(administrator=True)
    async def warn(self, interaction: discord.Interaction, user: discord.User = None, user_id: str = None, grund: str = "Kein Grund angegeben"):
        # Überprüfe ob User ODER user_id angegeben wurde
        if user is None and user_id is None:
            await interaction.response.send_message("Du musst entweder einen Nutzer auswählen oder eine Nutzer-ID angeben!", ephemeral=True)
            return
            
        # Wenn user_id angegeben wurde, versuche den Nutzer zu finden
        if user_id is not None:
            try:
                user_id_int = int(user_id)
                user = await self.bot.fetch_user(user_id_int)
            except (ValueError, discord.NotFound):
                await interaction.response.send_message(f"Konnte keinen Nutzer mit der ID {user_id} finden!", ephemeral=True)
                return
                
        add_warning(str(user.id), str(interaction.guild.id), grund)
        await interaction.response.send_message(f"Der Nutzer {user.name} wurde erfolgreich gewarnt!", ephemeral=True)
    @app_commands.command(
        name = "warnings",
        description = "Zeigt alle Warnungen eines Nutzers an (per Mention oder ID)"
    )
    @app_commands.describe(
        user_id="Die ID des Nutzers, dessen Warnungen angezeigt werden sollen (falls kein Nutzer ausgewählt)",
        user="Der Nutzer, dessen Warnungen angezeigt werden sollen",
    )
    @app_commands.default_permissions(administrator=True)
    async def warnings(self, interaction: discord.Interaction, user: discord.User = None, user_id: str = None):
        # Überprüfe ob User ODER user_id angegeben wurde
        if user is None and user_id is None:
            await interaction.response.send_message("Du musst entweder einen Nutzer auswählen oder eine Nutzer-ID angeben!", ephemeral=True)
            return
            
        # Wenn user_id angegeben wurde, versuche den Nutzer zu finden
        if user_id is not None:
            try:
                user_id_int = int(user_id)
                user = await self.bot.fetch_user(user_id_int)
            except (ValueError, discord.NotFound):
                await interaction.response.send_message(f"Konnte keinen Nutzer mit der ID {user_id} finden!", ephemeral=True)
                return
                
        warnings = get_warnings(str(user.id), str(interaction.guild.id))
        if not warnings:
            await interaction.response.send_message(f"Der Nutzer {user.name} hat keine Warnungen!", ephemeral=True)
            return
        embed = discord.Embed(title=f"Warnungen für {user.name}", color=COLORS["red"], timestamp=get_timestamp())
        for warning in warnings:
            embed.add_field(name="Warnung", value=f"Grund: {warning['reason']}\nZeit: {warning['timestamp']}", inline=False)
        await interaction.response.send_message(embed=embed)
    @app_commands.command(
        name="welcome_config",
        description="Konfiguriere die Willkommens- und Abschiedsnachrichten"
    )
    @app_commands.describe(
        channel="Der Channel für die Nachrichten",
        welcome_msg="Die Willkommensnachricht (nutze {user} für Mention, {server} für Servername, {count} für Mitgliederzahl)",
        leave_msg="Die Abschiedsnachricht (nutze {user} für Username, {server} für Servername, {count} für Mitgliederzahl)"
    )
    @app_commands.default_permissions(administrator=True)
    async def welcome_config(self, interaction: discord.Interaction, channel: discord.TextChannel, 
                           welcome_msg: str = None, leave_msg: str = None):
        # Speichere Konfiguration
        setup_welcome_system(str(interaction.guild.id))
        set_welcome_channel(str(interaction.guild.id), str(channel.id))
        
        if welcome_msg:
            set_welcome_message(str(interaction.guild.id), welcome_msg)
        if leave_msg:
            set_leave_message(str(interaction.guild.id), leave_msg)

        await interaction.response.send_message(
            f"✅ Welcome-System wurde konfiguriert!\nChannel: {channel.mention}", 
            ephemeral=True
        )

    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Event wird ausgelöst wenn ein neuer User dem Server beitritt"""
        try:
            # Prüfe ob System aktiviert ist
            if not is_welcome_system_enabled(str(member.guild.id)):
                return

            # Get custom channel and message
            channel_id = get_welcome_channel(str(member.guild.id))
            if not channel_id:
                return
                
            channel = member.guild.get_channel(int(channel_id))
            if not channel:
                return

            # Get custom message or use default
            msg = get_welcome_message(str(member.guild.id))
            if not msg:
                msg = "Willkommen {user} auf {server}! Du bist unser {count}. Mitglied!"
                
            msg = msg.replace("{user}", member.mention)\
                    .replace("{server}", member.guild.name)\
                    .replace("{count}", str(len(member.guild.members)))

            # Welcome Embed erstellen
            embed = discord.Embed(
                title="👋 Willkommen!",
                description=msg,
                color=COLORS["green"],
                timestamp=get_timestamp()
            )
            
            if member.avatar:
                embed.set_thumbnail(url=member.avatar.url)
                
            if member.guild.icon:
                embed.set_footer(text=member.guild.name, icon_url=member.guild.icon.url)

            await channel.send(embed=embed)
        except Exception as e:
            print(f"Fehler im Welcome-System: {e}")

    @commands.Cog.listener() 
    async def on_member_remove(self, member):
        """Event wird ausgelöst wenn ein User den Server verlässt"""
        try:
            # Prüfe ob System aktiviert ist
            if not is_welcome_system_enabled(str(member.guild.id)):
                return

            # Get custom channel and message
            channel_id = get_welcome_channel(str(member.guild.id))
            if not channel_id:
                return
                
            channel = member.guild.get_channel(int(channel_id))
            if not channel:
                return

            # Get custom message or use default
            msg = get_leave_message(str(member.guild.id))
            if not msg:
                msg = "Auf Wiedersehen {user}! Wir werden dich vermissen..."
                
            msg = msg.replace("{user}", member.name)\
                    .replace("{server}", member.guild.name)\
                    .replace("{count}", str(len(member.guild.members)))

            # Leave Embed erstellen
            embed = discord.Embed(
                title="👋 Auf Wiedersehen!",
                description=msg,
                color=COLORS["red"], 
                timestamp=get_timestamp()
            )
            
            if member.avatar:
                embed.set_thumbnail(url=member.avatar.url)
                
            if member.guild.icon:
                embed.set_footer(text=member.guild.name, icon_url=member.guild.icon.url)

            await channel.send(embed=embed)
        except Exception as e:
            print(f"Fehler im Leave-System: {e}")

    @app_commands.command(
        name="serverstats",
        description="Zeigt detaillierte Statistiken über den Server an"
    )
    async def serverstats(self, interaction: discord.Interaction):
        """Zeigt umfassende Server-Statistiken an"""
        try:
            guild = interaction.guild
            
            # Member-Statistiken sammeln
            total_members = guild.member_count
            bots = sum(1 for member in guild.members if member.bot)
            humans = total_members - bots
            
            # Online-Status sammeln (nur für gecachte Member)
            online = sum(1 for member in guild.members if member.status == discord.Status.online and not member.bot)
            idle = sum(1 for member in guild.members if member.status == discord.Status.idle and not member.bot)
            dnd = sum(1 for member in guild.members if member.status == discord.Status.dnd and not member.bot)
            offline = sum(1 for member in guild.members if member.status == discord.Status.offline and not member.bot)
            
            # Channel-Statistiken sammeln
            text_channels = len(guild.text_channels)
            voice_channels = len(guild.voice_channels)
            categories = len(guild.categories)
            stage_channels = len(guild.stage_channels)
            forum_channels = len([c for c in guild.channels if isinstance(c, discord.ForumChannel)])
            
            # Server-Boost-Infos
            boost_count = guild.premium_subscription_count or 0
            boost_level = guild.premium_tier
            boosters = len(guild.premium_subscribers)
            
            # Rollen-Info
            role_count = len(guild.roles) - 1  # @everyone ausschließen
            
            # Verification Level
            verification_levels = {
                discord.VerificationLevel.none: "Keine",
                discord.VerificationLevel.low: "Niedrig", 
                discord.VerificationLevel.medium: "Mittel",
                discord.VerificationLevel.high: "Hoch",
                discord.VerificationLevel.highest: "Höchste"
            }
            verification = verification_levels.get(guild.verification_level, "Unbekannt")
            
            # Server-Features
            feature_translations = {
                "COMMUNITY": "Community-Server",
                "PARTNERED": "Discord-Partner",
                "VERIFIED": "Verifiziert",
                "VANITY_URL": "Vanity-URL",
                "BANNER": "Server-Banner",
                "ANIMATED_ICON": "Animiertes Icon",
                "INVITE_SPLASH": "Invite-Splash",
                "VIP_REGIONS": "VIP-Regionen",
                "WELCOME_SCREEN_ENABLED": "Willkommensbildschirm",
                "MEMBER_VERIFICATION_GATE_ENABLED": "Mitgliederverifizierung",
                "PREVIEW_ENABLED": "Server-Vorschau",
                "TICKETED_EVENTS_ENABLED": "Ticketing-Events",
                "MONETIZATION_ENABLED": "Monetarisierung",
                "MORE_STICKERS": "Mehr Sticker",
                "NEWS": "Ankündigungen",
                "THREADS_ENABLED": "Threads aktiviert",
                "PRIVATE_THREADS": "Private Threads"
            }
            
            features = [feature_translations.get(f, f) for f in guild.features]
            
            # Hauptembed erstellen
            embed = discord.Embed(
                title=f"📊 Server-Statistiken für {guild.name}",
                color=COLORS["blue"],
                timestamp=get_timestamp()
            )
            
            # Server-Icon setzen
            if guild.icon:
                embed.set_thumbnail(url=guild.icon.url)
            
            # Server-Banner setzen
            if guild.banner:
                embed.set_image(url=guild.banner.url)
            
            # Grundlegende Server-Infos
            embed.add_field(
                name="🏠 Server-Informationen",
                value=f"**Name:** {guild.name}\n"
                      f"**ID:** {guild.id}\n"
                      f"**Owner:** {guild.owner.mention if guild.owner else 'Unbekannt'}\n"
                      f"**Erstellt:** <t:{int(guild.created_at.timestamp())}:D>\n"
                      f"**Verifizierung:** {verification}",
                inline=False
            )
            
            # Member-Statistiken
            embed.add_field(
                name="👥 Mitglieder-Statistiken",
                value=f"**Gesamt:** {total_members:,}\n"
                      f"**Menschen:** {humans:,}\n"
                      f"**Bots:** {bots:,}\n"
                      f"**Online:** {online:,}\n"
                      f"**Idle:** {idle:,}\n"
                      f"**Beschäftigt:** {dnd:,}\n"
                      f"**Offline:** {offline:,}",
                inline=True
            )
            
            # Channel-Statistiken
            total_channels = text_channels + voice_channels + categories + stage_channels + forum_channels
            embed.add_field(
                name="📺 Channel-Statistiken",
                value=f"**Gesamt:** {total_channels:,}\n"
                      f"**Text:** {text_channels:,}\n"
                      f"**Voice:** {voice_channels:,}\n"
                      f"**Kategorien:** {categories:,}\n"
                      f"**Stage:** {stage_channels:,}\n"
                      f"**Forum:** {forum_channels:,}",
                inline=True
            )
            
            # Server-Boost-Infos
            embed.add_field(
                name="🚀 Server-Boost",
                value=f"**Level:** {boost_level}\n"
                      f"**Boosts:** {boost_count:,}\n"
                      f"**Booster:** {boosters:,}\n"
                      f"**Rollen:** {role_count:,}",
                inline=True
            )
            
            # Server-Features (falls vorhanden)
            if features:
                feature_text = ", ".join(features[:5])
                if len(features) > 5:
                    feature_text += f" (+{len(features) - 5} weitere)"
                embed.add_field(
                    name="✨ Server-Features",
                    value=feature_text,
                    inline=False
                )
            
            # Upload-Limit
            upload_limit = guild.filesize_limit // (1024 * 1024)  # In MB
            embed.add_field(
                name="📤 Upload-Limit",
                value=f"{upload_limit} MB",
                inline=True
            )
            
            # Max. Mitglieder
            if guild.max_members:
                embed.add_field(
                    name="👥 Max. Mitglieder",
                    value=f"{guild.max_members:,}",
                    inline=True
                )
            
            # Footer
            embed.set_footer(
                text=f"Angefragt von {interaction.user.display_name}",
                icon_url=interaction.user.display_avatar.url
            )
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            logger.error(f"Fehler in serverstats: {e}")
            await interaction.response.send_message(
                "❌ Ein Fehler ist aufgetreten! Bitte versuche es später erneut.",
                ephemeral=True
            )

    @app_commands.command(
        name="memberinfo",
        description="Zeigt detaillierte Informationen über einen User an"
    )
    @app_commands.describe(
        member="Der User, dessen Informationen angezeigt werden sollen"
    )
    async def memberinfo(self, interaction: discord.Interaction, member: discord.Member = None):
        try:
            member = member or interaction.user
            
            # Timestamps
            unix_join_time = int(member.joined_at.timestamp())
            unix_create_time = int(member.created_at.timestamp())
            
            # Badges sammeln
            badges = []
            flags = member.public_flags
            
            if flags.bug_hunter:
                badges.append("Bug Hunter")
            if flags.bug_hunter_level_2:
                badges.append("Bug Hunter Level 2")
            if flags.early_supporter:
                badges.append("Early Supporter")
            if flags.verified_bot_developer:
                badges.append("Developer")
            if flags.partner:
                badges.append("Partner")
            if flags.staff:
                badges.append("Staff")
            if flags.hypesquad_balance:
                badges.append("Hypesquad Balance")
            if flags.hypesquad_bravery:
                badges.append("Hypesquad Bravery")
            if flags.hypesquad_brilliance:
                badges.append("Hypesquad Brilliance")
                
            # Embed erstellen
            embed = discord.Embed(
                color=member.color,
                timestamp=get_timestamp()
            )
            
            # Banner & Avatar
            user = await self.bot.fetch_user(member.id)
            
            if user.banner:
                embed.set_image(url=user.banner.url)
                if member.avatar:
                    embed.description = f"[Avatar]({member.avatar.url}) | [Banner]({user.banner.url})"
                else:
                    embed.description = f"[Banner]({user.banner.url})"
            elif member.avatar:
                embed.description = f"[Avatar]({member.avatar.url})"
                
            if member.avatar:
                embed.set_thumbnail(url=member.display_avatar.url)
                
            embed.set_author(name=f"Userinfo für {member}")
            
            # Basis-Infos
            embed.add_field(name="Name", value=f"`{member}` {'(Bot)' if member.bot else ''}", inline=True)
            embed.add_field(name="ID", value=f"`{member.id}`", inline=True)
            embed.add_field(name="Nick", value=f"`{member.nick}`" if member.nick else "Nicht gesetzt", inline=True)
            
            # Status
            status_text = "Unbekannt"
            if member.status == discord.Status.online:
                status_text = "Handy" if member.is_on_mobile() else "Online"
            elif member.status == discord.Status.idle:
                status_text = "Abwesend"
            elif member.status == discord.Status.dnd:
                status_text = "Beschäftigt"
            elif member.status == discord.Status.offline:
                status_text = "Offline"
            elif member.status == discord.Status.invisible:
                status_text = "Unsichtbar"
                
            embed.add_field(name="Status", value=f"`{status_text}`", inline=True)
            
            # Zeiten
            embed.add_field(
                name="Erstellt am",
                value=f"<t:{unix_create_time}:f> (<t:{unix_create_time}:R>)",
                inline=True
            )
            embed.add_field(
                name="Beigetreten am",
                value=f"<t:{unix_join_time}:f> (<t:{unix_join_time}:R>)",
                inline=True
            )
            
            # Rollen & Boost
            embed.add_field(name="Höchste Rolle", value=member.top_role.mention, inline=True)
            embed.add_field(name="Boostet", value="`Ja`" if member.premium_since else "`Nein`", inline=True)
            
            # Badges
            if badges:
                embed.add_field(name="Badges", value="\n".join(badges), inline=True)
            
            # Aktivitäten
            for activity in member.activities:
                if isinstance(activity, discord.Spotify):
                    embed.add_field(
                        name="Spotify",
                        value=f"**Titel:** {activity.title}\n**Artist:** {activity.artist}",
                        inline=False
                    )
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            logger.error(f"Fehler in memberinfo: {e}")
            await interaction.response.send_message(
                "❌ Ein Fehler ist aufgetreten! Bitte versuche es später erneut.",
                ephemeral=True
            )
    @app_commands.command(
        name="admin-setup",
        description="Setup für Admins"
    )
    @app_commands.default_permissions(administrator=True)
    async def admin_setup(self, interaction: discord.Interaction):
        # Überprüfe ob der User ein Admin ist
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ Du hast keine Berechtigung, diesen Befehl auszuführen!",
                ephemeral=True
            )
            return
        embed = discord.Embed(
            title="Admin Setup",
            description="Bitte wähle eine Option aus:",
            color=COLORS["blue"]
        )
        embed.add_field(name="1. Ticket System", value="Setup für das Ticket System", inline=True)
        embed.add_field(name="2. Level System", value="Setup für das Level System", inline=True)
        embed.add_field(name="3. Welcome System", value="Setup für das Welcome System", inline=True)
        # Erstelle die View mit den Buttons
        view = AdminSetupView()
        
        # Sende das Embed mit der View
        await interaction.response.send_message(embed=embed, view=view)
        
        # Warte auf Interaktion
        try:
            # Timeout nach 60 Sekunden
            interaction = await view.wait()
            if interaction is None:
                # Wenn timeout, deaktiviere Buttons
                for item in view.children:
                    item.disabled = True
                await interaction.message.edit(view=view)
                
        except Exception as e:
            logger.error(f"Fehler beim Warten auf Interaktion: {e}")
            await interaction.followup.send(
                "❌ Ein Fehler ist aufgetreten!",
                ephemeral=True
            )

class AdminSetupView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)  # 60 Sekunden timeout
        
    @discord.ui.button(label="Ticket System", style=discord.ButtonStyle.primary)
    async def ticket_setup(self, interaction: discord.Interaction, button: discord.ui.Button):
        ticket_setup = discord.Embed(
            title="🎫 Ticket System Setup - Vollständiger Guide",
            description="**Das neue Community-Custom Ticket-System! 🚀**\n"
                       "Erstelle eigene Kategorien und Buttons für deine Community!",
            color=COLORS["blue"]
        )
        
        # Panel Setup
        ticket_setup.add_field(
            name="🚀 Panel-Setup (Erste Schritte)",
            value="`/ticket-setup` - Erstellt das Haupt-Panel mit Buttons\n"
                  "`/ticket-panel-refresh` - Panel nach Änderungen aktualisieren",
            inline=False
        )
        
        # Category Management
        ticket_setup.add_field(
            name="📂 Category Management (Custom-Kategorien)",
            value="`/ticket-category-add` - Neue Kategorie erstellen (Modal)\n"
                  "`/ticket-category-edit` - Kategorien bearbeiten (Select-Menu)\n"
                  "`/ticket-category-remove` - Kategorien löschen (Bestätigung)\n"
                  "`/ticket-category-list` - Alle Kategorien anzeigen",
            inline=False
        )
        
        # Settings & Configuration
        ticket_setup.add_field(
            name="⚙️ Einstellungen & Konfiguration",
            value="`/ticket-settings` - Staff-Rollen, Log-Channel, Auto-Close\n"
                  "`/ticket-config` - Aktuelle Konfiguration anzeigen\n"
                  "`/ticket-staff-remove` - Staff-Rollen entfernen",
            inline=False
        )
        
        # User Commands
        ticket_setup.add_field(
            name="👥 User-Commands (In Tickets)",
            value="`/close` - Ticket schließen (mit Bestätigung)\n"
                  "**Buttons:** Schließen | User hinzufügen | Transcript",
            inline=False
        )
        
        # Features
        ticket_setup.add_field(
            name="✨ Features & Highlights",
            value="• **Bis zu 25 Custom-Kategorien** pro Server\n"
                  "• **Persistent Buttons** (funktionieren nach Bot-Restart)\n"
                  "• **Custom Embeds** pro Kategorie\n"
                  "• **Transcript-System** (.txt Download)\n"
                  "• **Auto-Close Timer** für inaktive Tickets\n"
                  "• **Staff-Ping System** & Berechtigungen\n"
                  "• **Rate-Limiting** (max 3 Tickets pro User)",
            inline=False
        )
        
        # Quick Start
        ticket_setup.add_field(
            name="🏃‍♂️ Quick Start Guide",
            value="**1.** `/ticket-setup` → Panel erstellen\n"
                  "**2.** `/ticket-category-add` → Custom-Kategorien\n"
                  "**3.** `/ticket-settings` → Staff-Rollen setzen\n"
                  "**4.** `/ticket-panel-refresh` → Panel aktualisieren\n"
                  "**5.** Fertig! 🎉",
            inline=False
        )
        
        await interaction.response.send_message(embed=ticket_setup, ephemeral=True)
    @discord.ui.button(label="Level System", style=discord.ButtonStyle.primary) 
    async def level_setup(self, interaction: discord.Interaction, button: discord.ui.Button):
        level_setup = discord.Embed(
            title="Level System Setup",
            description="Funktionen und Good To Know Sachen:",
            color=COLORS["blue"]
        )
        level_setup.add_field(name="1. /setup-level", value="Richtet das Level-System in diesem Server ein", inline=True)
        level_setup.add_field(name="2. /change-announcement", value="Ändert den Channel für Level-Up Benachrichtigungen", inline=True)
        level_setup.add_field(name="3. /block-channel", value="Blockiert einen Channel für XP-Gewinn (Anti-Spam)", inline=True)
        level_setup.add_field(name="4. /unblock-channel", value="Entblockiert einen Channel für XP-Gewinn", inline=True)
        level_setup.add_field(name="5. /list-blocked", value="Zeigt alle blockierten Channels an", inline=True)
        level_setup.add_field(name="6. /block-channels", value="Blockiert mehrere Channels für XP-Gewinn (Anti-Spam)", inline=True)
        level_setup.add_field(name="7. /unblock-channels", value="Entblockiert mehrere Channels für XP-Gewinn", inline=True)
        level_setup.add_field(name="8. /block-all-except", value="Blockiert alle Channels außer den angegebenen (Whitelist)", inline=True)
        await interaction.response.send_message(embed=level_setup, ephemeral=True)
    @discord.ui.button(label="Welcome System", style=discord.ButtonStyle.primary)
    async def welcome_setup(self, interaction: discord.Interaction, button: discord.ui.Button):
        welcome_setup = discord.Embed(
            title="Welcome System Setup",
            description="Funktionen und Good To Know Sachen:",
            color=COLORS["blue"]
        )
        welcome_setup.add_field(name="1. /welcome-setup", value="Setup für das Welcome System", inline=True)
        await interaction.response.send_message(embed=welcome_setup, ephemeral=True)
async def setup(bot):
    await bot.add_cog(Unix(bot))
    print("Unix Extension Loaded!")
