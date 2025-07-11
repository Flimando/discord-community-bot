"""
Counter Extension für den Discord Bot

Hauptfunktionen:
1. Counter-Setup
    - /setup-counter command
    - Channel-Tracking
    - Counter-Status speichern

2. Counter-Logik
    - Nachrichten auf Zahlen prüfen
    - Reihenfolge prüfen
    - User-Wechsel prüfen
    - Reaktionen senden
    - Fehlermeldungen bei falscher Zahl
"""

import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import logging
import asyncio

# Datenbank für Counter-Status
COUNTER_DB = "counter_data.json"

# Logger Setup
logger = logging.getLogger(__name__)

class Counter(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.counter_data = self.load_counter_data()
        
    def load_counter_data(self):
        """Lädt die Counter-Daten aus der JSON-Datei"""
        try:
            if os.path.exists(COUNTER_DB):
                with open(COUNTER_DB, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Fehler beim Laden der Counter-Daten: {e}")
            return {}
        
    def save_counter_data(self):
        """Speichert die Counter-Daten in die JSON-Datei"""
        try:
            with open(COUNTER_DB, 'w', encoding='utf-8') as f:
                json.dump(self.counter_data, f, indent=4, ensure_ascii=False)
        except IOError as e:
            logger.error(f"Fehler beim Speichern der Counter-Daten: {e}")
            
    @app_commands.command(
        name="setup-counter",
        description="Richtet den Counter in diesem Channel ein"
    )
    @app_commands.default_permissions(administrator=True)
    async def setup_counter(self, interaction: discord.Interaction):
        """Richtet den Counter in einem Channel ein"""
        try:
            guild_id = str(interaction.guild_id)
            channel_id = str(interaction.channel_id)
            
            # Erstelle Guild-Eintrag falls nicht vorhanden
            if guild_id not in self.counter_data:
                self.counter_data[guild_id] = {}
                
            # Prüfe ob Channel bereits Counter hat
            if channel_id in self.counter_data[guild_id]:
                await interaction.response.send_message("Der Counter ist in diesem Channel bereits aktiv!", ephemeral=True)
                return
                
            self.counter_data[guild_id][channel_id] = {
                "current_number": 0,
                "last_user": None,
                "active": True
            }
            self.save_counter_data()
            
            await interaction.response.send_message("Counter wurde erfolgreich eingerichtet! Beginnt bei 1.", ephemeral=True)
            logger.info(f"Counter setup in guild {guild_id}, channel {channel_id}")
            
        except Exception as e:
            logger.error(f"Fehler beim Setup des Counters: {e}")
            try:
                await interaction.response.send_message("❌ Fehler beim Einrichten des Counters!", ephemeral=True)
            except discord.InteractionResponded:
                await interaction.followup.send("❌ Fehler beim Einrichten des Counters!", ephemeral=True)
        
    @commands.Cog.listener()
    async def on_message(self, message):
        """Prüft jede Nachricht auf Counter-Relevanz"""
        if message.author.bot:
            return
            
        # Ignoriere DMs (keine Guild)
        if not message.guild:
            return
            
        guild_id = str(message.guild.id)
        channel_id = str(message.channel.id)
        
        # Prüfe ob Server und Channel Counter-aktiv sind
        if (guild_id not in self.counter_data or 
            channel_id not in self.counter_data[guild_id] or 
            not self.counter_data[guild_id][channel_id]["active"]):
            return
            
        try:
            number = int(message.content)
        except ValueError:
            return
            
        counter_info = self.counter_data[guild_id][channel_id]
        expected_number = counter_info["current_number"] + 1
        
        try:
            # Prüfe ob die Zahl korrekt ist
            if number == expected_number:
                # Prüfe ob der User sich wiederholt
                if message.author.id == counter_info["last_user"]:
                    await self._send_failure_message(message, "hat die Kette ruiniert! Der nächste muss bei 1 anfangen!")
                    counter_info["current_number"] = 0
                    counter_info["last_user"] = None
                else:
                    # Alles korrekt, füge Checkmark hinzu
                    try:
                        await message.add_reaction("✅")
                    except discord.Forbidden:
                        logger.warning(f"Keine Berechtigung für Reaction in {guild_id}/{channel_id}")
                    except discord.HTTPException as e:
                        logger.warning(f"HTTP-Fehler bei Reaction: {e}")
                    except Exception as e:
                        logger.error(f"Unerwarteter Fehler bei Reaction: {e}")
                        
                    counter_info["current_number"] = number
                    counter_info["last_user"] = message.author.id
            else:
                await self._send_failure_message(message, "hat die Kette ruiniert! Der nächste muss bei 1 anfangen!")
                counter_info["current_number"] = 0
                counter_info["last_user"] = None
                
            self.save_counter_data()

        except Exception as e:
            logger.error(f"Fehler beim Verarbeiten der Counter-Nachricht: {e}")
    
    async def _send_failure_message(self, message: discord.Message, failure_text: str):
        """Sendet eine Fehlermeldung mit Error-Handling"""
        try:
            await message.channel.send(f"{message.author.mention} {failure_text}")
        except discord.Forbidden:
            logger.warning(f"Keine Berechtigung zum Senden in {message.guild.id}/{message.channel.id}")
        except discord.HTTPException as e:
            logger.warning(f"HTTP-Fehler beim Senden der Fehlermeldung: {e}")
        except Exception as e:
            logger.error(f"Unerwarteter Fehler beim Senden der Fehlermeldung: {e}")

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Counter(bot)) 