const { InteractionType, EmbedBuilder } = require('discord.js');
const { createTicketChannel, COLORS } = require('../utils/ticketManager');
const { getTicket, closeTicket, claimTicket, getGuildSettings } = require('../utils/database');
const { generateTranscript } = require('../utils/ticketManager');

module.exports = {
    name: 'interactionCreate',
    async execute(interaction) {
        // Handle slash commands
        if (interaction.type === InteractionType.ApplicationCommand) {
            const command = interaction.client.commands.get(interaction.commandName);

            if (!command) {
                console.warn(`Command not found: ${interaction.commandName}`);
                return;
            }

            try {
                await command.execute(interaction);
            } catch (error) {
                console.error(`Error executing command ${interaction.commandName}:`, error);
                
                const errorMessage = {
                    content: '❌ There was an error executing this command.',
                    ephemeral: true
                };

                if (interaction.replied || interaction.deferred) {
                    await interaction.followUp(errorMessage);
                } else {
                    await interaction.reply(errorMessage);
                }
            }
        }

        // Handle button clicks
        if (interaction.type === InteractionType.MessageComponent) {
            try {
                // Ticket creation buttons
                if (interaction.customId.startsWith('ticket_create_')) {
                    const category = interaction.customId.replace('ticket_create_', '').replace(/_/g, ' ');

                    await interaction.deferReply({ ephemeral: true });

                    const channel = await createTicketChannel(
                        interaction.guild,
                        interaction.user,
                        category
                    );

                    const successEmbed = new EmbedBuilder()
                        .setColor(COLORS.SUCCESS)
                        .setDescription(`✅ Your ticket has been created: ${channel}\n\nPlease describe your issue there.`);

                    await interaction.editReply({
                        embeds: [successEmbed]
                    });
                }

                // Close ticket button
                if (interaction.customId === 'ticket_close') {
                    const ticket = await getTicket(interaction.channelId);

                    if (!ticket) {
                        return interaction.reply({
                            content: '❌ This is not a ticket channel.',
                            ephemeral: true
                        });
                    }

                    await interaction.deferReply();

                    // Generate transcript
                    const transcript = await generateTranscript(interaction.channel);

                    // Update database
                    await closeTicket(interaction.channelId, transcript);

                    // Send closing message
                    const closeEmbed = new EmbedBuilder()
                        .setColor(COLORS.DANGER)
                        .setTitle('🔒 Ticket Closed')
                        .setDescription(`This ticket has been closed by ${interaction.user}`)
                        .addFields(
                            { name: 'Closed At', value: `<t:${Math.floor(Date.now() / 1000)}:F>`, inline: true }
                        )
                        .setFooter({ text: 'This channel will be deleted in 5 seconds' });

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
                                    { name: 'User ID', value: ticket.user_id, inline: true }
                                )
                                .setTimestamp();

                            await logChannel.send({ embeds: [logEmbed] });

                            // Send transcript as file
                            const buffer = Buffer.from(transcript, 'utf-8');
                            await logChannel.send({
                                content: `📋 Transcript for ${interaction.channel.name}`,
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
                            console.error('Error deleting channel:', err);
                        }
                    }, 5000);
                }

                // Claim ticket button
                if (interaction.customId === 'ticket_claim') {
                    const ticket = await getTicket(interaction.channelId);

                    if (!ticket) {
                        return interaction.reply({
                            content: '❌ This is not a ticket channel.',
                            ephemeral: true
                        });
                    }

                    if (ticket.claimed_by) {
                        return interaction.reply({
                            content: `❌ This ticket has already been claimed by <@${ticket.claimed_by}>`,
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

                    await claimTicket(interaction.channelId, interaction.user.id);

                    const claimEmbed = new EmbedBuilder()
                        .setColor(COLORS.SUCCESS)
                        .setDescription(`✋ This ticket has been claimed by ${interaction.user}\n\nThey will be assisting you shortly.`);

                    await interaction.reply({ embeds: [claimEmbed] });
                }

            } catch (error) {
                console.error('Error handling button interaction:', error);
                
                const errorMessage = {
                    content: `❌ Error: ${error.message}`,
                    ephemeral: true
                };

                if (interaction.replied || interaction.deferred) {
                    await interaction.followUp(errorMessage);
                } else {
                    await interaction.reply(errorMessage);
                }
            }
        }
    }
};
