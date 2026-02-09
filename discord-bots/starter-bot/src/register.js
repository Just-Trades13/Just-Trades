/**
 * Registers slash commands with Discord. 
 * For dev speed, use a GUILD_ID to register instantly in one server.
 * For global commands, omit GUILD_ID (can take up to an hour to propagate).
 */
require("dotenv").config();
const fs = require("fs");
const path = require("path");
const { REST, Routes } = require("discord.js");

const token = process.env.DISCORD_TOKEN;
const clientId = process.env.CLIENT_ID;
const guildId = process.env.GUILD_ID || null;

if (!token || !clientId) {
  console.error("Missing DISCORD_TOKEN or CLIENT_ID in environment.");
  process.exit(1);
}

const commands = [];
const commandsPath = path.join(__dirname, "../commands");
const commandFiles = fs.readdirSync(commandsPath).filter(file => file.endsWith(".js"));

for (const file of commandFiles) {
  const filePath = path.join(commandsPath, file);
  const command = require(filePath);
  if ("data" in command && "execute" in command) {
    commands.push(command.data.toJSON());
  }
}

const rest = new REST({ version: "10" }).setToken(token);

(async () => {
  try {
    if (guildId) {
      console.log(`[REGISTER] Refreshing ${commands.length} guild (/) commands for guild ${guildId}...`);
      await rest.put(Routes.applicationGuildCommands(clientId, guildId), { body: commands });
      console.log("[REGISTER] Guild commands registered.");
    } else {
      console.log(`[REGISTER] Refreshing ${commands.length} global (/) commands...`);
      await rest.put(Routes.applicationCommands(clientId), { body: commands });
      console.log("[REGISTER] Global commands registered (may take up to 1 hour).");
    }
  } catch (error) {
    console.error(error);
  }
})();
