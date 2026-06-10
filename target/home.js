
(function () {
    /* 
     * home.js - Essay Editor Frontend Logic
     * Refactored for clarity and removal of legacy contenteditable code.
     * Includes Offline Resilience and Action Queueing.
     */

    // Global State
    const GlobalState = {
        socket: null,
        assignmentTakerId: null,
        wordLimit: null,
        offlineQueue: [], // Queue for actions when offline
        isOffline: false,
        reconnectTimer: null, // Timer for reconnection attempts
        reconnectAttempts: 0, // Number of reconnection attempts
        debouncedSplitUpdate: null, // Debounced function for split view
        isComposing: false, // Track IME composition state
        internalClipboard: null // Custom clipboard: { text, from, to, type }
    };

    // DOM Elements Cache
    const DOM = {
        editor: null, // textarea
        saveIndicator: null,
        limitIndicator: null,
        wordCount: null,
        previewModal: null,
        modalContent: null,
        deadline: null,
        connectionStatus: null,
        splitPreviewPane: null
    };

    document.addEventListener('DOMContentLoaded', () => {
        initDOMElements();
        if (!DOM.editor) return;

        // Load from local storage if available (resilience)
        restoreFromLocalStorage();

        initWebSocket();
        initEditorEvents();
        initLogout();
        initDeadline();

        // Theme
        initTheme();

        // Initial Word Count
        updateWordCount();

        // Online/Offline listeners
        window.addEventListener('online', handleOnline);
        window.addEventListener('offline', handleOffline);

    });

    // Render Math after everything (scripts/fonts) is fully loaded
    window.addEventListener('load', () => {
        renderTaskMath();
        initSplitView(); // Initialize split view state
    });

    function initDOMElements() {
        DOM.editor = document.getElementById('textarea1');
        DOM.saveIndicator = document.getElementById('save-indicator');
        DOM.limitIndicator = document.getElementById('word-limit-indicator');
        DOM.wordCount = document.getElementById('wordCount');
        DOM.previewModal = document.getElementById('previewModal');
        DOM.modalContent = document.getElementById('modal-preview-content');
        DOM.deadline = document.getElementById('deadline');
        DOM.connectionStatus = document.getElementById('connectionStatus'); // New element
        DOM.splitPreviewPane = document.getElementById('splitPreviewPane');

        // Get assignment ID
        if (DOM.editor) {
            GlobalState.assignmentTakerId = DOM.editor.dataset.assignmentTakerId;
            GlobalState.wordLimit = getWordLimit();
        }
    }

    // --- WebSocket & Sync Logic ---

    function setEditorLock(isLocked) {
        GlobalState.isOffline = isLocked; // Sync the state

        if (DOM.editor) {
            DOM.editor.disabled = isLocked;

            // UX: Visual cue that the editor is locked
            if (isLocked) {
                DOM.editor.style.cursor = "not-allowed";
                try { DOM.editor.blur(); } catch (e) { }
            } else {
                DOM.editor.style.cursor = "text";
            }
        }
    }

    function initWebSocket() {
        if (!GlobalState.assignmentTakerId) {
            console.error("No Assignment Taker ID found.");
            return;
        }

        // CRITICAL FIX: Guard against disrupting active or ongoing connection sequences
        if (GlobalState.socket && (GlobalState.socket.readyState === WebSocket.OPEN || GlobalState.socket.readyState === WebSocket.CONNECTING)) {
            console.log("WebSocket is already active or connecting. Skipping initialization.");
            return;
        }

        // Cleanup existing socket and timer
        // if (GlobalState.socket) {
        //     // Remove listeners to prevent zombie callbacks
        //     GlobalState.socket.onopen = null;
        //     GlobalState.socket.onclose = null;
        //     GlobalState.socket.onerror = null;
        //     GlobalState.socket.onmessage = null;
        //     GlobalState.socket.close();
        //     GlobalState.socket = null;
        // }

        // Cleanup stale backoff timers
        if (GlobalState.reconnectTimer) {
            clearTimeout(GlobalState.reconnectTimer);
            GlobalState.reconnectTimer = null;
        }

        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/assignments/${GlobalState.assignmentTakerId}/`;

        console.log("Connecting to WS:", wsUrl);
        updateConnectionStatus('connecting');
        setEditorLock(true); // Ensure editor is locked while initially connecting

        const socket = new WebSocket(wsUrl);
        GlobalState.socket = socket;

        socket.onopen = (e) => {
            console.log("WebSocket connected.");
            GlobalState.reconnectAttempts = 0; // Reset backoff on success
            setEditorLock(false);
            updateConnectionStatus('online');

            if (DOM.editor) {
                DOM.editor.disabled = false;
            }
            if (DOM.saveIndicator) DOM.saveIndicator.style.display = "none";

            // Do not process queue yet. Wait for 'init' to establish base version.
        };

        socket.onmessage = (e) => {
            const data = JSON.parse(e.data);
            handleServerMessage(data);
        };

        socket.onclose = (e) => {
            // Verify this is the current socket
            if (GlobalState.socket !== socket) return;

            console.warn("WebSocket closed.", e.code, e.reason);

            // If authentication failed (4003) or assignment taker not found (4004), log out
            if (e.code === 4003 || e.code === 4004) {
                if (window.logout_user_from_session) {
                    window.logout_user_from_session();
                } else {
                    window.location.reload();
                }
                return;
            }

            // If superseded by another tab (4009), permanently disconnect (No Auto-Reconnect Loop Allowed)
            if (e.code === 4009) {
                setEditorLock(true);
                updateConnectionStatus('superseded');
                if (GlobalState.reconnectTimer) clearTimeout(GlobalState.reconnectTimer);
                GlobalState.socket = null;
                return;
            }

            handleOffline();

            // Schedule reconnect if not already scheduled
            if (!GlobalState.reconnectTimer) {
                // Exponential backoff: 2s, 4s, 8s, 16s, max 30s
                let backoffSeconds = Math.pow(2, GlobalState.reconnectAttempts + 1);
                if (backoffSeconds > 30) backoffSeconds = 30;

                GlobalState.reconnectAttempts++;
                console.log(`Scheduling reconnect in ${backoffSeconds}s (Attempt ${GlobalState.reconnectAttempts})...`);
                GlobalState.reconnectTimer = setTimeout(() => {
                    GlobalState.reconnectTimer = null; // Reset pointer before execution
                    initWebSocket();
                }, backoffSeconds * 1000);
            }
        };

        socket.onerror = (err) => {
            if (GlobalState.socket !== socket) return;
            console.error("WebSocket error:", err);
            // OnError usually precedes OnClose, so we let OnClose handle the retry logic
            // But we ensure we treat it as offline immediately
            handleOffline();
        };
    }

    function handleServerMessage(data) {
        if (data.type === 'init') {
            // Initial load
            if (data.full_text !== undefined) {
                DOM.editor.value = data.full_text;
                saveToLocalStorage();
                updateWordCount();
                showSavedIndicator();

                processOfflineQueue();
            }
        } else if (data.type === 'error') {
            if (data.message) alert(data.message);
            // Non-recoverable desync or paste detected. Force a page reload to pull fresh db state.
            window.location.reload();
        }
    }

    let saveIndicatorTimeout;
    function showSavedIndicator() {
        if (DOM.saveIndicator) {
            DOM.saveIndicator.style.display = "flex";
            clearTimeout(saveIndicatorTimeout);
            saveIndicatorTimeout = setTimeout(() => {
                if (DOM.saveIndicator) DOM.saveIndicator.style.display = "none";
            }, 4000);
        }
    }

    function sendAction(action) {
        if (GlobalState.socket && GlobalState.socket.readyState === WebSocket.OPEN) {
            // console.log("Sending action:", JSON.stringify(action)); // Debug
            GlobalState.socket.send(JSON.stringify(action));
            showSavedIndicator(); // Optimistic feedback

        } else {
            console.warn("Offline! Action queued.", action);
            GlobalState.offlineQueue.push(action);
            updateConnectionStatus('offline'); // Ensure UI knows we are effective offline
        }
    }

    // --- Offline & Queue Handling ---

    function handleOffline() {
        setEditorLock(true);
        if (DOM.connectionStatus && DOM.connectionStatus.classList.contains('status-superseded')) {
            return;
        }
        updateConnectionStatus('reconnecting'); // Show reconnecting status immediately
    }

    function handleOnline() {
        console.log("Browser detected 'online' event. Reconnecting immediately.");
        // Browser says online, force immediate reconnect attempt
        initWebSocket();
    }

    function updateConnectionStatus(status) {
        // status: 'online', 'offline', 'reconnecting', 'connecting'
        if (!DOM.connectionStatus) return;

        DOM.connectionStatus.className = 'connection-status'; // reset
        DOM.connectionStatus.style.display = 'block';

        if (status === 'online') {
            DOM.connectionStatus.style.display = 'none'; // Hide when good
            DOM.connectionStatus.textContent = 'Online';
        } else if (status === 'offline') {
            DOM.connectionStatus.classList.add('status-offline');
            DOM.connectionStatus.innerHTML = '<i class="fas fa-exclamation-triangle"></i> Offline - Editor Locked (Please reconnect)';
        } else if (status === 'reconnecting' || status === 'connecting') {
            DOM.connectionStatus.classList.add('status-reconnecting');
            DOM.connectionStatus.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Reconnecting - Editor Locked...';
        } else if (status === 'superseded') {
            DOM.connectionStatus.classList.add('status-offline');
            DOM.connectionStatus.innerHTML = '<i class="fas fa-exclamation-triangle"></i> Session Terminated - Editor opened in another tab.';
        }
    }

    function saveToLocalStorage() {
        if (DOM.editor) {
            localStorage.setItem(`editor_content_${GlobalState.assignmentTakerId}`, DOM.editor.value);
        }
    }

    function restoreFromLocalStorage() {
        if (!DOM.editor || !GlobalState.assignmentTakerId) return;
        const saved = localStorage.getItem(`editor_content_${GlobalState.assignmentTakerId}`);
        if (saved) {
            console.log("Restoring from local storage");
            DOM.editor.value = saved;
        }
    }

    function processOfflineQueue() {
        if (GlobalState.offlineQueue.length === 0) return;

        console.log(`Processing ${GlobalState.offlineQueue.length} offline actions...`);

        const queue = [...GlobalState.offlineQueue];
        GlobalState.offlineQueue = [];

        queue.forEach(action => {
            if (GlobalState.socket && GlobalState.socket.readyState === WebSocket.OPEN) {
                GlobalState.socket.send(JSON.stringify(action));
            } else {
                // Should not happen if we are called from init (connected)
                // But simply push back if connection dropped again
                GlobalState.offlineQueue.push(action);
            }
        });
    }


    // --- Editor Events ---

    function initEditorEvents() {
        const editor = DOM.editor;

        editor.addEventListener('copy', (e) => {
            e.preventDefault();
            copySelection();
        });
        editor.addEventListener('cut', (e) => {
            e.preventDefault();
        });
        editor.addEventListener('paste', (e) => {
            e.preventDefault();
            pasteAtCursor();
        });

        // Suppress Drag and Drop robustly + Logging for Safari debug
        ['dragstart', 'dragenter', 'dragover', 'drop', 'dragend', 'dragleave', 'selectstart'].forEach(evName => {
            editor.addEventListener(evName, (e) => {
                e.preventDefault();
                e.stopPropagation();
            });
        });

        // For spellcheck: enable contextmenu but BLOCKED the 'auto-fix' action
        editor.addEventListener('beforeinput', (event) => {
            const blockedTypes = ['insertReplacementText', 'insertFromSpelling', 'historyUndo', 'historyRedo'];

            if (blockedTypes.includes(event.inputType)) {
                event.preventDefault();
                console.warn("Blocked native replacement:", event.inputType);
            }
        });

        // Composition Events (IME / Dead Keys)
        editor.addEventListener('compositionstart', (event) => {
            GlobalState.isComposing = true;
        });

        editor.addEventListener('compositionend', (event) => {
            GlobalState.isComposing = false;
            const text = event.data;
            if (text) {
                // Browser has already inserted the text.
                // We just need to sync the state.
                const { selectionStart, selectionEnd } = editor;
                // Note: selectionStart is now AFTER the inserted text

                // Construct action matching what browser did
                // The browser replaced the *previous* selection with `text`.
                // But we don't know exactly where the selection was at start of composition 
                // if we strictly rely on current selection. 
                // However, usually composition happens at cursor.
                // To be robust: "Insert" action is text.
                // We assume browser placed it correctly.

                // We need to know where it was inserted. 
                // Simplification: We assume the user didn't move cursor during composition.
                // So the insertion start was (selectionStart - text.length).

                const insertedAt = selectionStart - text.length;

                const action = {
                    type: 'insert',
                    text: text,
                    from: insertedAt,
                    to: insertedAt // It was an insert at this Point (replacing nothing, usually)
                    // If text was selected before composition, browser deleted it? 
                    // Actually, composition usually replaces selection.
                    // But managing that state is hard. 
                    // Let's assume standard typing (no selection).
                };

                // Send action but DO NOT apply optimistic update since DOM is already correct
                sendAction(action);
                updateWordCount();
                saveToLocalStorage();
                handleEditorChange();
            }
        });

        // Keystroke handling
        editor.addEventListener('keydown', (event) => {
            const nonModifyingKeys = ['Shift', 'Control', 'Alt', 'Meta', 'ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'Home', 'End', 'PageUp', 'PageDown'];
            if (nonModifyingKeys.includes(event.key)) {
                return;
            }

            // Custom Clipboard & History Shortcuts
            if (event.ctrlKey || event.metaKey) {
                const key = event.key.toLowerCase();

                // Suppress Undo/Redo
                if (key === 'z' || key === 'y') {
                    event.preventDefault();
                    console.warn("Blocked native history action:", key === 'z' ? (event.shiftKey ? "Redo" : "Undo") : "Redo");
                    return;
                }

                if (!event.shiftKey) {
                    if (key === 'c') {
                        event.preventDefault();
                        copySelection();
                        return;
                    }
                    if (key === 'x') {
                        event.preventDefault(); // Just prevent default for Cut
                        return;
                    }
                    if (key === 'v') {
                        event.preventDefault();
                        pasteAtCursor();
                        return;
                    }
                }
            }

            // General non-modifying check for other Ctrl combos
            if ((event.ctrlKey || event.metaKey) && event.key !== 'Backspace' && event.key !== 'Delete') {
                return;
            }

            // Ignore if in composition mode (let browser start composition)
            if (GlobalState.isComposing) return;

            const { selectionStart, selectionEnd, value } = editor;
            const key = event.key;
            let action = null;

            // Handle Control Keys Manually
            if (key === 'Enter') {
                event.preventDefault();
                action = { type: 'insert', text: '\n', from: selectionStart, to: selectionEnd };
            } else if (key === 'Backspace') {
                event.preventDefault();
                let from = selectionStart;
                if (selectionStart === selectionEnd) {
                    if (event.ctrlKey || event.altKey || event.metaKey) {
                        const textBefore = value.slice(0, selectionStart);
                        let match = textBefore.match(/(\w+|[^\w\s]+)\s*$/);
                        if (!match) match = textBefore.match(/\s+$/);
                        from = match ? selectionStart - match[0].length : 0;
                    } else {
                        from -= 1;
                    }
                }
                if (from < 0) from = 0;
                if (from === selectionStart && selectionStart === selectionEnd) return; // Nothing to delete
                action = { type: 'delete', from: from, to: selectionEnd };
            } else if (key === 'Delete') {
                event.preventDefault();
                let to = selectionEnd;
                if (selectionStart === selectionEnd) {
                    if (event.ctrlKey || event.altKey || event.metaKey) {
                        const textAfter = value.slice(selectionEnd);
                        let match = textAfter.match(/^\s*(\w+|[^\w\s]+)/);
                        if (!match) match = textAfter.match(/^\s+/);
                        to = match ? selectionEnd + match[0].length : value.length;
                    } else {
                        to += 1;
                    }
                }
                if (to > value.length) to = value.length;
                if (selectionStart >= value.length && selectionStart === selectionEnd) return; // Nothing to delete
                action = { type: 'delete', from: selectionStart, to: to };
            }

            // NOTE: We NO LONGER preventDefault() for standard characters here.
            // We let them pass through to trigger 'beforeinput' or composition.

            if (action) {
                applyOptimisticUpdate(action);
                sendAction(action);
            }
        });

        // 3. 'beforeinput' Handler for standard typing
        editor.addEventListener('beforeinput', (event) => {
            if (event.inputType === 'insertText') {
                // This fires for standard typing (e.g. 'a', 'b', '1') but NOT for composition start.
                event.preventDefault(); // Stop browser insertion

                const text = event.data;
                const { selectionStart, selectionEnd } = editor;

                if (text) {
                    // The "Context Menu / Paste" Check
                    if (text.length > 1 && !GlobalState.isComposing) {
                        // We allow a small buffer for things like emoji or smart quotes 
                        // but block anything that looks like a word or sentence.
                        if (text.length > 3) {
                            console.warn("Blocked potential paste/replacement:", text);
                            return;
                        }
                    }

                    const action = { type: 'insert', text: text, from: selectionStart, to: selectionEnd };
                    clearClipboard(); // Flush clipboard on manual edit
                    applyOptimisticUpdate(action);
                    sendAction(action);
                }
            }
        });

        // Debounced update for Split View stored in GlobalState to be accessible
        GlobalState.debouncedSplitUpdate = debounce(() => {
            // console.log("Debounced split update. Active?", document.body.classList.contains('split-view')); 
            if (document.body.classList.contains('split-view')) {
                updateSplitPreview();
            }
        }, 300);

        editor.addEventListener('input', () => {
            updateWordCount();
            saveToLocalStorage();
            handleEditorChange();
        });
    }

    // --- Clipboard & Move Logic ---
    window.copySelection = copySelection;
    window.pasteAtCursor = pasteAtCursor;

    function clearClipboard() {
        if (GlobalState.internalClipboard) {
            console.log("Internal clipboard flushed.");
            GlobalState.internalClipboard = null;
        }
    }

    function copySelection() {
        const sel = getSelectionInfo();
        if (!sel || sel.start === sel.end) return;

        GlobalState.internalClipboard = {
            text: sel.value.slice(sel.start, sel.end),
            from: sel.start,
            to: sel.end,
            type: 'copy'
        };
    }

    function pasteAtCursor() {
        const cb = GlobalState.internalClipboard;
        if (!cb || !DOM.editor) return;

        const { selectionStart, selectionEnd } = DOM.editor;

        // Final action to server uses ranges/positions
        // To keep within DB limits (text: 10 chars), we send target as string
        // If replacing a selection, send a delete first
        if (selectionStart !== selectionEnd) {
            sendAction({ type: 'delete', from: selectionStart, to: selectionEnd });
        }

        const action = {
            type: 'paste',
            from: cb.from,
            to: cb.to,
            target: selectionStart
        };

        // Optimistic update
        applyOptimisticUpdate({ type: 'insert', text: cb.text, from: selectionStart, to: selectionEnd }, true);
        sendAction(action);
    }

    function applyOptimisticUpdate(action, isInternal = false) {
        if (!isInternal) {
            clearClipboard();
        }
        const editor = DOM.editor;
        const value = editor.value;
        let newCursorPos = action.from;
        let newText = value;

        if (action.type === 'insert') {
            newText = value.slice(0, action.from) + action.text + value.slice(action.to);
            newCursorPos = action.from + action.text.length;
        } else if (action.type === 'delete') {
            newText = value.slice(0, action.from) + value.slice(action.to);
            newCursorPos = action.from;
        }

        editor.value = newText;
        editor.setSelectionRange(newCursorPos, newCursorPos);

        updateWordCount();
        saveToLocalStorage();
        handleEditorChange(); // Trigger preview update
    }

    function handleEditorChange() {
        // Centralized place for side-effects of content change
        // We use a debounced global function or one defined here.
        // Since we need debounce state, let's use a module-level var or just define it here if possible.
        // Actually, let's look for a text change.
        if (GlobalState.debouncedSplitUpdate) {
            GlobalState.debouncedSplitUpdate();
        }
    }

    // --- Formatting Helpers ---

    // Helper to replace text and send actions
    function replaceSelectionWithText(start, end, newText) {
        if (!DOM.editor) return;

        // 1. Optimistic Update
        const full = DOM.editor.value;
        const before = full.slice(0, start);
        const after = full.slice(end);
        const newFull = before + newText + after;
        clearClipboard();

        DOM.editor.value = newFull;
        const cursorPos = start + newText.length;
        DOM.editor.setSelectionRange(cursorPos, cursorPos);

        updateWordCount();
        saveToLocalStorage();
        handleEditorChange();

        // 2. Send Actions (Delete range then Insert)
        // We can allow async here but we don't await strictly for UI response
        (async () => {
            if (end > start) {
                sendAction({ type: 'delete', from: start, to: end });
            }
            if (newText.length > 0) {
                // Send sequentially
                for (let i = 0; i < newText.length; i++) {
                    sendAction({ type: 'insert', text: newText[i], from: start + i, to: start + i });
                    await new Promise(r => setTimeout(r, 2)); // slight delay
                }
            }
        })();
    }

    function getSelectionInfo() {
        if (!DOM.editor || GlobalState.isOffline) return null;
        return {
            start: DOM.editor.selectionStart,
            end: DOM.editor.selectionEnd,
            value: DOM.editor.value
        };
    }

    // Global functions exposed to HTML onClick handlers

    window.formatText = function (kind) {
        const sel = getSelectionInfo();
        if (!sel) return;
        const { start, end, value } = sel;
        const selected = value.slice(start, end);

        let prefix = '', suffix = '';

        // Delegation to specific helpers
        if (kind === 'insertUnorderedList') return formatList(false);
        if (kind === 'insertOrderedList') return formatList(true);
        if (kind === 'indent') return indentSelection();
        if (kind === 'outdent') return outdentSelection();

        // Wrapper formatting
        if (kind === 'bold') { prefix = '**'; suffix = '**'; }
        else if (kind === 'italic') { prefix = '*'; suffix = '*'; }
        else if (kind === 'underline') { prefix = '<u>'; suffix = '</u>'; } // HTML fallback

        if (prefix) {
            replaceSelectionWithText(start, end, prefix + selected + suffix);
        }
    };

    window.formatHeading = function (level) {
        const sel = getSelectionInfo();
        if (!sel) return;
        // ... (existing logic adaptable here)
        // Simplify usage of existing logic but implemented cleanly
        processLineOperation(sel, (line) => {
            // simple toggle H#
            const n = parseInt(level.replace('H', '')) || 0;
            const currentHash = line.match(/^(#+)\s/);

            let cleaned = line.replace(/^(#{1,6}\s+)/, '');
            if (level === 'P') return cleaned;

            const targetHash = '#'.repeat(n) + ' ';
            if (currentHash && currentHash[1].length === n) {
                return cleaned; // Toggle off
            }
            return targetHash + cleaned;
        });
    };

    // Helper for line-based ops
    function processLineOperation(sel, transformFn) {
        const { start, end, value } = sel;
        const lineStart = value.lastIndexOf('\n', start - 1) + 1;
        let lineEnd = value.indexOf('\n', end);
        if (lineEnd === -1) lineEnd = value.length;

        const lines = value.slice(lineStart, lineEnd).split('\n');
        const newLines = lines.map(transformFn);
        const newText = newLines.join('\n');

        replaceSelectionWithText(lineStart, lineEnd, newText);
    }

    window.formatList = function (ordered) {
        const sel = getSelectionInfo();
        if (!sel) return;

        processLineOperation(sel, (line) => {
            const prefix = ordered ? '1. ' : '- ';
            // naive toggle
            if (ordered && /^\d+\.\s/.test(line)) return line.replace(/^\d+\.\s/, '');
            if (!ordered && /^-\s/.test(line)) return line.replace(/^-\s/, '');
            return prefix + line;
        });
    };

    window.indentSelection = function () {
        const sel = getSelectionInfo();
        if (!sel) return;
        processLineOperation(sel, line => '    ' + line);
    };

    window.outdentSelection = function () {
        const sel = getSelectionInfo();
        if (!sel) return;
        processLineOperation(sel, line => line.replace(/^ {1,4}/, ''));
    };

    window.insertFormula = function () {
        const sel = getSelectionInfo();
        if (!sel) return;
        const scaffold = '$$  $$';
        replaceSelectionWithText(sel.start, sel.end, scaffold);
        // Put cursor inside
        setTimeout(() => {
            DOM.editor.setSelectionRange(sel.start + 3, sel.start + 3);
            DOM.editor.focus();
        }, 10);
    };

    // --- Other Features ---

    window.manualSave = function () {
        // With WS, we just sync or show indicator
        console.log("Manual save triggered");
        saveToLocalStorage(); // force local save
        if (!GlobalState.isOffline) {
            // Maybe trigger a sync or just UI
            showSavedIndicator();
        } else {
            alert("Saved locally (Offline).");
        }
    };

    window.logout_user_from_session = function () {
        if (!GlobalState.assignmentTakerId) {
            window.location.reload();
            return;
        }

        fetch(`/logout/${GlobalState.assignmentTakerId}/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            }
        }).then(r => {
            window.location.reload();
        }).catch(e => {
            console.error("Logout fetch error:", e);
            window.location.reload();
        });
    };

    function initLogout() {
        // Wired via onclick in HTML
    }


    // --- Word Count ---

    function getWordLimit() {
        if (DOM.editor && DOM.editor.dataset.wordLimit) {
            return parseInt(DOM.editor.dataset.wordLimit, 10);
        }
        return null;
    }

    function updateWordCount() {
        if (!DOM.editor) return;
        const text = DOM.editor.value.trim();
        const count = text ? text.split(/\s+/).length : 0;

        if (DOM.wordCount) DOM.wordCount.textContent = count;

        if (GlobalState.wordLimit && count > GlobalState.wordLimit) {
            if (DOM.limitIndicator) DOM.limitIndicator.style.display = 'flex';
        } else {
            if (DOM.limitIndicator) DOM.limitIndicator.style.display = 'none';
        }
    }

    // --- Preview / PDF ---
    function renderMarkdown(md) {
        const rawHtml = marked.parse(md);
        const cleanHtml = DOMPurify.sanitize(rawHtml);
        const wrapper = document.createElement('div');
        wrapper.innerHTML = cleanHtml;

        // Render math
        renderMathInElement(wrapper, {
            delimiters: [
                { left: "$$", right: "$$", display: true },
                { left: "\\[", right: "\\]", display: true },
                { left: "$", right: "$", display: false },
                { left: "\\(", right: "\\)", display: false }
            ],
            throwOnError: false
        });
        return wrapper.innerHTML;
    }

    window.showPreview = function () {
        if (!DOM.modalContent) return;
        DOM.modalContent.innerHTML = renderMarkdown(DOM.editor.value);
        // Force links to _blank
        DOM.modalContent.querySelectorAll('a').forEach(a => a.setAttribute('target', '_blank'));
    }

    window.downloadPDF = function () {
        // Create a wrapper that resets all styles to prevent flex/inherited layout issues
        const wrapper = document.createElement('div');
        wrapper.style.all = 'initial';
        wrapper.style.display = 'block';
        wrapper.style.position = 'absolute';
        wrapper.style.left = '-10000px';
        wrapper.style.top = '0';
        wrapper.style.width = '800px';
        wrapper.style.zIndex = '-9999';

        const element = document.createElement('div');
        element.className = 'pdf-container';
        element.style.display = 'block';
        element.style.width = '100%';
        element.style.background = 'white';
        element.style.color = 'black';
        element.style.padding = '40px';
        element.style.fontFamily = 'serif';
        element.style.fontSize = '12pt';

        const markdown = DOM.editor.value;
        element.innerHTML = renderMarkdown(markdown);

        wrapper.appendChild(element);
        document.body.appendChild(wrapper);

        console.log("PDF: Wrapper scrollHeight:", wrapper.scrollHeight);
        console.log("PDF: Element scrollHeight:", element.scrollHeight);

        const opt = {
            margin: 0.5,
            filename: 'essay.pdf',
            image: { type: 'jpeg', quality: 0.98 },
            html2canvas: {
                scale: 1.5,
                useCORS: true,
                logging: true
            },
            jsPDF: { unit: 'in', format: 'letter', orientation: 'portrait' }
        };

        // Even longer delay to ensure browser layout engine settles after style.all = 'initial'
        setTimeout(() => {
            html2pdf().from(element).set(opt).toContainer().toCanvas().toImg().toPdf().save()
                .then(() => {
                    document.body.removeChild(wrapper);
                })
                .catch(err => {
                    console.error("PDF: Error:", err);
                    if (document.body.contains(wrapper)) {
                        document.body.removeChild(wrapper);
                    }
                });
        }, 500);
    }

    window.undo = function () { console.log('Undo not implemented (Backlog)'); }
    window.redo = function () { console.log('Redo not implemented (Backlog)'); }


    // --- Theme & View Mode Logic ---

    window.toggleDarkMode = function () {
        document.body.classList.toggle('dark-mode');
        const isDark = document.body.classList.contains('dark-mode');
        localStorage.setItem('theme', isDark ? 'dark' : 'light');
        updateThemeIcon(isDark);
    };

    window.toggleViewMode = function () {
        if (document.body.classList.contains('split-view')) return; // Disabled in split view

        document.body.classList.toggle('editor-card-view');
        const isCard = document.body.classList.contains('editor-card-view');
        localStorage.setItem('viewMode', isCard ? 'card' : 'seamless');
        // Optional: Update icon or visuals
    };

    window.toggleSplitView = function () {
        document.body.classList.toggle('split-view');
        const isSplit = document.body.classList.contains('split-view');
        localStorage.setItem('splitView', isSplit ? 'active' : 'inactive');

        updateViewToggleState();

        if (isSplit) {
            updateSplitPreview(); // Initial render
        }
    };

    function updateViewToggleState() {
        const viewBtn = document.getElementById('viewToggle');
        const isSplit = document.body.classList.contains('split-view');

        if (viewBtn) {
            viewBtn.disabled = isSplit;
            if (isSplit) {
                viewBtn.title = "Card View disabled in Split View";
                // Ensure visual cue is clear (CSS handles opacity/cursor)
            } else {
                viewBtn.title = "Toggle Card View";
                viewBtn.disabled = false;
            }
        }
    }

    function updateSplitPreview() {
        const pane = DOM.splitPreviewPane;
        if (!pane || !DOM.editor) return;

        // Render Markdown
        pane.innerHTML = renderMarkdown(DOM.editor.value);

        // Force links to _blank in preview
        pane.querySelectorAll('a').forEach(a => a.setAttribute('target', '_blank'));
    }

    function initSplitView() {
        const savedSplit = localStorage.getItem('splitView');
        if (savedSplit === 'active') {
            document.body.classList.add('split-view');
            updateSplitPreview(); // Render immediately
        }
        updateViewToggleState();
    }

    function initTheme() {
        const savedTheme = localStorage.getItem('theme');
        const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;

        // Theme
        if (savedTheme === 'dark' || (!savedTheme && prefersDark)) {
            document.body.classList.add('dark-mode');
            updateThemeIcon(true);
        } else {
            updateThemeIcon(false);
        }

        // View Mode
        const savedView = localStorage.getItem('viewMode');
        if (savedView === 'card') {
            document.body.classList.add('editor-card-view');
        }
    }

    function renderTaskMath() {
        // Render LaTeX in the header container (title and task text)
        const container = document.getElementById('collapsible-container');
        if (container) {
            renderMathInElement(container, {
                delimiters: [
                    { left: "$$", right: "$$", display: true },
                    { left: "\\[", right: "\\]", display: true },
                    { left: "$", right: "$", display: false },
                    { left: "\\(", right: "\\)", display: false }
                ],
                throwOnError: false
            });
        }
    }

    // --- Utilities ---

    function debounce(func, wait) {
        let timeout;
        return function (...args) {
            const context = this;
            clearTimeout(timeout);
            timeout = setTimeout(() => func.apply(context, args), wait);
        };
    }


    function updateThemeIcon(isDark) {
        const btn = document.getElementById('themeToggle');
        if (!btn) return;
        const icon = btn.querySelector('i');
        if (isDark) {
            icon.className = 'fas fa-sun'; // Sun icon for switching back to light
        } else {
            icon.className = 'fas fa-moon'; // Moon icon for switching to dark
        }
    }


    // --- Utils ---
    function getCsrfToken() {
        let token = document.querySelector('[name=csrfmiddlewaretoken]')?.value;
        if (!token) {
            const matches = document.cookie.match(/csrftoken=([^;]+)/);
            if (matches) {
                token = matches[1];
            }
        }
        return token || '';
    }

    function initDeadline() {
        const el = DOM.deadline;
        if (!el) return;
        const utc = el.dataset.utc;
        if (utc) {
            const date = new Date(utc);
            el.textContent = date.toLocaleString();
        }
    }

    // Collapsing logic
    const container = document.getElementById('collapsible-container');
    if (container) {
        container.addEventListener('click', () => {
            container.classList.toggle('collapsed');
        });
    }

})(); // End of IIFE