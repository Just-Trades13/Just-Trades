const { SlashCommandBuilder, EmbedBuilder } = require('discord.js');
const { getTicket, claimTicket, getGuildSettings } = require('../utils/database');
const { COLORS } = require('../utils/ticketManager');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('claim')
        .setDescription('Claim this ticket to handle it'),

    async execute(interaction) {
        const ticket = await getTicket(interaction.channelId);

        if (!ticket) {
            return interaction.reply({
                content: '❌ This command can only be used in a ticket channel.',
                ephemeral: true
            });
        }

        if (ticket.claimed_by) {
            const claimedEmbed = new EmbedBuilder()
                .setColor(COLORS.WARNING)
                .setDescription(`❌ This ticket has already been claimed by <@${ticket.claimed_by}>`);

            return interaction.reply({
                embeds: [claimedEmbed],
                ephemeral: true
            });
        }

        // Check if user has support role
        const settings = await getGuildSettings(interaction.guildId);
        if (settings?.support_role_id) {
            const hasRole = interaction.member.roles.cache.has(settings.support_role_id);
            if (!hasRole) {
                return interaction.reply({
                    content: '❌ Only support team members can claim tickets.',
                    ephemeral: true
                });
            }
        }

        try {
            await claimTicket(interaction.channelId, interaction.user.id);

            const claimEmbed = new EmbedBuilder()
                .setColor(COLORS.SUCCESS)
                .setTitle('✋ Ticket Claimed')
                .setDescription(`${interaction.user} has claimed this ticket and will be assisting you.`)
                .setTimestamp();

            await interaction.reply({ embeds: [claimEmbed] });

        } catch (error) {
            console.error('Error claiming ticket:', error);
            await interaction.reply({
                content: '❌ Error claiming ticket. Please try again.',
                ephemeral: true
            });
        }
    }
};
