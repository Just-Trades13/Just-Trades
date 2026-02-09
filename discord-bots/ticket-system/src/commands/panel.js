const { SlashCommandBuilder, PermissionFlagsBits, EmbedBuilder, ActionRowBuilder, ButtonBuilder, ButtonStyle } = require('discord.js');
const { COLORS } = require('../utils/ticketManager');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('panel')
        .setDescription('Create a ticket panel for users to open support tickets')
        .addChannelOption(option =>
            option.setName('channel')
                .setDescription('Channel to send the panel to (defaults to current channel)')
                .setRequired(false))
        .setDefaultMemberPermissions(PermissionFlagsBits.ManageChannels),

    async execute(interaction) {
        const channel = interaction.options.getChannel('channel') || interaction.channel;

        // Main embed
        const embed = new EmbedBuilder()
            .setColor(COLORS.PRIMARY)
            .setTitle('🎫 Just Trades Support')
            .setDescription(
                'Need help? Our support team is here to assist you!\n\n' +
                'Click a button below to create a support ticket. Please select the category that best matches your issue.\n\n' +
                '⏰ **Response Time:** Usually within a few hours during business hours'
            )
            .addFields(
                { 
                    name: '📈 Trading Support', 
                    value: 'Questions about strategies, signals, recorders, or trade execution', 
                    inline: true 
                },
                { 
                    name: '💳 Billing', 
                    value: 'Subscription, payments, refunds, or Whop-related issues', 
                    inline: true 
                },
                { 
                    name: '🔧 Technical Issues', 
                    value: 'Platform bugs, connection problems, or broker integration issues', 
                    inline: true 
                },
                { 
                    name: '🤝 General Support', 
                    value: 'Account help, feature requests, or anything else', 
                    inline: true 
                }
            )
            .setImage('https://i.imgur.com/placeholder.png') // You can add a banner image here
            .setFooter({ text: 'Just Trades • Select a category below to get started' })
            .setTimestamp();

        // Remove the image if you don't have one
        embed.setImage(null);

        // Button row 1 - Main categories
        const row1 = new ActionRowBuilder()
            .addComponents(
                new ButtonBuilder()
                    .setCustomId('ticket_create_Trading_Support')
                    .setLabel('Trading Support')
                    .setStyle(ButtonStyle.Primary)
                    .setEmoji('📈'),
                new ButtonBuilder()
                    .setCustomId('ticket_create_Billing')
                    .setLabel('Billing')
                    .setStyle(ButtonStyle.Success)
                    .setEmoji('💳'),
                new ButtonBuilder()
                    .setCustomId('ticket_create_Technical_Issues')
                    .setLabel('Technical Issues')
                    .setStyle(ButtonStyle.Danger)
                    .setEmoji('🔧'),
                new ButtonBuilder()
                    .setCustomId('ticket_create_General_Support')
                    .setLabel('General')
                    .setStyle(ButtonStyle.Secondary)
                    .setEmoji('🤝')
            );

        await channel.send({ embeds: [embed], components: [row1] });

        const successEmbed = new EmbedBuilder()
            .setColor(COLORS.SUCCESS)
            .setDescription(`✅ Ticket panel created in ${channel}`);

        await interaction.reply({
            embeds: [successEmbed],
            ephemeral: true
        });
    }
};
