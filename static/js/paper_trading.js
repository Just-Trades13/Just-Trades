/**
 * Paper Trading Dashboard — vanilla JS (converted from PaperTradingDashboard_v3.jsx)
 * SocketIO on /paper namespace, price_update on main namespace
 */
(function() {
    'use strict';

    // ── State ───────────────────────────────────────────────────────────
    let positions = [];
    let history = [];
    let marks = {};
    let stats = {};
    let analysis = null;
    let connected = false;
    let currentTab = 'positions';
    let prevPrice = 0;
    let currentPrice = 0;
    let tickCount = 0;

    // ── Socket.IO ───────────────────────────────────────────────────────
    const paperSocket = io('/paper', { transports: ['websocket', 'polling'] });
    const mainSocket = io('/', { transports: ['websocket', 'polling'] });

    paperSocket.on('connect', function() {
        connected = true;
        renderStatusDot();
        paperSocket.emit('get_state', { account: 'default' });
    });

    paperSocket.on('disconnect', function() {
        connected = false;
        renderStatusDot();
    });

    paperSocket.on('paper_state', function(state) {
        applyState(state);
    });

    paperSocket.on('paper_analysis', function(data) {
        analysis = data;
        if (currentTab === 'analytics') renderAnalytics();
    });

    // Live price from main namespace
    mainSocket.on('price_update', function(data) {
        if (data && data.symbol && data.price) {
            var sym = data.symbol.toUpperCase();
            prevPrice = marks[sym] || parseFloat(data.price);
            currentPrice = parseFloat(data.price);
            marks[sym] = currentPrice;
            renderTicker(sym);
        }
    });

    function applyState(state) {
        if (state.open_positions) positions = state.open_positions;
        if (state.history) history = state.history;
        if (state.marks) {
            for (var k in state.marks) {
                prevPrice = marks[k] || state.marks[k];
                currentPrice = state.marks[k];
                marks[k] = state.marks[k];
            }
        }
        if (state.stats) stats = state.stats;
        tickCount++;
        renderAll();
    }

    // ── Helpers ─────────────────────────────────────────────────────────
    function fmt$(n) {
        if (n == null) return '—';
        return (n >= 0 ? '+' : '') + n.toLocaleString('en-US', {
            style: 'currency', currency: 'USD', minimumFractionDigits: 2
        });
    }
    function fmtPt(n) {
        if (n == null) return '—';
        return (n >= 0 ? '+' : '') + n.toFixed(2) + 'pts';
    }
    function pnlClass(n) {
        return n > 0 ? 'pnl-positive' : n < 0 ? 'pnl-negative' : 'pnl-zero';
    }
    function pnlColor(n) {
        return n > 0 ? '#00ff88' : n < 0 ? '#ff4466' : '#555';
    }
    function elapsed(iso) {
        var s = Math.floor((Date.now() - new Date(iso)) / 1000);
        if (s < 60) return s + 's';
        if (s < 3600) return Math.floor(s / 60) + 'm ' + (s % 60) + 's';
        return Math.floor(s / 3600) + 'h ' + Math.floor((s % 3600) / 60) + 'm';
    }
    function ftime(iso) {
        return new Date(iso).toLocaleTimeString('en-US', {
            hour: '2-digit', minute: '2-digit', second: '2-digit'
        });
    }
    function exitTag(str) {
        if (!str) return null;
        if (str.indexOf('TP') >= 0) return { label: 'TP', color: '#00ff88' };
        if (str.indexOf('SL') >= 0) return { label: 'SL', color: '#ff4466' };
        if (str.indexOf('TRAIL') >= 0) return { label: 'TRAIL', color: '#ffcc44' };
        if (str.indexOf('RISK') >= 0) return { label: 'RISK', color: '#ff8800' };
        if (str.indexOf('FLIP') >= 0) return { label: 'FLIP', color: '#44aaff' };
        if (str.indexOf('PARTIAL') >= 0) return { label: 'PART', color: '#aa88ff' };
        return { label: 'EXIT', color: '#888' };
    }
    function tagHTML(label, color) {
        return '<span class="paper-tag" style="background:' + color + '18;color:' + color +
            ';border:1px solid ' + color + '44">' + label + '</span>';
    }
    function capturePillHTML(ratio) {
        if (ratio == null) return '<span style="color:#555;font-size:11px">—</span>';
        var pct = Math.max(0, Math.min(ratio * 100, 150));
        var c = pct >= 75 ? '#00ff88' : pct >= 50 ? '#ffcc44' : '#ff4466';
        return '<span class="paper-capture-pill" style="color:' + c + '">' + Math.round(pct) + '%</span>';
    }
    function loc(n) {
        return n != null ? n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '—';
    }

    // ── Render Functions ────────────────────────────────────────────────
    function renderStatusDot() {
        var dot = document.getElementById('paper-status-dot');
        if (dot) {
            dot.className = 'paper-status-dot' + (connected ? ' connected' : '');
        }
    }

    function renderTicker(symbol) {
        var el = document.getElementById('paper-ticker-price');
        if (el) {
            el.textContent = loc(currentPrice);
            el.className = 'paper-ticker-price ' + (currentPrice >= prevPrice ? 'up' : 'down');
        }
        var arrow = document.getElementById('paper-ticker-arrow');
        if (arrow) {
            arrow.textContent = currentPrice >= prevPrice ? '\u25B2' : '\u25BC';
            arrow.style.color = currentPrice >= prevPrice ? '#00ff88' : '#ff4466';
        }
    }

    function renderHeaderStats() {
        var realized = stats.realized_pnl || 0;
        var unrealized = stats.unrealized_pnl || 0;
        var net = stats.net_pnl || 0;
        var winRate = stats.win_rate || 0;

        var caps = history.filter(function(t) { return t.capture_ratio != null; });
        var avgCap = caps.length ? caps.reduce(function(s, t) { return s + t.capture_ratio; }, 0) / caps.length : 0;

        var items = [
            { l: 'NET PnL', v: fmt$(net), c: pnlColor(net) },
            { l: 'REALIZED', v: fmt$(realized), c: pnlColor(realized) },
            { l: 'UNREALIZED', v: fmt$(unrealized), c: pnlColor(unrealized) },
            { l: 'WIN RATE', v: winRate + '%', c: winRate >= 50 ? '#00ff88' : '#ff8844' },
            { l: 'CAPTURE', v: caps.length ? Math.round(avgCap * 100) + '%' : '—',
              c: avgCap >= 0.7 ? '#00ff88' : avgCap >= 0.5 ? '#ffcc44' : '#ff8844' },
        ];
        var el = document.getElementById('paper-header-stats');
        if (!el) return;
        el.innerHTML = items.map(function(item) {
            return '<div class="paper-header-stat">' +
                '<div class="paper-header-stat-label">' + item.l + '</div>' +
                '<div class="paper-header-stat-value" style="color:' + item.c + '">' + item.v + '</div>' +
                '</div>';
        }).join('');
    }

    function renderTabs() {
        var tabs = [
            { id: 'positions', label: 'Open (' + positions.length + ')' },
            { id: 'history', label: 'History (' + history.length + ')' },
            { id: 'analytics', label: 'MAE/MFE' },
        ];
        var el = document.getElementById('paper-tabs');
        if (!el) return;
        el.innerHTML = tabs.map(function(t) {
            return '<button class="paper-tab' + (currentTab === t.id ? ' active' : '') +
                '" data-tab="' + t.id + '">' + t.label + '</button>';
        }).join('');

        el.querySelectorAll('.paper-tab').forEach(function(btn) {
            btn.addEventListener('click', function() {
                currentTab = this.getAttribute('data-tab');
                renderTabs();
                renderContent();
                if (currentTab === 'analytics' && !analysis) {
                    paperSocket.emit('get_analysis', { account: 'default' });
                }
            });
        });
    }

    function renderContent() {
        var el = document.getElementById('paper-content');
        if (!el) return;

        if (currentTab === 'positions') {
            renderPositions(el);
        } else if (currentTab === 'history') {
            renderHistory(el);
        } else if (currentTab === 'analytics') {
            renderAnalytics(el);
        }
    }

    // ── Positions Tab ───────────────────────────────────────────────────
    function renderPositions(container) {
        container = container || document.getElementById('paper-content');
        if (!container) return;

        if (positions.length === 0) {
            container.innerHTML = '<div class="paper-empty">' +
                'No open paper positions.' +
                '<div class="paper-empty-hint">Send a webhook to /paper/signal to open one.</div></div>';
            return;
        }

        container.innerHTML = positions.map(function(pos) {
            var up = (pos.unrealized_pnl || 0) >= 0;
            var exc = pos.excursion || {};
            var sideColor = pos.side === 'long' ? '#00ff88' : '#ff4466';

            // Brackets
            var brackets = '';
            if (pos.tp) brackets += tagHTML('TP ' + loc(pos.tp), '#00ff88') + ' ';
            if (pos.sl) brackets += tagHTML('SL ' + loc(pos.sl), '#ff4466') + ' ';
            if (pos.trail_points) {
                brackets += tagHTML('TRAIL ' + pos.trail_points + 'pt', '#ffcc44') + ' ';
                if (pos.trail_stop) {
                    brackets += '<span style="font-size:10px;font-family:monospace;color:rgba(255,204,68,0.4)">' +
                        'stop@' + loc(pos.trail_stop) + '</span>';
                }
            }

            // Excursion meter
            var maxV = Math.max((exc.mae_points || 0) + (exc.mfe_points || 0) + 5, 20);
            var maePct = Math.min((exc.mae_points || 0) / maxV * 50, 50);
            var mfePct = Math.min((exc.mfe_points || 0) / maxV * 50, 50);

            var excHTML = '<div class="paper-excursion">' +
                '<div style="text-align:right;min-width:80px">' +
                    '<div class="paper-exc-label mae">MAE</div>' +
                    '<div class="paper-exc-value mae">' + fmtPt(-(exc.mae_points || 0)) + '</div>' +
                    '<div class="paper-exc-sub">' + (exc.mae_ticks || 0) + 't  ' + fmt$(-(exc.mae_dollars || 0)) + '</div>' +
                '</div>' +
                '<div class="paper-exc-bar-wrap">' +
                    '<div class="paper-exc-bar">' +
                        '<div class="paper-exc-bar-mae" style="width:' + maePct + '%"></div>' +
                        '<div class="paper-exc-bar-center"></div>' +
                        '<div class="paper-exc-bar-mfe" style="width:' + mfePct + '%"></div>' +
                    '</div>' +
                    '<div class="paper-exc-range"><span>' + loc(exc.lowest_seen) + '</span><span>' + loc(exc.highest_seen) + '</span></div>' +
                '</div>' +
                '<div style="min-width:80px">' +
                    '<div class="paper-exc-label mfe">MFE</div>' +
                    '<div class="paper-exc-value mfe">' + fmtPt(exc.mfe_points || 0) + '</div>' +
                    '<div class="paper-exc-sub">' + (exc.mfe_ticks || 0) + 't  ' + fmt$(exc.mfe_dollars || 0) + '</div>' +
                '</div>' +
                '<div class="paper-exc-stat">' +
                    '<div class="paper-exc-stat-label">CAPTURE</div>' +
                    capturePillHTML(exc.capture_ratio) +
                '</div>' +
                (exc.efficiency != null ? '<div class="paper-exc-stat">' +
                    '<div class="paper-exc-stat-label">EDGE</div>' +
                    '<span class="paper-exc-stat-value" style="color:' +
                        (exc.efficiency >= 0.7 ? '#00ff88' : exc.efficiency >= 0.5 ? '#ffcc44' : '#ff4466') +
                    '">' + Math.round(exc.efficiency * 100) + '%</span>' +
                '</div>' : '') +
                '<div class="paper-exc-stat">' +
                    '<div class="paper-exc-stat-label">TICKS</div>' +
                    '<span style="font-family:monospace;font-size:11px;color:#555">' +
                        (exc.tick_count || 0).toLocaleString() + '</span>' +
                '</div>' +
            '</div>';

            // DCA legs
            var legsHTML = '';
            if (pos.legs && pos.legs.length > 1) {
                legsHTML = '<div class="paper-legs">' + pos.legs.map(function(leg, i) {
                    return '<div class="paper-leg">' +
                        '<span class="paper-leg-num">leg ' + (i + 1) + '  </span>' +
                        '<span class="paper-leg-detail">' + leg.qty + 'ct @ ' + loc(leg.price) + '</span>' +
                        (leg.comment ? '<span class="paper-leg-comment">' + leg.comment + '</span>' : '') +
                    '</div>';
                }).join('') + '</div>';
            }

            return '<div class="paper-position-card ' + (up ? 'profit' : 'loss') + '">' +
                '<div class="paper-position-top">' +
                    tagHTML(pos.side, sideColor) +
                    '<div class="paper-position-info">' +
                        '<span class="paper-position-symbol">' + pos.symbol + '</span>' +
                        '<span class="paper-position-qty">' + pos.qty + ' contract' + (pos.qty > 1 ? 's' : '') + '</span>' +
                    '</div>' +
                    '<div class="paper-position-prices">' +
                        'avg <span class="avg">' + loc(pos.avg_entry) + '</span>' +
                        '<span class="arrow">\u2192</span>' +
                        'mark <span class="mark">' + loc(pos.mark_price) + '</span>' +
                    '</div>' +
                    '<div class="paper-position-brackets">' + brackets + '</div>' +
                    '<div class="paper-position-pnl">' +
                        '<div class="paper-position-pnl-value" style="color:' + pnlColor(pos.unrealized_pnl) + '">' +
                            fmt$(pos.unrealized_pnl) + '</div>' +
                        '<div class="paper-position-pnl-time">' + elapsed(pos.entry_time) + ' open</div>' +
                    '</div>' +
                '</div>' +
                excHTML +
                legsHTML +
            '</div>';
        }).join('');
    }

    // ── History Tab ─────────────────────────────────────────────────────
    function renderHistory(container) {
        container = container || document.getElementById('paper-content');
        if (!container) return;

        var headerHTML = '<div class="paper-history-header">' +
            '<div>Side</div><div>Symbol</div><div>Time</div><div>Entry\u2192Exit</div>' +
            '<div>MAE/MFE</div><div>Capture</div><div>Legs</div>' +
            '<div style="text-align:right">PnL</div><div>Exit</div></div>';

        if (history.length === 0) {
            container.innerHTML = '<div class="paper-history-table">' + headerHTML +
                '<div class="paper-empty" style="padding:40px">No closed trades yet.</div></div>';
            return;
        }

        var rows = history.slice().reverse().map(function(t) {
            var sideColor = t.side === 'long' ? '#00ff88' : '#ff4466';
            var tag = exitTag(t.exit_comment);
            var total = (t.mae_points || 0) + (t.mfe_points || 0) || 1;
            var maePct = ((t.mae_points || 0) / total) * 100;
            var mfePct = ((t.mfe_points || 0) / total) * 100;

            return '<div class="paper-history-row">' +
                tagHTML(t.side, sideColor) +
                '<span style="color:#bbb">' + t.symbol + '</span>' +
                '<span style="color:#555;font-size:10px">' + (t.exit_time ? ftime(t.exit_time) : '') + '</span>' +
                '<span><span style="color:#666">' + loc(t.avg_entry) + '</span>' +
                    '<span style="color:#333;margin:0 3px">\u2192</span>' +
                    '<span style="color:#999">' + loc(t.exit_price) + '</span></span>' +
                '<div>' +
                    '<div style="display:flex;gap:4px;font-size:10px;margin-bottom:2px">' +
                        '<span style="color:rgba(255,68,102,0.5)">' + (t.mae_points != null ? t.mae_points.toFixed(1) : '0') + 'p</span>' +
                        '<span style="color:#333">/</span>' +
                        '<span style="color:rgba(0,255,136,0.5)">+' + (t.mfe_points != null ? t.mfe_points.toFixed(1) : '0') + 'p</span>' +
                    '</div>' +
                    '<div class="paper-minibar">' +
                        '<div class="paper-minibar-mae" style="width:' + maePct + '%"></div>' +
                        '<div class="paper-minibar-mfe" style="width:' + mfePct + '%"></div>' +
                    '</div>' +
                '</div>' +
                capturePillHTML(t.capture_ratio) +
                '<span style="color:#555;font-size:10px">' + (t.legs && t.legs.length > 1 ? t.legs.length + ' legs' : '') + '</span>' +
                '<span class="paper-history-pnl" style="color:' + pnlColor(t.realized_pnl) + '">' + fmt$(t.realized_pnl) + '</span>' +
                (tag ? tagHTML(tag.label, tag.color) : '') +
            '</div>';
        }).join('');

        container.innerHTML = '<div class="paper-history-table">' + headerHTML + rows + '</div>';
    }

    // ── Analytics Tab ───────────────────────────────────────────────────
    function renderAnalytics(container) {
        container = container || document.getElementById('paper-content');
        if (!container) return;

        if (!analysis || analysis.trades_analyzed === 0) {
            container.innerHTML = '<div class="paper-empty" style="padding:60px">' +
                'No closed trades with MAE/MFE data yet.</div>';
            return;
        }

        var a = analysis;
        var cards = [
            { l: 'Avg MAE', v: a.avg_mae.toFixed(1) + 'pts', c: '#ff4466', s: 'avg worst excursion' },
            { l: 'Avg MFE', v: '+' + a.avg_mfe.toFixed(1) + 'pts', c: '#00ff88', s: 'avg best excursion' },
            { l: 'Capture', v: a.avg_capture != null ? a.avg_capture.toFixed(0) + '%' : '—',
              c: a.avg_capture >= 70 ? '#00ff88' : a.avg_capture >= 50 ? '#ffcc44' : '#ff8844',
              s: 'avg % of MFE taken' },
            { l: 'Stop Rec', v: a.p80_mae.toFixed(1) + 'pts', c: '#ffcc44', s: '80th pct MAE — min stop' },
            { l: 'Target Rec', v: '+' + a.p50_mfe.toFixed(1) + 'pts', c: '#44aaff', s: 'median MFE' },
            { l: 'W/L MAE', v: a.winner_mae.toFixed(1) + ' / ' + a.loser_mae.toFixed(1),
              c: a.winner_mae < a.loser_mae * 0.7 ? '#00ff88' : '#ffcc44', s: 'winner vs loser adverse' },
        ];

        var gridHTML = '<div class="paper-analytics-grid">' + cards.map(function(c) {
            return '<div class="paper-stat-card">' +
                '<div class="paper-stat-card-label">' + c.l + '</div>' +
                '<div class="paper-stat-card-value" style="color:' + c.c + '">' + c.v + '</div>' +
                (c.s ? '<div class="paper-stat-card-sub">' + c.s + '</div>' : '') +
            '</div>';
        }).join('') + '</div>';

        // MAE distribution
        var dist = a.mae_distribution || [];
        var maxMae = dist.length > 0 ? Math.max.apply(null, dist.map(function(d) { return d.mae; })) : 30;
        var p80Scale = a.p80_mae * 1.5 || maxMae;

        var distHTML = '';
        if (dist.length > 0) {
            distHTML = '<div class="paper-mae-dist">' +
                '<div class="paper-mae-dist-title">MAE Distribution (worst \u2192 best)</div>' +
                '<div class="paper-mae-dist-bars">' + dist.map(function(d) {
                    var h = Math.min((d.mae / p80Scale) * 100, 100);
                    return '<div class="paper-mae-dist-bar ' + (d.win ? 'win' : 'loss') +
                        '" style="height:' + h + '%" title="' + d.mae.toFixed(1) + 'pts — ' + fmt$(d.pnl) + '"></div>';
                }).join('') + '</div>' +
                '<div class="paper-mae-dist-range">' +
                    '<span>0pts</span>' +
                    '<span style="color:rgba(255,204,68,0.5)">p80: ' + a.p80_mae.toFixed(1) + 'pts</span>' +
                    '<span>' + maxMae.toFixed(1) + 'pts</span>' +
                '</div></div>';
        }

        // Insights
        var insightsHTML = '';
        if (a.insights && a.insights.length > 0) {
            insightsHTML = '<div class="paper-insights">' +
                '<div class="paper-insights-title">Strategy Insights</div>' +
                a.insights.map(function(ins) {
                    return '<div class="paper-insight">' +
                        '<span class="paper-insight-bullet">\u25B8</span>' + ins + '</div>';
                }).join('') + '</div>';
        }

        container.innerHTML = gridHTML + distHTML + insightsHTML;
    }

    // ── Master render ───────────────────────────────────────────────────
    function renderAll() {
        renderStatusDot();
        renderHeaderStats();
        renderTabs();
        renderContent();
        // Update ticker from marks
        for (var sym in marks) {
            renderTicker(sym);
            break;  // Just use first symbol for now
        }
    }

    // ── Flatten button ──────────────────────────────────────────────────
    document.addEventListener('DOMContentLoaded', function() {
        var flattenBtn = document.getElementById('paper-flatten-btn');
        if (flattenBtn) {
            flattenBtn.addEventListener('click', function() {
                if (confirm('Flatten all paper positions?')) {
                    paperSocket.emit('flatten_all', { account: 'default' });
                }
            });
        }
        renderAll();
    });

    // ── Periodic elapsed time update ────────────────────────────────────
    setInterval(function() {
        if (currentTab === 'positions' && positions.length > 0) {
            renderPositions();
        }
    }, 5000);

})();
