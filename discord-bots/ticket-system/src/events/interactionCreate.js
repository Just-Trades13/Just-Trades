const { InteractionType, EmbedBuilder } = require('discord.js');
const { createTicketChannel, closeTicketChannel, COLORS } = require('../utils/ticketManager');
const { getTicket, claimTicket, getGuildSettings } = require('../utils/database');

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

                // Close ticket button — uses shared closeTicketChannel helper
                if (interaction.customId === 'ticket_close') {
                    await interaction.deferReply();
                    await closeTicketChannel(interaction, 'Closed via button');
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
