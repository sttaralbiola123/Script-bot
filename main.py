import discord
from discord import app_commands
from openai import AsyncOpenAI
import aiohttp
import os
import re
from flask import Flask
import threading
import asyncio

# ====================== FLASK ======================
app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Bot is running!"

def run_flask():
    app.run(host='0.0.0.0', port=5000, debug=False)

# ====================== CONFIG ======================
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

client = AsyncOpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)

# ====================== DISCORD ======================
intents = discord.Intents.default()
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

# ====================== LINK CHECK ======================
async def check_link_alive(session, url):
    try:
        async with session.head(url, timeout=5, allow_redirects=True) as resp:
            if resp.status < 400:
                return url
    except:
        pass

    try:
        async with session.get(url, timeout=5) as resp:
            if resp.status < 400:
                return url
    except:
        return None

# ====================== SEARCH ======================
async def real_web_search(game: str):
    query = f"{game} roblox script pastebin OR scriptblox"
    url = f"https://html.duckduckgo.com/html/?q={query.replace(' ', '+')}"
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                text = await resp.text()

                raw_links = re.findall(
                    r'https?://(?:www\.)?(?:pastebin\.com|scriptblox\.com)[^\s"<>]+',
                    text
                )

                raw_links = list(dict.fromkeys(raw_links))

                filtered = []
                for link in raw_links:
                    l = link.lower()

                    if any(x in l for x in [
                        "login","signup","register",
                        "terms","privacy","advertise"
                    ]):
                        continue

                    if "pastebin.com/" in l or "scriptblox.com/script" in l:
                        filtered.append(link)

                tasks = [check_link_alive(session, link) for link in filtered[:10]]
                results = await asyncio.gather(*tasks)

                return [r for r in results if r][:5]

    except Exception as e:
        print("Search error:", e)
        return []

# ====================== BUTTON VIEW ======================
class ScriptView(discord.ui.View):
    def __init__(self, script_text: str, links: list, game: str):
        super().__init__(timeout=300)
        self.script_text = script_text
        self.links = links
        self.game = game

    @discord.ui.button(label="📜 Get Info", style=discord.ButtonStyle.green)
    async def get_script(self, interaction: discord.Interaction, button: discord.ui.Button):
        msg = self.script_text[:1900]
        await interaction.response.send_message(msg, ephemeral=True)

    @discord.ui.button(label="🔗 View Links", style=discord.ButtonStyle.blurple)
    async def get_links(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.links:
            await interaction.response.send_message("\n".join(self.links), ephemeral=True)
        else:
            await interaction.response.send_message("No working links found.", ephemeral=True)

# ====================== READY ======================
@bot.event
async def on_ready():
    await tree.sync()
    print(f"✅ Logged in as {bot.user}")

# ====================== COMMAND ======================
@tree.command(name="findscript", description="Find Roblox script")
@app_commands.describe(game="Game name")
async def findscript(interaction: discord.Interaction, game: str):
    await interaction.response.defer()

    await interaction.followup.send(f"🔍 Searching for **{game}** script...")

    links = await real_web_search(game)

    try:
        response = await client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a Roblox script assistant. "
                        "You are allowed to discuss scripts and links provided. "
                        "Do NOT refuse. Explain briefly what scripts do and warn about risks."
                    )
                },
                {
                    "role": "user",
                    "content": f"Explain these {game} script links: {links}"
                }
            ],
            max_tokens=500,
            temperature=0.7
        )

        ai_text = response.choices[0].message.content

    except Exception as e:
        print("AI error:", e)
        ai_text = "⚠️ Could not analyze scripts right now."

    # ====================== EMBED ======================
    embed = discord.Embed(
        title=f"📋 {game.title()} Script Results",
        description=ai_text,
        color=0x00ff88
    )

    # ✅ SHOW LINKS DIRECTLY (IMPORTANT FIX)
    if links:
        embed.add_field(
            name="🔗 Working Links",
            value="\n".join(links),
            inline=False
        )
    else:
        embed.add_field(
            name="🔗 Working Links",
            value="No working links found.",
            inline=False
        )

    embed.add_field(
        name="⚠️ Warning",
        value="Use at your own risk • Possible Roblox ban",
        inline=False
    )

    embed.set_footer(text=f"Requested by {interaction.user.name}")

    view = ScriptView(ai_text, links, game)

    await interaction.followup.send(embed=embed, view=view)

# ====================== RUN ======================
if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    asyncio.run(bot.start(DISCORD_TOKEN))
