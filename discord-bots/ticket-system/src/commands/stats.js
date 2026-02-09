const { SlashCommandBuilder, EmbedBuilder, PermissionFlagsBits } = require('discord.js');
const { getTicketStats } = require('../utils/database');
const { COLORS } = require('../utils/ticketManager');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('stats')
        .setDescription('View ticket statistics')
        .setDefaultMemberPermissions(PermissionFlagsBits.ManageChannels),

    async execute(interaction) {
        await interaction.deferReply({ ephemeral: true });

        try {
            const stats = await getTicketStats(interaction.guildId);

            const embed = new EmbedBuilder()
                .setColor(COLORS.PRIMARY)
                .setTitle('📊 Just Trades Ticket Statistics')
                .addFields(
                    { 
                        name: '📋 Total Tickets', 
                        value: `\`${stats?.total || 0}\``, 
                        inline: true 
                    },
                    { 
                        name: '🟢 Open', 
                        value: `\`${stats?.open || 0}\``, 
                        inline: true 
                    },
                    { 
                        name: '🔴 Closed', 
                        value: `\`${stats?.closed || 0}\``, 
                        inline: true 
                    }
                )
                .setFooter({ text: 'Just Trades Support System' })
                .setTimestamp();

            // Add percentage if there are tickets
            if (stats?.total > 0) {
                const closedPercent = ((stats.closed / stats.total) * 100).toFixed(1);
                embed.addFields({
                    name: '📈 Resolution Rate',
                    value: `${closedPercent}% of tickets have been resolved`,
                    inline: false
                });
            }

            await interaction.editReply({ embeds: [embed] });

        } catch (error) {
            console.error('Error fetching stats:', error);
            await interaction.editReply({
                content: '❌ Error fetching ticket statistics.'
            });
        }
    }
};
