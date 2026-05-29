document.addEventListener('DOMContentLoaded', function () {
    initTabSwitching();
    initSendMessage();
});

function shortModelName(model) {
    var idx = model.indexOf('/');
    return idx !== -1 ? model.substring(idx + 1) : model;
}

/* === Tab Switching === */
function initTabSwitching() {
    document.body.addEventListener('click', function (e) {
        const tab = e.target.closest('.tab');
        if (!tab) return;

        const stage = tab.getAttribute('data-stage');
        const tabIndex = tab.getAttribute('data-tab');
        const stageEl = tab.closest('.stage');
        if (!stageEl) return;

        // Update tab buttons
        stageEl.querySelectorAll('.tab[data-stage="' + stage + '"]').forEach(function (t) {
            t.classList.toggle('active', t.getAttribute('data-tab') === tabIndex);
        });

        // Update tab content
        stageEl.querySelectorAll('.tab-content[data-stage="' + stage + '"]').forEach(function (c) {
            var isActive = c.getAttribute('data-tab-index') === tabIndex;
            c.classList.toggle('hidden', !isActive);
        });
    });
}

/* === Send Message with SSE === */
function initSendMessage() {
    var form = document.querySelector('.input-form');
    if (!form) return;

    var conversationId = form.getAttribute('data-conversation-id');
    var textarea = form.querySelector('.message-input');
    var sendBtn = form.querySelector('.send-button');

    form.addEventListener('submit', async function (e) {
        e.preventDefault();
        var content = textarea.value.trim();
        if (!content) return;

        textarea.disabled = true;
        sendBtn.disabled = true;

        var container = document.querySelector('.messages-container');

        // Remove empty state if present
        var emptyState = container.querySelector('.empty-state');
        if (emptyState) emptyState.remove();

        // Add user message
        var userGroup = document.createElement('div');
        userGroup.className = 'message-group';
        userGroup.innerHTML =
            '<div class="user-message">' +
            '<div class="message-label">You</div>' +
            '<div class="message-content"><div class="markdown-content">' +
            marked.parse(content) +
            '</div></div></div>';
        container.appendChild(userGroup);

        // Add placeholder assistant message
        var assistantGroup = document.createElement('div');
        assistantGroup.className = 'message-group';
        assistantGroup.innerHTML =
            '<div class="assistant-message">' +
            '<div class="message-label">LLM Council</div>' +
            '<div class="stage-loading" id="stage-loading-1"><div class="spinner"></div><span>Running Stage 1...</span></div>' +
            '<div class="stage-loading hidden" id="stage-loading-2"><div class="spinner"></div><span>Running Stage 2...</span></div>' +
            '<div class="stage-loading hidden" id="stage-loading-3"><div class="spinner"></div><span>Running Stage 3...</span></div>' +
            '</div>';
        container.appendChild(assistantGroup);
        scrollToBottom();

        // Stream SSE
        try {
            var response = await fetch('/api/conversations/' + conversationId + '/message/stream', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ content: content })
            });

            if (!response.ok) throw new Error('Failed to send message');

            var reader = response.body.getReader();
            var decoder = new TextDecoder();
            var buffer = '';

            while (true) {
                var result = await reader.read();
                if (result.done) break;

                buffer += decoder.decode(result.value, { stream: true });
                var lines = buffer.split('\n');
                buffer = lines.pop(); // Keep incomplete line in buffer

                for (var i = 0; i < lines.length; i++) {
                    var line = lines[i].trim();
                    if (!line.startsWith('data: ')) continue;
                    try {
                        var event = JSON.parse(line.slice(6));
                        handleSSEEvent(event, assistantGroup, userGroup, conversationId);
                    } catch (parseErr) {
                        console.error('SSE parse error:', parseErr);
                    }
                }
            }

            // Process any remaining buffer
            if (buffer.trim().startsWith('data: ')) {
                try {
                    var event = JSON.parse(buffer.trim().slice(6));
                    handleSSEEvent(event, assistantGroup, userGroup, conversationId);
                } catch (parseErr) { /* ignore */ }
            }
        } catch (err) {
            userGroup.remove();
            assistantGroup.remove();
            showErrorNotification(container, 'Error: ' + err.message);
        }

        textarea.value = '';
        textarea.disabled = false;
        sendBtn.disabled = false;
        scrollToBottom();
    });

    // Enter to send, Shift+Enter for newline
    textarea.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            form.dispatchEvent(new Event('submit'));
        }
    });
}

/* === SSE Event Handler === */
function handleSSEEvent(event, assistantGroup, userGroup, conversationId) {
    var assistantMsg = assistantGroup.querySelector('.assistant-message');

    switch (event.type) {
        case 'stage1_start':
            showStageLoading(assistantMsg, 1);
            break;

        case 'stage1_complete':
            hideStageLoading(assistantMsg, 1);
            var s1Html = renderStage1(event.data);
            insertBeforeLoaders(assistantMsg, s1Html);
            break;

        case 'stage2_start':
            showStageLoading(assistantMsg, 2);
            break;

        case 'stage2_complete':
            hideStageLoading(assistantMsg, 2);
            var labelToModel = event.metadata ? event.metadata.label_to_model : null;
            var aggregateRankings = event.metadata ? event.metadata.aggregate_rankings : null;
            var s2Html = renderStage2(event.data, labelToModel, aggregateRankings);
            insertBeforeLoaders(assistantMsg, s2Html);
            break;

        case 'stage3_start':
            showStageLoading(assistantMsg, 3);
            break;

        case 'stage3_complete':
            hideStageLoading(assistantMsg, 3);
            var s3Html = renderStage3(event.data);
            insertBeforeLoaders(assistantMsg, s3Html);
            break;

        case 'title_complete':
            var titleEl = document.getElementById('sidebar-title-' + conversationId);
            if (titleEl) titleEl.textContent = event.data.title;
            break;

        case 'complete':
            removeAllLoaders(assistantMsg);
            break;

        case 'error':
            userGroup.remove();
            assistantGroup.remove();
            var container = document.querySelector('.messages-container');
            if (container) showErrorNotification(container, 'Error: ' + event.message);
            break;
    }
    scrollToBottom();
}

/* === Stage Rendering === */
function renderStage1(responses) {
    if (!responses || responses.length === 0) return '';
    var tabs = '';
    var contents = '';
    for (var i = 0; i < responses.length; i++) {
        var r = responses[i];
        var shortName = shortModelName(r.model);
        tabs += '<button class="tab' + (i === 0 ? ' active' : '') + '" data-stage="stage1" data-tab="' + i + '">' + escapeHtml(shortName) + '</button>';
        contents += '<div class="tab-content' + (i === 0 ? '' : ' hidden') + '" data-stage="stage1" data-tab-index="' + i + '">' +
            '<div class="model-name">' + escapeHtml(shortName) + '</div>' +
            '<div class="response-text markdown-content">' + marked.parse(r.response || '') + '</div>' +
            '</div>';
    }
    return '<div class="stage stage1">' +
        '<h3 class="stage-title">Stage 1: Individual Responses</h3>' +
        '<div class="tabs">' + tabs + '</div>' +
        contents + '</div>';
}

function renderStage2(rankings, labelToModel, aggregateRankings) {
    if (!rankings || rankings.length === 0) return '';
    var tabs = '';
    var contents = '';
    for (var i = 0; i < rankings.length; i++) {
        var r = rankings[i];
        var shortName = shortModelName(r.model);
        tabs += '<button class="tab' + (i === 0 ? ' active' : '') + '" data-stage="stage2" data-tab="' + i + '">' + escapeHtml(shortName) + '</button>';

        var rankingText = deAnonymizeText(r.ranking || '', labelToModel);
        var parsedHtml = '';
        if (r.parsed_ranking && r.parsed_ranking.length > 0) {
            parsedHtml = '<div class="parsed-ranking"><strong>Extracted Ranking:</strong><ol>';
            for (var j = 0; j < r.parsed_ranking.length; j++) {
                var label = r.parsed_ranking[j];
                var resolved = (labelToModel && labelToModel[label])
                    ? shortModelName(labelToModel[label])
                    : label;
                parsedHtml += '<li>' + escapeHtml(resolved) + '</li>';
            }
            parsedHtml += '</ol></div>';
        }

        contents += '<div class="tab-content' + (i === 0 ? '' : ' hidden') + '" data-stage="stage2" data-tab-index="' + i + '">' +
            '<div class="ranking-model">' + escapeHtml(shortName) + '</div>' +
            '<div class="ranking-content markdown-content">' + marked.parse(rankingText) + '</div>' +
            parsedHtml + '</div>';
    }

    var aggregateHtml = '';
    if (aggregateRankings && aggregateRankings.length > 0) {
        aggregateHtml = '<div class="aggregate-rankings">' +
            '<h4>Aggregate Rankings (Street Cred)</h4>' +
            '<p class="stage-description">Combined results across all peer evaluations (lower score is better):</p>' +
            '<div class="aggregate-list">';
        for (var k = 0; k < aggregateRankings.length; k++) {
            var agg = aggregateRankings[k];
            var aggShort = shortModelName(agg.model);
            aggregateHtml += '<div class="aggregate-item">' +
                '<span class="rank-position">#' + (k + 1) + '</span>' +
                '<span class="rank-model">' + escapeHtml(aggShort) + '</span>' +
                '<span class="rank-score">Avg: ' + agg.average_rank.toFixed(2) + '</span>' +
                '<span class="rank-count">(' + agg.rankings_count + ' votes)</span>' +
                '</div>';
        }
        aggregateHtml += '</div></div>';
    }

    return '<div class="stage stage2">' +
        '<h3 class="stage-title">Stage 2: Peer Rankings</h3>' +
        '<h4>Raw Evaluations</h4>' +
        '<p class="stage-description">Each model evaluated all responses (anonymized as Response A, B, C, etc.) and provided rankings. Below, model names are shown in <strong>bold</strong> for readability, but the original evaluation used anonymous labels.</p>' +
        '<div class="tabs">' + tabs + '</div>' +
        contents + aggregateHtml + '</div>';
}

function renderStage3(result) {
    if (!result) return '';
    var shortName = shortModelName(result.model);
    return '<div class="stage stage3">' +
        '<h3 class="stage-title">Stage 3: Final Council Answer</h3>' +
        '<div class="final-response">' +
        '<div class="chairman-label">Chairman: ' + escapeHtml(shortName) + '</div>' +
        '<div class="final-text markdown-content">' + marked.parse(result.response || '') + '</div>' +
        '</div></div>';
}

/* === De-anonymization === */
function deAnonymizeText(text, labelToModel) {
    if (!labelToModel) return text;
    var result = text;
    var labels = Object.keys(labelToModel);
    for (var i = 0; i < labels.length; i++) {
        var label = labels[i];
        var model = labelToModel[label];
        var shortName = shortModelName(model);
        result = result.split(label).join('**' + shortName + '**');
    }
    return result;
}

/* === Helpers === */
function showStageLoading(msg, stageNum) {
    var el = msg.querySelector('#stage-loading-' + stageNum);
    if (el) el.classList.remove('hidden');
}

function hideStageLoading(msg, stageNum) {
    var el = msg.querySelector('#stage-loading-' + stageNum);
    if (el) el.classList.add('hidden');
}

function removeAllLoaders(msg) {
    msg.querySelectorAll('.stage-loading').forEach(function (el) { el.remove(); });
}

function insertBeforeLoaders(msg, html) {
    var temp = document.createElement('div');
    temp.innerHTML = html;
    var loaders = msg.querySelector('.stage-loading');
    while (temp.firstChild) {
        if (loaders) {
            msg.insertBefore(temp.firstChild, loaders);
        } else {
            msg.appendChild(temp.firstChild);
        }
    }
}

function showErrorNotification(container, message) {
    var errorDiv = document.createElement('div');
    errorDiv.className = 'error-notification';
    errorDiv.innerHTML =
        '<span>' + escapeHtml(message) + '</span>' +
        '<button class="error-dismiss" onclick="this.parentElement.remove()">&times;</button>';
    container.appendChild(errorDiv);
    scrollToBottom();
}

function scrollToBottom() {
    var container = document.querySelector('.messages-container');
    if (container) container.scrollTop = container.scrollHeight;
}

function escapeHtml(text) {
    var div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function deleteConversation(id) {
    fetch('/api/conversations/' + id, { method: 'DELETE' })
        .then(function (r) {
            if (!r.ok) throw new Error('Delete failed');
            window.location.href = '/';
        })
        .catch(function (err) {
            console.error('Failed to delete conversation:', err);
        });
}
