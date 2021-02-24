import discord
import requests
from PIL import Image
import Levenshtein

import json
import re
import subprocess
from io import BytesIO

DISCORD_EMOJI_LIMIT = 50

CONFIG = {}
EMOJI_LOOKUP = {}
DISCORD_BUILTIN_EMOJIS = {}

# Who are we waiting on a photo for an emoji from, and in what channel?
waiting_for_photo = []

client = discord.Client()

discord_emoji_re = re.compile("<:[^:]*:[^>]*>")
emoji_tag_re = re.compile(":[^:]*:")


def add_emoji(guild, author, name, url):
    # Actually add the emoji!
    EMOJI_LOOKUP[str(guild.id)][f":{name}:"] = {
        "url": url,
        "creator": author.id,
        "uses": 0
    }

    # Save to disk
    with open(CONFIG['emoji_file'], "w") as f:
        json.dump(EMOJI_LOOKUP, f)


async def command_add(message, args):
    guild_id = str(message.guild.id)
    if len(args) != 1 and len(args) != 2:
        await message.channel.send("usage: e!add name [url]")
        return

    # Name validation
    name = args[0].strip().lower()

    if name[0] == ":" and name[-1] == ":":
        name = name[1:-1]

    for emoji in message.guild.emojis:
        if name == emoji.name:
            await message.channel.send("Name already in use!")
            return

    if f":{name}:" in EMOJI_LOOKUP[guild_id].keys():
        await message.channel.send("Name already in use!")
        return

    if name in DISCORD_BUILTIN_EMOJIS:
        await message.channel.send("That name collides with a Discord builtin emoji!")
        return

    if len(args) == 1:
        # Add this user to the waiting for a photo list
        waiting_for_photo.append((message.author.id, message.channel.id, name))
    elif len(args) == 2:
        try:
            res = requests.get(args[1])
            Image.open(BytesIO(res.content))
        except:
            await message.channel.send("Invalid URL / image!")

        add_emoji(message.guild, message.author, name, args[1])

        await message.channel.send(f"Succesfully added :{name}:")


async def command_remove(message, args):
    if len(args) != 1:
        await message.channel.send("Usage: e!remove [name]")
        return

    guild_id = str(message.guild.id)

    name = args[0].lower()
    if name[0] != ":" and name[-1] != ":":
        name = f":{name}:"

    # Is this a valid emoji?
    if name not in EMOJI_LOOKUP[guild_id]:
        await message.channel.send(f"The emoji :{name}: doesn't exist!")
        return

    # Check if it's registered, and if so, remove it
    [await e.delete() for e in await message.guild.fetch_emojis() if e.user == client.user and e.name == name[1:-1]]

    # Remove it!
    del EMOJI_LOOKUP[guild_id][name]

    # Save to disk
    with open(CONFIG['emoji_file'], "w") as f:
        json.dump(EMOJI_LOOKUP, f)

    await message.channel.send(f"Succesfully removed {name}")


async def command_list(message, args):
    try:
        if len(args) == 0:
            page_index = 0
        else:
            page_index = int(args[0]) - 1
    except:
        await message.channel.send("Invalid page number!")
        return

    guild_id = str(message.guild.id)
    emojis = EMOJI_LOOKUP[guild_id].items()
    emojis = sorted(emojis, key=lambda x: x[1]['uses'], reverse=True)

    pages = []
    current_page = ""
    for (emoji, data) in emojis:
        line = f"{emoji} ({data['uses']} uses)\n"
        if len(current_page) + len(line) < 2048:
            current_page += line
        else:
            pages.append(current_page)
            current_page = ""

    pages.append(current_page)

    if page_index >= len(pages):
        await message.channel.send(f"Invalid page number! {len(pages)} available.")
        return

    if len(pages) > 1:
        title = f"Emojis on {message.guild.name} (page {page_index + 1} of {len(pages)})"
    else:
        title = f"Emojis on {message.guild.name}"

    embed = discord.Embed(title=title, description=pages[page_index])
    await message.channel.send(embed=embed)

COMMANDS = {
    "e!add": command_add,
    "e!remove": command_remove,
    "e!list": command_list
}


async def process_command(message):
    content = message.content.strip().lower().split()

    if len(content) == 0 or content[0] not in COMMANDS:
        return False

    await COMMANDS[content[0]](message, content[1:])
    return True


async def register_emoji(guild, name):
    # Read in the image
    # TODO: support for things other than images
    res = requests.get(EMOJI_LOOKUP[str(guild.id)][f":{name}:"]["url"])
    return await guild.create_custom_emoji(name=name, image=res.content)


async def update_frequent_emojis(guild):
    guild_id = str(guild.id)

    # Update the registered emoji list to reflect the new emoji totals
    registered_emojis = [i for i in await guild.fetch_emojis() if i.user == client.user]
    top_n_emojis = sorted(EMOJI_LOOKUP[guild_id].items(
    ), key=lambda x: x[1]['uses'], reverse=True)[:CONFIG['frequent_emoji_slots']]

    # Do we need to perform any updates?
    registered_emojis_names = set([i.name for i in registered_emojis])
    top_n_emojis_names = set([i[0][1:-1] for i in top_n_emojis])

    emojis_to_be_deleted = registered_emojis_names - top_n_emojis_names
    emojis_to_be_registered = top_n_emojis_names - registered_emojis_names

    # Register all the new emojis we need to register
    [await register_emoji(guild, emoji) for emoji in emojis_to_be_registered]

    # And delete all the ones we need to delete
    [await emoji.delete() for emoji in registered_emojis if emoji.name in emojis_to_be_deleted]


def spellcheck_emojis(guild_id, content):
    # Grab a list of emojis in this message
    discord_emojiless = re.sub(discord_emoji_re, "", content)
    emoji_tags = emoji_tag_re.findall(discord_emojiless)

    for emoji in emoji_tags:
        # Replace the emoji with a lowercase version of itself
        content = content.replace(emoji, emoji.lower())
        emoji = emoji.lower()

        # Is this emoji in our database?
        if emoji in EMOJI_LOOKUP[guild_id]:
            # Great! No action needed.
            continue

        # Nope. Spellcheck time!
        maximum_ratio = 0
        closest_emoji = None
        for registered_emoji in EMOJI_LOOKUP[guild_id].keys():
            ratio = Levenshtein.ratio(registered_emoji, emoji)
            if ratio > maximum_ratio:
                maximum_ratio = ratio
                closest_emoji = registered_emoji

        if maximum_ratio > CONFIG['levenshtein_ratio_threshold']:
            content = content.replace(emoji, closest_emoji)

    return content


@client.event
async def on_message(message):
    global waiting_for_photo

    if message.author == client.user:
        return

    guild_id = str(message.guild.id)

    if guild_id not in EMOJI_LOOKUP:
        EMOJI_LOOKUP[guild_id] = {}

    author_remove_id = None

    # Is this message from someone who's on the waiting_for_photo list?
    for (author_id, channel_id, emoji_name) in waiting_for_photo:
        if author_id != message.author.id or channel_id != message.channel.id:
            continue

        # Remove them from the waiting_for_photo list
        author_remove_id = author_id

        # Is there a photo attached?
        if len(message.attachments) == 0:
            # Nope.
            await message.channel.send("No photo found!")
            return

        # Is the attachment a valid photo?
        try:
            res = requests.get(message.attachments[0].url)
            Image.open(BytesIO(res.content))
        except:
            await message.channel.send("Invalid URL / image!")
            return

        add_emoji(message.guild, message.author,
                  emoji_name, message.attachments[0].url)
        await message.channel.send(f"Succesfully added :{emoji_name}:")

    if author_remove_id is not None:
        waiting_for_photo = [
            i for i in waiting_for_photo if i[0] != author_remove_id]

    # Command parsing
    if await process_command(message):
        return

    # Update the emoji count before we do any further processing
    for emoji in set(emoji_tag_re.findall(message.content)):
        # Make sure this emoji is under our juristiction
        if emoji in EMOJI_LOOKUP[guild_id]:
            EMOJI_LOOKUP[guild_id][emoji.lower()]['uses'] += 1

    # Save to disk
    with open(CONFIG['emoji_file'], "w") as f:
        json.dump(EMOJI_LOOKUP, f)

    # Hand off the message content to the emoji spellchecker
    content_spellchecked = spellcheck_emojis(guild_id, message.content)

    # Remove all discord emojis of the format <:something:1234>
    # Those are emojis already in the discord emojilist, so we can ignore them
    discord_emojiless = re.sub(discord_emoji_re, "", content_spellchecked)
    emoji_tags = emoji_tag_re.findall(discord_emojiless)
    if len(emoji_tags) == 0:
        return

    # Make our tag searching case insensitive
    unique_emoij_tags = set([i.lower() for i in emoji_tags])

    # How many of those do we actually have registered?
    unique_emoij_tags = set(
        EMOJI_LOOKUP[guild_id].keys()).intersection(unique_emoij_tags)

    if len(unique_emoij_tags) == 0:
        return

    # Get the effective emoji limit for this server (how many slots are actually left)
    if len(unique_emoij_tags) > CONFIG['working_emoji_slots']:
        await message.channel.send("Too many emoji tags in a single message!")

    if len(unique_emoij_tags) > DISCORD_EMOJI_LIMIT - len(message.guild.emojis):
        await message.channel.send("Not enough free emoji slots!")

    # Register all the emojis
    new_emojis = []
    new_content = content_spellchecked
    for emoji in unique_emoij_tags:
        # Do we need to register this emoji?
        if emoji[1:-1] not in [e.name for e in message.guild.emojis]:
            new_emoji = await register_emoji(message.guild, emoji[1:-1])
        else:
            # Grab a reference to this already registered emojis
            new_emoji = [
                e for e in message.guild.emojis if e.name == emoji[1:-1]][0]

        # Replace the emojitags in the message with actual emojis
        new_content = new_content.replace(emoji, str(new_emoji))

        new_emojis.append(new_emoji)

    await message.delete()

    # Grab or create the webhook for this channel
    channel_webhook = None
    for webhook in await message.guild.webhooks():
        if webhook.channel == message.channel:
            channel_webhook = webhook

    if channel_webhook is None:
        channel_webhook = await message.channel.create_webhook(name="EmojiBotWebhook")

    await channel_webhook.send(new_content, username=message.author.name, avatar_url=message.author.avatar_url)

    # Update the frequent emoji list
    await update_frequent_emojis(message.guild)

if __name__ == "__main__":
    # TODO: replace with persistent storage
    with open("config.json") as f:
        CONFIG = json.load(f)

    with open(CONFIG['emoji_file']) as f:
        EMOJI_LOOKUP = json.load(f)

    with open(CONFIG['discord_builtin_emojis_file']) as f:
        DISCORD_BUILTIN_EMOJIS = json.load(f)

    # Keep IBM happy
    subprocess.Popen(["python", "-m", "http.server", "8080", "-d", "empty"])
    client.run(CONFIG['bot_token'])