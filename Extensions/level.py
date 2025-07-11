from discord.ext import commands
import discord
from discord import app_commands
from functions import *
from config import COLORS
import random
import math
from asyncio import TimeoutError
import logging

# Logger Setup
logger = logging.getLogger(__name__)

class Level(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(
        name="setup-level",
        description="Richtet das Level-System in diesem Server ein"
    )
    @app_commands.default_permissions(administrator=True)
    async def setup_level(self, interaction: discord.Interaction, announcement_channel: discord.TextChannel = None):
        """Richtet das Level-System ein"""
        try:
            guild_id = str(interaction.guild_id)
        
            # Prüfe ob Level-System bereits aktiv ist
            if is_level_system_enabled(guild_id):
                embed = discord.Embed(
                    title="❌ Level-System bereits aktiv",
                    description="Das Level-System ist bereits in diesem Server eingerichtet!",
                    color=COLORS["red"]
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            # Initialisiere Level-System
            init_level_system(guild_id, str(announcement_channel.id) if announcement_channel else None)
            
            embed = discord.Embed(
                title="✅ Level-System eingerichtet!",
                description="Das Level-System wurde erfolgreich aktiviert!\n\n"
                           "**Features:**\n"
                           "• XP sammeln durch Nachrichten\n"
                           "• Automatische Level-Ups\n"
                           "• Leaderboard\n"
                           "• Channel-Blocking möglich\n\n"
                           f"**Announcement-Channel:** {announcement_channel.mention if announcement_channel else 'Keiner gesetzt'}",
                color=COLORS["green"]
            )
        
            await interaction.response.send_message(embed=embed, ephemeral=True)
            logger.info(f"Level-System setup in guild {guild_id}")
            
        except Exception as e:
            logger.error(f"Fehler beim Setup des Level-Systems: {e}")
            try:
                await interaction.response.send_message("❌ Fehler beim Einrichten des Level-Systems!", ephemeral=True)
            except discord.InteractionResponded:
                await interaction.followup.send("❌ Fehler beim Einrichten des Level-Systems!", ephemeral=True)
    
    @app_commands.command(
        name="change-announcement",
        description="Ändert den Channel für Level-Up Benachrichtigungen"
    )
    @app_commands.default_permissions(administrator=True)
    async def change_announcement(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """Ändert den Announcement-Channel"""
        try:
            guild_id = str(interaction.guild_id)
            
            if not is_level_system_enabled(guild_id):
                embed = discord.Embed(
                    title="❌ Level-System nicht aktiv",
                    description="Richte zuerst das Level-System mit `/setup-level` ein!",
                    color=COLORS["red"]
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            # Hole aktuellen Channel
            current_channel_id = get_announcement_channel(guild_id)
            current_channel_info = ""
            
            if current_channel_id:
                try:
                    current_channel = interaction.guild.get_channel(int(current_channel_id))
                    if current_channel:
                        current_channel_info = f"\n**Vorheriger Channel:** {current_channel.mention}"
                    else:
                        current_channel_info = f"\n**Vorheriger Channel:** Unbekannter Channel ({current_channel_id})"
                except (ValueError, TypeError) as e:
                    logger.warning(f"Fehler beim Verarbeiten der Channel-ID {current_channel_id}: {e}")
                    current_channel_info = f"\n**Vorheriger Channel:** Unbekannter Channel ({current_channel_id})"
            else:
                current_channel_info = "\n**Vorheriger Channel:** Keiner gesetzt"
            
            if set_announcement_channel(guild_id, str(channel.id)):
                embed = discord.Embed(
                    title="✅ Announcement-Channel geändert!",
                    description=f"Level-Up Benachrichtigungen werden jetzt in {channel.mention} gesendet!" + current_channel_info,
                    color=COLORS["green"]
                )
                logger.info(f"Announcement-Channel changed in guild {guild_id} to {channel.id}")
            else:
                embed = discord.Embed(
                    title="❌ Fehler",
                    description="Fehler beim Ändern des Announcement-Channels!",
                    color=COLORS["red"]
                )
                logger.error(f"Failed to change announcement channel in guild {guild_id}")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Fehler beim Ändern des Announcement-Channels: {e}")
            try:
                await interaction.response.send_message("❌ Fehler beim Ändern des Announcement-Channels!", ephemeral=True)
            except discord.InteractionResponded:
                await interaction.followup.send("❌ Fehler beim Ändern des Announcement-Channels!", ephemeral=True)
    
    @app_commands.command(
        name="block-channel",
        description="Blockiert einen Channel für XP-Gewinn (Anti-Spam)"
    )
    @app_commands.default_permissions(administrator=True)
    async def block_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """Blockiert einen Channel für XP-Gewinn"""
        try:
            guild_id = str(interaction.guild_id)
        
            if not is_level_system_enabled(guild_id):
                embed = discord.Embed(
                    title="❌ Level-System nicht aktiv",
                    description="Richte zuerst das Level-System mit `/setup-level` ein!",
                    color=COLORS["red"]
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            if block_channel_for_xp(guild_id, str(channel.id)):
                embed = discord.Embed(
                    title="🚫 Channel blockiert!",
                    description=f"**{channel.mention}** ist jetzt für XP-Gewinn blockiert!\n\n"
                            f"User können in diesem Channel keine XP mehr sammeln.",
                    color=COLORS["orange"]
                )
                logger.info(f"Channel {channel.id} blocked for XP in guild {guild_id}")
            else:
                embed = discord.Embed(
                    title="ℹ️ Channel bereits blockiert",
                    description=f"**{channel.mention}** ist bereits für XP blockiert!",
                    color=COLORS["blue"]
                )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
                
        except Exception as e:
            logger.error(f"Fehler beim Blockieren des Channels: {e}")
            try:
                await interaction.response.send_message("❌ Fehler beim Blockieren des Channels!", ephemeral=True)
            except discord.InteractionResponded:
                await interaction.followup.send("❌ Fehler beim Blockieren des Channels!", ephemeral=True)
    
    @app_commands.command(
        name="unblock-channel",
        description="Entblockiert einen Channel für XP-Gewinn"
    )
    @app_commands.default_permissions(administrator=True)
    async def unblock_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """Entblockiert einen Channel für XP-Gewinn"""
        try:
            guild_id = str(interaction.guild_id)
            
            if not is_level_system_enabled(guild_id):
                embed = discord.Embed(
                    title="❌ Level-System nicht aktiv",
                    description="Richte zuerst das Level-System mit `/setup-level` ein!",
                    color=COLORS["red"]
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            if unblock_channel_for_xp(guild_id, str(channel.id)):
                embed = discord.Embed(
                    title="✅ Channel entblockiert!",
                    description=f"**{channel.mention}** ist jetzt wieder für XP-Gewinn freigegeben!\n\n"
                            f"User können in diesem Channel wieder XP sammeln.",
                    color=COLORS["green"]
                )
                logger.info(f"Channel {channel.id} unblocked for XP in guild {guild_id}")
            else:
                embed = discord.Embed(
                    title="ℹ️ Channel nicht blockiert",
                    description=f"**{channel.mention}** war nicht für XP blockiert!",
                    color=COLORS["blue"]
                )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
                
        except Exception as e:
            logger.error(f"Fehler beim Entblockieren des Channels: {e}")
            try:
                await interaction.response.send_message("❌ Fehler beim Entblockieren des Channels!", ephemeral=True)
            except discord.InteractionResponded:
                await interaction.followup.send("❌ Fehler beim Entblockieren des Channels!", ephemeral=True)
    
    @app_commands.command(
        name="list-blocked",
        description="Zeigt alle blockierten Channels an"
    )
    @app_commands.default_permissions(administrator=True)
    async def list_blocked(self, interaction: discord.Interaction):
        """Zeigt alle blockierten Channels an"""
        try:
            guild_id = str(interaction.guild_id)
            
            if not is_level_system_enabled(guild_id):
                embed = discord.Embed(
                    title="❌ Level-System nicht aktiv",
                    description="Richte zuerst das Level-System mit `/setup-level` ein!",
                    color=COLORS["red"]
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            blocked_channels = get_blocked_channels(guild_id)
            
            if not blocked_channels:
                embed = discord.Embed(
                    title="📋 Blockierte Channels",
                    description="Keine Channels sind für XP blockiert!",
                    color=COLORS["green"]
                )
            else:
                embed = discord.Embed(
                    title="🚫 Blockierte Channels",
                    description="Folgende Channels sind für XP-Gewinn blockiert:",
                    color=COLORS["orange"]
                )
                
                blocked_list = ""
                for channel_id in blocked_channels:
                    try:
                        channel = interaction.guild.get_channel(int(channel_id))
                        if channel:
                            blocked_list += f"• {channel.mention}\n"
                        else:
                            blocked_list += f"• Unbekannter Channel ({channel_id})\n"
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Fehler beim Verarbeiten der Channel-ID {channel_id}: {e}")
                        blocked_list += f"• Unbekannter Channel ({channel_id})\n"
                
                embed.add_field(
                    name="Blockierte Channels",
                    value=blocked_list,
                    inline=False
                )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
                
        except Exception as e:
            logger.error(f"Fehler beim Anzeigen der blockierten Channels: {e}")
            try:
                await interaction.response.send_message("❌ Fehler beim Anzeigen der blockierten Channels!", ephemeral=True)
            except discord.InteractionResponded:
                await interaction.followup.send("❌ Fehler beim Anzeigen der blockierten Channels!", ephemeral=True)
    
    @app_commands.command(
        name="level",
        description="Zeigt dein aktuelles Level und XP an"
    )
    async def level(self, interaction: discord.Interaction):
        """Zeigt das Level des Users an"""
        guild_id = str(interaction.guild_id)
        user_id = str(interaction.user.id)
        
        if not is_level_system_enabled(guild_id):
            embed = discord.Embed(
                title="❌ Level-System nicht aktiv",
                description="Das Level-System ist in diesem Server nicht aktiviert!",
                color=COLORS["red"]
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        user_data = get_user_level_data(guild_id, user_id)
        if not user_data:
            embed = discord.Embed(
                title="❌ Fehler",
                description="Deine Level-Daten konnten nicht geladen werden!",
                color=COLORS["red"]
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Fortschritt zum nächsten Level berechnen
        current_xp, needed_xp, percentage = get_progress_to_next_level(user_data["xp"])
        
        # Progress Bar erstellen
        progress_bar_length = 20
        filled_length = int((percentage / 100) * progress_bar_length)
        progress_bar = "█" * filled_length + "░" * (progress_bar_length - filled_length)
        
        embed = discord.Embed(
            title=f"🎮 Level von {interaction.user.display_name}",
            color=COLORS["violet"]
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        
        embed.add_field(
            name="📊 Statistiken",
            value=f"**Level:** {user_data['level']}\n"
                  f"**XP:** {user_data['xp']:,}\n"
                  f"**Nachrichten:** {user_data['messages']:,}",
            inline=True
        )
        
        embed.add_field(
            name="📈 Fortschritt",
            value=f"**Nächstes Level:** {user_data['level'] + 1}\n"
                  f"**XP benötigt:** {needed_xp:,}\n"
                  f"**Fortschritt:** {percentage:.1f}%",
            inline=True
        )
        
        embed.add_field(
            name="🎯 Progress Bar",
            value=f"`{progress_bar}`\n"
                  f"`{current_xp:,} / {needed_xp:,} XP`",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(
        name="rank",
        description="Zeigt das Level eines anderen Users an"
    )
    async def rank(self, interaction: discord.Interaction, user: discord.Member):
        """Zeigt das Level eines anderen Users an"""
        guild_id = str(interaction.guild_id)
        user_id = str(user.id)
        
        if not is_level_system_enabled(guild_id):
            embed = discord.Embed(
                title="❌ Level-System nicht aktiv",
                description="Das Level-System ist in diesem Server nicht aktiviert!",
                color=COLORS["red"]
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        user_data = get_user_level_data(guild_id, user_id)
        if not user_data:
            embed = discord.Embed(
                title="❌ Keine Daten",
                description=f"{user.display_name} hat noch keine Level-Daten!",
                color=COLORS["orange"]
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Fortschritt zum nächsten Level berechnen
        current_xp, needed_xp, percentage = get_progress_to_next_level(user_data["xp"])
        
        # Progress Bar erstellen
        progress_bar_length = 20
        filled_length = int((percentage / 100) * progress_bar_length)
        progress_bar = "█" * filled_length + "░" * (progress_bar_length - filled_length)
        
        embed = discord.Embed(
            title=f"🎮 Level von {user.display_name}",
            color=COLORS["violet"]
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        
        embed.add_field(
            name="📊 Statistiken",
            value=f"**Level:** {user_data['level']}\n"
                  f"**XP:** {user_data['xp']:,}\n"
                  f"**Nachrichten:** {user_data['messages']:,}",
            inline=True
        )
        
        embed.add_field(
            name="📈 Fortschritt",
            value=f"**Nächstes Level:** {user_data['level'] + 1}\n"
                  f"**XP benötigt:** {needed_xp:,}\n"
                  f"**Fortschritt:** {percentage:.1f}%",
            inline=True
        )
        
        embed.add_field(
            name="🎯 Progress Bar",
            value=f"`{progress_bar}`\n"
                  f"`{current_xp:,} / {needed_xp:,} XP`",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(
        name="leaderboard",
        description="Zeigt die Top 10 User des Servers an"
    )
    async def leaderboard(self, interaction: discord.Interaction):
        """Zeigt die Server-Rangliste an"""
        guild_id = str(interaction.guild_id)
        
        if not is_level_system_enabled(guild_id):
            embed = discord.Embed(
                title="❌ Level-System nicht aktiv",
                description="Das Level-System ist in diesem Server nicht aktiviert!",
                color=COLORS["red"]
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        leaderboard_data = get_leaderboard(guild_id, 10)
        
        if not leaderboard_data:
            embed = discord.Embed(
                title="📊 Server-Rangliste",
                description="Noch keine Level-Daten vorhanden!",
                color=COLORS["blue"]
            )
            await interaction.response.send_message(embed=embed)
            return
        
        embed = discord.Embed(
            title="🏆 Server-Rangliste",
            description="Die Top 10 User nach XP",
            color=COLORS["violet"]
        )
        
        # Medaillen-Emojis
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        
        leaderboard_text = ""
        for i, (user_id, user_data) in enumerate(leaderboard_data):
            try:
                user = await self.bot.fetch_user(int(user_id))
                username = user.display_name
                avatar = user.display_avatar.url
            except:
                username = f"Unbekannter User ({user_id})"
                avatar = None
            
            medal = medals[i] if i < len(medals) else f"{i+1}."
            leaderboard_text += f"{medal} **{username}**\n"
            leaderboard_text += f"   Level {user_data['level']} • {user_data['xp']:,} XP • {user_data['messages']:,} Nachrichten\n\n"
            
            # Avatar für Embed setzen (erster User)
            if i == 0 and avatar:
                embed.set_thumbnail(url=avatar)
        
        embed.add_field(
            name="🏅 Rangliste",
            value=leaderboard_text,
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(
        name="show-announcement",
        description="Zeigt den aktuellen Level-Up Announcement-Channel an"
    )
    @app_commands.default_permissions(administrator=True)
    async def show_announcement(self, interaction: discord.Interaction):
        """Zeigt den aktuellen Announcement-Channel an"""
        guild_id = str(interaction.guild_id)
        
        if not is_level_system_enabled(guild_id):
            embed = discord.Embed(
                title="❌ Level-System nicht aktiv",
                description="Richte zuerst das Level-System mit `/setup-level` ein!",
                color=COLORS["red"]
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        announcement_channel_id = get_announcement_channel(guild_id)
        
        if announcement_channel_id:
            try:
                channel = interaction.guild.get_channel(int(announcement_channel_id))
                if channel:
                    embed = discord.Embed(
                        title="📢 Level-Up Announcement-Channel",
                        description=f"**Aktueller Channel:** {channel.mention}\n\n"
                                   f"Level-Up Benachrichtigungen werden in diesem Channel gesendet.",
                        color=COLORS["blue"]
                    )
                else:
                    embed = discord.Embed(
                        title="⚠️ Ungültiger Announcement-Channel",
                        description=f"Der gespeicherte Channel ({announcement_channel_id}) existiert nicht mehr!\n\n"
                                   f"Verwende `/change-announcement` um einen neuen Channel zu setzen.",
                        color=COLORS["orange"]
                    )
            except:
                embed = discord.Embed(
                    title="⚠️ Fehler beim Laden des Channels",
                    description=f"Der gespeicherte Channel ({announcement_channel_id}) konnte nicht geladen werden!\n\n"
                               f"Verwende `/change-announcement` um einen neuen Channel zu setzen.",
                    color=COLORS["orange"]
                )
        else:
            embed = discord.Embed(
                title="📢 Level-Up Announcement-Channel",
                description="**Kein Channel gesetzt!**\n\n"
                           f"Level-Up Benachrichtigungen werden im jeweiligen Channel gesendet, wo das Level-Up passiert.\n\n"
                           f"Verwende `/change-announcement` um einen spezifischen Channel zu setzen.",
                color=COLORS["blue"]
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @commands.Cog.listener()
    async def on_message(self, message):
        """Event für XP-Vergabe bei Nachrichten"""
        # Ignoriere Bot-Nachrichten
        if message.author.bot:
            return
        
        # Ignoriere DMs
        if not message.guild:
            return
        
        guild_id = str(message.guild.id)
        user_id = str(message.author.id)
        channel_id = str(message.channel.id)
        
        # Prüfe ob Level-System aktiviert ist
        if not is_level_system_enabled(guild_id):
            return
        
        # Prüfe ob Channel blockiert ist
        if is_channel_blocked(guild_id, channel_id):
            return
        
        # Prüfe Cooldown
        if not can_gain_xp(guild_id, user_id):
            return
        
        # Zufällige XP zwischen 1-15
        xp_gained = random.randint(1, 15)
        
        # XP hinzufügen und prüfen ob Level-Up
        level_up = add_xp_to_user(guild_id, user_id, xp_gained)
        
        if level_up:
            # Level-Up Benachrichtigung
            user_data = get_user_level_data(guild_id, user_id)
            new_level = user_data["level"]
            
            embed = discord.Embed(
                title="🎉 Level-Up!",
                description=f"**{message.author.display_name}** ist auf Level **{new_level}** aufgestiegen!",
                color=COLORS["green"]
            )
            embed.set_thumbnail(url=message.author.display_avatar.url)
            embed.add_field(
                name="📊 Neue Statistiken",
                value=f"**Level:** {new_level}\n"
                      f"**XP:** {user_data['xp']:,}\n"
                      f"**Nachrichten:** {user_data['messages']:,}",
                inline=True
            )
            
            # Sende Benachrichtigung in Announcement-Channel oder aktuellen Channel
            announcement_channel_id = get_announcement_channel(guild_id)
            if announcement_channel_id:
                try:
                    channel = message.guild.get_channel(int(announcement_channel_id))
                    if channel:
                        await channel.send(embed=embed)
                        return
                except (ValueError, TypeError, discord.Forbidden, discord.HTTPException) as e:
                    logger.warning(f"Fehler beim Senden in Announcement-Channel {announcement_channel_id}: {e}")
                    # Fallback zum aktuellen Channel
                    
            # Fallback: Sende in aktuellen Channel wenn kein Announcement-Channel gesetzt
            try:
                await message.channel.send(embed=embed)
            except (discord.Forbidden, discord.HTTPException) as e:
                logger.warning(f"Fehler beim Senden der Level-Up Nachricht in {message.channel.id}: {e}")
    
    @app_commands.command(
        name="block-channels",
        description="Blockiert mehrere Channels für XP-Gewinn (Anti-Spam)"
    )
    @app_commands.default_permissions(administrator=True)
    async def block_channels(self, interaction: discord.Interaction, channels: str):
        """Blockiert mehrere Channels für XP-Gewinn"""
        guild_id = str(interaction.guild_id)
        
        if not is_level_system_enabled(guild_id):
            embed = discord.Embed(
                title="❌ Level-System nicht aktiv",
                description="Richte zuerst das Level-System mit `/setup-level` ein!",
                color=COLORS["red"]
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Parse Channel-IDs aus dem String
        channel_ids = []
        for item in channels.split():
            # Entferne # und < > falls vorhanden
            clean_item = item.strip().replace('#', '').replace('<', '').replace('>', '')
            if clean_item.isdigit():
                channel_ids.append(clean_item)
        
        if not channel_ids:
            embed = discord.Embed(
                title="❌ Keine gültigen Channels",
                description="Gib gültige Channel-IDs oder Mentions an!\n\n**Beispiel:**\n`/block-channels #spam #bot-commands 123456789`",
                color=COLORS["red"]
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Blockiere alle Channels
        blocked_channels = []
        already_blocked = []
        invalid_channels = []
        
        for channel_id in channel_ids:
            try:
                channel = interaction.guild.get_channel(int(channel_id))
                if channel:
                    if block_channel_for_xp(guild_id, channel_id):
                        blocked_channels.append(channel)
                    else:
                        already_blocked.append(channel)
                else:
                    invalid_channels.append(channel_id)
            except:
                invalid_channels.append(channel_id)
        
        # Erstelle Response Embed
        embed = discord.Embed(
            title="🚫 Channel-Blocking Ergebnis",
            color=COLORS["orange"]
        )
        
        if blocked_channels:
            blocked_list = "\n".join([f"• {channel.mention}" for channel in blocked_channels])
            embed.add_field(
                name=f"✅ Neu blockiert ({len(blocked_channels)})",
                value=blocked_list,
                inline=False
            )
        
        if already_blocked:
            already_list = "\n".join([f"• {channel.mention}" for channel in already_blocked])
            embed.add_field(
                name=f"ℹ️ Bereits blockiert ({len(already_blocked)})",
                value=already_list,
                inline=False
            )
        
        if invalid_channels:
            invalid_list = "\n".join([f"• {channel_id}" for channel_id in invalid_channels])
            embed.add_field(
                name=f"❌ Ungültige Channels ({len(invalid_channels)})",
                value=invalid_list,
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(
        name="unblock-channels",
        description="Entblockiert mehrere Channels für XP-Gewinn"
    )
    @app_commands.default_permissions(administrator=True)
    async def unblock_channels(self, interaction: discord.Interaction, channels: str):
        """Entblockiert mehrere Channels für XP-Gewinn"""
        guild_id = str(interaction.guild_id)
        
        if not is_level_system_enabled(guild_id):
            embed = discord.Embed(
                title="❌ Level-System nicht aktiv",
                description="Richte zuerst das Level-System mit `/setup-level` ein!",
                color=COLORS["red"]
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Parse Channel-IDs aus dem String
        channel_ids = []
        for item in channels.split():
            # Entferne # und < > falls vorhanden
            clean_item = item.strip().replace('#', '').replace('<', '').replace('>', '')
            if clean_item.isdigit():
                channel_ids.append(clean_item)
        
        if not channel_ids:
            embed = discord.Embed(
                title="❌ Keine gültigen Channels",
                description="Gib gültige Channel-IDs oder Mentions an!\n\n**Beispiel:**\n`/unblock-channels #spam #bot-commands 123456789`",
                color=COLORS["red"]
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Entblockiere alle Channels
        unblocked_channels = []
        not_blocked = []
        invalid_channels = []
        
        for channel_id in channel_ids:
            try:
                channel = interaction.guild.get_channel(int(channel_id))
                if channel:
                    if unblock_channel_for_xp(guild_id, channel_id):
                        unblocked_channels.append(channel)
                    else:
                        not_blocked.append(channel)
                else:
                    invalid_channels.append(channel_id)
            except:
                invalid_channels.append(channel_id)
        
        # Erstelle Response Embed
        embed = discord.Embed(
            title="✅ Channel-Unblocking Ergebnis",
            color=COLORS["green"]
        )
        
        if unblocked_channels:
            unblocked_list = "\n".join([f"• {channel.mention}" for channel in unblocked_channels])
            embed.add_field(
                name=f"✅ Entblockiert ({len(unblocked_channels)})",
                value=unblocked_list,
                inline=False
            )
        
        if not_blocked:
            not_list = "\n".join([f"• {channel.mention}" for channel in not_blocked])
            embed.add_field(
                name=f"ℹ️ Nicht blockiert ({len(not_blocked)})",
                value=not_list,
                inline=False
            )
        
        if invalid_channels:
            invalid_list = "\n".join([f"• {channel_id}" for channel_id in invalid_channels])
            embed.add_field(
                name=f"❌ Ungültige Channels ({len(invalid_channels)})",
                value=invalid_list,
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(
        name="block-all-except",
        description="Blockiert alle Channels außer den angegebenen (Whitelist)"
    )
    @app_commands.default_permissions(administrator=True)
    async def block_all_except(self, interaction: discord.Interaction, allowed_channels: str):
        """Blockiert alle Channels außer den angegebenen"""
        guild_id = str(interaction.guild_id)
        
        if not is_level_system_enabled(guild_id):
            embed = discord.Embed(
                title="❌ Level-System nicht aktiv",
                description="Richte zuerst das Level-System mit `/setup-level` ein!",
                color=COLORS["red"]
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Parse erlaubte Channel-IDs
        allowed_channel_ids = []
        for item in allowed_channels.split():
            clean_item = item.strip().replace('#', '').replace('<', '').replace('>', '')
            if clean_item.isdigit():
                allowed_channel_ids.append(clean_item)
        
        if not allowed_channel_ids:
            embed = discord.Embed(
                title="❌ Keine gültigen Channels",
                description="Gib mindestens einen erlaubten Channel an!\n\n**Beispiel:**\n`/block-all-except #general #chat`",
                color=COLORS["red"]
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Bestätigung Embed
        allowed_list = ""
        for channel_id in allowed_channel_ids:
            try:
                channel = interaction.guild.get_channel(int(channel_id))
                if channel:
                    allowed_list += f"• {channel.mention}\n"
                else:
                    allowed_list += f"• Unbekannter Channel ({channel_id})\n"
            except:
                allowed_list += f"• Unbekannter Channel ({channel_id})\n"
        
        embed = discord.Embed(
            title="⚠️ Bestätigung erforderlich",
            description="**Diese Aktion wird ALLE Channels blockieren außer:**\n" + allowed_list + "\n**Möchtest du fortfahren?**\n\n"
                       f"**Antwort mit:**\n`ja` - Bestätigen\n`nein` - Abbrechen",
            color=COLORS["orange"]
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # Warte auf Bestätigung
        def check(m):
            return m.author == interaction.user and m.channel == interaction.channel and m.content.lower() in ['ja', 'nein']
        
        try:
            response = await self.bot.wait_for('message', timeout=30.0, check=check)
            
            if response.content.lower() == 'ja':
                # Hole alle Text-Channels des Servers
                all_text_channels = [channel for channel in interaction.guild.text_channels]
                
                # Blockiere alle außer den erlaubten
                blocked_count = 0
                for channel in all_text_channels:
                    if str(channel.id) not in allowed_channel_ids:
                        if block_channel_for_xp(guild_id, str(channel.id)):
                            blocked_count += 1
                
                # Bestätigung
                confirm_embed = discord.Embed(
                    title="✅ Mass-Blocking abgeschlossen!",
                    description=f"**{blocked_count} Channels** wurden blockiert!\n\n"
                               f"**Erlaubte Channels:**\n{allowed_list}\n"
                               f"**Verwende `/list-blocked` um alle blockierten Channels zu sehen.**",
                    color=COLORS["green"]
                )
                await interaction.followup.send(embed=confirm_embed, ephemeral=True)
                
            else:
                cancel_embed = discord.Embed(
                    title="❌ Abgebrochen",
                    description="Das Mass-Blocking wurde abgebrochen.",
                    color=COLORS["red"]
                )
                await interaction.followup.send(embed=cancel_embed, ephemeral=True)
                
        except TimeoutError:
            timeout_embed = discord.Embed(
                title="⏰ Zeitüberschreitung",
                description="Die Bestätigung ist abgelaufen. Das Mass-Blocking wurde abgebrochen.",
                color=COLORS["red"]
            )
            await interaction.followup.send(embed=timeout_embed, ephemeral=True)

async def setup(bot):
    """Fügt den Level-Cog zum Bot hinzu"""
    await bot.add_cog(Level(bot))
        