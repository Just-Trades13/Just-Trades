const { SlashCommandBuilder, PermissionFlagsBits, ChannelType, EmbedBuilder } = require('discord.js');
const { updateGuildSettings } = require('../utils/database');
const { COLORS } = require('../utils/ticketManager');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('setup')
        .setDescription('Set up the Just Trades ticket system')
        .addChannelOption(option =>
            option.setName('category')
                .setDescription('Category where ticket channels will be created')
                .setRequired(true)
                .addChannelTypes(ChannelType.GuildCategory))
        .addRoleOption(option =>
            option.setName('support_role')
                .setDescription('Role that can view and respond to tickets')
                .setRequired(true))
        .addChannelOption(option =>
            option.setName('log_channel')
                .setDescription('Channel for ticket logs and transcripts')
                .setRequired(false)
                .addChannelTypes(ChannelType.GuildText))
        .setDefaultMemberPermissions(PermissionFlagsBits.Administrator),

    async execute(interaction) {
        const category = interaction.options.getChannel('category');
        const supportRole = interaction.options.getRole('support_role');
        const logChannel = interaction.options.getChannel('log_channel');

        try {
            await updateGuildSettings(interaction.guildId, {
                categoryId: category.id,
                supportRoleId: supportRole.id,
                logChannelId: logChannel?.id || null
            });

            const successEmbed = new EmbedBuilder()
                .setColor(COLORS.SUCCESS)
                .setTitle('✅ Ticket System Configured')
                .setDescription('The Just Trades ticket system has been set up successfully!')
                .addFields(
                    { name: '📁 Ticket Category', value: `${category}`, inline: true },
                    { name: '👥 Support Role', value: `${supportRole}`, inline: true },
                    { name: '📋 Log Channel', value: logChannel ? `${logChannel}` : 'None', inline: true }
                )
                .addFields({
                    name: '📝 Next Steps',
                    value: '1. Use `/panel` to create a ticket panel in your support channel\n2. Users can click buttons to open tickets\n3. Support team will be pinged on new tickets'
                })
                .setFooter({ text: 'Just Trades Support System' })
                .setTimestamp();

            await interaction.reply({
                embeds: [successEmbed],
                ephemeral: true
            });

        } catch (error) {
            console.error('Setup error:', error);
            await interaction.reply({
                content: '❌ Error setting up ticket system. Please try again.',
                ephemeral: true
            });
        }
    }
};
