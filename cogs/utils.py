from discord import Embed, Color, ApplicationContext, Forbidden, option, User
from discord.ext import commands

import json

from main import get_parameter, MyBot, db, time_now
from custom_errors import CodeLimitReached, UnknownCode, UnexpectedError


curA = db.cursor(buffered=True)
curB = db.cursor(buffered=True)
curC = db.cursor(buffered=True)


class Utils(commands.Cog):

    def __init__(self, bot_: MyBot):
        self.bot = bot_

    @commands.Cog.listener()
    async def on_ready(self):
        log_msg = "[COG] 'UtilsCog' has been loaded"
        self.bot.log_action(log_msg, self.bot.bot_logger)

    @commands.slash_command(name="redeem")
    async def redeem(self, ctx: ApplicationContext, code: str):
        with open("json/codes.json", "r", encoding="utf-8") as code_file:
            codes = json.load(code_file)

        if code not in codes:
            raise UnknownCode

        user = ctx.author
        user_id_str = str(user.id)

        now = time_now()

        code_data = codes[code]
        effect = code_data['effect']
        extra = code_data['extra']
        usage_limit = code_data['usage_limit'][0]
        usage_mode = code_data['usage_limit'][1]
        used_by = code_data['used_by']
        disabled = code_data['disabled']

        if disabled:
            raise UnknownCode

        if usage_mode == "each":
            if user_id_str in used_by:
                if len(used_by[user_id_str]) >= usage_limit != -1:
                    raise CodeLimitReached

                else:
                    used_by[user_id_str].append(round(now.timestamp()))
            else:
                used_by[user_id_str] = [round(now.timestamp())]

        else:
            if user_id_str in used_by:
                raise CodeLimitReached

            else:
                used_by[user_id_str] = [round(now.timestamp())]

        if effect == "money":
            curA.execute(f"UPDATE users SET coins = coins + {extra} WHERE discordID = {user.id}")
            emb = Embed(color=Color.green(),
                        description=f"You successfully redeemed the code `{code}`.\nYou received {extra} coins.")
            emb.set_footer(text=f"『Redeem』     『TyranBot』•『{get_parameter('version')}』")
            await ctx.respond(embed=emb, ephemeral=True)
            self.bot.log_action(f"[ECO] {user} got {extra} coins with code {code}", self.bot.eco_logger)

        elif effect == "DM":
            try:
                await user.send(extra)
                emb = Embed(color=Color.green(),
                            description=f"You successfully redeemed the code `{code}`.")
                emb.set_footer(text=f"『Redeem』     『TyranBot』•『{get_parameter('version')}』")
                await ctx.respond(embed=emb, ephemeral=True)
            except Forbidden:
                await ctx.respond(extra, ephemeral=True)

        elif effect == "role":
            guild = self.bot.get_guild(extra[0])
            role = guild.get_role(extra[1])
            member = guild.get_member(user.id)

            emb = Embed(color=Color.green(),
                        description=f"You successfully redeemed the code `{code}`.\n"
                                    f"You received the role {role.mention}")
            emb.set_footer(text=f"『Redeem』     『TyranBot』•『{get_parameter('version')}』")

            await member.add_roles(role)
            await ctx.respond(embed=emb, ephemeral=True)

        elif effect == "ping":
            channel = self.bot.get_channel(extra[0])
            emb = Embed(color=Color.dark_teal(), timestamp=now,
                        description=f"{user.mention} {extra[1]}")
            emb.set_footer(text=f"Code • {code}")
            await channel.send("@everyone", embed=emb)

            emb = Embed(color=Color.green(),
                        description=f"You successfully redeemed the code `{code}`.\n**You {extra[1]}.**")
            emb.set_footer(text=f"『Redeem』     『TyranBot』•『{get_parameter('version')}』")
            await ctx.respond(embed=emb, ephemeral=True)

        else:
            raise UnexpectedError

        # Save changes if there was no error
        db.commit()
        codes[code]['usage_count'] += 1
        with open("json/codes.json", "w", encoding="utf-8") as code_file:
            json.dump(codes, code_file, indent=2)

    @commands.slash_command(name="server")
    async def server(self, ctx: ApplicationContext):
        guild = ctx.guild
        emb = Embed(color=Color.blurple(), description=guild.description)
        emb.set_author(name=f"{guild.name}")

        icon = guild.icon
        if icon is not None:
            emb.set_thumbnail(url=icon.url)
        emb.set_footer(text=f"『Server』     『TyranBot』•『{get_parameter('version')}』")

        channel_amt = len(guild.channels)
        category_amt = len(guild.categories)
        member_amt = guild.member_count
        role_amt = len(guild.roles)
        owner = guild.owner
        boost_lvl = guild.premium_tier
        boost_amt = guild.premium_subscription_count
        creation_date = guild.created_at

        boost_txt = f"Boosted to level {boost_lvl} with {boost_amt} boost{'s' if boost_amt > 1 else ''}" if boost_amt > 0 else "No boost"

        emb.add_field(name=f"Description", inline=False,
                      value=f"<:owner:1117147820235952199> Owned by {owner.mention} \n"
                            f"<:calendar:988081833252106302> Created <t:{round(creation_date.timestamp())}:R> \n"
                            f"<:boost_color:1117147819095109672> {boost_txt}")

        emb.add_field(name=f"Population", inline=True,
                      value=f"<:user:1117145041102712986> **{member_amt}** members \n"
                            f"<:role_amt:1117146149103620128> **{role_amt}** roles")

        emb.add_field(name=f"Structure", inline=True,
                      value=f"<:hashtag:1117140322674290730> **{channel_amt}** channels\n"
                            f"<:category:1117142612722335875> **{category_amt}** categories")

        await ctx.respond(embed=emb, ephemeral=True)

    @commands.slash_command(name="about")
    async def about(self, ctx: ApplicationContext):
        emb = Embed(color=Color.blurple(), description=f"The TyranBot is private multi-purpose bot. Its main functionality"
                                                       f" is its economic system but it also handle moderation and has the"
                                                       f" ambition to be able to do a lot more in the future.")

        emb.set_author(name="TyranBot").set_thumbnail(url=self.bot.user.avatar.url)

        emb.add_field(name="Statistics", value=f"Soon:tm:", inline=False)

        emb.add_field(name="Credits", inline=False,
                      value=f"Owner and developer : <@444504367152889877>\n"
                            f"Icons : [Icons server](https://discord.gg/9AtkECMX2P)")

        emb.set_footer(text=f"『About』     『TyranBot』•『{get_parameter('version')}』")

        await ctx.respond(embed=emb, ephemeral=True)

    @commands.slash_command(name="avatar")
    @option(name="user")
    async def avatar(self, ctx: ApplicationContext, user: User = None):
        if user is None:
            user = ctx.author
        await ctx.respond(user.display_avatar, ephemeral=True)

    @commands.slash_command(name="banner")
    @option(name="user")
    async def banner(self, ctx: ApplicationContext, user: User = None):
        if user is None:
            user = ctx.author
        banner = user.banner
        if banner is None:
            await ctx.respond(f"{user.mention} doesn't have a banner")
        else:
            await ctx.respond(user.banner, ephemeral=True)


def setup(bot_):
    bot_.add_cog(Utils(bot_))
