# EmojiBot
_an emoji managing Discord bot_

## Introduction
Discord limits the number of emojis in a single server to 50, which can be a little tight if you have a lot of members. EmojiBot dynamically swaps out emojis according to usage, allowing you to add a theoretically limitless amount of emojis to one server.

### Features
* Allows an unlimited amount of emojis on a single Discord server!
* Keeps the most used emojis in the Discord emoji list to enable autocompletion
* Emoji spellchecking (:happy: will trigger :happy_face:)

## Usage
* `e!add name [url]` adds an emoji to the bot. If the URL to an image is not provided, it will wait for you to post an image in the same channel, and use that instead.
* `e!remove name` removes an emoji from the bot (and the Discord emoji list if it's loaded).
* `e!list` lists all the emojis registered with EmojiBot.

An important note: by default, EmojiBot assumes it has control over all 50 emoji slots in the server (40 for frequently used emojis, and 10 scratch emojis). To edit those numbers, change the appropriate values in `config.json`.

## Setup
For now, I'm not offering a hosted version of the bot (although I may in the future). That being said, it's designed for deployment on [IBM's cloud platform](https://www.ibm.com/cloud), which lets you run the bot for free. It isn't too hard to set up (although you will need a bit of familiatity with the command line).

1. [Create a new Discord application](https://discord.com/developers/) to run your instance of EmoijBot as. Go to the bots section, and create a bot. Make a note of the bot token - we'll need that later.
2. (optional, for IBM users) [Create an IBM cloud account](https://cloud.ibm.com/login) and create a new Cloud Foundary app, using Python as the SDK and with 256MB of RAM.
3. (optional, for IBM users) [Install the IBM CLI](https://cloud.ibm.com/docs/cli?topic=cli-install-ibmcloud-cli) and login to your account.
4. Download / clone this repository. Rename emojis_template.json to emojis.json, and replace the placeholder in config.json with your bot token.
5. (for running locally) run `pip install -r requirements.txt` and `python emojibot.py`
6. (for IBM) edit `manifest.yml` so that `name:` matches the name of your cloud foundary app, and run `ibm cf push` in the project directory.
7. Back in the Discord developer panel, go to the OAuth2 tab, and tick the `bot` scope. Give the bot at least send messages, manage emojis, and manage webhooks (or simply administrator). Paste the link into a new tab, then add the bot to a server of your choice!
