const sqlite3 = require('sqlite3').verbose();
const path = require('path');

const dbPath = path.join(__dirname, '../../tickets.db');
const db = new sqlite3.Database(dbPath);

function initDatabase() {
    db.serialize(() => {
        // Tickets table
        db.run(`
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id TEXT UNIQUE NOT NULL,
                user_id TEXT NOT NULL,
                guild_id TEXT NOT NULL,
                category TEXT,
                status TEXT DEFAULT 'open',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                closed_at DATETIME,
                claimed_by TEXT,
                transcript TEXT
            )
        `);

        // Settings table
        db.run(`
            CREATE TABLE IF NOT EXISTS settings (
                guild_id TEXT PRIMARY KEY,
                category_id TEXT,
                support_role_id TEXT,
                log_channel_id TEXT,
                ticket_counter INTEGER DEFAULT 0
            )
        `);

        console.log('✓ Database initialized');
    });
}

function createTicket(channelId, userId, guildId, category = 'general') {
    return new Promise((resolve, reject) => {
        db.run(
            'INSERT INTO tickets (channel_id, user_id, guild_id, category) VALUES (?, ?, ?, ?)',
            [channelId, userId, guildId, category],
            function(err) {
                if (err) reject(err);
                else resolve(this.lastID);
            }
        );
    });
}

function getTicket(channelId) {
    return new Promise((resolve, reject) => {
        db.get('SELECT * FROM tickets WHERE channel_id = ?', [channelId], (err, row) => {
            if (err) reject(err);
            else resolve(row);
        });
    });
}

function getUserOpenTickets(userId, guildId) {
    return new Promise((resolve, reject) => {
        db.all(
            'SELECT * FROM tickets WHERE user_id = ? AND guild_id = ? AND status = ?',
            [userId, guildId, 'open'],
            (err, rows) => {
                if (err) reject(err);
                else resolve(rows || []);
            }
        );
    });
}

function closeTicket(channelId, transcript = '') {
    return new Promise((resolve, reject) => {
        db.run(
            'UPDATE tickets SET status = ?, closed_at = CURRENT_TIMESTAMP, transcript = ? WHERE channel_id = ?',
            ['closed', transcript, channelId],
            function(err) {
                if (err) reject(err);
                else resolve(this.changes);
            }
        );
    });
}

function claimTicket(channelId, userId) {
    return new Promise((resolve, reject) => {
        db.run(
            'UPDATE tickets SET claimed_by = ? WHERE channel_id = ?',
            [userId, channelId],
            function(err) {
                if (err) reject(err);
                else resolve(this.changes);
            }
        );
    });
}

function getGuildSettings(guildId) {
    return new Promise((resolve, reject) => {
        db.get('SELECT * FROM settings WHERE guild_id = ?', [guildId], (err, row) => {
            if (err) reject(err);
            else resolve(row);
        });
    });
}

function updateGuildSettings(guildId, settings) {
    return new Promise((resolve, reject) => {
        db.run(
            `INSERT INTO settings (guild_id, category_id, support_role_id, log_channel_id, ticket_counter)
             VALUES (?, ?, ?, ?, 0)
             ON CONFLICT(guild_id) DO UPDATE SET
             category_id = excluded.category_id,
             support_role_id = excluded.support_role_id,
             log_channel_id = excluded.log_channel_id`,
            [guildId, settings.categoryId, settings.supportRoleId, settings.logChannelId],
            function(err) {
                if (err) reject(err);
                else resolve(this.changes);
            }
        );
    });
}

function incrementTicketCounter(guildId) {
    return new Promise((resolve, reject) => {
        db.run(
            `UPDATE settings SET ticket_counter = ticket_counter + 1 WHERE guild_id = ?`,
            [guildId],
            function(err) {
                if (err) reject(err);
                else {
                    db.get('SELECT ticket_counter FROM settings WHERE guild_id = ?', [guildId], (err, row) => {
                        if (err) reject(err);
                        else resolve(row ? row.ticket_counter : 1);
                    });
                }
            }
        );
    });
}

function getTicketStats(guildId) {
    return new Promise((resolve, reject) => {
        db.get(
            `SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status = 'open' THEN 1 ELSE 0 END) as open,
                SUM(CASE WHEN status = 'closed' THEN 1 ELSE 0 END) as closed
             FROM tickets WHERE guild_id = ?`,
            [guildId],
            (err, row) => {
                if (err) reject(err);
                else resolve(row);
            }
        );
    });
}

module.exports = {
    initDatabase,
    createTicket,
    getTicket,
    getUserOpenTickets,
    closeTicket,
    claimTicket,
    getGuildSettings,
    updateGuildSettings,
    incrementTicketCounter,
    getTicketStats,
    db
};
