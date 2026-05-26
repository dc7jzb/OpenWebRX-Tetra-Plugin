// TETRA meta panel for OpenWebRX+
// Author: SP8MB

function TetraMetaPanel(el) {
    MetaPanel.call(this, el);
    this.modes = ['TETRA'];
    this.networkNames = {
        '901-9999': 'Tetrapack'
    };
    // Group name lookup — extend as needed
    this.groupNames = {
        '91': 'tetraspot 91'
    };
    this.callTypeNames = {
        'individual': 'Indyw.',
        'group': 'Grupowe',
        'broadcast': 'Broadcast',
        'acknowledged group': 'Grupa potw.',
        'other': 'Inne'
    };
    this._activityLog = [];   // newest-first array of HTML row strings
    this._seenSsis = {};      // ssi -> true (for "new" detection)
    this._currentCall = null; // {call_id, gssi, issis:Set, tx_ssi, timeslot, last_freq_mhz}
    this._currentTimeslot = null;  // from latest burst timeslot data
    var self = this;
    $(el).on('click', '.tetra-active-ssi-toggle', function(){
        var listEl = $(el).find('.tetra-active-ssi-list');
        var open = listEl.is(':visible');
        listEl.toggle(!open);
        $(el).find('.tetra-active-ssi-arrow').text(open ? '▸' : '▾');
    });
    $(el).on('click', '.tetra-activity-toggle', function(){
        var listEl = $(el).find('.tetra-activity-list');
        var open = listEl.is(':visible');
        listEl.toggle(!open);
        $(el).find('.tetra-activity-arrow').text(open ? '▸' : '▾');
        $(el).find('.tetra-activity-clear').toggle(!open);
    });
    $(el).on('click', '.tetra-activity-clear', function(){
        self._activityLog = [];
        $(el).find('.tetra-activity-list').html('');
        $(el).find('.tetra-activity-count').text('0');
    });
    $(el).on('click', '.tetra-open-ttt', function(){
        self._showTttWindow();
    });
    this._lastCarrier = null;
    this._lastNet = null;
}

// Set up prototype chain BEFORE adding methods, otherwise the assignment
// below would wipe them out.
TetraMetaPanel.prototype = new MetaPanel();

TetraMetaPanel.prototype._timestamp = function() {
    var d = new Date();
    var pad = function(n){ return n < 10 ? '0' + n : '' + n; };
    return pad(d.getHours()) + ':' + pad(d.getMinutes()) + ':' + pad(d.getSeconds());
};

TetraMetaPanel.prototype._logActivity = function(html, color) {
    var ts = this._timestamp();
    var row = '<div style="color:' + (color || '#bcd') + '">' +
              '<span style="color:#789">' + ts + '</span> ' + html + '</div>';
    this._activityLog.unshift(row);
    if (this._activityLog.length > 200) this._activityLog.length = 200;
    var el = $(this.el);
    el.find('.tetra-activity-list').html(this._activityLog.join(''));
    el.find('.tetra-activity-count').text(this._activityLog.length);
    if (this._tttWin && this._tttWin.style.display !== 'none') {
        this._tttWin.querySelector('.ttt-log').innerHTML = this._activityLog.join('');
        this._tttWin.querySelector('.ttt-log-count').textContent = '(' + this._activityLog.length + ')';
    }
};

TetraMetaPanel.prototype._ensureTttWindow = function() {
    if (this._tttWin && document.body.contains(this._tttWin)) return;
    var self = this;
    var win = document.createElement('div');
    win.className = 'tetra-ttt-window';
    win.style.cssText = 'position:fixed;left:60px;top:60px;width:680px;max-width:90vw;'+
        'background:#0b1622;color:#cde;border:2px solid #345;border-radius:5px;'+
        'box-shadow:0 4px 14px rgba(0,0,0,0.6);z-index:10000;font-family:system-ui,sans-serif;font-size:0.9em;display:none';
    win.innerHTML = ''+
        '<div class="ttt-title" style="background:#1a3050;padding:4px 8px;cursor:move;display:flex;justify-content:space-between;align-items:center;border-radius:3px 3px 0 0">'+
        '  <div><b>TETRA Trunk Tracker</b> <span style="color:#9cf;margin-left:8px" class="ttt-net">—</span></div>'+
        '  <div>'+
        '    <span class="ttt-clear" style="cursor:pointer;color:#9ab;margin-right:10px" title="Wyczyść log">[wyczyść]</span>'+
        '    <span class="ttt-close" style="cursor:pointer;color:#fcc;font-weight:bold" title="Zamknij">✕</span>'+
        '  </div>'+
        '</div>'+
        '<div style="display:flex">'+
        '  <div class="ttt-left" style="flex:0 0 250px;padding:6px 8px;border-right:1px solid #234">'+
        '    <div style="font-size:0.8em;color:#9ab;margin-bottom:4px">Call details</div>'+
        '    <div><span class="ttt-status" style="display:inline-block;padding:2px 10px;border-radius:3px;background:#445;color:#aaa;font-weight:bold">Idle</span>'+
        '         <span class="ttt-call-type" style="margin-left:6px;color:#9cf"></span></div>'+
        '    <div style="margin-top:6px"><span style="color:#789">Call ID:</span> <b class="ttt-cid">—</b></div>'+
        '    <div><span style="color:#789">Carrier:</span> <b class="ttt-carrier">—</b></div>'+
        '    <div><span style="color:#789">Timeslot:</span> <b class="ttt-ts">—</b></div>'+
        '    <div style="margin-top:4px"><span style="color:#789">Grupa:</span> <b class="ttt-gssi">—</b></div>'+
        '    <div class="ttt-gname" style="color:#9cf;font-style:italic;min-height:18px"></div>'+
        '    <div style="margin-top:6px;color:#789">ISSI w rozmowie:</div>'+
        '    <div class="ttt-issis" style="border:1px solid #234;background:#021;padding:3px 5px;min-height:60px;max-height:120px;overflow-y:auto;font-family:monospace;font-size:0.9em;color:#cde;border-radius:2px">—</div>'+
        '    <div style="margin-top:6px"><span style="color:#789">TX SSI:</span> <b class="ttt-tx" style="color:#51cf66">—</b></div>'+
        '    <div class="ttt-time" style="margin-top:6px;color:#789;font-size:0.85em"></div>'+
        '  </div>'+
        '  <div class="ttt-right" style="flex:1;padding:6px 8px">'+
        '    <div style="font-size:0.8em;color:#9ab;margin-bottom:4px">Aktywność <span class="ttt-log-count" style="color:#789">(0)</span></div>'+
        '    <div class="ttt-log" style="font-family:monospace;font-size:0.78em;color:#cde;height:330px;overflow-y:auto;border:1px solid #234;background:#021;padding:4px;border-radius:2px;line-height:1.4">brak zdarzeń</div>'+
        '  </div>'+
        '</div>';
    document.body.appendChild(win);
    this._tttWin = win;

    // Close + clear handlers
    win.querySelector('.ttt-close').addEventListener('click', function(){ win.style.display = 'none'; });
    win.querySelector('.ttt-clear').addEventListener('click', function(){
        self._activityLog = [];
        win.querySelector('.ttt-log').innerHTML = 'brak zdarzeń';
        win.querySelector('.ttt-log-count').textContent = '(0)';
        $(self.el).find('.tetra-activity-list').html('');
        $(self.el).find('.tetra-activity-count').text('0');
    });

    // Draggable by title bar
    var title = win.querySelector('.ttt-title');
    var drag = null;
    title.addEventListener('mousedown', function(e){
        if (e.target.classList.contains('ttt-close') || e.target.classList.contains('ttt-clear')) return;
        drag = { ox: e.clientX - win.offsetLeft, oy: e.clientY - win.offsetTop };
        e.preventDefault();
    });
    document.addEventListener('mousemove', function(e){
        if (!drag) return;
        win.style.left = (e.clientX - drag.ox) + 'px';
        win.style.top = (e.clientY - drag.oy) + 'px';
    });
    document.addEventListener('mouseup', function(){ drag = null; });
};

TetraMetaPanel.prototype._showTttWindow = function() {
    this._ensureTttWindow();
    this._tttWin.style.display = 'block';
    this._renderTttWindow();
};

TetraMetaPanel.prototype._renderTttWindow = function() {
    if (!this._tttWin || this._tttWin.style.display === 'none') return;
    var w = this._tttWin;
    var c = this._currentCall;
    var statusEl = w.querySelector('.ttt-status');
    if (c) {
        statusEl.textContent = c.status || 'Aktywne';
        statusEl.style.background = c.status === 'TX' ? '#2b8a3e' :
            c.status === 'Zestawienie' ? '#8a6d2b' :
            c.status === 'Aktywne' ? '#2b8a3e' : '#445';
        statusEl.style.color = '#fff';
        w.querySelector('.ttt-call-type').textContent = c.call_type ? '[' + c.call_type + ']' : '';
        w.querySelector('.ttt-cid').textContent = c.call_id || '—';
        w.querySelector('.ttt-ts').textContent = c.timeslot != null ? c.timeslot : '—';
        w.querySelector('.ttt-gssi').textContent = c.gssi || '—';
        var gn = c.gssi ? (this.groupNames[String(c.gssi)] || '') : '';
        w.querySelector('.ttt-gname').textContent = gn;
        var issis = Array.from(c.issis || []);
        w.querySelector('.ttt-issis').innerHTML = issis.length
            ? issis.map(function(i){
                var isTx = c.tx_ssi && i === c.tx_ssi;
                return '<div' + (isTx ? ' style="color:#51cf66;font-weight:bold"' : '') + '>' + i + '</div>';
            }).join('')
            : '—';
        w.querySelector('.ttt-tx').textContent = c.tx_ssi || '—';
        w.querySelector('.ttt-time').textContent = c.last_update || '';
    } else {
        statusEl.textContent = 'Idle';
        statusEl.style.background = '#445';
        statusEl.style.color = '#aaa';
        w.querySelector('.ttt-call-type').textContent = '';
        w.querySelector('.ttt-cid').textContent = '—';
        w.querySelector('.ttt-ts').textContent = '—';
        w.querySelector('.ttt-gssi').textContent = '—';
        w.querySelector('.ttt-gname').textContent = '';
        w.querySelector('.ttt-issis').innerHTML = '—';
        w.querySelector('.ttt-tx').textContent = '—';
        w.querySelector('.ttt-time').textContent = '';
    }
    // Carrier from netinfo (stored on instance)
    if (this._lastCarrier) w.querySelector('.ttt-carrier').textContent = this._lastCarrier;
    if (this._lastNet) w.querySelector('.ttt-net').textContent = this._lastNet;
    // Mirror activity log to right column
    w.querySelector('.ttt-log').innerHTML = this._activityLog.length ? this._activityLog.join('') : 'brak zdarzeń';
    w.querySelector('.ttt-log-count').textContent = '(' + this._activityLog.length + ')';
};

TetraMetaPanel.prototype.getCallTypeLabel = function(callType) {
    if (!callType) return '';
    for (var key in this.callTypeNames) {
        if (callType.indexOf(key) === 0) {
            var suffix = callType.substring(key.length);
            return this.callTypeNames[key] + suffix;
        }
    }
    return callType;
};

TetraMetaPanel.prototype.update = function(data) {
    if (!this.isSupported(data)) return;
    var el = $(this.el);
    var type = data.type;

    if (type === 'netinfo') {
        var mcc = data.mcc || '---';
        var mnc = data.mnc || '---';
        var key = mcc + '-' + mnc;
        var networkName = this.networkNames[key] || key;

        el.find('.tetra-network').text(networkName);
        el.find('.tetra-mcc').text(mcc);
        el.find('.tetra-mnc').text(mnc);

        if (data.dl_freq) {
            el.find('.tetra-dl-freq').text((data.dl_freq / 1e6).toFixed(4) + ' MHz');
        }
        if (data.ul_freq) {
            el.find('.tetra-ul-freq').text((data.ul_freq / 1e6).toFixed(4) + ' MHz');
        }
        if (data.color_code !== undefined) {
            el.find('.tetra-color-code').text(data.color_code);
        }
        if (data.la) {
            el.find('.tetra-la').text(data.la);
        }
        if (data.dl_freq) {
            this._lastCarrier = (data.dl_freq / 1e6).toFixed(4) + ' MHz';
        }
        this._lastNet = key + (networkName !== key ? ' ' + networkName : '');
        this._renderTttWindow();
        el.find('.tetra-encrypted').text(data.encrypted ? 'TAK' : 'NIE')
            .css('color', data.encrypted ? '#ff6b6b' : '#51cf66');
    }
    else if (type === 'encinfo') {
        el.find('.tetra-encrypted').text(data.encrypted ? 'TAK (' + data.enc_mode + ')' : 'NIE')
            .css('color', data.encrypted ? '#ff6b6b' : '#51cf66');
    }
    else if (type === 'call_setup') {
        var ctLabel = this.getCallTypeLabel(data.call_type);
        el.find('.tetra-call-status').text('Zestawienie').css('color', '#ffd43b');
        el.find('.tetra-call-type').text(ctLabel ? '[' + ctLabel + ']' : '');
        el.find('.tetra-gssi').text(data.ssi || '---');
        var issi = data.ssi2 || data.calling_ssi || '---';
        el.find('.tetra-issi').text(issi);
        el.find('.tetra-call-id').text('CID:' + (data.call_id || ''));
        // Update floating TTT window state
        if (!this._currentCall || this._currentCall.call_id !== data.call_id) {
            this._currentCall = {
                call_id: data.call_id, gssi: data.ssi, issis: new Set(),
                tx_ssi: null, timeslot: this._currentTimeslot, last_update: this._timestamp(),
                status: 'Zestawienie', call_type: ctLabel
            };
            var gname = this.groupNames[String(data.ssi)] || '';
            var gnTag = gname ? ' [' + gname + ']' : '';
            this._logActivity('<b>Call ID: ' + (data.call_id || '?') + '</b> — Setup — Group: ' +
                (data.ssi || '?') + gnTag + (ctLabel ? ' [' + ctLabel + ']' : ''), '#ffd43b');
        }
        var c = this._currentCall;
        if (data.calling_ssi && !c.issis.has(data.calling_ssi)) {
            c.issis.add(data.calling_ssi);
            this._logActivity('<b>Call ID: ' + (data.call_id || '?') + '</b> — Calling SSI: ' + data.calling_ssi, '#9af');
        }
        if (data.ssi2 && !c.issis.has(data.ssi2)) c.issis.add(data.ssi2);
        c.last_update = this._timestamp();
        this._renderTttWindow();
    }
    else if (type === 'call_connect') {
        el.find('.tetra-call-status').text('Aktywne').css('color', '#51cf66');
        if (data.ssi) el.find('.tetra-gssi').text(data.ssi);
        var issi = data.ssi2 || data.calling_ssi;
        if (issi) el.find('.tetra-issi').text(issi);
        if (!this._currentCall) {
            this._currentCall = { call_id: data.call_id, gssi: data.ssi, issis: new Set(),
                tx_ssi: null, timeslot: this._currentTimeslot, last_update: this._timestamp(), status: 'Aktywne' };
        } else {
            this._currentCall.status = 'Aktywne';
            this._currentCall.last_update = this._timestamp();
        }
        if (issi) this._currentCall.issis.add(issi);
        this._renderTttWindow();
        this._logActivity('<b>Call ID: ' + (data.call_id || '?') + '</b> — Connected' +
            (issi ? ' — SSI: ' + issi : ''), '#51cf66');
    }
    else if (type === 'tx_grant') {
        el.find('.tetra-call-status').text('TX').css('color', '#51cf66');
        if (data.ssi) el.find('.tetra-gssi').text(data.ssi);
        var issi = data.ssi2 || data.calling_ssi;
        if (issi) el.find('.tetra-issi').text(issi);
        if (!this._currentCall || this._currentCall.call_id !== data.call_id) {
            this._currentCall = { call_id: data.call_id, gssi: data.ssi, issis: new Set(),
                tx_ssi: null, timeslot: this._currentTimeslot, last_update: this._timestamp(), status: 'TX' };
        }
        var c = this._currentCall;
        c.status = 'TX';
        c.last_update = this._timestamp();
        if (issi) { c.issis.add(issi); c.tx_ssi = issi; }
        this._renderTttWindow();
        this._logActivity('<b>Call ID: ' + (data.call_id || '?') + '</b> — D-TX-Granted SSI: ' + (issi || '?'), '#51cf66');
    }
    else if (type === 'call_release') {
        el.find('.tetra-call-status').text('Idle').css('color', '#868e96');
        el.find('.tetra-call-type').text('');
        el.find('.tetra-gssi').text('---');
        el.find('.tetra-issi').text('---');
        el.find('.tetra-call-id').text('');
        var reason = data.reason ? ' (' + data.reason + ')' : '';
        this._logActivity('<b>Call ID: ' + (data.call_id || '?') + '</b> — D-Released' + reason, '#ff8787');
        this._currentCall = null;
        this._renderTttWindow();
    }
    else if (type === 'status') {
        el.find('.tetra-call-status').text('Status: ' + data.status).css('color', '#4dabf7');
        el.find('.tetra-gssi').text(data.ssi || '---');
        el.find('.tetra-issi').text(data.ssi2 || '---');
    }
    else if (type === 'resource') {
        // SSI2 in resource = ISSI of individual subscriber (if available)
        if (data.ssi2) {
            el.find('.tetra-issi').text(data.ssi2);
        }
    }
    else if (type === 'neighbours') {
        var cells = data.cells || [];
        el.find('.tetra-neighbour-count').text(cells.length);
        if (cells.length === 0) {
            el.find('.tetra-neighbour-list').text('');
        } else {
            var max = 4;
            var parts = cells.slice(0, max).map(function(c){
                return 'c' + c.cell_id + '@' + (c.dlf / 1e6).toFixed(3);
            });
            var extra = cells.length > max ? ' +' + (cells.length - max) : '';
            el.find('.tetra-neighbour-list').text('[' + parts.join(', ') + extra + ']');
        }
    }
    else if (type === 'active_ssi') {
        el.find('.tetra-active-ssi-count').text(data.total || 0);
        var ssis = data.ssis || [];
        var rows = ssis.map(function(r){
            var enc = r.encr === 2 ? ' 🔒' : (r.encr === 0 ? ' ?' : '');
            return '<div>' + r.ssi + enc + ' <span style="color:#678">(' + r.age.toFixed(0) + 's)</span></div>';
        }).join('');
        el.find('.tetra-active-ssi-list').html(rows || '<div style="color:#678">brak</div>');
        // Detect new ISSIs (first appearance in this session) → log entry
        for (var i = 0; i < ssis.length; i++) {
            var r = ssis[i];
            if (!this._seenSsis[r.ssi]) {
                this._seenSsis[r.ssi] = true;
                var enc = r.encr === 2 ? ' 🔒' : (r.encr === 0 ? '' : '');
                this._logActivity('SSI ' + r.ssi + enc + ' — pojawił się w komórce', '#9af');
            }
        }
    }
    else if (type === 'burst') {
        // AFC
        if (data.afc !== undefined) {
            var afcHz = data.afc;
            var afcColor = Math.abs(afcHz) < 500 ? '#51cf66' : (Math.abs(afcHz) < 1500 ? '#ffd43b' : '#ff6b6b');
            el.find('.tetra-afc').text(afcHz.toFixed(0) + ' Hz').css('color', afcColor);
        }
        // Burst rate
        if (data.burst_rate !== undefined) {
            var br = data.burst_rate;
            var brColor = br > 40 ? '#51cf66' : (br > 20 ? '#ffd43b' : '#ff6b6b');
            el.find('.tetra-burst-rate').text(br.toFixed(0) + '/s').css('color', brColor);
        }
        // Timeslots
        if (data.timeslots) {
            el.find('.tetra-ts').removeClass('busy idle');
            var assignedTs = null;
            for (var tn in data.timeslots) {
                var usage = data.timeslots[tn];
                var tsEl = el.find('.tetra-ts-' + tn);
                if (usage === 'assigned') {
                    tsEl.addClass('busy');
                    if (assignedTs == null) assignedTs = tn;
                } else if (usage === 'unallocated') {
                    tsEl.addClass('idle');
                }
            }
            if (assignedTs != null) {
                this._currentTimeslot = assignedTs;
                if (this._currentCall) {
                    this._currentCall.timeslot = assignedTs;
                    el.find('.tetra-timeslot').text(assignedTs);
                }
            }
        }
        // Call type from burst (updated periodically)
        if (data.call_type) {
            var ct = this.getCallTypeLabel(data.call_type);
            if (ct && el.find('.tetra-call-status').text() !== 'Idle') {
                el.find('.tetra-call-type').text('[' + ct + ']');
            }
        }
    }
};

TetraMetaPanel.prototype.clear = function() {
    MetaPanel.prototype.clear.call(this);
    var el = $(this.el);
    el.find('.tetra-network, .tetra-mcc, .tetra-mnc').text('---');
    el.find('.tetra-dl-freq, .tetra-ul-freq, .tetra-carrier').text('---');
    el.find('.tetra-color-code, .tetra-la').text('---');
    el.find('.tetra-encrypted').text('---').css('color', '');
    el.find('.tetra-afc, .tetra-burst-rate').text('---').css('color', '');
    el.find('.tetra-ts').removeClass('busy idle');
    el.find('.tetra-neighbour-count, .tetra-active-ssi-count').text('0');
    el.find('.tetra-neighbour-list').text('');
    el.find('.tetra-active-ssi-list').html('').hide();
    el.find('.tetra-active-ssi-arrow').text('▸');
    this._activityLog = [];
    this._seenSsis = {};
    this._currentCall = null;
    this._currentTimeslot = null;
    this._renderCallDetails();
    el.find('.tetra-activity-list').html('').hide();
    el.find('.tetra-activity-arrow').text('▸');
    el.find('.tetra-activity-count').text('0');
    el.find('.tetra-activity-clear').hide();
};
