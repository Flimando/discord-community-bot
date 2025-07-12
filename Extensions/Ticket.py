"""
Vollständiges Ticket-System mit persistenten Views und Customization

Features:
- Soft-coded Konfiguration
- Persistent Views (überleben Bot-Restart)
- Button-basierte UI
- Kategorie-System
- Custom Embeds
- Auto-close Timer
- Transcript-System
- Rate-limiting
- Staff-Notifications

Entwickelt von Flimando für Staiy-AI Community Bot
"""

import discord
from discord.ext import commands, tasks
from discord import app_commands
import logging
import json
import asyncio
import io
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path

from config import COLORS
from functions import (
    create_ticket,
    kill_ticket, 
    is_ticket,
    ticket_check,
    max_tickets,
    get_ticket_owner,
    get_ticket_data,
    get_timestamp,
    add_control_message_to_ticket,
    get_ticket_control_message_id
)

# Custom JSON Encoder für Discord-Objekte
class DiscordJSONEncoder(json.JSONEncoder):
    """Custom JSON Encoder der Discord-Objekte richtig serialisiert"""
    def default(self, obj):
        if isinstance(obj, discord.Color):
            return obj.value  # Konvertiert zu Integer
        elif isinstance(obj, discord.Colour):
            return obj.value  # Konvertiert zu Integer  
        return super().default(obj)

# Logger Setup
logger = logging.getLogger(__name__)

# Test ob Extension-Logging funktioniert
logger.info("🎫 TICKET EXTENSION: Logger initialisiert und bereit!")

# Config Paths
CONFIGS_DIR = Path("data/ticket_configs")
PANELS_PATH = Path("data/ticket_panels.json")

class TicketConfig:
    """Guild-spezifischer Ticket-System Konfiguration Manager"""
    
    DEFAULT_CONFIG = {
        "enabled": True,
        "max_tickets_per_user": 3,
        "auto_close_time": 24,  # Stunden
        "staff_role_ids": [],
        "log_channel_id": None,
        "transcript_enabled": True,
        "categories": {
            "support": {
                "name": "🛠️ Support",
                "description": "Allgemeine Hilfe und Support",
                "emoji": "🛠️",
                "staff_ping": True,
                "category_id": None,
                "embed": {
                    "title": "Support Ticket",
                    "description": "Willkommen in deinem Support-Ticket!\nEin Teammitglied wird sich in Kürze melden.",
                    "color": COLORS["blue"]
                }
            },
            "bug": {
                "name": "🐛 Bug Report",
                "description": "Melde Bugs und Fehler",
                "emoji": "🐛",
                "staff_ping": True,
                "category_id": None,
                "embed": {
                    "title": "Bug Report",
                    "description": "Danke für deinen Bug-Report!\nBitte beschreibe das Problem detailliert.",
                    "color": COLORS["red"]
                }
            },
            "feature": {
                "name": "💡 Feature Request",
                "description": "Schlage neue Features vor",
                "emoji": "💡",
                "staff_ping": False,
                "category_id": None,
                "embed": {
                    "title": "Feature Request",
                    "description": "Danke für deinen Vorschlag!\nWir werden ihn prüfen.",
                    "color": COLORS["green"]
                }
            }
        },
        "messages": {
            "panel_title": "🎫 Ticket System",
            "panel_description": "Wähle eine Kategorie um ein Ticket zu erstellen:",
            "panel_color": COLORS["blue"],
            "max_tickets_reached": "❌ Du hast bereits die maximale Anzahl an Tickets ({max}) erreicht!",
            "ticket_created": "✅ Dein {category} Ticket wurde erstellt: {channel}",
            "no_permission": "❌ Du hast keine Berechtigung für diese Aktion!",
            "not_a_ticket": "❌ Dieser Channel ist kein Ticket!",
            "ticket_closed": "🔒 Ticket wird geschlossen...",
            "user_added": "✅ {user} wurde zum Ticket hinzugefügt!",
            "user_removed": "✅ {user} wurde aus dem Ticket entfernt!",
            "add_user_instruction": "📝 **Antworte auf diese Nachricht** mit den Usern die du hinzufügen möchtest:",
            "add_user_timeout": "⏰ **Timeout!** Du hast zu lange gebraucht. Versuche es erneut.",
            "add_user_no_input": "❌ **Keine User angegeben!** Gib mindestens einen User an.",
            "add_user_invalid": "❌ **Keine gültigen User gefunden!** Verwende Mentions (@User) oder User-IDs (123456789)."
        }
    }
    
    def __init__(self, guild_id: int):
        self.guild_id = guild_id
        self.config_path = CONFIGS_DIR / f"guild_{guild_id}.json"
        self.config_path.parent.mkdir(exist_ok=True)
        self.config = self.load_config()
    
    def load_config(self) -> Dict[str, Any]:
        """Lädt die Guild-spezifische Konfiguration"""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                # Merge mit Default-Config
                return self._merge_config(self.DEFAULT_CONFIG, config)
            except Exception as e:
                logger.error(f"Fehler beim Laden der Ticket-Config für Guild {self.guild_id}: {e}")
        
        # Erstelle Default-Config für diese Guild
        self.save_config(self.DEFAULT_CONFIG)
        return self.DEFAULT_CONFIG.copy()
    
    def _merge_config(self, default: Dict, loaded: Dict) -> Dict:
        """Merged geladene Config mit Default-Werten"""
        result = default.copy()
        for key, value in loaded.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_config(result[key], value)
            else:
                result[key] = value
        return result
    
    def save_config(self, config: Optional[Dict] = None):
        """Speichert die Guild-spezifische Konfiguration"""
        logger.debug(f"💾 TicketConfig.save_config() aufgerufen für Guild {self.guild_id}")
        
        if config:
            self.config = config
            logger.debug(f"💾 Config überschrieben mit neuen Daten")
        
        try:
            logger.debug(f"💾 Speichere in Datei: {self.config_path}")
            
            # Log aktuelle Categories vor dem Speichern
            categories = self.config.get('categories', {})
            logger.info(f"💾 SPEICHERE CONFIG mit {len(categories)} Kategorien: {list(categories.keys())}")
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False, cls=DiscordJSONEncoder)
            
            logger.info(f"💾 CONFIG ERFOLGREICH GESPEICHERT für Guild {self.guild_id}")
            
            # Verification: Datei wieder laden und prüfen
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    saved_config = json.load(f)
                saved_categories = saved_config.get('categories', {})
                logger.info(f"💾 VERIFIKATION: Gespeicherte Datei enthält {len(saved_categories)} Kategorien: {list(saved_categories.keys())}")
            except Exception as verify_e:
                logger.error(f"💾 VERIFIKATION FEHLER: {verify_e}")
                
        except Exception as e:
            logger.error(f"💾 FEHLER beim Speichern der Ticket-Config für Guild {self.guild_id}: {e}", exc_info=True)
    
    def get(self, key: str, default=None):
        """Holt einen Config-Wert"""
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value
    
    def set(self, key: str, value: Any):
        """Setzt einen Config-Wert"""
        logger.debug(f"🔧 TicketConfig.set() aufgerufen für Guild {self.guild_id}: '{key}' = {type(value).__name__}")
        
        keys = key.split('.')
        config = self.config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        # Log was geändert wird
        old_value = config.get(keys[-1], None)
        config[keys[-1]] = value
        
        if key == 'categories':
            logger.info(f"🔧 CATEGORIES UPDATE: {len(old_value) if old_value else 0} -> {len(value) if isinstance(value, dict) else 'N/A'} Kategorien")
            if old_value and isinstance(old_value, dict) and isinstance(value, dict):
                removed = set(old_value.keys()) - set(value.keys())
                added = set(value.keys()) - set(old_value.keys())
                if removed:
                    logger.info(f"🔧 CATEGORIES REMOVED: {list(removed)}")
                if added:
                    logger.info(f"🔧 CATEGORIES ADDED: {list(added)}")
        
        logger.debug(f"🔧 TicketConfig.set() ruft save_config() auf...")
        self.save_config()

class PanelManager:
    """Verwaltet Ticket-Panels"""
    
    def __init__(self):
        self.panels_path = PANELS_PATH
        self.panels_path.parent.mkdir(exist_ok=True)
        self.panels = self.load_panels()
    
    def load_panels(self) -> Dict[str, Any]:
        """Lädt Panel-Daten"""
        if self.panels_path.exists():
            try:
                with open(self.panels_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Fehler beim Laden der Panel-Daten: {e}")
        return {}
    
    def save_panels(self):
        """Speichert Panel-Daten"""
        try:
            with open(self.panels_path, 'w', encoding='utf-8') as f:
                json.dump(self.panels, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Fehler beim Speichern der Panel-Daten: {e}")
    
    def add_panel(self, guild_id: int, channel_id: int, message_id: int):
        """Fügt ein Panel hinzu"""
        self.panels[str(guild_id)] = {
            "channel_id": channel_id,
            "message_id": message_id
        }
        self.save_panels()
    
    def get_panel(self, guild_id: int) -> Optional[Dict]:
        """Holt Panel-Daten für Guild"""
        return self.panels.get(str(guild_id))
    
    def remove_panel(self, guild_id: int):
        """Entfernt ein Panel"""
        if str(guild_id) in self.panels:
            del self.panels[str(guild_id)]
            self.save_panels()

class TicketPanelView(discord.ui.View):
    """Haupt-Panel View für Ticket-Erstellung"""
    
    def __init__(self, guild_id: int):
        super().__init__(timeout=None)
        self.guild_id = guild_id
        self.create_buttons()
    
    def create_buttons(self):
        """Erstellt Buttons basierend auf Kategorien"""
        self.clear_items()
        
        # WICHTIG: Config IMMER frisch laden für aktuelle Kategorien!
        config = TicketConfig(self.guild_id)
        categories = config.get('categories', {})
        
        logger.info(f"Panel-Buttons erstellen für Guild {self.guild_id}. Verfügbare Kategorien: {list(categories.keys())}")
        
        for cat_id, cat_data in categories.items():
            button = discord.ui.Button(
                label=cat_data['name'],
                emoji=cat_data['emoji'],
                style=discord.ButtonStyle.primary,
                custom_id=f"ticket_create_{cat_id}"
            )
            button.callback = self.create_ticket_callback
            self.add_item(button)
            logger.debug(f"Button erstellt für Kategorie: {cat_id} - {cat_data['name']}")
        
        if not categories:
            logger.warning(f"Keine Kategorien gefunden für Guild {self.guild_id}!")
    
    async def create_ticket_callback(self, interaction: discord.Interaction):
        """Callback für Ticket-Erstellung"""
        custom_id = interaction.data['custom_id']
        category = custom_id.replace('ticket_create_', '')
        
        # Frische Config laden
        config = TicketConfig(interaction.guild.id)
        
        # Rate-limiting prüfen
        max_tickets_allowed = config.get('max_tickets_per_user', 3)
        if not max_tickets(interaction.user.id, interaction.guild.id, interaction.client):
            msg = config.get('messages.max_tickets_reached', '❌ Max Tickets erreicht!')
            await interaction.response.send_message(
                msg.format(max=max_tickets_allowed),
                ephemeral=True
            )
            return
        
        # Kategorie-Daten holen
        cat_data = config.get(f'categories.{category}')
        if not cat_data:
            logger.warning(f"Kategorie '{category}' nicht gefunden für Guild {interaction.guild.id}. Verfügbare: {list(config.get('categories', {}).keys())}")
            await interaction.response.send_message(
                "❌ Kategorie nicht gefunden!",
                ephemeral=True
            )
            return

        try:
            # Channel-Overwrites
            overwrites = {
                interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                interaction.user: discord.PermissionOverwrite(
                    read_messages=True, 
                    send_messages=True,
                    attach_files=True,
                    embed_links=True
                ),
                interaction.guild.me: discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=True,
                    manage_messages=True,
                    embed_links=True
                )
            }

            # Staff-Rollen hinzufügen
            staff_roles = config.get('staff_role_ids', [])
            for role_id in staff_roles:
                role = interaction.guild.get_role(role_id)
                if role:
                    overwrites[role] = discord.PermissionOverwrite(
                        read_messages=True,
                        send_messages=True,
                        manage_messages=True
                    )
            
            # Kategorie für Channel
            category_obj = None
            if cat_data.get('category_id'):
                category_obj = interaction.guild.get_channel(cat_data['category_id'])
            
            # Channel erstellen
            channel_name = f"ticket-{interaction.user.name}-{category}"
            channel = await interaction.guild.create_text_channel(
                channel_name,
                overwrites=overwrites,
                category=category_obj,
                reason=f"Ticket erstellt von {interaction.user.name}"
            )

            # In DB speichern
            create_ticket(channel.id, interaction.user.id, interaction.guild.id, cat_data['name'])

            # Bestätigung senden
            msg = config.get('messages.ticket_created', '✅ Ticket erstellt!')
            await interaction.response.send_message(
                msg.format(category=cat_data['name'], channel=channel.mention),
                ephemeral=True
            )

            # Embed für Ticket
            embed_data = cat_data.get('embed', {})
            embed = discord.Embed(
                title=embed_data.get('title', f"{cat_data['name']} Ticket"),
                description=embed_data.get('description', f"Willkommen {interaction.user.mention}!"),
                color=embed_data.get('color', COLORS['blue']),
                timestamp=get_timestamp()
            )
                
            embed.add_field(
                name="📋 Ticket Info",
                value=f"**Ersteller:** {interaction.user.mention}\n"
                      f"**Kategorie:** {cat_data['name']}\n"
                      f"**Erstellt:** <t:{int(datetime.now().timestamp())}:F>",
                inline=False
            )
            
            # Control View hinzufügen
            control_view = TicketControlView(interaction.guild.id, category)
            
            # Willkommensnachricht senden
            embed_for_ticket = await channel.send(
                content=interaction.user.mention,
                embed=embed,
                view=control_view
            )
            
            # Control-Message-ID in DB speichern für persistente Views
            add_control_message_to_ticket(channel.id, interaction.guild.id, embed_for_ticket.id)
            logger.info(f"Control-Message-ID {embed_for_ticket.id} für Ticket {channel.id} gespeichert")
            
            # Staff ping falls aktiviert
            if cat_data.get('staff_ping') and staff_roles:
                staff_mentions = ' '.join([f"<@&{role_id}>" for role_id in staff_roles])
                await channel.send(f"📢 {staff_mentions}", delete_after=5)
            
            logger.info(f"Ticket erstellt: {channel.id} von {interaction.user.id} - Kategorie: {category}")
            
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ Ich habe keine Berechtigung, Channels zu erstellen!",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Fehler beim Erstellen des Tickets: {e}")
            await interaction.response.send_message(
                "❌ Ein Fehler ist aufgetreten!",
                ephemeral=True
            )

class TicketControlView(discord.ui.View):
    """Control Panel für Tickets"""
    
    def __init__(self, guild_id: int, category: str):
        super().__init__(timeout=None)
        self.guild_id = guild_id
        self.config = TicketConfig(guild_id)
        self.category = category
    
    @discord.ui.button(
        label="Schließen",
        emoji="🔒",
        style=discord.ButtonStyle.danger,
        custom_id="ticket_close"
    )
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Schließt das Ticket"""
        # Berechtigung prüfen
        if not (ticket_check(interaction.user.id, interaction.channel.id, interaction.guild.id) or 
                interaction.user.guild_permissions.administrator or
                any(role.id in self.config.get('staff_role_ids', []) for role in interaction.user.roles)):
            await interaction.response.send_message(
                self.config.get('messages.no_permission', '❌ Keine Berechtigung!'),
                ephemeral=True
            )
            return

        # Bestätigung anzeigen
        confirm_view = ConfirmCloseView(interaction.guild.id)
        await interaction.response.send_message(
            "⚠️ Möchtest du dieses Ticket wirklich schließen?",
            view=confirm_view,
            ephemeral=True
        )
    
    @discord.ui.button(
        label="User hinzufügen",
        emoji="➕",
        style=discord.ButtonStyle.secondary,
        custom_id="ticket_add_user"
    )
    async def add_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Fügt einen oder mehrere User hinzu"""
        # Berechtigung prüfen
        if not (ticket_check(interaction.user.id, interaction.channel.id, interaction.guild.id) or 
                interaction.user.guild_permissions.administrator or
                any(role.id in self.config.get('staff_role_ids', []) for role in interaction.user.roles)):
            await interaction.response.send_message(
                self.config.get('messages.no_permission', '❌ Keine Berechtigung!'),
                ephemeral=True
            )
            return

        # Message-basierte User-Abfrage starten
        embed = discord.Embed(
            title="➕ User zum Ticket hinzufügen",
            description="**Wie funktioniert es?**\n"
                       "• Erwähne einen oder mehrere User: `@User1 @User2 @User3`\n"
                       "• Oder gib User-IDs ein: `123456789 987654321`\n"
                       "• Oder eine Mischung: `@User1 123456789 @User2`\n\n"
                       "**Beispiel:**\n"
                       "`@user1 @user2 123456789`",
            color=COLORS['blue'],
            timestamp=get_timestamp()
        )
        
        embed.add_field(
            name="⏰ Timeout",
            value="Du hast **60 Sekunden** Zeit zu antworten.",
            inline=False
        )
        
        await interaction.response.send_message(
            self.config.get('messages.add_user_instruction', "📝 **Antworte auf diese Nachricht** mit den Usern die du hinzufügen möchtest:"),
            embed=embed,
            ephemeral=True
        )
        
        # User-Response Handler starten
        await self._handle_user_add_response(interaction)
    
    async def _handle_user_add_response(self, interaction: discord.Interaction):
        """Handler für User-Response beim Hinzufügen"""
        try:
            # Warte auf User-Response (60 Sekunden)
            def check(message):
                return (message.author == interaction.user and 
                       message.channel == interaction.channel and
                       not message.author.bot)
            # if channel was deleted or closed, go into return
            try:
                try:
                    user_message = await interaction.client.wait_for('message', timeout=60.0, check=check)
                except:
                    return
            except asyncio.TimeoutError:
                try:
                    await interaction.followup.send(
                        self.config.get('messages.add_user_timeout', "⏰ **Timeout!** Du hast zu lange gebraucht. Versuche es erneut."),
                        ephemeral=True
                    )
                    return
                except:
                    return
            # User-Input parsen
            user_input = user_message.content.strip()
            if not user_input:
                await interaction.followup.send(
                    self.config.get('messages.add_user_no_input', "❌ **Keine User angegeben!** Gib mindestens einen User an."),
                    ephemeral=True
                )
                return
            
            # User-IDs extrahieren
            user_ids = []
            words = user_input.split()
            
            for word in words:
                user_id = None
                
                # Mention format: <@123456789> oder <@!123456789>
                if word.startswith('<@') and word.endswith('>'):
                    user_id = int(word[2:-1].replace('!', ''))
                # Pure ID
                elif word.isdigit():
                    user_id = int(word)
                
                if user_id and user_id not in user_ids:
                    user_ids.append(user_id)
            
            if not user_ids:
                await interaction.followup.send(
                    self.config.get('messages.add_user_invalid', "❌ **Keine gültigen User gefunden!** Verwende Mentions (@User) oder User-IDs (123456789)."),
                    ephemeral=True
                )
                return
            
            # Users hinzufügen
            added_users = []
            failed_users = []
            
            for user_id in user_ids:
                try:
                    user = interaction.guild.get_member(user_id)
                    if not user:
                        failed_users.append(f"User-ID {user_id} (nicht auf Server)")
                        continue
                    
                    # Permissions setzen
                    await interaction.channel.set_permissions(
                        user,
                        read_messages=True,
                        send_messages=True,
                        attach_files=True
                    )
                    
                    added_users.append(user)
                    logger.info(f"User {user.id} zum Ticket {interaction.channel.id} hinzugefügt")
                    
                except Exception as e:
                    logger.error(f"Fehler beim Hinzufügen von User {user_id}: {e}")
                    failed_users.append(f"User-ID {user_id} (Fehler)")
            
            # Ergebnis anzeigen
            embed = discord.Embed(
                title="➕ User hinzugefügt",
                color=COLORS['green'] if added_users else COLORS['red'],
                timestamp=get_timestamp()
            )
            
            if added_users:
                added_mentions = ' '.join([user.mention for user in added_users])
                embed.description = f"✅ **Erfolgreich hinzugefügt:**\n{added_mentions}"
                
                # Benachrichtigung im Channel
                await interaction.channel.send(
                    f"➕ {added_mentions} wurde(n) zum Ticket hinzugefügt von {interaction.user.mention}"
                )
            
            if failed_users:
                failed_list = '\n'.join([f"• {user}" for user in failed_users])
                embed.add_field(
                    name="❌ Fehlgeschlagen",
                    value=failed_list,
                    inline=False
                )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Fehler beim User-Add-Response: {e}")
            await interaction.followup.send(
                "❌ **Fehler beim Hinzufügen der User!**",
                ephemeral=True
            )
    
    @discord.ui.button(
        label="Transcript",
        emoji="📄",
        style=discord.ButtonStyle.secondary,
        custom_id="ticket_transcript"
    )
    async def create_transcript(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Erstellt ein Transcript"""
        if not self.config.get('transcript_enabled', True):
            await interaction.response.send_message(
                "❌ Transcripts sind deaktiviert!",
                ephemeral=True
            )
            return

        # Berechtigung prüfen
        if not (ticket_check(interaction.user.id, interaction.channel.id, interaction.guild.id) or 
                interaction.user.guild_permissions.administrator or
                any(role.id in self.config.get('staff_role_ids', []) for role in interaction.user.roles)):
            await interaction.response.send_message(
                self.config.get('messages.no_permission', '❌ Keine Berechtigung!'),
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)
        
        try:
            # Sicheren Dateinamen erstellen
            safe_filename = "".join(c for c in interaction.channel.name if c.isalnum() or c in ('-', '_', '.')).rstrip()
            if not safe_filename:
                safe_filename = f"ticket-{interaction.channel.id}"
            
            # HTML-Transcript erstellen
            html_transcript = await self.generate_html_transcript(interaction.channel)
            
            # BytesIO für File-Objekt verwenden
            transcript_bytes = io.BytesIO()
            transcript_bytes.write(html_transcript.encode('utf-8', errors='replace'))
            transcript_bytes.seek(0)
            
            # Als HTML-File senden
            file = discord.File(
                transcript_bytes,
                filename=f"transcript-{safe_filename}.html"
            )
            
            embed = discord.Embed(
                title="📄 Ticket Transcript erstellt!",
                description=f"**Ticket:** {interaction.channel.name}\n"
                           f"**Format:** Modern HTML\n"
                           f"**Erstellt:** <t:{int(datetime.now().timestamp())}:F>",
                color=COLORS['green']
            )
            
            await interaction.followup.send(
                embed=embed,
                file=file,
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f"Fehler beim Erstellen des Transcripts: {e}")
            await interaction.followup.send(
                "❌ Fehler beim Erstellen des Transcripts!",
                ephemeral=True
            )
    
    async def generate_transcript(self, channel: discord.TextChannel) -> str:
        """Generiert ein Text-Transcript"""
        messages = []
        
        try:
            async for message in channel.history(limit=None, oldest_first=True):
                try:
                    timestamp = message.created_at.strftime("%Y-%m-%d %H:%M:%S")
                    
                    # Content sanitizen (problematische Unicode-Zeichen ersetzen)
                    content = message.content or "[Kein Text]"
                    # Ersetze problematische Unicode-Zeichen durch lesbare Alternativen
                    content = content.encode('ascii', errors='ignore').decode('ascii')
                    if not content.strip() and message.content:
                        content = "[Unicode-Inhalt]"
                    elif not content.strip():
                        content = "[Kein Text]"
                    
                    # Attachments hinzufügen
                    if message.attachments:
                        attachment_names = []
                        for att in message.attachments:
                            # Auch Dateinamen sanitizen
                            safe_name = att.filename.encode('ascii', errors='ignore').decode('ascii')
                            attachment_names.append(safe_name if safe_name else "[Unicode-Dateiname]")
                        attachments = ", ".join(attachment_names)
                        content += f" [Anhänge: {attachments}]"
                    
                    # Embeds hinzufügen
                    if message.embeds:
                        content += f" [Embeds: {len(message.embeds)}]"
                    
                    # Autor-Name sanitizen
                    author_name = message.author.display_name.encode('ascii', errors='ignore').decode('ascii')
                    if not author_name:
                        author_name = f"User-{message.author.id}"
                    
                    messages.append(f"[{timestamp}] {author_name}: {content}")
                    
                except Exception as msg_error:
                    logger.warning(f"Fehler beim Verarbeiten einer Nachricht: {msg_error}")
                    messages.append(f"[Fehler] Nachricht konnte nicht gelesen werden: {msg_error}")
                    
        except Exception as channel_error:
            logger.error(f"Fehler beim Lesen des Channel-Verlaufs: {channel_error}")
            messages.append("[Fehler] Channel-Verlauf konnte nicht vollständig gelesen werden")
        
        # Header erstellen
        safe_channel_name = channel.name.encode('ascii', errors='ignore').decode('ascii')
        if not safe_channel_name:
            safe_channel_name = f"ticket-{channel.id}"
            
        header = f"Ticket Transcript - {safe_channel_name}\n"
        header += f"Erstellt am: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        header += f"Channel-ID: {channel.id}\n"
        header += f"Guild: {channel.guild.name}\n"
        header += "=" * 50 + "\n\n"
        
        if not messages:
            return header + "[Keine Nachrichten gefunden oder alle Nachrichten fehlerhaft]"
        
        return header + "\n".join(messages)
    
    async def generate_html_transcript(self, channel: discord.TextChannel) -> str:
        """Generiert ein modernes HTML-Transcript"""
        messages = []
        
        try:
            async for message in channel.history(limit=None, oldest_first=True):
                try:
                    # Message-Daten sammeln
                    timestamp = message.created_at
                    timestamp_str = timestamp.strftime("%d.%m.%Y %H:%M:%S")
                    timestamp_unix = int(timestamp.timestamp())
                    
                    author = message.author
                    content = message.content or ""
                    
                    # HTML-Message-Objekt erstellen
                    msg_data = {
                        'id': message.id,
                        'timestamp': timestamp_str,
                        'timestamp_unix': timestamp_unix,
                        'author_name': self._escape_html(author.display_name),
                        'author_id': author.id,
                        'author_avatar': str(author.display_avatar.url),
                        'content': self._format_message_content(content),
                        'attachments': [],
                        'embeds': [],
                        'is_bot': author.bot
                    }
                    
                    # Attachments verarbeiten
                    for attachment in message.attachments:
                        att_data = {
                            'filename': self._escape_html(attachment.filename),
                            'url': attachment.url,
                            'size': attachment.size,
                            'is_image': any(attachment.filename.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp'])
                        }
                        msg_data['attachments'].append(att_data)
                    
                    # Embeds verarbeiten
                    for embed in message.embeds:
                        embed_data = {
                            'title': self._escape_html(embed.title) if embed.title else None,
                            'description': self._escape_html(embed.description) if embed.description else None,
                            'color': f"#{embed.color.value:06x}" if embed.color else "#2b2d31",
                            'fields': []
                        }
                        
                        for field in embed.fields:
                            embed_data['fields'].append({
                                'name': self._escape_html(field.name),
                                'value': self._escape_html(field.value),
                                'inline': field.inline
                            })
                        
                        msg_data['embeds'].append(embed_data)
                    
                    messages.append(msg_data)
                    
                except Exception as msg_error:
                    logger.warning(f"Fehler beim Verarbeiten einer Nachricht: {msg_error}")
                    # Fallback-Message
                    messages.append({
                        'id': 'error',
                        'timestamp': datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
                        'timestamp_unix': int(datetime.now().timestamp()),
                        'author_name': 'System',
                        'author_id': 0,
                        'author_avatar': '',
                        'content': f'❌ Nachricht konnte nicht gelesen werden: {str(msg_error)}',
                        'attachments': [],
                        'embeds': [],
                        'is_bot': True
                    })
                    
        except Exception as channel_error:
            logger.error(f"Fehler beim Lesen des Channel-Verlaufs: {channel_error}")
        
        # HTML generieren
        return self._generate_html_template(channel, messages)
    
    def _escape_html(self, text: str) -> str:
        """Escaped HTML-Zeichen"""
        if not text:
            return ""
        return (text.replace("&", "&amp;")
                   .replace("<", "&lt;")
                   .replace(">", "&gt;")
                   .replace('"', "&quot;")
                   .replace("'", "&#x27;"))
    
    def _format_message_content(self, content: str) -> str:
        """Formatiert Message-Content für HTML"""
        if not content:
            return "<em>Keine Nachricht</em>"
        
        # HTML escapen
        content = self._escape_html(content)
        
        # Discord-Formatierung zu HTML
        
        # Bold **text**
        content = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', content)
        
        # Italic *text*
        content = re.sub(r'\*(.*?)\*', r'<em>\1</em>', content)
        
        # Underline __text__
        content = re.sub(r'__(.*?)__', r'<u>\1</u>', content)
        
        # Strikethrough ~~text~~
        content = re.sub(r'~~(.*?)~~', r'<s>\1</s>', content)
        
        # Code `text`
        content = re.sub(r'`([^`]+)`', r'<code>\1</code>', content)
        
        # Code blocks ```text```
        content = re.sub(r'```(.*?)```', r'<pre><code>\1</code></pre>', content, flags=re.DOTALL)
        
        # User mentions <@123456>
        content = re.sub(r'&lt;@!?(\d+)&gt;', r'<span class="mention">@User-\1</span>', content)
        
        # Role mentions <@&123456>
        content = re.sub(r'&lt;@&amp;(\d+)&gt;', r'<span class="mention mention-role">@Role-\1</span>', content)
        
        # Channel mentions <#123456>
        content = re.sub(r'&lt;#(\d+)&gt;', r'<span class="mention mention-channel">#Channel-\1</span>', content)
        
        # URLs
        url_pattern = r'(https?://[^\s]+)'
        content = re.sub(url_pattern, r'<a href="\1" target="_blank" rel="noopener">\1</a>', content)
        
        # Zeilenumbrüche
        content = content.replace('\n', '<br>')
        
        return content
    
    def _generate_html_template(self, channel: discord.TextChannel, messages: list) -> str:
        """Generiert das HTML-Template"""
        
        # Ticket-Info sammeln
        ticket_data = get_ticket_data(channel.id, channel.guild.id)
        ticket_owner = None
        ticket_type = "Unbekannt"
        ticket_created = "Unbekannt"
        
        if ticket_data:
            try:
                ticket_owner = channel.guild.get_member(ticket_data["Owner_ID"])
                ticket_type = ticket_data.get("Type", "Unbekannt")
                ticket_created = ticket_data.get("Created", "Unbekannt")
            except:
                pass
        
        # Message-HTML generieren
        messages_html = ""
        for msg in messages:
            # Avatar Fallback
            avatar_url = msg['author_avatar'] if msg['author_avatar'] else 'https://cdn.discordapp.com/embed/avatars/0.png'
            
            # Message Content
            content_html = msg['content']
            
            # Attachments
            attachments_html = ""
            for att in msg['attachments']:
                if att['is_image']:
                    attachments_html += f'''
                        <div class="attachment">
                            <img src="{att['url']}" alt="{att['filename']}" class="attachment-image">
                            <div class="attachment-info">
                                <span class="attachment-name">{att['filename']}</span>
                                <span class="attachment-size">{att['size']} Bytes</span>
                            </div>
                        </div>
                    '''
                else:
                    attachments_html += f'''
                        <div class="attachment">
                            <div class="attachment-info">
                                <span class="attachment-name">📎 {att['filename']}</span>
                                <span class="attachment-size">{att['size']} Bytes</span>
                            </div>
                        </div>
                    '''
            
            # Embeds
            embeds_html = ""
            for embed in msg['embeds']:
                embed_html = f'<div class="embed" style="border-left-color: {embed["color"]}">'
                
                if embed['title']:
                    embed_html += f'<div class="embed-title">{embed["title"]}</div>'
                
                if embed['description']:
                    embed_html += f'<div class="embed-description">{embed["description"]}</div>'
                
                if embed['fields']:
                    embed_html += '<div class="embed-fields">'
                    for field in embed['fields']:
                        inline_class = "inline" if field['inline'] else ""
                        embed_html += f'''
                            <div class="embed-field {inline_class}">
                                <div class="embed-field-name">{field["name"]}</div>
                                <div class="embed-field-value">{field["value"]}</div>
                            </div>
                        '''
                    embed_html += '</div>'
                
                embed_html += '</div>'
                embeds_html += embed_html
            
            # Bot-Badge
            bot_badge = '<span class="bot-badge">BOT</span>' if msg['is_bot'] else ''
            
            # Message zusammenbauen
            messages_html += f'''
                <div class="message" data-message-id="{msg['id']}">
                    <div class="message-avatar">
                        <img src="{avatar_url}" alt="{msg['author_name']}" class="avatar">
                    </div>
                    <div class="message-content">
                        <div class="message-header">
                            <span class="author-name">{msg['author_name']}</span>
                            {bot_badge}
                            <span class="message-timestamp" title="{msg['timestamp']}">{msg['timestamp']}</span>
                        </div>
                        <div class="message-text">{content_html}</div>
                        {attachments_html}
                        {embeds_html}
                    </div>
                </div>
            '''
        
        # Vollständiges HTML
        html = f'''
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Ticket Transcript - {self._escape_html(channel.name)}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #36393f;
            color: #dcddde;
            line-height: 1.4;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }}
        
        .header {{
            background: linear-gradient(135deg, #5865f2, #3b4cca);
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 24px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
        }}
        
        .header h1 {{
            font-size: 28px;
            margin-bottom: 12px;
            color: white;
        }}
        
        .header-info {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 16px;
            opacity: 0.95;
        }}
        
        .info-item {{
            background: rgba(255, 255, 255, 0.1);
            padding: 12px;
            border-radius: 8px;
            backdrop-filter: blur(10px);
        }}
        
        .info-label {{
            font-weight: 600;
            color: #b9bbbe;
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        
        .info-value {{
            font-size: 14px;
            color: white;
            margin-top: 4px;
        }}
        
        .messages {{
            background: #2f3136;
            border-radius: 12px;
            padding: 0;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
        }}
        
        .message {{
            display: flex;
            padding: 16px 20px;
            border-bottom: 1px solid #40444b;
            transition: background-color 0.2s;
        }}
        
        .message:hover {{
            background-color: #32353b;
        }}
        
        .message:last-child {{
            border-bottom: none;
        }}
        
        .message-avatar {{
            margin-right: 16px;
            flex-shrink: 0;
        }}
        
        .avatar {{
            width: 40px;
            height: 40px;
            border-radius: 50%;
            object-fit: cover;
        }}
        
        .message-content {{
            flex: 1;
            min-width: 0;
        }}
        
        .message-header {{
            display: flex;
            align-items: center;
            margin-bottom: 4px;
            gap: 8px;
        }}
        
        .author-name {{
            font-weight: 600;
            color: #ffffff;
            font-size: 16px;
        }}
        
        .bot-badge {{
            background: #5865f2;
            color: white;
            font-size: 10px;
            font-weight: 600;
            padding: 2px 6px;
            border-radius: 4px;
            text-transform: uppercase;
        }}
        
        .message-timestamp {{
            color: #72767d;
            font-size: 12px;
            margin-left: auto;
        }}
        
        .message-text {{
            word-wrap: break-word;
            white-space: pre-wrap;
            line-height: 1.5;
        }}
        
        .mention {{
            background: #5865f2;
            color: white;
            padding: 2px 6px;
            border-radius: 4px;
            font-weight: 500;
            text-decoration: none;
        }}
        
        .mention-role {{
            background: #f47b67;
        }}
        
        .mention-channel {{
            background: #00b0f4;
        }}
        
        code {{
            background: #2f3136;
            color: #f8f8f2;
            padding: 2px 4px;
            border-radius: 4px;
            font-family: 'Consolas', 'Monaco', monospace;
            font-size: 0.85em;
        }}
        
        pre {{
            background: #2f3136;
            color: #f8f8f2;
            padding: 12px;
            border-radius: 6px;
            margin: 8px 0;
            overflow-x: auto;
            border-left: 4px solid #5865f2;
        }}
        
        pre code {{
            background: none;
            padding: 0;
        }}
        
        .attachment {{
            margin: 8px 0;
            background: #40444b;
            border-radius: 8px;
            padding: 12px;
            border-left: 4px solid #faa61a;
        }}
        
        .attachment-image {{
            max-width: 400px;
            max-height: 300px;
            border-radius: 4px;
            margin-bottom: 8px;
        }}
        
        .attachment-info {{
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        
        .attachment-name {{
            color: #00b0f4;
            font-weight: 500;
        }}
        
        .attachment-size {{
            color: #72767d;
            font-size: 12px;
        }}
        
        .embed {{
            background: #2f3136;
            border-radius: 4px;
            border-left: 4px solid #5865f2;
            margin: 8px 0;
            padding: 12px;
        }}
        
        .embed-title {{
            font-weight: 600;
            color: #ffffff;
            margin-bottom: 8px;
        }}
        
        .embed-description {{
            color: #dcddde;
            margin-bottom: 8px;
        }}
        
        .embed-fields {{
            display: grid;
            gap: 8px;
        }}
        
        .embed-field {{
            margin-bottom: 8px;
        }}
        
        .embed-field.inline {{
            display: inline-block;
            width: calc(33.33% - 8px);
            margin-right: 12px;
            vertical-align: top;
        }}
        
        .embed-field-name {{
            font-weight: 600;
            color: #ffffff;
            font-size: 14px;
            margin-bottom: 2px;
        }}
        
        .embed-field-value {{
            color: #dcddde;
            font-size: 14px;
        }}
        
        a {{
            color: #00b0f4;
            text-decoration: none;
        }}
        
        a:hover {{
            text-decoration: underline;
        }}
        
        .footer {{
            text-align: center;
            margin-top: 24px;
            padding: 20px;
            color: #72767d;
            font-size: 12px;
        }}
        
        @media (max-width: 768px) {{
            .container {{
                padding: 12px;
            }}
            
            .message {{
                padding: 12px;
            }}
            
            .message-avatar {{
                margin-right: 12px;
            }}
            
            .avatar {{
                width: 32px;
                height: 32px;
            }}
            
            .embed-field.inline {{
                width: 100%;
                margin-right: 0;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎫 Ticket Transcript</h1>
            <div class="header-info">
                <div class="info-item">
                    <div class="info-label">Channel</div>
                    <div class="info-value">#{self._escape_html(channel.name)}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Guild</div>
                    <div class="info-value">{self._escape_html(channel.guild.name)}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Ticket Ersteller</div>
                    <div class="info-value">{self._escape_html(ticket_owner.display_name) if ticket_owner else "Unbekannt"}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Kategorie</div>
                    <div class="info-value">{self._escape_html(ticket_type)}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Erstellt am</div>
                    <div class="info-value">{datetime.now().strftime("%d.%m.%Y %H:%M:%S")}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Nachrichten</div>
                    <div class="info-value">{len(messages)} Nachrichten</div>
                </div>
            </div>
        </div>
        
        <div class="messages">
            {messages_html if messages_html else '<div class="message"><div class="message-content"><div class="message-text"><em>Keine Nachrichten gefunden</em></div></div></div>'}
        </div>
        
        <div class="footer">
            <p>Generiert von Staiy-AI Community Bot • {datetime.now().strftime("%d.%m.%Y %H:%M:%S")}</p>
        </div>
    </div>
</body>
</html>
        '''
        
        return html

class ConfirmCloseView(discord.ui.View):
    """Bestätigung für Ticket-Schließung"""
    
    def __init__(self, guild_id: int):
        super().__init__(timeout=30)
        self.guild_id = guild_id
        self.config = TicketConfig(guild_id)
    
    @discord.ui.button(
        label="Ja, schließen",
        emoji="✅",
        style=discord.ButtonStyle.success
    )
    async def confirm_close(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Bestätigt die Schließung"""
        try:
            # Ticket-Daten für Log
            ticket_data = get_ticket_data(interaction.channel.id, interaction.guild.id)
            if ticket_data:
                owner = await interaction.client.fetch_user(ticket_data["Owner_ID"])
            else:
                owner = interaction.guild.get_member(interaction.user.id)

            # Log Embed
            log_embed = discord.Embed(
                title="🎫 Ticket geschlossen",
                description=f"**Ticket:** {interaction.channel.name}\n"
                           f"**Ersteller:** {owner.mention if owner else 'Unbekannt'}\n"
                           f"**Geschlossen von:** {interaction.user.mention}",
                color=COLORS["red"],
                timestamp=get_timestamp()
            )

            # Log senden
            try:
                log_channel_id = self.config.get('log_channel_id')
                if log_channel_id:
                    log_channel = interaction.guild.get_channel(log_channel_id)
                if log_channel:
                    try:
                        await log_channel.send(embed=log_embed)
                    except Exception as e:
                        logger.warning(f"Fehler beim Senden des Logs: {e}")
            except:
                pass

            # Aus DB entfernen
            kill_ticket(interaction.channel.id, interaction.guild.id)
            
            # Channel löschen
            await interaction.response.send_message(
                self.config.get('messages.ticket_closed', '🔒 Ticket wird geschlossen...'),
                ephemeral=True
            )
            
            await asyncio.sleep(3)
            await interaction.channel.delete(reason=f"Ticket geschlossen von {interaction.user.name}")
            
            logger.info(f"Ticket geschlossen: {interaction.channel.id} von {interaction.user.id}")
            
        except Exception as e:
            logger.error(f"Fehler beim Schließen des Tickets: {e}")
            await interaction.response.send_message(
                "❌ Fehler beim Schließen des Tickets!",
                ephemeral=True
            )

    @discord.ui.button(
        label="Abbrechen",
        emoji="❌",
        style=discord.ButtonStyle.secondary
    )
    async def cancel_close(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Bricht die Schließung ab"""
        await interaction.response.edit_message(
            content="❌ Schließung abgebrochen.",
            view=None
        )



class CategoryCreateModal(discord.ui.Modal):
    """Modal für das Erstellen neuer Kategorien"""
    
    def __init__(self, guild_id: int, panel_manager: PanelManager, bot):
        super().__init__(title="Neue Ticket-Kategorie erstellen")
        self.guild_id = guild_id
        self.config = TicketConfig(guild_id)
        self.panel_manager = panel_manager
        self.bot = bot
    
    category_id = discord.ui.TextInput(
        label="Kategorie-ID (eindeutig)",
        placeholder="z.B. custom_support, vip_help",
        required=True,
        max_length=50
    )
    
    category_name = discord.ui.TextInput(
        label="Kategorie-Name",
        placeholder="z.B. VIP Support",
        required=True,
        max_length=100
    )
    
    category_emoji = discord.ui.TextInput(
        label="Emoji",
        placeholder="🎯",
        required=True,
        max_length=10
    )
    
    category_description = discord.ui.TextInput(
        label="Beschreibung",
        placeholder="Kurze Beschreibung der Kategorie",
        required=True,
        style=discord.TextStyle.paragraph,
        max_length=200
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        cat_id = self.category_id.value.strip().lower().replace(' ', '_')
        name = self.category_name.value.strip()
        emoji = self.category_emoji.value.strip()
        description = self.category_description.value.strip()
        
        # Validation
        if not cat_id.replace('_', '').isalnum():
            await interaction.response.send_message(
                "❌ Kategorie-ID darf nur Buchstaben, Zahlen und Unterstriche enthalten!",
                ephemeral=True
            )
            return
        
        # Prüfe ob ID bereits existiert
        categories = self.config.get('categories', {})
        if cat_id in categories:
            await interaction.response.send_message(
                f"❌ Kategorie-ID `{cat_id}` existiert bereits!",
                ephemeral=True
            )
            return
        
        try:
            # Neue Kategorie erstellen
            new_category = {
                "name": name,
                "description": description,
                "emoji": emoji,
                "staff_ping": True,
                "category_id": None,
                "embed": {
                    "title": f"{name} Ticket",
                    "description": f"Willkommen in deinem {name} Ticket!\nEin Teammitglied wird sich in Kürze melden.",
                    "color": COLORS["blue"]
                }
            }
            
            # In Config speichern
            self.config.set(f'categories.{cat_id}', new_category)
            
            # Validierung nach dem Speichern
            saved_category = self.config.get(f'categories.{cat_id}')
            if not saved_category:
                logger.error(f"Kategorie '{cat_id}' wurde nicht korrekt gespeichert!")
                await interaction.response.send_message(
                    "❌ Fehler beim Speichern der Kategorie!",
                    ephemeral=True
                )
                return
            
            # Success Response
            embed = discord.Embed(
                title="✅ Kategorie erstellt!",
                description=f"**ID:** `{cat_id}`\n"
                           f"**Name:** {emoji} {name}\n"
                           f"**Beschreibung:** {description}",
                color=COLORS['green'],
                timestamp=get_timestamp()
            )
            
            embed.add_field(
                name="📝 Nächste Schritte",
                value="• Nutze `/ticket-category-edit` um weitere Einstellungen anzupassen\n"
                      "• Nutze `/ticket-panel-refresh` um das Panel zu aktualisieren",
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
            logger.info(f"Kategorie '{cat_id}' erfolgreich erstellt von {interaction.user.id}. Gespeicherte Daten: {saved_category}")
            
        except Exception as e:
            logger.error(f"Fehler beim Erstellen der Kategorie '{cat_id}': {e}", exc_info=True)
            await interaction.response.send_message(
                "❌ Fehler beim Erstellen der Kategorie!",
                ephemeral=True
            )

class CategorySelectView(discord.ui.View):
    """Select-Menu für Kategorie-Management"""
    
    def __init__(self, guild_id: int, panel_manager: PanelManager, bot, action: str):
        super().__init__(timeout=60)
        self.guild_id = guild_id
        self.config = TicketConfig(guild_id)
        self.panel_manager = panel_manager
        self.bot = bot
        self.action = action
        
        logger.info(f"🗑️ SCHRITT 3.1 - CategorySelectView.__init__ für Action: {action}")
        
        # Select-Menu erstellen
        options = []
        categories = self.config.get('categories', {})
        
        logger.info(f"🗑️ SCHRITT 3.2 - CategorySelectView Kategorien: {list(categories.keys())}")
        
        for cat_id, cat_data in categories.items():
            options.append(discord.SelectOption(
                label=cat_data['name'],
                value=cat_id,
                description=cat_data['description'][:100],
                emoji=cat_data['emoji']
            ))
            logger.debug(f"🗑️ SCHRITT 3.3 - Option erstellt: {cat_id} - {cat_data['name']}")
        
        logger.info(f"🗑️ SCHRITT 3.4 - {len(options)} Optionen erstellt")
        
        if options:
            select = CategorySelect(self.guild_id, self.panel_manager, self.bot, self.action, options)
            self.add_item(select)
            logger.info(f"🗑️ SCHRITT 3.5 - CategorySelect hinzugefügt")
        else:
            logger.warning(f"🗑️ SCHRITT 3.5 - FEHLER: Keine Optionen für CategorySelect!")

class CategorySelect(discord.ui.Select):
    """Select-Component für Kategorien"""
    
    def __init__(self, guild_id: int, panel_manager: PanelManager, bot, action: str, options: List[discord.SelectOption]):
        super().__init__(
            placeholder=f"Kategorie zum {action}en auswählen...",
            options=options,
            min_values=1,
            max_values=1
        )
        self.guild_id = guild_id
        self.config = TicketConfig(guild_id)
        self.panel_manager = panel_manager
        self.bot = bot
        self.action = action
    
    async def callback(self, interaction: discord.Interaction):
        selected_category = self.values[0]
        logger.info(f"🗑️ SCHRITT 6 - CategorySelect.callback: Kategorie '{selected_category}' ausgewählt für Action '{self.action}'")
        
        if self.action == "edit":
            # Edit Modal öffnen
            cat_data = self.config.get(f'categories.{selected_category}')
            modal = CategoryEditModal(self.guild_id, self.panel_manager, self.bot, selected_category, cat_data)
            await interaction.response.send_modal(modal)
            
        elif self.action == "remove":
            logger.info(f"🗑️ SCHRITT 7 - REMOVE ACTION: Bestätigung für Kategorie '{selected_category}'")
            
            # Bestätigung für Löschung
            cat_data = self.config.get(f'categories.{selected_category}')
            
            if not cat_data:
                logger.error(f"🗑️ SCHRITT 7 - FEHLER: Kategorie '{selected_category}' nicht in Config gefunden!")
                await interaction.response.send_message(
                    "❌ Kategorie nicht gefunden!",
                    ephemeral=True
                )
                return
            
            logger.info(f"🗑️ SCHRITT 8 - Kategorie-Daten gefunden: {cat_data['name']}")
            
            embed = discord.Embed(
                title="⚠️ Kategorie löschen",
                description=f"Möchtest du die Kategorie **{cat_data['emoji']} {cat_data['name']}** wirklich löschen?\n\n"
                           "⚠️ **Diese Aktion kann nicht rückgängig gemacht werden!**",
                color=COLORS['red']
            )
            
            logger.info(f"🗑️ SCHRITT 9 - ConfirmDeleteView wird erstellt...")
            view = ConfirmDeleteView(self.guild_id, self.panel_manager, selected_category)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            logger.info(f"🗑️ SCHRITT 10 - Bestätigungs-Dialog an User gesendet")

class CategoryEditModal(discord.ui.Modal):
    """Modal für das Bearbeiten von Kategorien"""
    
    def __init__(self, guild_id: int, panel_manager: PanelManager, bot, category_id: str, category_data: Dict):
        super().__init__(title=f"Kategorie '{category_data['name']}' bearbeiten")
        self.guild_id = guild_id
        self.config = TicketConfig(guild_id)
        self.panel_manager = panel_manager
        self.bot = bot
        self.category_id = category_id
        
        # Felder mit aktuellen Werten vorausfüllen
        self.category_name.default = category_data['name']
        self.category_emoji.default = category_data['emoji']
        self.category_description.default = category_data['description']
    
    category_name = discord.ui.TextInput(
        label="Kategorie-Name",
        placeholder="z.B. VIP Support",
        required=True,
        max_length=100
    )
    
    category_emoji = discord.ui.TextInput(
        label="Emoji",
        placeholder="🎯",
        required=True,
        max_length=10
    )
    
    category_description = discord.ui.TextInput(
        label="Beschreibung",
        placeholder="Kurze Beschreibung der Kategorie",
        required=True,
        style=discord.TextStyle.paragraph,
        max_length=200
    )
    
    embed_title = discord.ui.TextInput(
        label="Custom Embed-Titel (optional)",
        placeholder="Leer lassen für Standard-Titel",
        required=False,
        max_length=100
    )
    
    embed_description = discord.ui.TextInput(
        label="Custom Embed-Beschreibung (optional)",
        placeholder="Leer lassen für Standard-Beschreibung",
        required=False,
        style=discord.TextStyle.paragraph,
        max_length=500
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Aktuelle Kategorie-Daten holen
            current_data = self.config.get(f'categories.{self.category_id}')
            
            # Updates anwenden
            updated_data = current_data.copy()
            updated_data['name'] = self.category_name.value.strip()
            updated_data['emoji'] = self.category_emoji.value.strip()
            updated_data['description'] = self.category_description.value.strip()
            
            # Custom Embed falls angegeben
            if self.embed_title.value.strip():
                updated_data['embed']['title'] = self.embed_title.value.strip()
            
            if self.embed_description.value.strip():
                updated_data['embed']['description'] = self.embed_description.value.strip()
            
            # In Config speichern
            self.config.set(f'categories.{self.category_id}', updated_data)
            
            # Validierung nach dem Speichern
            saved_category = self.config.get(f'categories.{self.category_id}')
            if not saved_category or saved_category['name'] != updated_data['name']:
                logger.error(f"Kategorie '{self.category_id}' wurde nicht korrekt aktualisiert!")
                await interaction.response.send_message(
                    "❌ Fehler beim Speichern der Kategorie-Änderungen!",
                    ephemeral=True
                )
                return
            
            # Success Response
            embed = discord.Embed(
                title="✅ Kategorie aktualisiert!",
                description=f"**ID:** `{self.category_id}`\n"
                           f"**Name:** {updated_data['emoji']} {updated_data['name']}\n"
                           f"**Beschreibung:** {updated_data['description']}",
                color=COLORS['green'],
                timestamp=get_timestamp()
            )
            
            embed.add_field(
                name="📝 Tipp",
                value="Nutze `/ticket-panel-refresh` um das Panel zu aktualisieren!",
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
            logger.info(f"Kategorie '{self.category_id}' erfolgreich bearbeitet von {interaction.user.id}. Neue Daten: {saved_category}")
            
        except Exception as e:
            logger.error(f"Fehler beim Bearbeiten der Kategorie '{self.category_id}': {e}", exc_info=True)
            await interaction.response.send_message(
                "❌ Fehler beim Bearbeiten der Kategorie!",
                ephemeral=True
            )

class ConfirmDeleteView(discord.ui.View):
    """Bestätigung für Kategorie-Löschung"""
    
    def __init__(self, guild_id: int, panel_manager: PanelManager, category_id: str):
        super().__init__(timeout=30)
        self.guild_id = guild_id
        self.config = TicketConfig(guild_id)
        self.panel_manager = panel_manager
        self.category_id = category_id
    
    @discord.ui.button(
        label="Ja, löschen",
        emoji="🗑️",
        style=discord.ButtonStyle.danger
    )
    async def confirm_delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Bestätigt die Löschung"""
        logger.info(f"🗑️ SCHRITT 11 - CONFIRM DELETE: User {interaction.user.id} bestätigt Löschung von '{self.category_id}'")
        
        try:
            logger.info(f"🗑️ SCHRITT 12 - Config wird geladen für Kategorie '{self.category_id}'...")
            cat_data = self.config.get(f'categories.{self.category_id}')
            
            if not cat_data:
                logger.error(f"🗑️ SCHRITT 12 - FEHLER: Kategorie '{self.category_id}' nicht in Config!")
                await interaction.response.send_message(
                    "❌ Kategorie nicht gefunden!",
                    ephemeral=True
                )
                return
            
            logger.info(f"🗑️ SCHRITT 13 - Kategorie gefunden: {cat_data['name']}. Beginne Löschung...")
            
            # Aktuelle Kategorien vor Löschung anzeigen
            all_categories_before = self.config.get('categories', {})
            logger.info(f"🗑️ SCHRITT 14 - Kategorien VOR Löschung: {list(all_categories_before.keys())}")
            
            # Direkte Löschung
            categories = self.config.get('categories', {}).copy()  # Explizite Kopie
            logger.info(f"🗑️ SCHRITT 15 - Kopie erstellt mit {len(categories)} Kategorien")
            
            if self.category_id in categories:
                logger.info(f"🗑️ SCHRITT 16 - Kategorie '{self.category_id}' gefunden in Kopie. Lösche...")
                del categories[self.category_id]
                logger.info(f"🗑️ SCHRITT 17 - Kategorie aus Kopie gelöscht. Verbleibend: {list(categories.keys())}")
                
                logger.info(f"🗑️ SCHRITT 18 - Speichere neue Kategorien...")
                self.config.set('categories', categories)
                logger.info(f"🗑️ SCHRITT 19 - Config.set() aufgerufen")
                
                # Verifikation
                categories_after = self.config.get('categories', {})
                logger.info(f"🗑️ SCHRITT 20 - VERIFIKATION: Kategorien NACH Speichern: {list(categories_after.keys())}")
                
                if self.category_id in categories_after:
                    logger.error(f"🗑️ SCHRITT 20 - FEHLER: Kategorie '{self.category_id}' ist IMMER NOCH in der Config!")
                else:
                    logger.info(f"🗑️ SCHRITT 20 - ERFOLG: Kategorie '{self.category_id}' ist NICHT MEHR in der Config!")
                    
            else:
                logger.warning(f"🗑️ SCHRITT 16 - WARNUNG: Kategorie '{self.category_id}' war nicht in Config vorhanden")
            
            embed = discord.Embed(
                title="✅ Kategorie gelöscht!",
                description=f"Die Kategorie **{cat_data['emoji']} {cat_data['name']}** wurde erfolgreich gelöscht.",
                color=COLORS['green']
            )
            
            embed.add_field(
                name="📝 Tipp",
                value="Nutze `/ticket-panel-refresh` um das Panel zu aktualisieren!",
                inline=False
            )
            
            await interaction.response.edit_message(embed=embed, view=None)
            logger.info(f"🗑️ SCHRITT 21 - Success-Message an User gesendet")
            
            logger.info(f"🗑️ SCHRITT 22 - CATEGORY DELETE COMPLETE: '{self.category_id}' von User {interaction.user.id}")
            
        except Exception as e:
            logger.error(f"🗑️ FEHLER beim Löschen der Kategorie '{self.category_id}': {e}", exc_info=True)
            await interaction.response.send_message(
                "❌ Fehler beim Löschen der Kategorie!",
                ephemeral=True
            )
    
    @discord.ui.button(
        label="Abbrechen",
        emoji="❌",
        style=discord.ButtonStyle.secondary
    )
    async def cancel_delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Bricht die Löschung ab"""
        await interaction.response.edit_message(
            content="❌ Löschung abgebrochen.",
            embed=None,
            view=None
        )

class Ticket(commands.Cog):
    """Hauptklasse für das Ticket-System"""
    
    def __init__(self, bot):
        self.bot = bot
        self.panel_manager = PanelManager()
        
        # Auto-close Task starten
        self.auto_close_tickets.start()
        
        # Persistente Views beim Start wieder laden
        self.restore_persistent_views.start()
    
    def cog_unload(self):
        """Cleanup beim Entladen"""
        if hasattr(self, 'auto_close_tickets'):
            self.auto_close_tickets.cancel()
        if hasattr(self, 'restore_persistent_views'):
            self.restore_persistent_views.cancel()
    
    @tasks.loop(hours=1)
    async def auto_close_tickets(self):
        """Auto-close inaktive Tickets für alle Guilds"""
        try:
            # Iteriere durch alle Guilds des Bots
            for guild in self.bot.guilds:
                config = TicketConfig(guild.id)
                auto_close_hours = config.get('auto_close_time', 24)
                
                # Skip wenn Auto-Close deaktiviert
                if auto_close_hours <= 0:
                    continue
                    
                cutoff_time = datetime.now() - timedelta(hours=auto_close_hours)
                
                # Hier würdest du durch alle Tickets der Guild iterieren und prüfen
                # Das erfordert eine Erweiterung der DB-Struktur
                pass
            
        except Exception as e:
            logger.error(f"Fehler beim Auto-Close: {e}")
    
    @auto_close_tickets.before_loop
    async def before_auto_close(self):
        await self.bot.wait_until_ready()
    
    @tasks.loop(count=1)  # Läuft nur einmal beim Start
    async def restore_persistent_views(self):
        """Stellt persistente Views nach Bot-Neustart wieder her"""
        try:
            logger.info("🔄 PERSISTENT VIEWS RESTORE: Starte Wiederherstellung...")
            
            panel_restored_count = 0
            ticket_restored_count = 0
            failed_count = 0
            
            # 1. SCHRITT: Alle gespeicherten PANELS durchgehen
            for guild_id_str, panel_data in self.panel_manager.panels.items():
                try:
                    guild_id = int(guild_id_str)
                    guild = self.bot.get_guild(guild_id)
                    
                    if not guild:
                        logger.warning(f"🔄 Guild {guild_id} nicht gefunden, überspringe Panel")
                        failed_count += 1
                        continue
                    
                    channel = guild.get_channel(panel_data['channel_id'])
                    if not channel:
                        logger.warning(f"🔄 Channel {panel_data['channel_id']} in Guild {guild_id} nicht gefunden")
                        failed_count += 1
                        continue
                    
                    try:
                        message = await channel.fetch_message(panel_data['message_id'])
                        
                        # Neue persistente View erstellen und zu Message hinzufügen
                        view = TicketPanelView(guild_id)
                        await message.edit(view=view)
                        
                        logger.info(f"🔄 Panel-View wiederhergestellt: Guild {guild_id}, Channel {channel.name}")
                        panel_restored_count += 1
                        
                    except discord.NotFound:
                        logger.warning(f"🔄 Panel-Message {panel_data['message_id']} nicht gefunden in {channel.name}")
                        # Message existiert nicht mehr, Panel-Daten entfernen
                        self.panel_manager.remove_panel(guild_id)
                        failed_count += 1
                        
                    except discord.Forbidden:
                        logger.error(f"🔄 Keine Berechtigung für Message {panel_data['message_id']} in {channel.name}")
                        failed_count += 1
                        
                except Exception as guild_error:
                    logger.error(f"🔄 Fehler bei Guild {guild_id_str}: {guild_error}")
                    failed_count += 1
            
            # 2. SCHRITT: Alle TICKET-CONTROL-VIEWS wiederherstellen
            logger.info("🎫 TICKET CONTROL VIEWS RESTORE: Starte Wiederherstellung...")
            
            # Tickets aus der JSON-DB laden
            from functions import lib
            data = lib()
            
            if "tickets" in data:
                for guild_id_str, guild_tickets in data["tickets"].items():
                    try:
                        guild_id = int(guild_id_str)
                        guild = self.bot.get_guild(guild_id)
                        
                        if not guild:
                            logger.warning(f"🎫 Guild {guild_id} nicht gefunden für Ticket-Restore")
                            continue
                        
                        for channel_id_str, ticket_data in guild_tickets.items():
                            try:
                                channel_id = int(channel_id_str)
                                control_message_id = ticket_data.get('control_message_id')
                                
                                if not control_message_id:
                                    logger.debug(f"🎫 Ticket {channel_id} hat keine Control-Message-ID")
                                    continue
                                
                                # Channel holen
                                ticket_channel = guild.get_channel(channel_id)
                                if not ticket_channel:
                                    logger.warning(f"🎫 Ticket-Channel {channel_id} nicht gefunden")
                                    continue
                                
                                # Control-Message holen
                                try:
                                    control_message = await ticket_channel.fetch_message(control_message_id)
                                    
                                    # Ticket-Config für Kategorie bestimmen
                                    category = "support"  # Fallback
                                    if "Type" in ticket_data:
                                        # Versuche Kategorie aus Type zu ermitteln
                                        type_name = ticket_data["Type"]
                                        config = TicketConfig(guild_id)
                                        categories = config.get('categories', {})
                                        for cat_id, cat_data in categories.items():
                                            if cat_data['name'] == type_name:
                                                category = cat_id
                                                break
                                    
                                    # Control-View erstellen und wiederherstellen
                                    control_view = TicketControlView(guild_id, category)
                                    await control_message.edit(view=control_view)
                                    
                                    logger.info(f"🎫 Ticket-Control-View wiederhergestellt: Channel {ticket_channel.name}")
                                    ticket_restored_count += 1
                                    
                                except discord.NotFound:
                                    logger.warning(f"🎫 Control-Message {control_message_id} nicht gefunden in {ticket_channel.name}")
                                    # Control-Message-ID aus DB entfernen
                                    add_control_message_to_ticket(channel_id, guild_id, None)
                                    
                                except discord.Forbidden:
                                    logger.error(f"🎫 Keine Berechtigung für Control-Message {control_message_id}")
                                    
                            except Exception as ticket_error:
                                logger.error(f"🎫 Fehler bei Ticket {channel_id_str}: {ticket_error}")
                                
                    except Exception as guild_ticket_error:
                        logger.error(f"🎫 Fehler bei Guild-Tickets {guild_id_str}: {guild_ticket_error}")
            
            logger.info(f"🔄 PERSISTENT VIEWS RESTORE COMPLETE: {panel_restored_count} Panels, {ticket_restored_count} Tickets wiederhergestellt, {failed_count} fehlgeschlagen")
            
        except Exception as e:
            logger.error(f"🔄 FEHLER bei Persistent Views Restore: {e}", exc_info=True)
    
    @restore_persistent_views.before_loop
    async def before_restore_views(self):
        await self.bot.wait_until_ready()
        # Kurz warten damit alle Guilds geladen sind
        await asyncio.sleep(2)
    
    # Setup Commands (Admin-only)

    @app_commands.command(
        name="ticket-setup",
        description="Erstellt ein Ticket-Panel"
    )
    @app_commands.describe(
        channel="Channel für das Panel"
    )
    @app_commands.default_permissions(administrator=True)
    async def setup_panel(self, interaction: discord.Interaction, channel: Optional[discord.TextChannel] = None):
        """Erstellt ein Ticket-Panel"""
        config = TicketConfig(interaction.guild.id)
        
        if not channel:
            channel = interaction.channel
        
        try:
            # Panel Embed
            embed = discord.Embed(
                title=config.get('messages.panel_title', '🎫 Ticket System'),
                description=config.get('messages.panel_description', 'Wähle eine Kategorie:'),
                color=config.get('messages.panel_color', COLORS['blue']),
                timestamp=get_timestamp()
            )
            
            # Kategorien als Fields
            categories = config.get('categories', {})
            for cat_id, cat_data in categories.items():
                embed.add_field(
                    name=f"{cat_data['emoji']} {cat_data['name']}",
                    value=cat_data['description'],
                    inline=True
                )
            
            # View erstellen
            view = TicketPanelView(interaction.guild.id)
            
            # Panel senden
            message = await channel.send(embed=embed, view=view)
            
            # Panel speichern
            self.panel_manager.add_panel(interaction.guild.id, channel.id, message.id)
            
            await interaction.response.send_message(
                f"✅ Ticket-Panel erstellt in {channel.mention}!",
                ephemeral=True
            )
            
            logger.info(f"Ticket-Panel erstellt in {channel.id} von {interaction.user.id}")
            
        except Exception as e:
            logger.error(f"Fehler beim Erstellen des Panels: {e}")
            await interaction.response.send_message(
                "❌ Fehler beim Erstellen des Panels!",
                ephemeral=True
            )
    
    @app_commands.command(
        name="ticket-config",
        description="Zeigt die aktuelle Ticket-Konfiguration"
    )
    @app_commands.default_permissions(administrator=True)
    async def show_config(self, interaction: discord.Interaction):
        """Zeigt die Konfiguration"""
        config = TicketConfig(interaction.guild.id)
        
        embed = discord.Embed(
            title="🎫 Ticket Konfiguration",
            color=COLORS['blue'],
            timestamp=get_timestamp()
        )
        
        embed.add_field(
            name="⚙️ Allgemein",
            value=f"**Aktiviert:** {'✅' if config.get('enabled') else '❌'}\n"
                  f"**Max Tickets:** {config.get('max_tickets_per_user', 3)}\n"
                  f"**Auto-Close:** {config.get('auto_close_time', 24)}h\n"
                  f"**Transcripts:** {'✅' if config.get('transcript_enabled') else '❌'}",
            inline=False
        )
        
        # Staff-Rollen
        staff_roles = config.get('staff_role_ids', [])
        staff_mentions = []
        for role_id in staff_roles:
            role = interaction.guild.get_role(role_id)
            if role:
                staff_mentions.append(role.mention)
        
        embed.add_field(
            name="👥 Staff-Rollen",
            value=', '.join(staff_mentions) if staff_mentions else "Keine",
            inline=False
        )
        
        # Log-Channel
        log_channel_id = config.get('log_channel_id')
        log_channel = interaction.guild.get_channel(log_channel_id) if log_channel_id else None
        
        embed.add_field(
            name="📝 Log-Channel",
            value=log_channel.mention if log_channel else "Nicht gesetzt",
            inline=False
        )
        
        # Kategorien
        categories = config.get('categories', {})
        cat_list = []
        for cat_id, cat_data in categories.items():
            cat_list.append(f"{cat_data['emoji']} **{cat_data['name']}**")
        
        embed.add_field(
            name="📂 Kategorien",
            value='\n'.join(cat_list) if cat_list else "Keine",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    # Category Management Commands
    
    @app_commands.command(
        name="ticket-category-add",
        description="Erstellt eine neue Ticket-Kategorie"
    )
    @app_commands.default_permissions(administrator=True)
    async def add_category(self, interaction: discord.Interaction):
        """Erstellt eine neue Kategorie über Modal"""
        config = TicketConfig(interaction.guild.id)
        
        # Prüfe maximale Kategorien (Discord Button-Limit)
        categories = config.get('categories', {})
        if len(categories) >= 25:
            await interaction.response.send_message(
                "❌ Maximale Anzahl von Kategorien erreicht (25)!",
                ephemeral=True
            )
            return

        modal = CategoryCreateModal(interaction.guild.id, self.panel_manager, self.bot)
        await interaction.response.send_modal(modal)
    
    @app_commands.command(
        name="ticket-category-edit", 
        description="Bearbeitet eine bestehende Ticket-Kategorie"
    )
    @app_commands.default_permissions(administrator=True)
    async def edit_category(self, interaction: discord.Interaction):
        """Bearbeitet eine bestehende Kategorie"""
        config = TicketConfig(interaction.guild.id)
        
        categories = config.get('categories', {})
        if not categories:
            await interaction.response.send_message(
                "❌ Keine Kategorien vorhanden!",
                ephemeral=True
            )
            return

        view = CategorySelectView(interaction.guild.id, self.panel_manager, self.bot, "edit")
        await interaction.response.send_message(
            "🛠️ Wähle eine Kategorie zum Bearbeiten:",
            view=view,
            ephemeral=True
        )
    
    @app_commands.command(
        name="ticket-category-remove",
        description="Entfernt eine Ticket-Kategorie"
    )
    @app_commands.default_permissions(administrator=True)
    async def remove_category(self, interaction: discord.Interaction):
        """Entfernt eine Kategorie"""
        logger.info(f"🗑️ SCHRITT 1 - CATEGORY-REMOVE START: User {interaction.user.id} ({interaction.user.name}) in Guild {interaction.guild.id}")
        
        config = TicketConfig(interaction.guild.id)
        categories = config.get('categories', {})
        
        logger.info(f"🗑️ SCHRITT 2 - KATEGORIEN GELADEN: {list(categories.keys())} (Anzahl: {len(categories)})")
        
        if not categories:
            logger.warning(f"🗑️ SCHRITT 2 - FEHLER: Keine Kategorien in Guild {interaction.guild.id}")
            await interaction.response.send_message(
                "❌ Keine Kategorien vorhanden!",
                ephemeral=True
            )
            return

        logger.info(f"🗑️ SCHRITT 3 - CategorySelectView wird erstellt...")
        view = CategorySelectView(interaction.guild.id, self.panel_manager, self.bot, "remove")
        logger.info(f"🗑️ SCHRITT 4 - CategorySelectView erstellt mit {len(view.children)} Items")
        
        await interaction.response.send_message(
            "🗑️ Wähle eine Kategorie zum Entfernen:",
            view=view,
            ephemeral=True
        )
        logger.info(f"🗑️ SCHRITT 5 - Select-Menu an User gesendet")
    
    @app_commands.command(
        name="ticket-category-list",
        description="Zeigt alle Ticket-Kategorien"
    )
    @app_commands.default_permissions(administrator=True)
    async def list_categories(self, interaction: discord.Interaction):
        """Listet alle Kategorien auf"""
        config = TicketConfig(interaction.guild.id)
        
        categories = config.get('categories', {})
        
        if not categories:
            await interaction.response.send_message(
                "❌ Keine Kategorien vorhanden!\nNutze `/ticket-category-add` um eine zu erstellen.",
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title="📂 Ticket Kategorien",
            description=f"Insgesamt: {len(categories)}/25 Kategorien",
            color=COLORS['blue'],
            timestamp=get_timestamp()
        )
        
        for cat_id, cat_data in categories.items():
            embed.add_field(
                name=f"{cat_data['emoji']} {cat_data['name']}",
                value=f"**ID:** `{cat_id}`\n"
                      f"**Description:** {cat_data['description']}\n"
                      f"**Staff-Ping:** {'✅' if cat_data.get('staff_ping') else '❌'}\n"
                      f"**Kategorie:** {f'<#{cat_data["category_id"]}>' if cat_data.get('category_id') else 'Keine'}",
                inline=True
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(
        name="ticket-panel-refresh",
        description="Aktualisiert das Ticket-Panel mit neuen Kategorien"
    )
    @app_commands.default_permissions(administrator=True)
    async def refresh_panel(self, interaction: discord.Interaction):
        """Aktualisiert das Panel"""
        config = TicketConfig(interaction.guild.id)
        
        panel_data = self.panel_manager.get_panel(interaction.guild.id)
        if not panel_data:
            await interaction.response.send_message(
                "❌ Kein Panel gefunden! Nutze `/ticket-setup` um eins zu erstellen.",
                ephemeral=True
            )
            return
        
        try:
            channel = interaction.guild.get_channel(panel_data['channel_id'])
            if not channel:
                await interaction.response.send_message(
                    "❌ Panel-Channel nicht gefunden!",
                    ephemeral=True
                )
                return
            
            message = await channel.fetch_message(panel_data['message_id'])
            if not message:
                await interaction.response.send_message(
                    "❌ Panel-Nachricht nicht gefunden!",
                    ephemeral=True
                )
                return
            
            # Neues Embed erstellen
            embed = discord.Embed(
                title=config.get('messages.panel_title', '🎫 Ticket System'),
                description=config.get('messages.panel_description', 'Wähle eine Kategorie:'),
                color=config.get('messages.panel_color', COLORS['blue']),
                timestamp=get_timestamp()
            )
            
            # Kategorien hinzufügen
            categories = config.get('categories', {})
            logger.info(f"Panel-Refresh für Guild {interaction.guild.id}: {len(categories)} Kategorien gefunden: {list(categories.keys())}")
            
            for cat_id, cat_data in categories.items():
                embed.add_field(
                    name=f"{cat_data['emoji']} {cat_data['name']}",
                    value=cat_data['description'],
                    inline=True
                )
            
            # Falls keine Kategorien vorhanden
            if not categories:
                embed.add_field(
                    name="ℹ️ Keine Kategorien",
                    value="Nutze `/ticket-category-add` um Kategorien hinzuzufügen.",
                    inline=False
                )
            
            # Neue View erstellen (lädt automatisch frische Config)
            view = TicketPanelView(interaction.guild.id)
            
            # Message aktualisieren
            await message.edit(embed=embed, view=view)
            
            # Success Message mit Details
            embed_response = discord.Embed(
                title="✅ Panel aktualisiert!",
                description=f"**Kategorien:** {len(categories)}\n"
                           f"**Buttons:** {len(view.children)}",
                color=COLORS['green']
            )
            
            if categories:
                category_list = '\n'.join([f"• {cat_data['emoji']} {cat_data['name']}" for cat_id, cat_data in categories.items()])
                embed_response.add_field(
                    name="📋 Aktive Kategorien",
                    value=category_list[:1024],  # Discord Field Limit
                    inline=False
                )
            
            await interaction.response.send_message(embed=embed_response, ephemeral=True)
            
            logger.info(f"Panel erfolgreich aktualisiert von {interaction.user.id}. {len(categories)} Kategorien, {len(view.children)} Buttons.")
            
        except Exception as e:
            logger.error(f"Fehler beim Aktualisieren des Panels: {e}")
            await interaction.response.send_message(
                "❌ Fehler beim Aktualisieren des Panels!",
                ephemeral=True
            )
    
    @app_commands.command(
        name="ticket-panel-restore",
        description="Stellt alle Panel-Views nach Bot-Neustart wieder her"
    )
    @app_commands.default_permissions(administrator=True)
    async def restore_panels_manual(self, interaction: discord.Interaction):
        """Manueller Panel-Restore für Admins"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            restored_count = 0
            failed_count = 0
            
            # Nur Panel für diese Guild wiederherstellen
            panel_data = self.panel_manager.get_panel(interaction.guild.id)
            
            if not panel_data:
                await interaction.followup.send(
                    "❌ Kein Panel für diese Guild gefunden!",
                    ephemeral=True
                )
                return
            
            try:
                channel = interaction.guild.get_channel(panel_data['channel_id'])
                if not channel:
                    await interaction.followup.send(
                        f"❌ Panel-Channel nicht gefunden!",
                        ephemeral=True
                    )
                    return
                
                message = await channel.fetch_message(panel_data['message_id'])
                
                # Neue persistente View erstellen
                view = TicketPanelView(interaction.guild.id)
                await message.edit(view=view)
                
                embed = discord.Embed(
                    title="✅ Panel-Views wiederhergestellt!",
                    description=f"**Channel:** {channel.mention}\n"
                               f"**Buttons:** {len(view.children)}",
                    color=COLORS['green']
                )
                
                await interaction.followup.send(embed=embed, ephemeral=True)
                logger.info(f"🔄 Manual Panel-Restore von {interaction.user.id} in Guild {interaction.guild.id}")
                
            except discord.NotFound:
                self.panel_manager.remove_panel(interaction.guild.id)
                await interaction.followup.send(
                    "❌ Panel-Message nicht gefunden! Panel-Daten wurden entfernt.",
                    ephemeral=True
                )
                
        except Exception as e:
            logger.error(f"Fehler beim manuellen Panel-Restore: {e}")
            await interaction.followup.send(
                "❌ Fehler beim Wiederherstellen der Panel-Views!",
                ephemeral=True
            )
    
    @app_commands.command(
        name="ticket-settings",
        description="Konfiguriere allgemeine Ticket-Einstellungen"
    )
    @app_commands.describe(
        staff_role="Rolle die automatisch Zugriff auf alle Tickets bekommt",
        log_channel="Channel für Ticket-Logs",
        max_tickets="Maximale Tickets pro User (1-10)",
        auto_close_hours="Auto-Close Timer in Stunden (0 = deaktiviert)",
        transcripts_enabled="Transcript-Feature aktivieren"
    )
    @app_commands.default_permissions(administrator=True)
    async def ticket_settings(
        self, 
        interaction: discord.Interaction,
        staff_role: Optional[discord.Role] = None,
        log_channel: Optional[discord.TextChannel] = None,
        max_tickets: Optional[int] = None,
        auto_close_hours: Optional[int] = None,
        transcripts_enabled: Optional[bool] = None
    ):
        """Konfiguriert allgemeine Ticket-Einstellungen"""
        config = TicketConfig(interaction.guild.id)
        
        changes = []
        
        # Staff-Rolle hinzufügen/entfernen
        if staff_role:
            staff_roles = config.get('staff_role_ids', [])
            if staff_role.id not in staff_roles:
                staff_roles.append(staff_role.id)
                config.set('staff_role_ids', staff_roles)
                changes.append(f"✅ Staff-Rolle hinzugefügt: {staff_role.mention}")
            else:
                changes.append(f"ℹ️ {staff_role.mention} ist bereits eine Staff-Rolle")
        
        # Log-Channel setzen
        if log_channel:
            config.set('log_channel_id', log_channel.id)
            changes.append(f"✅ Log-Channel gesetzt: {log_channel.mention}")
        
        # Max Tickets validieren und setzen
        if max_tickets is not None:
            if 1 <= max_tickets <= 10:
                config.set('max_tickets_per_user', max_tickets)
                changes.append(f"✅ Max Tickets pro User: {max_tickets}")
            else:
                changes.append("❌ Max Tickets muss zwischen 1 und 10 liegen!")
        
        # Auto-Close Timer setzen
        if auto_close_hours is not None:
            if auto_close_hours >= 0:
                config.set('auto_close_time', auto_close_hours)
                if auto_close_hours == 0:
                    changes.append("✅ Auto-Close deaktiviert")
                else:
                    changes.append(f"✅ Auto-Close Timer: {auto_close_hours} Stunden")
                
                # Task neu starten falls nötig
                if hasattr(self, 'auto_close_tickets'):
                    self.auto_close_tickets.cancel()
                if auto_close_hours > 0:
                    self.auto_close_tickets.start()
            else:
                changes.append("❌ Auto-Close Timer muss >= 0 sein!")
        
        # Transcripts aktivieren/deaktivieren
        if transcripts_enabled is not None:
            config.set('transcript_enabled', transcripts_enabled)
            status = "aktiviert" if transcripts_enabled else "deaktiviert"
            changes.append(f"✅ Transcripts {status}")
        
        if not changes:
            await interaction.response.send_message(
                "ℹ️ Keine Änderungen vorgenommen!\n"
                "Gib mindestens einen Parameter an um Einstellungen zu ändern.",
                ephemeral=True
            )
            return
        
        # Änderungen anzeigen
        embed = discord.Embed(
            title="⚙️ Ticket-Einstellungen aktualisiert",
            description="\n".join(changes),
            color=COLORS['green'],
            timestamp=get_timestamp()
        )
        
        # Aktuelle Konfiguration anzeigen
        embed.add_field(
            name="📋 Aktuelle Konfiguration",
            value=f"**Max Tickets:** {config.get('max_tickets_per_user', 3)}\n"
                  f"**Auto-Close:** {config.get('auto_close_time', 24)}h\n"
                  f"**Transcripts:** {'✅' if config.get('transcript_enabled') else '❌'}\n"
                  f"**Staff-Rollen:** {len(config.get('staff_role_ids', []))}\n"
                  f"**Log-Channel:** {'✅' if config.get('log_channel_id') else '❌'}",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        logger.info(f"Ticket-Einstellungen geändert von {interaction.user.id}: {changes}")
    
    @app_commands.command(
        name="ticket-staff-remove",
        description="Entfernt eine Staff-Rolle"
    )
    @app_commands.describe(
        role="Die Rolle die entfernt werden soll"
    )
    @app_commands.default_permissions(administrator=True)
    async def remove_staff_role(self, interaction: discord.Interaction, role: discord.Role):
        """Entfernt eine Staff-Rolle"""
        config = TicketConfig(interaction.guild.id)
        
        staff_roles = config.get('staff_role_ids', [])
        
        if role.id not in staff_roles:
            await interaction.response.send_message(
                f"❌ {role.mention} ist keine Staff-Rolle!",
                ephemeral=True
            )
            return
        
        staff_roles.remove(role.id)
        config.set('staff_role_ids', staff_roles)
        
        await interaction.response.send_message(
            f"✅ Staff-Rolle {role.mention} entfernt!",
            ephemeral=True
        )
        
        logger.info(f"Staff-Rolle {role.id} entfernt von {interaction.user.id}")

    # Legacy Slash Commands für Kompatibilität
    
    @app_commands.command(
        name="close",
        description="Schließt das aktuelle Ticket"
    )
    async def close_ticket_slash(self, interaction: discord.Interaction):
        """Legacy Close Command"""
        config = TicketConfig(interaction.guild.id)
        
        if not is_ticket(interaction.channel.id, interaction.guild.id):
            await interaction.response.send_message(
                config.get('messages.not_a_ticket', '❌ Kein Ticket!'),
                ephemeral=True
            )
            return
        
        # Control View mit Close senden
        view = ConfirmCloseView(interaction.guild.id)
        await interaction.response.send_message(
            "⚠️ Möchtest du dieses Ticket wirklich schließen?",
            view=view,
            ephemeral=True
        )

    @app_commands.command(
        name="ticket-cleanup",
        description="Räumt Ghost-Tickets auf (Tickets deren Kanäle nicht mehr existieren)"
    )
    @app_commands.default_permissions(administrator=True)
    async def cleanup_ghost_tickets_slash(self, interaction: discord.Interaction):
        """Räumt Ghost-Tickets auf"""
        from functions import cleanup_ghost_tickets
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            cleaned_count = cleanup_ghost_tickets(interaction.guild.id, self.bot)
            
            if cleaned_count > 0:
                embed = discord.Embed(
                    title="🧹 Ghost-Ticket Cleanup",
                    description=f"✅ {cleaned_count} Ghost-Tickets erfolgreich entfernt!",
                    color=COLORS['green'],
                    timestamp=get_timestamp()
                )
                embed.add_field(
                    name="📋 Was wurde gemacht?",
                    value="Alle Ticket-Einträge deren Discord-Kanäle nicht mehr existieren wurden aus der Datenbank entfernt.",
                    inline=False
                )
            else:
                embed = discord.Embed(
                    title="🧹 Ghost-Ticket Cleanup",
                    description="✅ Keine Ghost-Tickets gefunden - alles sauber!",
                    color=COLORS['blue'],
                    timestamp=get_timestamp()
                )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Fehler beim Ghost-Ticket Cleanup: {e}")
            await interaction.followup.send(
                "❌ Fehler beim Cleanup der Ghost-Tickets!",
                ephemeral=True
            )

    @app_commands.command(
        name="ticket-debug-views",
        description="[DEBUG] Zeigt Status der persistenten Views und lädt sie neu"
    )
    @app_commands.default_permissions(administrator=True)
    async def debug_persistent_views(self, interaction: discord.Interaction):
        """Debug-Command für persistente Views"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            from functions import lib
            data = lib()
            
            # Panel-Status
            panel_data = self.panel_manager.get_panel(interaction.guild.id)
            panel_status = "✅ Aktiv" if panel_data else "❌ Nicht gefunden"
            
            # Ticket-Status
            tickets = data.get("tickets", {}).get(str(interaction.guild.id), {})
            ticket_count = len(tickets)
            control_messages = sum(1 for ticket in tickets.values() if ticket.get('control_message_id'))
            
            embed = discord.Embed(
                title="🔧 Persistent Views Debug",
                color=COLORS['blue'],
                timestamp=get_timestamp()
            )
            
            embed.add_field(
                name="📋 Panel Status",
                value=f"**Status:** {panel_status}\n"
                      f"**Channel:** {f'<#{panel_data["channel_id"]}>' if panel_data else 'N/A'}\n"
                      f"**Message-ID:** {panel_data['message_id'] if panel_data else 'N/A'}",
                inline=False
            )
            
            embed.add_field(
                name="🎫 Ticket Status",
                value=f"**Aktive Tickets:** {ticket_count}\n"
                      f"**Mit Control-Views:** {control_messages}/{ticket_count}\n"
                      f"**Missing Control-Views:** {ticket_count - control_messages}",
                inline=False
            )
            
            # Ticket-Details
            if tickets:
                ticket_details = []
                for channel_id, ticket_data in list(tickets.items())[:5]:  # Max 5 anzeigen
                    channel = interaction.guild.get_channel(int(channel_id))
                    channel_name = channel.name if channel else f"#{channel_id} (Gelöscht)"
                    control_status = "✅" if ticket_data.get('control_message_id') else "❌"
                    ticket_details.append(f"{control_status} {channel_name}")
                
                if len(tickets) > 5:
                    ticket_details.append(f"... und {len(tickets) - 5} weitere")
                
                embed.add_field(
                    name="🎫 Ticket-Details",
                    value="\n".join(ticket_details) if ticket_details else "Keine",
                    inline=False
                )
            
            embed.add_field(
                name="🔄 Nächste Schritte",
                value="• Nutze `/ticket-panel-restore` um Panel-Views zu reparieren\n"
                      "• Bot-Neustart lädt alle Views automatisch\n"
                      "• Bei Problemen: Ticket neu erstellen",
                inline=False
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Fehler beim Debug-Command: {e}")
            await interaction.followup.send(
                "❌ Fehler beim Laden der Debug-Informationen!",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(Ticket(bot))
