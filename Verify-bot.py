import os 
import discord
from discord import app_commands
from discord.ext import commands
import json
from server import keep_alive


intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

def load_settings():
    if os.path.exists("settings.json"):
        with open("settings.json", "r") as file:
            return json.load(file)
    return {}

def save_settings(settings):
    with open("settings.json", "w") as file:
        json.dump(settings, file, indent=4)

settings = load_settings()

class SetupView(discord.ui.View):
    def __init__(self, roles, channels):
        super().__init__()

        role_chunk = roles[:25]
        channel_chunk = channels[:25]

        select_role = discord.ui.Select(
            placeholder="Select a role...",
            options=[discord.SelectOption(label=role.name, value=str(role.id)) for role in role_chunk]
        )
        select_role.callback = self.role_callback
        self.add_item(select_role)

        select_channel = discord.ui.Select(
            placeholder="Select a notification channel...",
            options=[discord.SelectOption(label=channel.name, value=str(channel.id)) for channel in channel_chunk]
        )
        select_channel.callback = self.channel_callback
        self.add_item(select_channel)

        submit_button = discord.ui.Button(label="Submit", style=discord.ButtonStyle.green, custom_id="submit_button")
        submit_button.callback = self.submit_button_callback
        self.add_item(submit_button)

        cancel_button = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.red, custom_id="cancel_button")
        cancel_button.callback = self.cancel_button_callback
        self.add_item(cancel_button)

    async def role_callback(self, interaction: discord.Interaction):
        role_id = int(interaction.data["values"][0])
        guild_id = str(interaction.guild.id)
        if guild_id not in settings:
            settings[guild_id] = {}
        settings[guild_id]["role_id"] = role_id
        save_settings(settings)
        await interaction.response.send_message(f"Role has been set to <@&{role_id}>", ephemeral=True)

    async def channel_callback(self, interaction: discord.Interaction):
        channel_id = int(interaction.data["values"][0])
        guild_id = str(interaction.guild.id)
        if guild_id not in settings:
            settings[guild_id] = {}
        settings[guild_id]["notification_channel_id"] = channel_id
        save_settings(settings)
        await interaction.response.send_message(f"Notification channel has been set to <#{channel_id}>", ephemeral=True)

    async def submit_button_callback(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild.id)
        if guild_id in settings and "role_id" in settings[guild_id] and "notification_channel_id" in settings[guild_id]:
            await interaction.response.send_message(f"""```diff
+ Setup completed successfully!
```""", ephemeral=True)
        else:
            await interaction.response.send_message("Setup is incomplete. Please select both a role and a notification channel.", ephemeral=True)

    async def cancel_button_callback(self, interaction: discord.Interaction):
        await interaction.response.send_message("Setup has been cancelled.", ephemeral=True)

class VerifyModal(discord.ui.Modal, title="Verify User"):
    def __init__(self):
        super().__init__()
        self.name = discord.ui.TextInput(label="Name", placeholder="กรอกชื่อของคุณ")
        self.gender = discord.ui.TextInput(label="Gender", placeholder="กรอกเพศของคุณ")
        self.age = discord.ui.TextInput(label="Age", placeholder="กรอกอายุของคุณ", max_length=3)

        self.add_item(self.name)
        self.add_item(self.gender)
        self.add_item(self.age)

    async def on_submit(self, interaction: discord.Interaction):
        user_name = self.name.value
        user_gender = self.gender.value
        user_age = self.age.value
        user_id = interaction.user.id  

        guild_id = str(interaction.guild.id)
        if guild_id in settings:
            notification_channel_id = settings[guild_id].get("notification_channel_id")
            role_id = settings[guild_id].get("role_id")

            if notification_channel_id:
                channel = interaction.guild.get_channel(notification_channel_id)
                if channel:
                    embed = discord.Embed(
                        title="Verified notification",
                        color=discord.Color.blue()
                    )
                    embed.set_thumbnail(url=interaction.user.display_avatar.url)
                    embed.add_field(name="ชื่อ", value=user_name, inline=False)
                    embed.add_field(name="เพศ", value=user_gender, inline=False)
                    embed.add_field(name="อายุ", value=user_age, inline=False)
                    embed.add_field(name="ID card", value=str(user_id), inline=True) 
                    embed.set_footer(text=f"Verified by: {interaction.user.name}#{interaction.user.discriminator}", icon_url=interaction.user.display_avatar.url)

                    await channel.send(embed=embed)

            if role_id:
                role = interaction.guild.get_role(role_id)
                if role:
                    await interaction.user.add_roles(role)
                    await interaction.response.send_message(f"""```diff
+ Add Role Success
```""", ephemeral=True)
                else:
                    await interaction.response.send_message("ข้อมูลของคุณถูกส่งแล้ว! แต่ไม่พบยศที่ต้องการเพิ่ม", ephemeral=True)
        else:
            await interaction.response.send_message("ข้อมูลของคุณถูกส่งแล้ว! แต่ไม่พบการตั้งค่าสำหรับเซิร์ฟเวอร์นี้", ephemeral=True)

@tree.command(name="verify", description="Verify yourself by providing your Name, Gender, and Age.")
async def verify_command(interaction: discord.Interaction):
    await interaction.response.send_modal(VerifyModal())

@tree.command(name="setup", description="Set the role and notification channel.")
@app_commands.checks.has_permissions(administrator=True)
async def setup_command(interaction: discord.Interaction):
    roles = interaction.guild.roles
    channels = interaction.guild.text_channels

    view = SetupView(roles, channels)
    await interaction.response.send_message("Please select the role and notification channel.", view=view, ephemeral=True)

@setup_command.error
async def setup_command_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.errors.MissingPermissions):
        await interaction.response.send_message("You do not have the required permissions to use this command.", ephemeral=True)

@bot.event
async def on_ready():
    try:
        await tree.sync()
        print(f'Logged in as {bot.user}')
    except Exception as e:
        print(f"Error syncing commands: {e}")
keep_alive()
bot.run(os.getenv('Token'))
