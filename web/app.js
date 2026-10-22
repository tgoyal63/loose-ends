"use strict";

(() => {
  const byId = (id) => document.getElementById(id);
  const MAX_NOTES = 60000;
  const ui = {
    form: byId("notes-form"), notes: byId("notes"), count: byId("notes-count"),
    inputError: byId("notes-error"),
    generate: byId("generate-button"), generateLabel: byId("generate-label"),
    cancel: byId("cancel-button"), sample: byId("sample-button"),
    sampleConfirm: byId("sample-confirm"), sampleReplace: byId("sample-replace"),
    sampleCancel: byId("sample-cancel"), status: byId("model-status"),
    statusDot: byId("status-dot"), statusLabel: byId("status-label"),
    statusMessage: byId("status-message"), retry: byId("status-retry"),
    panel: byId("actions-panel"), heading: byId("actions-heading"),
    feedback: byId("feedback"), stale: byId("stale-notice"),
    loading: byId("loading-state"), empty: byId("empty-state"),
    emptyTitle: byId("empty-title"), emptyCopy: byId("empty-copy"),
    emptyCaption: byId("empty-caption"), summary: byId("results-summary"),
    list: byId("task-list"), taskCount: byId("task-count"),
    export: byId("export-button"), resultNote: byId("results-note"),
    undo: byId("undo-notice"), undoMessage: byId("undo-message"),
    undoButton: byId("undo-button"), announcer: byId("announcer"),
    replacementNote: byId("replacement-note"),
    mode: byId("processing-mode"), modeHelp: byId("processing-help"),
    privacy: byId("privacy-summary"), loadingCopy: byId("loading-copy"),
    hostedForm: byId("hosted-form"), hostedKey: byId("hosted-key"),
    hostedConnect: byId("hosted-connect"), hostedDisconnect: byId("hosted-disconnect"),
    hostedMessage: byId("hosted-message"),
  };

  const SAMPLE_NOTES = [
    "Community garden catch-up — made-up sample notes",
    "",
    "Maya will email the seed order to the group by Friday.",
    "We liked the idea of adding a second compost bin, but haven't decided yet.",
    "If the forecast is dry, Sam will bring the spare watering cans on Saturday.",
    "I need to print six welcome signs before the next volunteer morning.",
    "The old noticeboard was repaired last week. No more work needed there.",
    "Lee will check whether the library can lend us a folding table.",
  ].join("\n");

  const state = {
    ready: false, statusPending: false, busy: false, hasRun: false,
    inputKind: "notes", lastFailure: "",
    tasks: [], sourceNotes: "", model: "", rejected: 0, initialCount: 0,
    controller: null, requestNumber: 0, editing: null, removed: null,
    mode: "local", hostedConfigured: false, configPending: false,
    statusController: null, statusNumber: 0,
    nextUiId: 1,
  };

  function node(tag, className, content) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (content !== undefined) element.textContent = content;
    return element;
  }

  function announce(message) {
    ui.announcer.textContent = message;
  }

  function showFeedback(message, kind = "info", focus = false) {
    ui.feedback.textContent = message;
    ui.feedback.className = `feedback ${kind}`;
    ui.feedback.setAttribute("role", kind === "error" ? "alert" : "status");
    ui.feedback.hidden = false;
    if (focus) ui.feedback.focus();
  }

  function clearFeedback() {
    ui.feedback.hidden = true;
    ui.feedback.textContent = "";
  }

  function updateControls() {
    const length = Array.from(ui.notes.value).length;
    const tooLong = length > MAX_NOTES;
    ui.count.textContent = `${length.toLocaleString("en-US")} / 60,000`;
    ui.notes.setAttribute("aria-invalid", String(tooLong));
    ui.inputError.hidden = !tooLong;
    ui.inputError.textContent = tooLong
      ? "Your full text is still here. Choose an excerpt of 60,000 characters or fewer before finding actions."
      : "";
    ui.generate.disabled = state.busy || state.configPending || !state.ready || !ui.notes.value.trim();
    ui.generateLabel.textContent = state.busy ? "Finding actions…" : state.hasRun ? "Find actions again" : "Find actions";
    ui.notes.readOnly = state.busy;
    ui.sample.disabled = state.busy;
    ui.sampleReplace.disabled = state.busy;
    ui.cancel.hidden = !state.busy;
    ui.loading.hidden = !state.busy;
    ui.panel.setAttribute("aria-busy", String(state.busy));
    ui.export.disabled = state.busy || !state.tasks.length || state.editing !== null;
    ui.export.title = state.editing !== null ? "Save or cancel your edit before exporting" : "Download your action list as Markdown";
    ui.stale.hidden = !state.hasRun || ui.notes.value === state.sourceNotes;
    ui.undoButton.disabled = state.busy || state.editing !== null;
    ui.replacementNote.hidden = !state.tasks.length;
    ui.mode.disabled = state.configPending;
    ui.retry.disabled = state.statusPending || state.configPending || state.busy;
    ui.hostedKey.disabled = state.busy || state.configPending;
    ui.hostedConnect.disabled = state.busy || state.configPending || !ui.hostedKey.value.trim();
    ui.hostedConnect.textContent = state.configPending ? "Updating…" : state.hostedConfigured ? "Replace key" : "Connect";
    ui.hostedDisconnect.disabled = state.busy || state.configPending;
    ui.hostedDisconnect.hidden = !state.hostedConfigured;
    for (const control of ui.list.querySelectorAll(".task-check, .task-controls button")) {
      const ownEdit = control.dataset.taskId === String(state.editing);
      control.disabled = state.busy || (state.editing !== null && !ownEdit);
    }
  }

  function updateSummary() {
    const done = state.tasks.filter((task) => task.done).length;
    const count = state.tasks.length;
    ui.taskCount.hidden = !state.hasRun;
    ui.taskCount.textContent = String(count);
    ui.summary.hidden = !state.hasRun || count === 0;
    ui.summary.textContent = `${count} ${count === 1 ? "action" : "actions"} · ${done} done · ${state.model}`;
    ui.resultNote.hidden = count === 0;
    ui.resultNote.textContent = state.inputKind === "transcript"
      ? "Review each draft against its source and nearby conversation, including prerequisites and later corrections. Unclear owners stay unassigned; other commitments may be missed."
      : "Quotes are checked against your text. Review the suggested actions, owners, dates and conditions before using them.";
    ui.empty.hidden = count > 0 || state.busy;
    ui.undo.hidden = state.removed === null;
    if (count === 0 && state.lastFailure) {
      ui.emptyCaption.hidden = true;
      ui.emptyTitle.textContent = "The draft couldn't be created.";
      ui.emptyCopy.textContent = "Your text is still here. Check the error above, then try again. This failed request does not mean your notes contain no actions.";
      return;
    }
    if (!state.hasRun) {
      ui.emptyCaption.hidden = false;
      ui.emptyTitle.textContent = "No draft actions yet.";
      ui.emptyCopy.textContent = "Add notes or a meeting transcript and select Find actions. Each suggestion will keep its original source text.";
      return;
    }
    ui.emptyCaption.hidden = true;
    if (state.initialCount > 0 && count === 0) {
      ui.emptyTitle.textContent = "All actions removed.";
      ui.emptyCopy.textContent = "Undo the last removal, or find actions in another set of notes.";
    } else if (count === 0 && state.rejected > 0) {
      ui.emptyTitle.textContent = "The drafts could not be verified.";
      ui.emptyCopy.textContent = state.inputKind === "transcript"
        ? "The request finished, but none of the model's suggestions could be grounded in the transcript. This does not mean there are no actions. Try a shorter complete exchange, keeping its speaker names and timestamps."
        : "The request finished, but none of the model's suggestions passed the source checks. This does not mean there are no actions. Try a shorter excerpt with each commitment and its conditions together.";
    } else if (count === 0) {
      ui.emptyTitle.textContent = "No actions suggested this time.";
      ui.emptyCopy.textContent = "The model didn't identify any actions in this run. It may have missed commitments. Review the source or try a shorter complete exchange.";
    }
  }

  function updateModeCopy() {
    const hosted = state.mode === "hosted";
    ui.mode.value = state.mode;
    ui.hostedForm.hidden = !hosted;
    ui.privacy.textContent = hosted
      ? "Hosted mode sends submitted notes to Groq."
      : "Local mode processes notes on this machine.";
    ui.modeHelp.textContent = hosted
      ? "GPT-OSS 120B runs on Groq. Find actions sends your submitted notes there and may use paid API credit. Switching modes keeps your current action list."
      : "Notes are processed on this machine. Switching modes keeps your current action list.";
    ui.retry.setAttribute("aria-label", hosted ? "Check Groq connection again" : "Check local model connection again");
    ui.loadingCopy.textContent = hosted
      ? "Groq is reading the submitted text; the app will check its sources. Stopping your wait cannot recall the request and may still use API credit."
      : "Reading the text and checking its sources. Long transcripts can take longer; your text stays here if you stop waiting.";
  }

  function cancelStatus() {
    state.statusNumber++;
    state.statusController?.abort();
    state.statusController = null;
    state.statusPending = false;
  }

  async function checkStatus() {
    if (state.statusPending || state.configPending || state.busy) return;
    const mode = state.mode;
    const hosted = mode === "hosted";
    const request = ++state.statusNumber;
    state.statusPending = true;
    state.ready = false;
    ui.statusLabel.textContent = hosted ? "Checking Groq…" : "Checking your local model…";
    ui.statusMessage.textContent = "Checking the connection without submitting your notes.";
    ui.statusDot.className = "status-dot checking";
    const controller = new AbortController();
    state.statusController = controller;
    const timeout = setTimeout(() => controller.abort(), 12000);
    updateControls();
    try {
      const response = await fetch(`/api/status?mode=${mode}`, { signal: controller.signal, cache: "no-store" });
      if (!response.ok) throw new Error("The local app could not check the model.");
      const data = await response.json();
      if (request !== state.statusNumber) return;
      if (typeof data.ready !== "boolean" || typeof data.model !== "string" || typeof data.message !== "string"
        || data.mode !== mode || typeof data.configured !== "boolean") {
        throw new Error("The local app returned an unexpected status. Restart it and check again.");
      }
      state.ready = data.ready;
      if (hosted) state.hostedConfigured = data.configured;
      ui.statusLabel.textContent = hosted
        ? data.ready ? "Groq ready" : data.configured ? "Groq isn't ready" : "Connect Groq to continue"
        : data.ready ? "Local model ready" : "Local model isn't ready";
      ui.statusMessage.textContent = data.ready
        ? `${data.model} · ${hosted ? "Submitted notes are sent to Groq" : "Runs on this machine"}`
        : data.message || (hosted ? "Connect your Groq key, then check again." : "Start your local model, then check again. Your notes will stay on this page.");
    } catch (error) {
      if (request !== state.statusNumber) return;
      state.ready = false;
      ui.statusLabel.textContent = hosted ? "Can't check the Groq connection" : "Can't reach the local model";
      ui.statusMessage.textContent = error.name === "AbortError"
        ? "The connection check timed out. Check again when the local app and selected model are available."
        : "Make sure the local app and selected model are available, then check again. Your notes are still here.";
    } finally {
      clearTimeout(timeout);
      if (request !== state.statusNumber) return;
      state.statusPending = false;
      state.statusController = null;
      ui.statusDot.className = `status-dot ${state.ready ? "ready" : "unavailable"}`;
      ui.status.classList.toggle("unavailable", !state.ready);
      updateControls();
      const name = hosted ? "Groq" : "Local model";
      announce(state.ready ? `${name} ready. Add notes to find actions.` : `${name} unavailable. Check the connection message for next steps.`);
    }
  }

  function changeMode() {
    if (state.configPending) { ui.mode.value = state.mode; return; }
    const mode = ui.mode.value;
    if (!["local", "hosted"].includes(mode) || mode === state.mode) return;
    const waiting = state.busy;
    const wasHosted = state.mode === "hosted";
    state.requestNumber++;
    state.controller?.abort();
    state.controller = null;
    state.busy = false;
    cancelStatus();
    state.ready = false;
    state.mode = mode;
    ui.hostedKey.value = "";
    ui.hostedMessage.hidden = true;
    updateModeCopy();
    updateControls();
    updateSummary();
    if (waiting) {
      showFeedback(`Switched modes and stopped waiting. Your notes and previous actions are still here. ${wasHosted ? "The request already sent to Groq may still finish and use API credit." : "The local model may take a moment to finish its current request."}`);
    }
    checkStatus();
  }

  async function configureHosted(disconnect = false) {
    if (state.busy || state.configPending || state.mode !== "hosted") return;
    if (!disconnect && !ui.hostedKey.value.trim()) { ui.hostedKey.focus(); return; }
    const body = JSON.stringify({ api_key: disconnect ? "" : ui.hostedKey.value.trim() });
    ui.hostedKey.value = "";
    cancelStatus();
    state.configPending = true;
    state.ready = false;
    ui.hostedMessage.hidden = false;
    ui.hostedMessage.setAttribute("role", "status");
    ui.hostedMessage.textContent = disconnect ? "Disconnecting Groq…" : "Connecting Groq…";
    ui.statusLabel.textContent = "Updating Groq connection…";
    ui.statusDot.className = "status-dot checking";
    updateControls();
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 12000);
    try {
      const response = await fetch("/api/hosted", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body, signal: controller.signal,
      });
      const data = await response.json();
      if (!response.ok || typeof data.configured !== "boolean" || data.configured !== !disconnect) {
        throw new Error("Connection setup failed");
      }
      state.hostedConfigured = data.configured;
      ui.hostedMessage.textContent = disconnect
        ? "Groq disconnected. Your notes and actions are still here."
        : "Key held in the local app's memory.";
    } catch {
      ui.hostedMessage.setAttribute("role", "alert");
      ui.hostedMessage.textContent = "The connection update could not be confirmed. Checking its current status; your notes and actions are still here.";
    } finally {
      clearTimeout(timeout);
      state.configPending = false;
      updateControls();
      checkStatus();
    }
  }

  function validatePlan(data, notes, mode) {
    if (!data || !Array.isArray(data.tasks) || typeof data.model !== "string"
      || data.mode !== mode
      || !Number.isInteger(data.rejected_count) || data.rejected_count < 0
      || (data.input_kind !== undefined && !["notes", "transcript"].includes(data.input_kind))) {
      throw new Error("The model returned an unreadable action list. Your notes and previous actions have been kept.");
    }
    for (const task of data.tasks) {
      if (!task || typeof task.id !== "string" || typeof task.title !== "string" || !task.title.trim()
        || typeof task.quote !== "string" || !task.quote.trim() || !notes.includes(task.quote)
        || !["owner", "due", "condition"].every((key) => task[key] === null || typeof task[key] === "string")) {
        throw new Error("A suggested action had missing or unmatched source text. Your notes and previous actions have been kept. Please try again.");
      }
      if (task.source !== undefined) {
        const source = task.source;
        if (!source || !["speaker", "timestamp", "context"].every((key) => typeof source[key] === "string" && source[key].trim())
          || !notes.includes(source.context) || !source.context.includes(task.quote)
          || !task.quote.includes(source.speaker) || !task.quote.includes(source.timestamp)) {
          throw new Error("A draft's transcript evidence did not match your text. Your notes and previous actions have been kept. Please try again.");
        }
      }
    }
    return data;
  }

  async function generate(event) {
    event.preventDefault();
    if (state.busy || state.configPending || !state.ready || !ui.notes.value.trim()) return;
    if (state.editing !== null) {
      showFeedback("Save or cancel the open action edit before finding a new list.", "info", true);
      return;
    }
    if (Array.from(ui.notes.value).length > MAX_NOTES) {
      showFeedback("Your full text has been kept. Choose an excerpt of 60,000 characters or fewer, then try again.", "error", true);
      return;
    }
    const notes = ui.notes.value;
    const mode = state.mode;
    const request = ++state.requestNumber;
    const controller = new AbortController();
    state.controller = controller;
    state.busy = true;
    state.lastFailure = "";
    ui.sampleConfirm.hidden = true;
    clearFeedback();
    updateControls();
    updateSummary();
    announce("Finding draft actions and checking their source quotes.");
    let timedOut = false;
    const timeout = setTimeout(() => { timedOut = true; controller.abort(); }, 180000);
    try {
      const response = await fetch("/api/plan", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ notes, mode }), signal: controller.signal,
      });
      let data;
      try { data = await response.json(); } catch { throw new Error("The local app returned an unreadable response. Your notes and previous actions have been kept."); }
      if (request !== state.requestNumber) return;
      if (!response.ok) {
        if (response.status === 503) {
          state.ready = false;
          ui.statusLabel.textContent = mode === "hosted" ? "Groq isn't ready" : "Local model isn't ready";
          ui.statusMessage.textContent = mode === "hosted"
            ? "Check your Groq connection, then select Check again."
            : "Check that your local model is running, then select Check again.";
          ui.statusDot.className = "status-dot unavailable";
          ui.status.classList.add("unavailable");
        }
        const detail = typeof data?.error?.message === "string" ? data.error.message : "The selected model couldn't make an action list. Please try again.";
        throw new Error(`${detail} Your notes and previous actions have been kept.`);
      }
      const plan = validatePlan(data, notes, mode);
      if (request !== state.requestNumber) return;
      state.tasks = plan.tasks.map((task) => ({ ...task, uiId: state.nextUiId++, done: false, humanEdited: false }));
      state.sourceNotes = notes;
      state.model = plan.model;
      state.inputKind = plan.input_kind || "notes";
      state.rejected = plan.rejected_count;
      state.initialCount = state.tasks.length;
      state.hasRun = true;
      state.removed = null;
      renderTasks();
      if (plan.rejected_count > 0 && state.tasks.length > 0) {
        showFeedback(`${plan.rejected_count} ${plan.rejected_count === 1 ? "suggestion was" : "suggestions were"} left out by the checks for unsupported, duplicate or uncertain details. Review the remaining drafts too.`);
      }
      const count = state.tasks.length;
      announce(count ? `${count} ${count === 1 ? "action is" : "actions are"} ready to review.` : "No draft actions were returned. Review the explanation below.");
      ui.heading.focus();
    } catch (error) {
      if (request !== state.requestNumber) return;
      const message = timedOut
        ? "The selected model is taking longer than expected. Your notes and previous actions have been kept. Check the model before trying again."
        : error instanceof TypeError
          ? "The connection was interrupted. Your notes and previous actions have been kept. Check the local app, then try again."
          : error.message || "Something went wrong. Your notes and previous actions have been kept.";
      state.lastFailure = message;
      showFeedback(message, "error", true);
    } finally {
      clearTimeout(timeout);
      if (request === state.requestNumber) {
        state.busy = false;
        state.controller = null;
        updateControls();
        updateSummary();
      }
    }
  }

  function stopWaiting() {
    if (!state.busy) return;
    state.requestNumber++;
    state.controller?.abort();
    state.controller = null;
    state.busy = false;
    updateControls();
    updateSummary();
    showFeedback(`Stopped waiting. Your notes and previous actions are still here. ${state.mode === "hosted" ? "The request already sent to Groq may still finish and use API credit." : "The local model may take a moment to finish its current request."}`, "info", true);
  }

  function addMeta(container, label, value) {
    if (!value) return;
    const group = node("div");
    group.append(node("dt", "", label), node("dd", "", value));
    container.append(group);
  }

  function renderTasks() {
    ui.list.replaceChildren();
    for (const task of state.tasks) {
      const item = node("li", `task-card${task.done ? " done" : ""}`);
      item.id = `task-${task.uiId}`;
      const top = node("div", "task-top");
      const checkbox = node("input", "task-check");
      checkbox.type = "checkbox";
      checkbox.id = `done-${task.uiId}`;
      checkbox.checked = task.done;
      checkbox.dataset.taskId = String(task.uiId);
      checkbox.setAttribute("aria-label", `Mark ${task.title} as ${task.done ? "not done" : "done"}`);
      checkbox.addEventListener("change", () => {
        task.done = checkbox.checked;
        item.classList.toggle("done", task.done);
        checkbox.setAttribute("aria-label", `Mark ${task.title} as ${task.done ? "not done" : "done"}`);
        updateSummary();
        announce(`Action marked ${task.done ? "done" : "not done"}.`);
      });
      const content = node("div", "task-content");
      content.append(node("h3", "task-title", task.title));
      const meta = node("dl", "task-meta");
      addMeta(meta, "Owner", task.owner);
      addMeta(meta, "Due", task.due);
      if (meta.childNodes.length) content.append(meta);
      if (task.condition) content.append(node("p", "condition", `Conditions / context: ${task.condition}`));
      top.append(checkbox, content);
      const quote = node("blockquote", "source-quote");
      const sourceLabel = task.source ? `Source · ${task.source.speaker} · ${task.source.timestamp}` : "Source";
      quote.append(node("span", "source-label", sourceLabel), node("p", "", task.quote));
      if (task.source && task.source.context !== task.quote) {
        const context = node("details", "source-context");
        context.append(node("summary", "", "Nearby conversation"), node("p", "", task.source.context));
        quote.append(context);
      }
      const bottom = node("div", "task-bottom");
      const edited = node("span", "edited-label", task.humanEdited ? "Edited by you" : "AI draft · review first");
      const controls = node("div", "task-controls");
      const edit = node("button", "button-text", "Edit");
      edit.id = `edit-${task.uiId}`;
      edit.type = "button";
      edit.dataset.taskId = String(task.uiId);
      edit.setAttribute("aria-label", `Edit action: ${task.title}`);
      edit.setAttribute("aria-expanded", "false");
      edit.addEventListener("click", () => openEditor(task, item, edit));
      const remove = node("button", "button-text", "Remove");
      remove.type = "button";
      remove.dataset.taskId = String(task.uiId);
      remove.setAttribute("aria-label", `Remove action: ${task.title}`);
      remove.addEventListener("click", () => {
        if (state.editing !== null || state.busy) return;
        const index = state.tasks.indexOf(task);
        state.removed = { task, index };
        state.tasks.splice(index, 1);
        ui.undoMessage.textContent = "Action removed.";
        renderTasks();
        updateControls();
        updateSummary();
        ui.undoButton.focus();
        announce("Action removed. Undo is available.");
      });
      controls.append(edit, remove);
      bottom.append(edited, controls);
      item.append(top, quote, bottom);
      ui.list.append(item);
    }
  }

  function openEditor(task, card, trigger) {
    if (state.busy || state.editing !== null) return;
    state.editing = task.uiId;
    trigger.setAttribute("aria-expanded", "true");
    const form = node("form", "edit-panel");
    form.setAttribute("aria-label", "Edit action");
    const fields = {};
    function field(key, label, multiline, maxLength) {
      const wrapper = node("div", "edit-field");
      const inputId = `${key}-${task.uiId}`;
      const caption = node("label", "", label);
      caption.htmlFor = inputId;
      const input = node(multiline ? "textarea" : "input");
      input.id = inputId;
      input.name = key;
      input.maxLength = maxLength;
      input.value = task[key] || "";
      if (key === "title") input.required = true;
      wrapper.append(caption, input);
      fields[key] = input;
      return wrapper;
    }
    form.append(field("title", "Action", true, 2000));
    const row = node("div", "edit-row");
    row.append(field("owner", "Owner · optional", false, 500), field("due", "Due · optional", false, 500));
    form.append(row, field("condition", "Conditions / context · optional", true, 12000));
    form.append(node("p", "edit-hint", "Your changes are marked as edited by you. The original source quote stays attached."));
    const buttons = node("div", "edit-buttons");
    const save = node("button", "button-small", "Save changes");
    save.type = "submit";
    const cancel = node("button", "button-text", "Cancel");
    cancel.type = "button";
    const close = () => {
      state.editing = null;
      form.remove();
      trigger.setAttribute("aria-expanded", "false");
      updateControls();
      trigger.focus();
    };
    cancel.addEventListener("click", close);
    form.addEventListener("keydown", (event) => {
      if (event.key === "Escape") { event.preventDefault(); close(); }
    });
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      if (!fields.title.value.trim()) {
        fields.title.setCustomValidity("Write an action before saving.");
        fields.title.reportValidity();
        return;
      }
      let changed = false;
      for (const key of ["title", "owner", "due", "condition"]) {
        const value = fields[key].value.trim() || (key === "title" ? "" : null);
        if (value !== task[key]) { changed = true; task[key] = value; }
      }
      task.humanEdited = task.humanEdited || changed;
      state.editing = null;
      renderTasks();
      updateControls();
      byId(`edit-${task.uiId}`).focus();
      announce(changed ? "Your changes were saved. The original source quote is unchanged." : "Action unchanged.");
    });
    fields.title.addEventListener("input", () => fields.title.setCustomValidity(""));
    buttons.append(save, cancel);
    form.append(buttons);
    card.append(form);
    updateControls();
    fields.title.focus();
  }

  function escapeMarkdown(value) {
    // CommonMark backslash escapes preserve every ASCII punctuation character,
    // including entity ampersands and markers at the beginning of a source line.
    return String(value).replace(/[!-/:-@[-`{-~]/g, "\\$&");
  }

  function exportMarkdown() {
    if (!state.tasks.length || state.busy || state.editing !== null) return;
    const lines = ["# Loose Ends", "", `Action list · ${new Date().toLocaleDateString("en-CA")}`, "", `Model: ${escapeMarkdown(state.model)}`, "", "Drafts need human review. Source quotes were checked against the submitted text; user edits are marked below.", ""];
    if (ui.notes.value !== state.sourceNotes) lines.push("Note: this list refers to an earlier version of the notes currently in the tab.", "");
    for (const task of state.tasks) {
      lines.push(`- [${task.done ? "x" : " "}] ${escapeMarkdown(task.title).replace(/\r?\n/g, " ")}`);
      for (const [key, label] of [["owner", "Who"], ["due", "When"], ["condition", "Conditions / context"]]) {
        if (task[key]) lines.push(`  - ${label}: ${escapeMarkdown(task[key]).replace(/\r?\n/g, " ")}`);
      }
      lines.push(`  - ${task.humanEdited ? "Edited by you; original source quote retained." : "AI draft."}`, "", "  Source:", "");
      for (const line of task.quote.split(/\r?\n/)) lines.push(`  > ${escapeMarkdown(line)}`);
      if (task.source && task.source.context !== task.quote) {
        lines.push("", "  Nearby conversation (review for prerequisites and corrections):", "");
        for (const line of task.source.context.split(/\r?\n/)) lines.push(`  > ${escapeMarkdown(line)}`);
      }
      lines.push("");
    }
    const blob = new Blob([lines.join("\n")], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = node("a");
    anchor.href = url;
    anchor.download = `loose-ends-${new Date().toISOString().slice(0, 10)}.md`;
    document.body.append(anchor);
    anchor.click();
    anchor.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    announce("Your action list was exported as a Markdown file.");
  }

  function useSample() {
    if (state.busy) return;
    ui.notes.value = SAMPLE_NOTES;
    ui.sampleConfirm.hidden = true;
    updateControls();
    ui.notes.focus();
    announce(`Made-up sample notes inserted. Select Find actions to ${state.mode === "hosted" ? "send them to Groq" : "run the local model"}.`);
  }

  ui.form.addEventListener("submit", generate);
  ui.mode.addEventListener("change", changeMode);
  ui.hostedKey.addEventListener("input", updateControls);
  ui.hostedForm.addEventListener("submit", (event) => { event.preventDefault(); configureHosted(); });
  ui.hostedDisconnect.addEventListener("click", () => configureHosted(true));
  ui.notes.addEventListener("input", updateControls);
  ui.cancel.addEventListener("click", stopWaiting);
  ui.retry.addEventListener("click", checkStatus);
  ui.export.addEventListener("click", exportMarkdown);
  ui.sample.addEventListener("click", () => {
    if (state.busy) return;
    if (ui.notes.value.trim()) { ui.sampleConfirm.hidden = false; ui.sampleCancel.focus(); }
    else useSample();
  });
  ui.sampleReplace.addEventListener("click", useSample);
  ui.sampleCancel.addEventListener("click", () => { ui.sampleConfirm.hidden = true; ui.sample.focus(); });
  ui.undoButton.addEventListener("click", () => {
    if (!state.removed || state.busy || state.editing !== null) return;
    const { task, index } = state.removed;
    state.tasks.splice(Math.min(index, state.tasks.length), 0, task);
    state.removed = null;
    renderTasks();
    updateControls();
    updateSummary();
    byId(`edit-${task.uiId}`).focus();
    announce("Removed action restored.");
  });
  window.addEventListener("beforeunload", (event) => {
    if (ui.notes.value.trim() || state.tasks.length || state.busy) {
      event.preventDefault();
      event.returnValue = "";
    }
  });
  updateModeCopy();
  updateControls();
  checkStatus();
})();
