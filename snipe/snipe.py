from datetime import datetime, timedelta
import logging
from typing import Optional

import discord
from redbot.core import Config, checks, commands
from redbot.core.commands.converter import TimedeltaConverter

log = logging.getLogger("red.flare.snipe")


class Snipe(commands.Cog):
    """Snipe the last message from a server."""

    __version__ = "0.0.4"

    def format_help_for_context(self, ctx):
        """Thanks Sinbad."""
        pre_processed = super().format_help_for_context(ctx)
        return f"{pre_processed}\nCog Version: {self.__version__}"

    def __init__(self, bot):
        defaults_guild = {"toggle": False, "timeout": 600}
        self.config = Config.get_conf(self, identifier=95932766180343808, force_registration=True)
        self.config.register_guild(**defaults_guild)
        self.bot = bot
        self.cache = {}

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload):
        guild_id = payload.guild_id
        if guild_id is None:
            return
        if not await self.config.guild_from_id(guild_id).toggle():
            return
        message = payload.cached_message
        if message is None:
            log.info(
                f"Message {payload.message_id} not found in the cache, not adding to snipe cache. Guild ID: {guild_id} | Channel ID: {payload.channel_id}"
            )
            return
        if message.author.bot:
            return
        self.add_cache_entry(message, guild_id, payload.channel_id)

    def add_cache_entry(self, message, guild, channel):
        if guild not in self.cache:
            self.cache[guild] = {}
        self.cache[guild][channel] = {
            "content": message.content,
            "author": message.author.id,
            "timestamp": message.created_at,
        }

    @commands.cooldown(rate=1, per=5, type=commands.BucketType.channel)
    @commands.command()
    async def snipe(self, ctx, channel: Optional[discord.TextChannel] = None):
        """Shows the last deleted message from a specified channel."""
        channel = channel or ctx.channel
        if not await self.config.guild(ctx.guild).toggle():
            await ctx.send(
                f"Sniping is not allowed in this server! An admin may turn it on by typing the `{ctx.clean_prefix}snipeset enable` command."
            )
            return
        guildcache = self.cache.get(ctx.guild.id, None)
        if guildcache is None:
            await ctx.send("There's nothing to snipe!")
            return
        channelsnipe = guildcache.get(channel.id, None)
        if channelsnipe is None:
            await ctx.send("There's nothing to snipe!")
            return
        if datetime.utcnow() - channelsnipe["timestamp"] > timedelta(
            seconds=await self.config.guild(ctx.guild).timeout()
        ):
            await ctx.send("There's nothing to snipe!")
            return
        author = ctx.guild.get_member(channelsnipe["author"])
        if not channelsnipe["content"]:
            embed = discord.Embed(
                description="No message content.\nThe deleted message may have been an image or an embed.",
                timestamp=channelsnipe["timestamp"],
                color=ctx.author.color,
            )
        else:
            embed = discord.Embed(
                description=channelsnipe["content"],
                timestamp=channelsnipe["timestamp"],
                color=ctx.author.color,
            )
        embed.set_footer(text=f"Sniped by: {str(ctx.author)}")
        if author is None:
            embed.set_author(name="Removed Member")
        else:
            embed.set_author(name=f"{author} ({author.id})", icon_url=author.avatar_url)
        await ctx.send(embed=embed)

    @checks.admin()
    @commands.group()
    async def snipeset(self, ctx):
        """Group Command for Snipe Settings."""
        pass

    @snipeset.command()
    async def enable(self, ctx, state: bool):
        """Enable or disable sniping.
        
        State must be a bool or one of the following: True/False, On/Off, Y/N"""
        if state:
            await self.config.guild(ctx.guild).toggle.set(True)
            await ctx.send(f"Sniping has been enabled in {ctx.guild}.")
            return
        else:
            await self.config.guild(ctx.guild).toggle.set(False)
            await ctx.send(f"Sniping has been disabled in {ctx.guild}.")
            return

    @snipeset.command()
    async def time(
        self,
        ctx,
        *,
        time: TimedeltaConverter(
            minimum=timedelta(),
            maximum=timedelta(minutes=60),
            default_unit="seconds",
            allowed_units=["seconds", "minutes"],
        ),
    ):
        """ 
        Set the time before snipes expire.  
        
        Takes seconds or minutes, use the whole unit name with the amount.  
        Defaults to seconds if no unit name used.   
        """
        duration = time.total_seconds()
        await self.config.guild(ctx.guild).timeout.set(duration)
        await ctx.tick()
