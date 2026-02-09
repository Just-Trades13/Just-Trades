const { PermissionFlagsBits, ChannelType, EmbedBuilder, ActionRowBuilder, ButtonBuilder, ButtonStyle } = require('discord.js');
const { createTicket, getGuildSettings, incrementTicketCounter, getUserOpenTickets, closeTicket, getTicket } = require('./database');

// Just Trades brand colors
const COLORS = {
    PRIMARY: '#0099ff',    // Blue
    SUCCESS: '#00ff88',    // Green
    WARNING: '#ffaa00',    // Orange
    DANGER: '#ff4444',     // Red
    PURPLE: '#9945FF'      // Just Trades purple
};

async function createTicketChannel(guild, user, category = 'General Support') {
    try {
        const settings = await getGuildSettings(guild.id);
        
        if (!settings || !settings.category_id) {
            throw new Error('Ticket system not set up. An admin needs to run `/setup` first.');
        }

        // Check if user already has an open ticket
        const existingTickets = await getUserOpenTickets(user.id, guild.id);
        if (existingTickets.length >= 3) {
            throw new Error('You already have 3 open tickets. Please close one before opening another.');
        }

        const ticketCategory = guild.channels.cache.get(settings.category_id);
        if (!ticketCategory) {
            throw new Error('Ticket category not found. Please contact an admin.');
        }

        // Increment counter
        const ticketNumber = await incrementTicketCounter(guild.id);

        // Create channel name based on category
        const categorySlug = category.toLowerCase().replace(/\s+/g, '-').substring(0, 10);
        const channelName = `${categorySlug}-${ticketNumber}`;

        // Build permission overwrites
        const permissionOverwrites = [
            {
                id: guild.id,
                deny: [PermissionFlagsBits.ViewChannel]
            },
            {
                id: user.id,
                allow: [
                    PermissionFlagsBits.ViewChannel,
                    PermissionFlagsBits.SendMessages,
                    PermissionFlagsBits.AttachFiles,
                    PermissionFlagsBits.ReadMessageHistory,
                    PermissionFlagsBits.EmbedLinks
                ]
            }
        ];

        // Add support role if configured
        if (settings.support_role_id) {
            permissionOverwrites.push({
                id: settings.support_role_id,
                allow: [
                    PermissionFlagsBits.ViewChannel,
                    PermissionFlagsBits.SendMessages,
                    PermissionFlagsBits.AttachFiles,
                    PermissionFlagsBits.ReadMessageHistory,
                    PermissionFlagsBits.EmbedLinks,
                    PermissionFlagsBits.ManageMessages
                ]
            });
        }

        // Create channel
        const channel = await guild.channels.create({
            name: channelName,
            type: ChannelType.GuildText,
            parent: ticketCategory.id,
            topic: `Support ticket for ${user.tag} | Category: ${category}`,
            permissionOverwrites
        });

        // Save to database
        await createTicket(channel.id, user.id, guild.id, category);

        // Build welcome embed
        const welcomeEmbed = new EmbedBuilder()
            .setColor(COLORS.PRIMARY)
            .setTitle(`🎫 Ticket #${ticketNumber}`)
            .setDescription(`Welcome ${user}!\n\nThank you for contacting **Just Trades** support. Please describe your issue below and our team will assist you shortly.`)
            .addFields(
                { name: '📁 Category', value: category, inline: true },
                { name: '🕐 Created', value: `<t:${Math.floor(Date.now() / 1000)}:R>`, inline: true },
                { name: '📋 Ticket ID', value: `#${ticketNumber}`, inline: true }
            )
            .setFooter({ text: 'Just Trades Support • Use the buttons below to manage this ticket' })
            .setTimestamp();

        // Category-specific guidance
        let guidance = '';
        switch (category) {
            case 'Trading Support':
                guidance = '**Please include:**\n• Your recorder/strategy name\n• Screenshot of the issue\n• Time the issue occurred';
                break;
            case 'Billing':
                guidance = '**Please include:**\n• Your Whop email\n• Transaction ID (if applicable)\n• Description of the billing issue';
                break;
            case 'Technical Issues':
                guidance = '**Please include:**\n• What you were trying to do\n• Error message (screenshot preferred)\n• Your broker (Tradovate, NinjaTrader, etc.)';
                break;
            default:
                guidance = '**Please describe your issue in detail and our team will respond as soon as possible.**';
        }

        const guidanceEmbed = new EmbedBuilder()
            .setColor(COLORS.WARNING)
            .setDescription(guidance);

        // Action buttons
        const actionRow = new ActionRowBuilder()
            .addComponents(
                new ButtonBuilder()
                    .setCustomId('ticket_close')
                    .setLabel('Close Ticket')
                    .setStyle(ButtonStyle.Danger)
                    .setEmoji('🔒'),
                new ButtonBuilder()
                    .setCustomId('ticket_claim')
                    .setLabel('Claim Ticket')
                    .setStyle(ButtonStyle.Secondary)
                    .setEmoji('✋')
            );

        // Send messages
        const pingContent = settings.support_role_id 
            ? `${user} | <@&${settings.support_role_id}>`
            : `${user}`;

        await channel.send({ 
            content: pingContent,
            embeds: [welcomeEmbed, guidanceEmbed],
            components: [actionRow]
        });

        return channel;

    } catch (error) {
        console.error('Error creating ticket:', error);
        throw error;
    }
}

async function generateTranscript(channel) {
    try {
        let allMessages = [];
        let lastId = null;

        // Fetch all messages (handling pagination)
        while (true) {
            const options = { limit: 100 };
            if (lastId) options.before = lastId;

            const messages = await channel.messages.fetch(options);
            if (messages.size === 0) break;

            allMessages = allMessages.concat(Array.from(messages.values()));
            lastId = messages.last().id;

            if (messages.size < 100) break;
        }

        // Reverse to get chronological order
        allMessages.reverse();

        let transcript = `╔══════════════════════════════════════════════════════════════╗\n`;
        transcript += `║           JUST TRADES SUPPORT - TICKET TRANSCRIPT           ║\n`;
        transcript += `╠══════════════════════════════════════════════════════════════╣\n`;
        transcript += `║ Channel: ${channel.name.padEnd(51)}║\n`;
        transcript += `║ Created: ${channel.createdAt.toISOString().padEnd(51)}║\n`;
        transcript += `║ Messages: ${allMessages.length.toString().padEnd(50)}║\n`;
        transcript += `╚══════════════════════════════════════════════════════════════╝\n\n`;

        allMessages.forEach(msg => {
            const timestamp = msg.createdAt.toISOString().replace('T', ' ').substring(0, 19);
            const author = msg.author.tag.padEnd(30);
            
            transcript += `┌─────────────────────────────────────────────────────────────┐\n`;
            transcript += `│ ${timestamp} │ ${author}│\n`;
            transcript += `├─────────────────────────────────────────────────────────────┤\n`;
            
            if (msg.content) {
                const lines = msg.content.split('\n');
                lines.forEach(line => {
                    // Word wrap at 60 chars
                    while (line.length > 60) {
                        transcript += `│ ${line.substring(0, 60)} │\n`;
                        line = line.substring(60);
                    }
                    transcript += `│ ${line.padEnd(60)}│\n`;
                });
            }
            
            if (msg.attachments.size > 0) {
                transcript += `│ 📎 Attachments:${' '.repeat(45)}│\n`;
                msg.attachments.forEach(att => {
                    transcript += `│   → ${att.url.substring(0, 55)}│\n`;
                });
            }

            if (msg.embeds.length > 0) {
                transcript += `│ 📋 [Embed content not shown]${' '.repeat(31)}│\n`;
            }
            
            transcript += `└─────────────────────────────────────────────────────────────┘\n\n`;
        });

        transcript += `\n═══════════════════════════════════════════════════════════════\n`;
        transcript += `                    END OF TRANSCRIPT\n`;
        transcript += `              Generated: ${new Date().toISOString()}\n`;
        transcript += `═══════════════════════════════════════════════════════════════\n`;

        return transcript;
    } catch (error) {
        console.error('Error generating transcript:', error);
        return 'Error generating transcript';
    }
}

async function closeTicketChannel(interaction, reason = 'No reason provided') {
    /**
     * Shared close logic used by both the /close command and the Close button.
     * Expects interaction to already be deferred.
     */
    const ticket = await getTicket(interaction.channelId);

    if (!ticket) {
        await interaction.editReply({ content: 'This is not a ticket channel.' });
        return;
    }

    if (ticket.status === 'closed') {
        await interaction.editReply({ content: 'This ticket is already closed.' });
        return;
    }

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
}

module.exports = {
    createTicketChannel,
    closeTicketChannel,
    generateTranscript,
    COLORS
};
