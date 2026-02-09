/**
 * Basic Discord bot with slash commands.
 * Commands live in ./commands and are auto-loaded.
 * Run `npm run register` once to register slash commands, then `npm start`.
 */
require("dotenv").config();
const fs = require("fs");
const path = require("path");
const { Client, Collection, GatewayIntentBits, Partials, Events } = require("discord.js");

const client = new Client({
  intents: [
    GatewayIntentBits.Guilds,
    GatewayIntentBits.GuildMessages,
    GatewayIntentBits.MessageContent
  ],
  partials: [Partials.Channel]
});

client.commands = new Collection();

const commandsPath = path.join(__dirname, "../commands");
const commandFiles = fs.readdirSync(commandsPath).filter(file => file.endsWith(".js"));

for (const file of commandFiles) {
  const filePath = path.join(commandsPath, file);
  const command = require(filePath);
  if ("data" in command && "execute" in command) {
    client.commands.set(command.data.name, command);
  } else {
    console.warn(`[WARN] The command at ${filePath} is missing "data" or "execute".`);
  }
}

client.once(Events.ClientReady, c => {
  console.log(`[READY] Logged in as ${c.user.tag}`);
});

client.on(Events.InteractionCreate, async interaction => {
  if (!interaction.isChatInputCommand()) return;

  const command = interaction.client.commands.get(interaction.commandName);
  if (!command) {
    console.error(`[ERROR] No command matching ${interaction.commandName} was found.`);
    return;
  }

  try {
    await command.execute(interaction);
  } catch (error) {
    console.error(error);
    if (interaction.deferred || interaction.replied) {
      await interaction.followUp({ content: "There was an error executing that command.", ephemeral: true });
    } else {
      await interaction.reply({ content: "There was an error executing that command.", ephemeral: true });
    }
  }
});

client.login(process.env.DISCORD_TOKEN);
