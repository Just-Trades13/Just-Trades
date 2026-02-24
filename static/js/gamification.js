(function () {
    'use strict';

    // -------------------------------------------------------------------------
    // Achievement definitions
    // -------------------------------------------------------------------------
    const ACHIEVEMENTS = [
        // Trading achievements
        { id: 'first_trade',     category: 'trading', icon: 'trending_up',          title: 'First Trade',    description: 'Execute your first automated trade',       xp: 50  },
        { id: 'ten_trades',      category: 'trading', icon: 'show_chart',            title: 'Getting Started',description: 'Execute 10 automated trades',               xp: 100 },
        { id: 'hundred_trades',  category: 'trading', icon: 'insights',              title: 'Centurion',      description: 'Execute 100 automated trades',              xp: 250 },
        { id: 'thousand_trades', category: 'trading', icon: 'military_tech',         title: 'Trade Machine',  description: 'Execute 1,000 automated trades',            xp: 500 },
        { id: 'first_profit',    category: 'trading', icon: 'paid',                  title: 'In The Green',   description: 'Complete your first profitable trade',      xp: 75  },
        { id: 'five_symbols',    category: 'trading', icon: 'pie_chart',             title: 'Diversified',    description: 'Trade 5 different symbols',                 xp: 150 },
        // Account achievements
        { id: 'create_account',  category: 'account', icon: 'person_add',            title: 'Welcome Aboard', description: 'Create your Just.Trades account',           xp: 25  },
        { id: 'connect_broker',  category: 'account', icon: 'link',                  title: 'Connected',      description: 'Connect your first broker account',         xp: 50  },
        { id: 'three_accounts',  category: 'account', icon: 'group',                 title: 'Multi-Account',  description: 'Connect 3 or more broker accounts',         xp: 150 },
        { id: 'create_recorder', category: 'account', icon: 'edit',                  title: 'Strategist',     description: 'Create your first recorder/strategy',       xp: 75  },
        { id: 'enable_dca',      category: 'account', icon: 'auto_fix_high',         title: 'DCA Master',     description: 'Enable DCA on a strategy',                  xp: 100 },
        // Social achievements
        { id: 'refer_one',       category: 'social',  icon: 'share',                 title: 'Advocate',       description: 'Refer your first trader',                   xp: 200 },
        { id: 'refer_five',      category: 'social',  icon: 'groups',                title: 'Influencer',     description: 'Refer 5 traders',                           xp: 500 },
        { id: 'affiliate',       category: 'social',  icon: 'handshake',             title: 'Partner',        description: 'Become an approved affiliate',              xp: 300 },
        // Streak achievements
        { id: 'streak_7',        category: 'trading', icon: 'local_fire_department', title: '7-Day Streak',   description: 'Trade 7 consecutive days',                  xp: 200 },
        { id: 'streak_30',       category: 'trading', icon: 'whatshot',              title: '30-Day Streak',  description: 'Trade 30 consecutive days',                 xp: 500 },
    ];

    // -------------------------------------------------------------------------
    // Level system
    // -------------------------------------------------------------------------
    function getLevel(totalXp) {
        const levels = [0, 100, 250, 500, 1000, 2000, 3500, 5500, 8000, 12000];
        let level = 1;
        for (let i = 1; i < levels.length; i++) {
            if (totalXp >= levels[i]) level = i + 1;
            else break;
        }
        const currentLevelXp = levels[level - 1] || 0;
        const nextLevelXp    = levels[level] || levels[levels.length - 1];
        const progress       = (totalXp - currentLevelXp) / (nextLevelXp - currentLevelXp);
        return { level, currentLevelXp, nextLevelXp, progress };
    }

    // -------------------------------------------------------------------------
    // State helpers (localStorage)
    // -------------------------------------------------------------------------
    function getUnlocked() {
        try {
            return JSON.parse(localStorage.getItem('gam_unlocked') || '[]');
        } catch (_) {
            return [];
        }
    }

    function getTotalXp() {
        return parseInt(localStorage.getItem('gam_total_xp') || '0', 10);
    }

    function getStreak() {
        return parseInt(localStorage.getItem('gam_streak') || '0', 10);
    }

    // -------------------------------------------------------------------------
    // Inject panel HTML + trigger button into the document
    // -------------------------------------------------------------------------
    function injectPanel() {
        if (document.getElementById('gam-panel')) return; // already injected

        // Styles ---------------------------------------------------------------
        const style = document.createElement('style');
        style.id = 'gam-styles';
        style.textContent = `
            /* Trigger button */
            #gam-trigger {
                position: fixed;
                bottom: 88px;
                right: 20px;
                z-index: 9000;
                width: 48px;
                height: 48px;
                border-radius: 50%;
                background: linear-gradient(135deg, #7c3aed, #a855f7);
                border: none;
                cursor: pointer;
                display: flex;
                align-items: center;
                justify-content: center;
                box-shadow: 0 4px 16px rgba(124,58,237,0.45);
                transition: transform 0.2s, box-shadow 0.2s;
            }
            #gam-trigger:hover {
                transform: scale(1.1);
                box-shadow: 0 6px 22px rgba(124,58,237,0.6);
            }
            #gam-trigger .material-icons {
                color: #fff;
                font-size: 22px;
            }

            /* Overlay */
            #gam-overlay {
                display: none;
                position: fixed;
                inset: 0;
                background: rgba(0,0,0,0.45);
                z-index: 9001;
            }
            #gam-overlay.gam-visible {
                display: block;
            }

            /* Side panel */
            #gam-panel {
                position: fixed;
                top: 0;
                right: 0;
                height: 100%;
                width: 360px;
                max-width: 100vw;
                background: #111827;
                border-left: 1px solid #1f2937;
                z-index: 9002;
                display: flex;
                flex-direction: column;
                transform: translateX(100%);
                transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
                box-shadow: -8px 0 32px rgba(0,0,0,0.5);
            }
            #gam-panel.gam-open {
                transform: translateX(0);
            }

            /* Panel header */
            .gam-header {
                padding: 16px 18px 12px;
                border-bottom: 1px solid #1f2937;
                display: flex;
                align-items: center;
                justify-content: space-between;
                flex-shrink: 0;
            }
            .gam-header-left {
                display: flex;
                align-items: center;
                gap: 10px;
            }
            .gam-header-left .material-icons {
                font-size: 26px;
                color: #a855f7;
            }
            .gam-header-title {
                font-size: 16px;
                font-weight: 700;
                color: #f9fafb;
                letter-spacing: 0.3px;
            }
            .gam-header-streak {
                display: flex;
                align-items: center;
                gap: 4px;
                font-size: 13px;
                font-weight: 600;
                color: #f97316;
            }
            .gam-header-streak .material-icons {
                font-size: 18px;
                color: #f97316;
            }
            .gam-close-btn {
                background: none;
                border: none;
                cursor: pointer;
                color: #6b7280;
                padding: 4px;
                border-radius: 6px;
                display: flex;
                align-items: center;
                transition: color 0.15s, background 0.15s;
            }
            .gam-close-btn:hover {
                color: #f9fafb;
                background: #1f2937;
            }
            .gam-close-btn .material-icons {
                font-size: 20px;
            }

            /* XP / Level section */
            .gam-level-section {
                padding: 14px 18px;
                border-bottom: 1px solid #1f2937;
                flex-shrink: 0;
            }
            .gam-level-row {
                display: flex;
                align-items: center;
                justify-content: space-between;
                margin-bottom: 8px;
            }
            .gam-level-badge {
                display: flex;
                align-items: center;
                gap: 6px;
            }
            .gam-level-num {
                background: linear-gradient(135deg, #7c3aed, #a855f7);
                color: #fff;
                font-size: 11px;
                font-weight: 800;
                padding: 3px 9px;
                border-radius: 12px;
                letter-spacing: 0.5px;
                text-transform: uppercase;
            }
            .gam-level-label {
                font-size: 13px;
                font-weight: 600;
                color: #d1d5db;
            }
            .gam-xp-display {
                font-size: 12px;
                color: #9ca3af;
            }
            .gam-xp-bar-wrap {
                background: #1f2937;
                border-radius: 6px;
                height: 7px;
                overflow: hidden;
            }
            .gam-xp-bar-fill {
                height: 100%;
                background: linear-gradient(90deg, #7c3aed, #a855f7);
                border-radius: 6px;
                transition: width 0.5s ease;
            }
            .gam-xp-caption {
                margin-top: 5px;
                font-size: 11px;
                color: #6b7280;
            }

            /* Tabs */
            .gam-tabs {
                display: flex;
                gap: 4px;
                padding: 10px 18px 8px;
                flex-shrink: 0;
                border-bottom: 1px solid #1f2937;
                overflow-x: auto;
            }
            .gam-tab {
                padding: 5px 12px;
                border-radius: 20px;
                border: 1px solid #374151;
                background: transparent;
                color: #9ca3af;
                font-size: 12px;
                font-weight: 600;
                cursor: pointer;
                white-space: nowrap;
                transition: background 0.15s, color 0.15s, border-color 0.15s;
            }
            .gam-tab:hover {
                border-color: #6d28d9;
                color: #c4b5fd;
            }
            .gam-tab.gam-tab-active {
                background: #6d28d9;
                border-color: #6d28d9;
                color: #fff;
            }

            /* Achievements list */
            .gam-list {
                flex: 1;
                overflow-y: auto;
                padding: 12px 18px 20px;
                display: flex;
                flex-direction: column;
                gap: 10px;
            }
            .gam-list::-webkit-scrollbar {
                width: 4px;
            }
            .gam-list::-webkit-scrollbar-track {
                background: transparent;
            }
            .gam-list::-webkit-scrollbar-thumb {
                background: #374151;
                border-radius: 4px;
            }

            /* Achievement card */
            .gam-card {
                display: flex;
                align-items: flex-start;
                gap: 12px;
                background: #1f2937;
                border: 1px solid #374151;
                border-radius: 10px;
                padding: 12px 14px;
                position: relative;
                transition: border-color 0.2s;
            }
            .gam-card.gam-card-unlocked {
                border-color: #5b21b6;
                background: linear-gradient(135deg, #1f1535 0%, #1f2937 100%);
            }
            .gam-card.gam-card-locked {
                opacity: 0.65;
            }

            /* Card icon */
            .gam-card-icon {
                width: 40px;
                height: 40px;
                border-radius: 10px;
                display: flex;
                align-items: center;
                justify-content: center;
                flex-shrink: 0;
            }
            .gam-card-unlocked .gam-card-icon {
                background: linear-gradient(135deg, #6d28d9, #a855f7);
            }
            .gam-card-locked .gam-card-icon {
                background: #374151;
            }
            .gam-card-icon .material-icons {
                font-size: 20px;
            }
            .gam-card-unlocked .gam-card-icon .material-icons {
                color: #fff;
            }
            .gam-card-locked .gam-card-icon .material-icons {
                color: #6b7280;
            }

            /* Card body */
            .gam-card-body {
                flex: 1;
                min-width: 0;
            }
            .gam-card-title-row {
                display: flex;
                align-items: center;
                gap: 6px;
                flex-wrap: wrap;
            }
            .gam-card-title {
                font-size: 14px;
                font-weight: 700;
                color: #f9fafb;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }
            .gam-card-locked .gam-card-title {
                color: #d1d5db;
            }
            .gam-unlocked-badge {
                font-size: 10px;
                font-weight: 800;
                background: #6d28d9;
                color: #e9d5ff;
                padding: 2px 7px;
                border-radius: 10px;
                letter-spacing: 0.5px;
                text-transform: uppercase;
                flex-shrink: 0;
            }
            .gam-card-desc {
                font-size: 12px;
                color: #9ca3af;
                margin-top: 3px;
                line-height: 1.4;
            }
            .gam-card-xp {
                font-size: 12px;
                font-weight: 700;
                color: #a855f7;
                margin-top: 5px;
            }
            .gam-card-locked .gam-card-xp {
                color: #6b7280;
            }

            /* Lock icon overlay */
            .gam-lock-overlay {
                position: absolute;
                top: 8px;
                right: 10px;
                color: #4b5563;
                display: flex;
                align-items: center;
            }
            .gam-lock-overlay .material-icons {
                font-size: 16px;
            }

            /* Check mark for unlocked */
            .gam-check-overlay {
                position: absolute;
                top: 8px;
                right: 10px;
                color: #a855f7;
                display: flex;
                align-items: center;
            }
            .gam-check-overlay .material-icons {
                font-size: 18px;
            }

            /* Progress bar on locked cards */
            .gam-card-progress-wrap {
                background: #374151;
                border-radius: 4px;
                height: 4px;
                margin-top: 7px;
                overflow: hidden;
            }
            .gam-card-progress-fill {
                height: 100%;
                background: #6d28d9;
                border-radius: 4px;
                transition: width 0.4s ease;
            }

            /* Toast notifications */
            .gam-toast-container {
                position: fixed;
                top: 20px;
                right: 20px;
                z-index: 99999;
                display: flex;
                flex-direction: column;
                gap: 10px;
                pointer-events: none;
            }
            .gam-toast {
                background: #1f2937;
                border: 1px solid #5b21b6;
                border-radius: 12px;
                padding: 12px 16px;
                display: flex;
                align-items: center;
                gap: 12px;
                box-shadow: 0 8px 24px rgba(0,0,0,0.5);
                min-width: 260px;
                max-width: 320px;
                animation: gam-toast-in 0.3s ease forwards;
                pointer-events: auto;
            }
            .gam-toast.gam-toast-out {
                animation: gam-toast-out 0.35s ease forwards;
            }
            @keyframes gam-toast-in {
                from { opacity: 0; transform: translateX(40px); }
                to   { opacity: 1; transform: translateX(0); }
            }
            @keyframes gam-toast-out {
                from { opacity: 1; transform: translateX(0); }
                to   { opacity: 0; transform: translateX(40px); }
            }
            .gam-toast-icon {
                width: 36px;
                height: 36px;
                border-radius: 9px;
                background: linear-gradient(135deg, #6d28d9, #a855f7);
                display: flex;
                align-items: center;
                justify-content: center;
                flex-shrink: 0;
            }
            .gam-toast-icon .material-icons {
                font-size: 18px;
                color: #fff;
            }
            .gam-toast-body {
                flex: 1;
                min-width: 0;
            }
            .gam-toast-label {
                font-size: 10px;
                font-weight: 800;
                color: #a855f7;
                text-transform: uppercase;
                letter-spacing: 0.6px;
            }
            .gam-toast-title {
                font-size: 14px;
                font-weight: 700;
                color: #f9fafb;
            }
            .gam-toast-xp {
                font-size: 12px;
                font-weight: 700;
                color: #86efac;
                margin-top: 1px;
            }

            /* Empty state */
            .gam-empty {
                text-align: center;
                padding: 32px 16px;
                color: #6b7280;
                font-size: 13px;
            }
            .gam-empty .material-icons {
                font-size: 36px;
                color: #374151;
                display: block;
                margin-bottom: 10px;
            }
        `;
        document.head.appendChild(style);

        // Toast container (outside the panel, always visible) -----------------
        const toastContainer = document.createElement('div');
        toastContainer.className = 'gam-toast-container';
        toastContainer.id = 'gam-toast-container';
        document.body.appendChild(toastContainer);

        // Trigger button -------------------------------------------------------
        const trigger = document.createElement('button');
        trigger.id = 'gam-trigger';
        trigger.title = 'Achievements';
        trigger.innerHTML = '<span class="material-icons">emoji_events</span>';
        trigger.addEventListener('click', openPanel);
        document.body.appendChild(trigger);

        // Overlay --------------------------------------------------------------
        const overlay = document.createElement('div');
        overlay.id = 'gam-overlay';
        overlay.addEventListener('click', closePanel);
        document.body.appendChild(overlay);

        // Panel ----------------------------------------------------------------
        const panel = document.createElement('div');
        panel.id = 'gam-panel';
        panel.setAttribute('role', 'dialog');
        panel.setAttribute('aria-modal', 'true');
        panel.setAttribute('aria-label', 'Achievements');
        panel.innerHTML = `
            <div class="gam-header">
                <div class="gam-header-left">
                    <span class="material-icons">emoji_events</span>
                    <span class="gam-header-title">Achievements</span>
                </div>
                <div style="display:flex;align-items:center;gap:12px;">
                    <div class="gam-header-streak" id="gam-streak-display" style="display:none;">
                        <span class="material-icons">local_fire_department</span>
                        <span id="gam-streak-count">0</span>d
                    </div>
                    <button class="gam-close-btn" id="gam-close-btn" aria-label="Close achievements panel">
                        <span class="material-icons">close</span>
                    </button>
                </div>
            </div>

            <div class="gam-level-section" id="gam-level-section">
                <div class="gam-level-row">
                    <div class="gam-level-badge">
                        <span class="gam-level-num" id="gam-level-num">Lv 1</span>
                        <span class="gam-level-label" id="gam-level-label">Newcomer</span>
                    </div>
                    <span class="gam-xp-display" id="gam-xp-display">0 XP</span>
                </div>
                <div class="gam-xp-bar-wrap">
                    <div class="gam-xp-bar-fill" id="gam-xp-bar-fill" style="width:0%"></div>
                </div>
                <div class="gam-xp-caption" id="gam-xp-caption">0 / 100 XP to next level</div>
            </div>

            <div class="gam-tabs" id="gam-tabs">
                <button class="gam-tab gam-tab-active" data-filter="all">All</button>
                <button class="gam-tab" data-filter="trading">Trading</button>
                <button class="gam-tab" data-filter="account">Account</button>
                <button class="gam-tab" data-filter="social">Social</button>
            </div>

            <div class="gam-list" id="gam-list"></div>
        `;
        document.body.appendChild(panel);

        // Wire up close button
        document.getElementById('gam-close-btn').addEventListener('click', closePanel);

        // Wire up tabs
        document.getElementById('gam-tabs').addEventListener('click', function (e) {
            const btn = e.target.closest('.gam-tab');
            if (!btn) return;
            document.querySelectorAll('.gam-tab').forEach(t => t.classList.remove('gam-tab-active'));
            btn.classList.add('gam-tab-active');
            renderAchievements(btn.dataset.filter || 'all');
        });

        // Escape key closes panel
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') closePanel();
        });
    }

    // -------------------------------------------------------------------------
    // Panel open / close
    // -------------------------------------------------------------------------
    function openPanel() {
        const panel   = document.getElementById('gam-panel');
        const overlay = document.getElementById('gam-overlay');
        if (!panel) return;
        panel.classList.add('gam-open');
        overlay.classList.add('gam-visible');
        document.body.style.overflow = 'hidden';
    }

    function closePanel() {
        const panel   = document.getElementById('gam-panel');
        const overlay = document.getElementById('gam-overlay');
        if (!panel) return;
        panel.classList.remove('gam-open');
        overlay.classList.remove('gam-visible');
        document.body.style.overflow = '';
    }

    // -------------------------------------------------------------------------
    // Level name helper
    // -------------------------------------------------------------------------
    function getLevelName(level) {
        const names = ['', 'Newcomer', 'Apprentice', 'Trader', 'Veteran', 'Expert',
                        'Elite', 'Master', 'Grand Master', 'Legend', 'Apex'];
        return names[level] || 'Apex';
    }

    // -------------------------------------------------------------------------
    // Render panel state (XP bar, streak, etc.)
    // -------------------------------------------------------------------------
    function renderPanel() {
        const totalXp = getTotalXp();
        const streak  = getStreak();
        const lvData  = getLevel(totalXp);

        // Level badge + XP bar
        const levelNumEl  = document.getElementById('gam-level-num');
        const levelLblEl  = document.getElementById('gam-level-label');
        const xpDisplayEl = document.getElementById('gam-xp-display');
        const xpBarEl     = document.getElementById('gam-xp-bar-fill');
        const xpCaptEl    = document.getElementById('gam-xp-caption');

        if (levelNumEl) levelNumEl.textContent = 'Lv ' + lvData.level;
        if (levelLblEl) levelLblEl.textContent = getLevelName(lvData.level);
        if (xpDisplayEl) xpDisplayEl.textContent = totalXp.toLocaleString() + ' XP';
        if (xpBarEl) xpBarEl.style.width = Math.min(100, Math.round(lvData.progress * 100)) + '%';
        if (xpCaptEl) {
            const xpInLevel    = totalXp - lvData.currentLevelXp;
            const xpNeeded     = lvData.nextLevelXp - lvData.currentLevelXp;
            xpCaptEl.textContent = xpInLevel.toLocaleString() + ' / ' + xpNeeded.toLocaleString() + ' XP to next level';
        }

        // Streak
        const streakDisplay = document.getElementById('gam-streak-display');
        const streakCount   = document.getElementById('gam-streak-count');
        if (streakDisplay && streakCount) {
            if (streak > 0) {
                streakDisplay.style.display = 'flex';
                streakCount.textContent = streak;
            } else {
                streakDisplay.style.display = 'none';
            }
        }

        // Render with current active tab
        const activeTab = document.querySelector('.gam-tab.gam-tab-active');
        renderAchievements(activeTab ? (activeTab.dataset.filter || 'all') : 'all');
    }

    // -------------------------------------------------------------------------
    // Achievement rendering
    // -------------------------------------------------------------------------
    function renderAchievements(filter) {
        const list     = document.getElementById('gam-list');
        if (!list) return;

        const unlocked = getUnlocked();
        const filtered = filter === 'all'
            ? ACHIEVEMENTS
            : ACHIEVEMENTS.filter(a => a.category === filter);

        if (filtered.length === 0) {
            list.innerHTML = `
                <div class="gam-empty">
                    <span class="material-icons">search_off</span>
                    No achievements in this category yet.
                </div>`;
            return;
        }

        // Sort: unlocked first, then locked
        const sorted = filtered.slice().sort((a, b) => {
            const aUnlocked = unlocked.includes(a.id) ? 0 : 1;
            const bUnlocked = unlocked.includes(b.id) ? 0 : 1;
            return aUnlocked - bUnlocked;
        });

        list.innerHTML = sorted.map(function (ach) {
            const isUnlocked = unlocked.includes(ach.id);

            if (isUnlocked) {
                return `
                    <div class="gam-card gam-card-unlocked">
                        <div class="gam-card-icon">
                            <span class="material-icons">${escapeHtml(ach.icon)}</span>
                        </div>
                        <div class="gam-card-body">
                            <div class="gam-card-title-row">
                                <span class="gam-card-title">${escapeHtml(ach.title)}</span>
                                <span class="gam-unlocked-badge">Unlocked</span>
                            </div>
                            <div class="gam-card-desc">${escapeHtml(ach.description)}</div>
                            <div class="gam-card-xp">+${ach.xp} XP</div>
                        </div>
                        <div class="gam-check-overlay">
                            <span class="material-icons">check_circle</span>
                        </div>
                    </div>`;
            } else {
                // Retrieve progress data if available (stored as gam_progress_{id})
                let progressHtml = '';
                try {
                    const rawProgress = localStorage.getItem('gam_progress_' + ach.id);
                    if (rawProgress !== null) {
                        const pct = Math.min(100, Math.max(0, parseFloat(rawProgress) || 0));
                        progressHtml = `
                            <div class="gam-card-progress-wrap">
                                <div class="gam-card-progress-fill" style="width:${pct}%"></div>
                            </div>`;
                    }
                } catch (_) { /* ignore */ }

                return `
                    <div class="gam-card gam-card-locked">
                        <div class="gam-card-icon">
                            <span class="material-icons">${escapeHtml(ach.icon)}</span>
                        </div>
                        <div class="gam-card-body">
                            <div class="gam-card-title-row">
                                <span class="gam-card-title">${escapeHtml(ach.title)}</span>
                            </div>
                            <div class="gam-card-desc">${escapeHtml(ach.description)}</div>
                            <div class="gam-card-xp">${ach.xp} XP</div>
                            ${progressHtml}
                        </div>
                        <div class="gam-lock-overlay">
                            <span class="material-icons">lock</span>
                        </div>
                    </div>`;
            }
        }).join('');
    }

    // -------------------------------------------------------------------------
    // Toast notifications
    // -------------------------------------------------------------------------
    function showToast(achievement) {
        const container = document.getElementById('gam-toast-container');
        if (!container) return;

        const toast = document.createElement('div');
        toast.className = 'gam-toast';
        toast.innerHTML = `
            <div class="gam-toast-icon">
                <span class="material-icons">${escapeHtml(achievement.icon)}</span>
            </div>
            <div class="gam-toast-body">
                <div class="gam-toast-label">Achievement Unlocked</div>
                <div class="gam-toast-title">${escapeHtml(achievement.title)}</div>
                <div class="gam-toast-xp">+${achievement.xp} XP</div>
            </div>`;

        container.appendChild(toast);

        // Auto-dismiss after 4 seconds
        setTimeout(function () {
            toast.classList.add('gam-toast-out');
            toast.addEventListener('animationend', function () {
                if (toast.parentNode) toast.parentNode.removeChild(toast);
            });
        }, 4000);
    }

    // -------------------------------------------------------------------------
    // API integration — graceful fallback to localStorage
    // -------------------------------------------------------------------------
    function fetchStatus() {
        fetch('/api/gamification/status')
            .then(function (r) { return r.ok ? r.json() : null; })
            .then(function (data) {
                if (data && data.unlocked) {
                    // Detect newly unlocked achievements to show toasts
                    const previouslyUnlocked = getUnlocked();
                    const newlyUnlocked = (data.unlocked || []).filter(function (id) {
                        return !previouslyUnlocked.includes(id);
                    });

                    localStorage.setItem('gam_unlocked', JSON.stringify(data.unlocked));
                    localStorage.setItem('gam_total_xp', data.total_xp || 0);

                    if (data.streak !== undefined) {
                        localStorage.setItem('gam_streak', data.streak || 0);
                    }

                    // Persist per-achievement progress if provided
                    if (data.progress && typeof data.progress === 'object') {
                        Object.keys(data.progress).forEach(function (id) {
                            localStorage.setItem('gam_progress_' + id, data.progress[id]);
                        });
                    }

                    // Show toasts for newly unlocked achievements
                    newlyUnlocked.forEach(function (id) {
                        const ach = ACHIEVEMENTS.find(function (a) { return a.id === id; });
                        if (ach) {
                            setTimeout(function () { showToast(ach); }, 500);
                        }
                    });
                }
                renderPanel();
            })
            .catch(function () {
                // Graceful fallback: just render with whatever is in localStorage
                renderPanel();
            });
    }

    // -------------------------------------------------------------------------
    // Escape HTML helper
    // -------------------------------------------------------------------------
    function escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    // -------------------------------------------------------------------------
    // Public helper — unlock an achievement programmatically from other scripts
    // Usage: window.GamUnlock('first_trade');
    // -------------------------------------------------------------------------
    window.GamUnlock = function (achievementId) {
        const ach = ACHIEVEMENTS.find(function (a) { return a.id === achievementId; });
        if (!ach) return;

        const unlocked = getUnlocked();
        if (unlocked.includes(achievementId)) return; // already unlocked

        unlocked.push(achievementId);
        const newXp = getTotalXp() + ach.xp;
        localStorage.setItem('gam_unlocked', JSON.stringify(unlocked));
        localStorage.setItem('gam_total_xp', newXp);

        showToast(ach);
        renderPanel();
    };

    // -------------------------------------------------------------------------
    // Init
    // -------------------------------------------------------------------------
    function init() {
        if (document.body.dataset.userLoggedIn !== 'true') return;
        injectPanel();
        fetchStatus();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();
