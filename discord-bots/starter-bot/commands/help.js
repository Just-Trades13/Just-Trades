const { SlashCommandBuilder } = require("discord.js");

module.exports = {
  data: new SlashCommandBuilder()
    .setName("help")
    .setDescription("Lists available commands."),
  async execute(interaction) {
    const list = interaction.client.commands.map(cmd => `• /${cmd.data.name} — ${cmd.data.description}`).join("\n");
    await interaction.reply({
      content: `Here are the available commands:\n${list}`,
      ephemeral: true
    });
  }
};
