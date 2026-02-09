const { SlashCommandBuilder, EmbedBuilder, PermissionFlagsBits } = require('discord.js');
const { getTicket } = require('../utils/database');
const { COLORS } = require('../utils/ticketManager');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('add')
        .setDescription('Add a user to the current ticket')
        .addUserOption(option =>
            option.setName('user')
                .setDescription('User to add to the ticket')
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

        const userToAdd = interaction.options.getUser('user');

        try {
            await interaction.channel.permissionOverwrites.edit(userToAdd.id, {
                ViewChannel: true,
                SendMessages: true,
                AttachFiles: true,
                ReadMessageHistory: true
            });

            const addEmbed = new EmbedBuilder()
                .setColor(COLORS.SUCCESS)
                .setDescription(`✅ ${userToAdd} has been added to this ticket by ${interaction.user}`);

            await interaction.reply({ embeds: [addEmbed] });

        } catch (error) {
            console.error('Error adding user:', error);
            await interaction.reply({
                content: '❌ Error adding user to ticket. Please check bot permissions.',
                ephemeral: true
            });
        }
    }
};
