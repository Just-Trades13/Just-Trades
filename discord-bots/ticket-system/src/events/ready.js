const { REST, Routes, ActivityType } = require('discord.js');

module.exports = {
    name: 'ready',
    once: true,
    async execute(client) {
        console.log(`\n╔════════════════════════════════════════╗`);
        console.log(`║     JUST TRADES TICKET BOT ONLINE      ║`);
        console.log(`╠════════════════════════════════════════╣`);
        console.log(`║ Bot: ${client.user.tag.padEnd(33)}║`);
        console.log(`║ Servers: ${client.guilds.cache.size.toString().padEnd(29)}║`);
        console.log(`║ Commands: ${client.commands.size.toString().padEnd(28)}║`);
        console.log(`╚════════════════════════════════════════╝\n`);

        // Register slash commands
        const commands = [];
        client.commands.forEach(command => {
            commands.push(command.data.toJSON());
        });

        const token = process.env.DISCORD_BOT_TOKEN || process.env.DISCORD_TOKEN;
        const rest = new REST({ version: '10' }).setToken(token);

        try {
            console.log('📝 Registering slash commands...');

            // Register to specific guild for instant updates
            if (process.env.GUILD_ID) {
                await rest.put(
                    Routes.applicationGuildCommands(process.env.CLIENT_ID, process.env.GUILD_ID),
                    { body: commands }
                );
                console.log(`✓ Registered ${commands.length} commands to guild ${process.env.GUILD_ID}`);
            } else {
                // Global registration (takes up to 1 hour)
                await rest.put(
                    Routes.applicationCommands(process.env.CLIENT_ID),
                    { body: commands }
                );
                console.log(`✓ Registered ${commands.length} commands globally`);
            }
        } catch (error) {
            console.error('✗ Error registering commands:', error);
        }

        // Set bot presence
        client.user.setPresence({
            activities: [{ 
                name: 'Just Trades Support',
                type: ActivityType.Watching
            }],
            status: 'online'
        });
    }
};
