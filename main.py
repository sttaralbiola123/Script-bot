import discord
from discord import app_commands
from openai import AsyncOpenAI
import aiohttp
import os
import re
from flask import Flask
import threading
import asyncio

# ====================== FLASK (for Render) ======================
app = Flask(__name__)

@app.route('/')
def home():
    return "<h1>✅ Roblox Script Bot is Running on Render!</h1>"

def run_flask():
    app.run(host='0.0.0.0', port=5000, debug=False)

# ====================== CONFIG ======================
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

client = AsyncOpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)

# ====================== DISCORD SETUP ======================
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


# ====================== SEARCH FUNCTION ======================
async def real_web_search(game: str):
    query = f"{game} roblox script delta OR solara OR wave"
    url = f"https://html.duckduckgo.com/html/?q={query.replace(' ', '+')}"
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                text = await resp.text()

                # Extract links
                raw_links = re.findall(
                    r'https?://(?:www\.)?(?:pastebin\.com|scriptblox\.com)[^\s"<>]+',
                    text
                )

                # Remove duplicates
                raw_links = list(dict.fromkeys(raw_links))

                # =========================
                # SMART FILTERING
                # =========================
                filtered_links = []
                for link in raw_links:
                    link_lower = link.lower()

                    # ❌ Skip junk
                    if any(x in link_lower for x in [
                        "login", "signup", "register",
                        "terms", "privacy", "advertise"
                    ]):
                        continue

                    # ✅ Keep only useful pages
                    if "pastebin.com/" in link_lower or "scriptblox.com/script" in link_lower:
                        filtered_links.append(link)

                # =========================
                # CHECK IF ALIVE
                # =========================
                tasks = [check_link_alive(session, link) for link in filtered_links[:10]]
                results = await asyncio.gather(*tasks)

                alive_links = [r for r in results if r]

                return alive_links[:5]

    except Exception as e:
        print("Search error:", e)
        return []

# ====================== BUTTON VIEW ======================
class ScriptView(discord.ui.View):
    def __init__(self, script_text: str, links: list, game: str):
        super().__init__(timeout=300)
        self.script_text = script_text
        self.links = links or []
        self.game = game

    @discord.ui.button(label="📜 Get Full Script", style=discord.ButtonStyle.green)
    async def get_script(self, interaction: discord.Interaction, button: discord.ui.Button):
        content = self.script_text[:1900]
        await interaction.response.send_message(f"```lua\n{content}\n```", ephemeral=True)

    @discord.ui.button(label="🔗 View Links", style=discord.ButtonStyle.blurple)
    async def get_links(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.links:
            msg = "\n".join([f"• {link}" for link in self.links])
        else:
            msg = "No working links found."
        await interaction.response.send_message(msg, ephemeral=True)

    @discord.ui.button(label="🔄 Search Again", style=discord.ButtonStyle.gray)
    async def search_again(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            f"🔍 Type `/findscript {self.game}` to search again!",
            ephemeral=True
        )

# ====================== EVENTS ======================
@bot.event
async def on_ready():
    await tree.sync()
    print(f"✅ Bot is online: {bot.user}")

# ====================== COMMAND ======================
@tree.command(name="findscript", description="Search for Roblox script")
@app_commands.describe(game="Game name (e.g. Rivals, Arsenal)")
async def findscript(interaction: discord.Interaction, game: str):
    await interaction.response.defer()

    await interaction.followup.send(f"🔍 Searching for **{game}** script...")

    found_links = await real_web_search(game)

    try:
        print("Using model: llama-3.1-8b-instant")

        response = await client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {
                    "role": "system",
                    "content": "You are a Roblox script finder. Provide info only, no fake scripts. Warn about risks."
                },
                {
                    "role": "user",
                    "content": f"Find working {game} script. Links: {found_links}"
                }
            ],
            max_tokens=700,
            temperature=0.7
        )

        ai_result = response.choices[0].message.content

    except Exception as e:
        print("Groq error:", e)
        ai_result = f"❌ Could not generate result.\nError: {str(e)}"

    # ====================== EMBED ======================
    embed = discord.Embed(
        title=f"📋 {game.title()} Script Results",
        description=ai_result[:2000],
        color=0x00ff88
    )

    embed.add_field(
        name="🔍 Links Found",
        value=f"**{len(found_links)}** working sources",
        inline=True
    )

    embed.add_field(
        name="🎮 Supported Executors",
        value="Delta • Solara • Wave",
        inline=True
    )

    embed.add_field(
        name="⚠️ Important Warning",
        value="• Scan scripts on VirusTotal\n• Use at your own risk\n• High risk of Roblox ban",
        inline=False
    )

    embed.set_footer(text=f"Requested by {interaction.user.name} • Groq Free Tier")
    embed.timestamp = discord.utils.utcnow()

    view = ScriptView(script_text=ai_result, links=found_links, game=game)

    await interaction.followup.send(embed=embed, view=view)

# ====================== RUN ======================
if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    asyncio.run(bot.start(DISCORD_TOKEN))
