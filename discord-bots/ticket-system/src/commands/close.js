const { SlashCommandBuilder } = require('discord.js');
const { closeTicketChannel } = require('../utils/ticketManager');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('close')
        .setDescription('Close the current ticket')
        .addStringOption(option =>
            option.setName('reason')
                .setDescription('Reason for closing the ticket')
                .setRequired(false)),

    async execute(interaction) {
        const reason = interaction.options.getString('reason') || 'No reason provided';
        await interaction.deferReply();

        try {
            await closeTicketChannel(interaction, reason);
        } catch (error) {
            console.error('Error closing ticket:', error);
            await interaction.editReply({
                content: '❌ Error closing ticket. Please try again or delete the channel manually.'
            });
        }
    }
};
