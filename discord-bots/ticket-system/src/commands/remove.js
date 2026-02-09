const { SlashCommandBuilder, EmbedBuilder, PermissionFlagsBits } = require('discord.js');
const { getTicket } = require('../utils/database');
const { COLORS } = require('../utils/ticketManager');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('remove')
        .setDescription('Remove a user from the current ticket')
        .addUserOption(option =>
            option.setName('user')
                .setDescription('User to remove from the ticket')
                .setRequired(true))
        .setDefaultMemberPermissions(PermissionFlagsBits.ManageChannels),

    async execute(interaction) {
        const ticket = await getTicket(interaction.channelId);

        if (!ticket) {
            return interaction.reply({
                content: '❌ This command can only be used in a ticket channel.',
                ephemeral: true
            });
        }

        const userToRemove = interaction.options.getUser('user');

        // Don't allow removing the ticket creator
        if (userToRemove.id === ticket.user_id) {
            return interaction.reply({
                content: '❌ Cannot remove the ticket creator.',
                ephemeral: true
            });
        }

        try {
            await interaction.channel.permissionOverwrites.delete(userToRemove.id);

            const removeEmbed = new EmbedBuilder()
                .setColor(COLORS.WARNING)
                .setDescription(`✅ ${userToRemove} has been removed from this ticket by ${interaction.user}`);

            await interaction.reply({ embeds: [removeEmbed] });

        } catch (error) {
            console.error('Error removing user:', error);
            await interaction.reply({
                content: '❌ Error removing user from ticket.',
                ephemeral: true
            });
        }
    }
};
