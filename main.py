import os
import re
import discord
from discord.ext import commands
from dotenv import load_dotenv
import asyncio
from flask import Flask
from threading import Thread

# Load environment variables
load_dotenv()
TOKEN = os.getenv("TOKEN")

# Define IDs for category and roles
ORDERED_CATEGORY_ID = 1299960187473498142 # ID for "ordered tickets" category
ROLE_REQUIRED_ID = 1299844660469960715     # ID for the "Admin" role required to use certain commands
ROLE_TO_ASSIGN_ID = 1299844821569114122    # Updated ID for the role to assign to users in the ticket channel

# Dictionary to store the ticket creator's ID based on the ticket channel ID
ticket_creators = {}

# Initialize the bot with appropriate intents
intents = discord.Intents.default()
intents.members = True
intents.guilds = True
intents.messages = True
intents.message_content = True

app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!" , 200

def run():
    app.run(host='127.0.0.1', port=5000)

def keep_alive():
    t = Thread(target=run)
    t.start()


bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")

@bot.event
async def on_message(message):
    # Check if the message contains the ticket creation phrase
    if "Thank you for creating a ticket" in message.content:
        # Extract the user mention from the message (e.g., "<@123456789012345678>")
        match = re.search(r'<@(\d+)>', message.content)
        if match:
            user_id = int(match.group(1))  # Extract the user ID from the mention
            ticket_creators[message.channel.id] = user_id  # Map the ticket channel to the creator's ID
            print(f"Stored ticket creator ID {user_id} for channel {message.channel.id}")

    # Process commands if the message starts with the command prefix
    await bot.process_commands(message)

async def move_to_ordered_category(guild, channel):
    # Find the 'ordered tickets' category by ID
    ordered_category = guild.get_channel(ORDERED_CATEGORY_ID)
    if ordered_category is None:
        await channel.send("The ordered tickets category could not be found.")
        return

    # Check if the channel is already in the correct category
    if channel.category != ordered_category:
        try:
            # Move the channel to the 'ordered tickets' category
            await channel.edit(category=ordered_category)
            print(f"Channel {channel.name} moved to 'ordered tickets' category.")
        except discord.Forbidden:
            await channel.send("I do not have permission to move this channel.")
        except discord.HTTPException as e:
            await channel.send(f"An error occurred while moving the channel: {e}")
    else:
        print(f"Channel {channel.name} is already in the 'ordered tickets' category.")

@bot.command(name='done')
@commands.has_role(ROLE_REQUIRED_ID)
@commands.cooldown(1, 60, commands.BucketType.channel)  # 1 use per minute per channel
async def done(ctx):
    try:
        channel = ctx.channel
        guild = ctx.guild
        role_to_assign = guild.get_role(ROLE_TO_ASSIGN_ID)

        if role_to_assign is None:
            await ctx.send("The role to assign could not be found.")
            return

        if not channel.name.startswith('ticket-'):
            await ctx.send("This command can only be used in ticket channels.")
            return

        if channel.name.endswith('-ordered'):
            await move_to_ordered_category(guild, channel)
            await ctx.send("This ticket has already been marked as done.")
            return

        # Define the ignore list of user IDs to skip
        ignore_list = [1300174988443254876, 443545183997657120, 204255221017214977, 235148962103951360, 155149108183695360, 557628352828014614, 499595256270946326, 1232134817831719012]  # Replace with actual user IDs to ignore

        # Track if anyone was assigned the role
        role_assigned = False

        for member in channel.members:
            if member.id in ignore_list:
                continue  # Skip users in the ignore list
            if role_to_assign not in member.roles:
                await member.add_roles(role_to_assign)
                await ctx.send(f"{member.mention} is now a Certified Grubber.")
                role_assigned = True
                await asyncio.sleep(0.5)  # Reduce API call rate

        if not role_assigned:
            await ctx.send("You are already a Certified Grubber.")

        # Update channel name and move to ordered tickets category if necessary
        if not channel.name.endswith('-ordered'):
            new_channel_name = f"{channel.name}-ordered"
            await channel.edit(name=new_channel_name)
            await move_to_ordered_category(guild, channel)
            await ctx.send("The ticket has been marked as done and moved to the 'ordered tickets' category.")

        # Notify the customer
        customer_id = ticket_creators.get(ctx.channel.id)
        customer = guild.get_member(customer_id) if customer_id else None

        if customer:
            await ctx.send(
                f"{customer.mention}, your food has been ordered! "
                "Please don't forget to vouch when you get it, it helps everyone stay safe and know that we are legit."
            )

    except Exception as e:
        print(f"An error occurred: {e}")
        await ctx.send(f"An error occurred while processing the command: {e}")



# Work command to notify that the admin is working on the order
@bot.command(name='work')
@commands.has_role(ROLE_REQUIRED_ID)
async def work(ctx):
    # Respond with a message tagging the user who invoked the command
    await ctx.send(
        f"{ctx.author.mention} is now working on your order. "
        "Please make sure that you have sent your payment confirmation so that your tracking link "
        "can be sent as soon as possible. Thanks!"
    )

    # Start a 45-minute timer
    await asyncio.sleep(45 * 60)  # 45 minutes in seconds

    # Get the customer (ticket creator) from the stored data
    customer_id = ticket_creators.get(ctx.channel.id)
    customer = ctx.guild.get_member(customer_id) if customer_id else None

    if customer:
        # Send a reminder message mentioning the customer
        await ctx.send(
            f"{customer.mention}, please don't forget to vouch when you get your food!"
        )

@bot.command(name='price')
async def price(ctx, amount: float, currency: str):
    currency = currency.lower()  # Make currency case-insensitive

    # Calculate for USD
    if currency == "usd":
        if 30 < amount < 50:
            calculated_price = round(amount * 0.5, 1)  # Calculate 50% and round to nearest tenth
            await ctx.send(f"The price for this order is {calculated_price} USD.")
        elif amount >= 50:
            calculated_price = round(amount * 0.3, 1)  # Calculate 30% and round to nearest tenth
            await ctx.send(f"The price for this order is {calculated_price} USD.")
        else:
            await ctx.send("No discount applied for amounts less than or equal to $30 USD.")

    # Calculate for CAD
    elif currency == "cad":
        if 40 < amount < 70:
            calculated_price = round(amount * 0.5, 1)  # Calculate 50% and round to nearest tenth
            await ctx.send(f"The price for this order is {calculated_price} CAD.")
        elif amount >= 70:
            calculated_price = round(amount * 0.3, 1)  # Calculate 30% and round to nearest tenth
            await ctx.send(f"The price for this order is {calculated_price} CAD.")
        else:
            await ctx.send("No discount applied for amounts less than or equal to $40 CAD.")
    else:
        await ctx.send("Unsupported currency. Please specify either USD or CAD.")

@bot.command(name='queue')
async def queue(ctx):
    guild = ctx.guild
    new_ticket_category = guild.get_channel(1299867367131709460)  # Use the new ticket category ID

    # Check if the category exists
    if new_ticket_category is None or not isinstance(new_ticket_category, discord.CategoryChannel):
        await ctx.send("The new ticket category could not be found.")
        return

    # Count the number of text channels in the new ticket category
    channel_count = len([channel for channel in new_ticket_category.channels if isinstance(channel, discord.TextChannel)])

    # Respond based on the number of channels found
    if channel_count == 0:
        await ctx.send("There is no one waiting in line right now. Make a ticket!")
    elif channel_count == 1:
        await ctx.send("There is 1 person currently in the queue. Please be patient!")
    else:
        await ctx.send(f"There are {channel_count} people currently in the queue. Please be patient!")

# Pay command to list cryptocurrency addresses
@bot.command(name='pay')
async def pay(ctx):
    payment_info = (
        "**Crypto Payment Addresses**\n"
        "BTC: `bc1qng90f308xp3wfsrehesv4sn9p4mnfu00usv07r`\n"
        "SOL: `CzAxnsim1YZ7G2z5NrVXF3YVedvfePifK91xgJonJmNb`\n"
        "ETH: `0x1D4062825cDc426100c17a0cE2d0Cd63d4664C4b`\n"
    )
    await ctx.send(payment_info)
    
from datetime import timedelta

# Dictionary to store the number of vouches per user
vouch_counts = {}

@bot.command(name='vouch')
@commands.cooldown(1, 3600, commands.BucketType.user)  # 1-hour cooldown for each user
async def vouch(ctx):
    allowed_channel_id = 1299843778361819196  # The ID for the vouch channel
    admin_role_id = 1299844660469960715  # Replace with actual admin role ID

    # Check if the command is being used in the allowed channel
    if ctx.channel.id != allowed_channel_id:
        await ctx.send("This command can only be used in the vouch channel. Please go there and try again!")
        return

    user = ctx.author
    user_id = user.id

    # Check if the user has the admin role and bypass cooldown if they do
    if any(role.id == admin_role_id for role in user.roles):
        ctx.command.reset_cooldown(ctx)  # Reset cooldown for the user with admin role

    # Increment the vouch count for the user
    if user_id in vouch_counts:
        vouch_counts[user_id] += 1
    else:
        vouch_counts[user_id] = 1

    # Retrieve the updated vouch count
    vouch_count = vouch_counts[user_id]

    # Send the thank you message with the vouch count
    await ctx.send(f"Thank you for vouching for us, {user.mention}. You have now vouched {vouch_count} times.")

# Error handler to let users know if they hit the cooldown
@vouch.error
async def vouch_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        # Calculate time left in MM:SS format
        remaining_time = str(timedelta(seconds=int(error.retry_after)))
        formatted_time = remaining_time[-5:]  # Ensures format is MM:SS

        await ctx.send(f"You can only vouch once per hour to reduce spam. Please wait {formatted_time} before vouching again.")

# Dictionary to keep track of channels that have received the response
responded_channels = {}

# Dictionary to keep track of channels that have received the response
responded_channels = {}

@bot.event
async def on_guild_channel_create(channel):
    # Check if the channel is in the "new tickets" category
    new_ticket_category_id = 1299867367131709460  # Replace with the actual category ID
    if channel.category and channel.category.id == new_ticket_category_id:

        # Function to check if a message contains an image
        def check_for_image(message):
            return (
                message.channel == channel and 
                message.attachments and 
                any(attachment.content_type.startswith("image/") for attachment in message.attachments)
            )

        # Start a background task for the 5-minute reminder timer
        bot.loop.create_task(send_reminder(channel))

        try:
            # Wait for the first message with an image
            message = await bot.wait_for('message', check=check_for_image)

            # Ensure we haven't already responded in this channel
            if channel.id not in responded_channels:
                # Mark the channel as responded to
                responded_channels[channel.id] = True

                # Send the thank you message
                await channel.send(
                    f"Thank you for sending your cart, {message.author.mention}. "
                    "Someone will be with you as soon as possible. While you wait, please make sure that your grand total "
                    "and all items are visible in your pictures. If they already are, you can ignore this message."
                )

        except asyncio.CancelledError:
            # This handles the background task in case it needs to be stopped
            pass

async def send_reminder(channel):
    """Send a reminder message if no image is sent within 5 minutes."""
    await asyncio.sleep(300)  # Wait for 5 minutes

    # If no response has been sent in this channel yet, send the reminder
    if channel.id not in responded_channels:
        await channel.send(
            "It has been 5 minutes since this ticket was made. "
            "Please send images of your cart so that we can take your order!"
        )




keep_alive()
bot.run(TOKEN)
