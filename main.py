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

# ====================== DISCORD BOT ======================
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

client = AsyncOpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)

intents = discord.Intents.default()
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

async def real_web_search(game: str):
    query = f"{game} roblox script delta OR solara OR wave 2026"
    url = f"https://html.duckduckgo.com/html/?q={query.replace(' ', '+')}"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            text = await resp.text()
            links = re.findall(r'https?://(?:www\.)?(pastebin\.com|scriptblox\.com)[^\s"<>]+', text)
            return list(dict.fromkeys(links))[:6]

class ScriptView(discord.ui.View):
    def __init__(self, script_text: str, links: list, game: str):
        super().__init__(timeout=300)
        self.script_text = script_text
        self.links = links or []
        self.game = game

    @discord.ui.button(label="📜 Get Full Script", style=discord.ButtonStyle.green)
    async def get_script(self, interaction: discord.Interaction, button: discord.ui.Button):
        content = self.script_text[:1950] + "..." if len(self.script_text) > 1950 else self.script_text
        await interaction.response.send_message(f"```lua\n{content}\n```", ephemeral=True)

    @discord.ui.button(label="🔗 View Links", style=discord.ButtonStyle.blurple)
    async def get_links(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.links:
            msg = "\n".join([f"• {link}" for link in self.links])
            await interaction.response.send_message(msg, ephemeral=True)
        else:
            await interaction.response.send_message("No direct links found.", ephemeral=True)

    @discord.ui.button(label="🔄 Search Again", style=discord.ButtonStyle.gray)
    async def search_again(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(f"🔍 Type `/findscript {self.game}` to search again!", ephemeral=True)

@bot.event
async def on_ready():
    await tree.sync()
    print(f"✅ Bot is online: {bot.user} | Free Tier Mode")

@tree.command(name="findscript", description="Search for Roblox script")
@app_commands.describe(game="Game name (e.g. Rivals, Arsenal)")
async def findscript(interaction: discord.Interaction, game: str):
    await interaction.response.defer()
    await interaction.followup.send(f"🔍 Searching for **{game}** script...")

    found_links = await real_web_search(game)

    try:
        response = await client.chat.completions.create(
            model="llama-3.1-8b-instant",   # ← Best for Free Tier (mabilis at stable)
            messages=[
                {"role": "system", "content": "You are a helpful Roblox script finder. Provide useful info and always warn users about risks."},
                {"role": "user", "content": f"Find working {game} script for Delta executor. Links: {found_links}"}
            ],
            max_tokens=800,
            temperature=0.7
        )
        ai_result = response.choices[0].message.content
    except Exception as e:
        ai_result = f"Could not generate result right now.\nError: {str(e)}"

    # Beautiful Embed
    embed = discord.Embed(
        title=f"📋 {game.title()} Script Results",
        description=ai_result[:2000] + "..." if len(ai_result) > 2000 else ai_result,
        color=0x00ff88
    )
    embed.add_field(name="🔍 Links Found", value=f"**{len(found_links)}** possible sources", inline=True)
    embed.add_field(name="🎮 Supported Executors", value="Delta • Solara • Wave", inline=True)
    embed.add_field(
        name="⚠️ Important Warning", 
        value="• Scan every script on VirusTotal\n• Use at your own risk\n• High risk of Roblox ban",
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
