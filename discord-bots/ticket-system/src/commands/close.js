const { SlashCommandBuilder, EmbedBuilder } = require('discord.js');
const { getTicket, closeTicket, getGuildSettings } = require('../utils/database');
const { generateTranscript, COLORS } = require('../utils/ticketManager');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('close')
        .setDescription('Close the current ticket')
        .addStringOption(option =>
            option.setName('reason')
                .setDescription('Reason for closing the ticket')
                .setRequired(false)),

    async execute(interaction) {
        const ticket = await getTicket(interaction.channelId);

        if (!ticket) {
            return interaction.reply({
                content: '❌ This command can only be used in a ticket channel.',
                ephemeral: true
            });
        }

        if (ticket.status === 'closed') {
            return interaction.reply({
                content: '❌ This ticket is already closed.',
                ephemeral: true
            });
        }

        const reason = interaction.options.getString('reason') || 'No reason provided';

        await interaction.deferReply();

        try {
            // Generate transcript
            const transcript = await generateTranscript(interaction.channel);

            // Close in database
            await closeTicket(interaction.channelId, transcript);

            // Send closing message
            const closeEmbed = new EmbedBuilder()
                .setColor(COLORS.DANGER)
                .setTitle('🔒 Ticket Closed')
                .setDescription(`This ticket has been closed by ${interaction.user}`)
                .addFields(
                    { name: 'Reason', value: reason, inline: false },
                    { name: 'Closed At', value: `<t:${Math.floor(Date.now() / 1000)}:F>`, inline: true }
                )
                .setFooter({ text: 'This channel will be deleted in 5 seconds' })
                .setTimestamp();

            await interaction.editReply({ embeds: [closeEmbed] });

            // Send transcript to log channel
            const settings = await getGuildSettings(interaction.guildId);
            if (settings?.log_channel_id) {
                const logChannel = interaction.guild.channels.cache.get(settings.log_channel_id);
                if (logChannel) {
                    const logEmbed = new EmbedBuilder()
                        .setColor(COLORS.DANGER)
                        .setTitle('🔒 Ticket Closed')
                        .addFields(
                            { name: 'Ticket', value: interaction.channel.name, inline: true },
                            { name: 'Closed By', value: interaction.user.tag, inline: true },
                            { name: 'Reason', value: reason, inline: false },
                            { name: 'Original User', value: `<@${ticket.user_id}>`, inline: true },
                            { name: 'Category', value: ticket.category || 'Unknown', inline: true }
                        )
                        .setTimestamp();

                    await logChannel.send({ embeds: [logEmbed] });

                    // Send transcript as file
                    const buffer = Buffer.from(transcript, 'utf-8');
                    await logChannel.send({
                        content: `📋 Transcript for **${interaction.channel.name}**`,
                        files: [{
                            attachment: buffer,
                            name: `transcript-${interaction.channel.name}.txt`
                        }]
                    });
                }
            }

            // Delete channel after 5 seconds
            setTimeout(async () => {
                try {
                    await interaction.channel.delete();
                } catch (err) {
                    console.error('Error deleting ticket channel:', err);
                }
            }, 5000);

        } catch (error) {
            console.error('Error closing ticket:', error);
            await interaction.editReply({
                content: '❌ Error closing ticket. Please try again or delete the channel manually.'
            });
        }
    }
};
