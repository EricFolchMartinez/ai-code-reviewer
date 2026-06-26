/* AI Code Reviewer - front-end logic */
(() => {
  "use strict";

  const $ = (sel) => document.querySelector(sel);

  // State
  let selectedFiles = [];          // File objects
  let reviews = {};                // name -> markdown
  let reportBlobUrl = null;        // object URL for the in-memory report download
  const serverHasKey = document.body.dataset.apiKeySet === "true";
  const publicDemo = document.body.dataset.publicDemo === "true";

  // Elements (several are absent in the public demo — guard every use).
  const apiBadge = $("#apiBadge");
  const apiKeyBtn = $("#apiKeyBtn");
  const apiModal = $("#apiModal");
  const apiKeyInput = $("#apiKeyInput");
  const dropzone = $("#dropzone");
  const fileInput = $("#fileInput");
  const browseBtn = $("#browseBtn");
  const fileList = $("#fileList");
  const codeInput = $("#codeInput");
  const snippetName = $("#snippetName");
  const analyzeBtn = $("#analyzeBtn");
  const clearBtn = $("#clearBtn");
  const resultTabs = $("#resultTabs");
  const resultBody = $("#resultBody");
  const emptyState = $("#emptyState");
  const loading = $("#loading");
  const loadingText = $("#loadingText");
  const markdownEl = $("#markdown");
  const downloadBtn = $("#downloadBtn");

  // Inline SVG icons
  const ICON_FILE =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/></svg>';
  const ICON_X =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>';

  // Markdown options (marked v12 removed the built-in highlight hook; we run
  // highlight.js manually on the rendered code blocks in showReview).
  if (window.marked) marked.setOptions({ breaks: false, gfm: true });

  // ---- API key handling (development only) ----
  const storedKey = () => localStorage.getItem("groq_api_key") || "";

  function refreshBadge() {
    if (!apiBadge) return;
    const hasKey = serverHasKey || !!storedKey();
    apiBadge.classList.toggle("ok", hasKey);
    apiBadge.classList.toggle("err", !hasKey);
    apiBadge.querySelector(".status-text").textContent =
      hasKey ? "API key configured" : "API key required";
  }

  if (apiKeyBtn && apiModal && apiKeyInput) {
    apiKeyBtn.addEventListener("click", () => {
      apiKeyInput.value = storedKey();
      apiModal.classList.remove("hidden");
      apiKeyInput.focus();
    });
    $("#apiCancel").addEventListener("click", () => apiModal.classList.add("hidden"));
    $("#apiSave").addEventListener("click", () => {
      const val = apiKeyInput.value.trim();
      if (val) localStorage.setItem("groq_api_key", val);
      else localStorage.removeItem("groq_api_key");
      apiModal.classList.add("hidden");
      refreshBadge();
      toast(val ? "API key saved." : "API key removed.");
    });
    apiModal.addEventListener("click", (e) => {
      if (e.target === apiModal) apiModal.classList.add("hidden");
    });
  }

  // ---- Tabs (input) ----
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
      tab.classList.add("active");
      const target = tab.dataset.tab;
      const upload = $("#tab-upload");
      const paste = $("#tab-paste");
      if (upload) upload.classList.toggle("hidden", target !== "upload");
      if (paste) paste.classList.toggle("hidden", target !== "paste");
    });
  });

  // ---- File selection (development only) ----
  if (dropzone && fileInput) {
    if (browseBtn) {
      browseBtn.addEventListener("click", (e) => { e.stopPropagation(); fileInput.click(); });
    }
    dropzone.addEventListener("click", (e) => {
      if (e.target === browseBtn) return;
      fileInput.click();
    });
    fileInput.addEventListener("change", () => addFiles(fileInput.files));

    ["dragenter", "dragover"].forEach((evt) =>
      dropzone.addEventListener(evt, (e) => { e.preventDefault(); dropzone.classList.add("dragover"); })
    );
    ["dragleave", "drop"].forEach((evt) =>
      dropzone.addEventListener(evt, (e) => { e.preventDefault(); dropzone.classList.remove("dragover"); })
    );
    dropzone.addEventListener("drop", (e) => {
      if (e.dataTransfer && e.dataTransfer.files) addFiles(e.dataTransfer.files);
    });
  }

  function addFiles(fileObjs) {
    const existing = new Set(selectedFiles.map((f) => f.name + f.size));
    for (const f of fileObjs) {
      const id = f.name + f.size;
      if (!existing.has(id)) { selectedFiles.push(f); existing.add(id); }
    }
    renderFileList();
    if (fileInput) fileInput.value = "";
  }

  function renderFileList() {
    if (!fileList) return;
    fileList.innerHTML = "";
    selectedFiles.forEach((f, i) => {
      const li = document.createElement("li");
      li.className = "file-row";

      const name = document.createElement("span");
      name.className = "name";
      name.innerHTML = ICON_FILE + "<span></span>";
      name.querySelector("span").textContent = f.name;

      const remove = document.createElement("button");
      remove.className = "remove";
      remove.type = "button";
      remove.title = "Remove";
      remove.innerHTML = ICON_X;
      remove.addEventListener("click", () => { selectedFiles.splice(i, 1); renderFileList(); });

      li.append(name, remove);
      fileList.appendChild(li);
    });
  }

  // ---- Analyze ----
  analyzeBtn.addEventListener("click", analyze);

  async function analyze() {
    const code = codeInput.value.trim();
    if (selectedFiles.length === 0 && !code) {
      toast("Add files or paste code first.", true);
      return;
    }
    if (!serverHasKey && !storedKey()) {
      toast("Configure your Groq API key first.", true);
      if (apiKeyBtn) apiKeyBtn.click();
      return;
    }

    const form = new FormData();
    selectedFiles.forEach((f) => form.append("files", f, f.name));
    if (code) {
      form.append("code", code);
      form.append("filename", (snippetName && snippetName.value.trim()) || "snippet.py");
    }
    // The server ignores any client key in production; only sent in dev.
    if (!publicDemo && storedKey()) form.append("api_key", storedKey());

    setLoading(true);
    try {
      const res = await fetch("/api/analyze", { method: "POST", body: form });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Analysis failed.");
      reviews = data.reviews || {};
      setReport(data.report_markdown, data.report_filename);
      renderResults();
    } catch (err) {
      toast(err.message || "Something went wrong.", true);
      setLoading(false);
    }
  }

  function setLoading(on) {
    emptyState.classList.add("hidden");
    if (on) {
      const n = selectedFiles.length + (codeInput.value.trim() ? 1 : 0);
      loadingText.textContent = `Analyzing ${n} file${n === 1 ? "" : "s"}`;
      loading.classList.remove("hidden");
      markdownEl.classList.add("hidden");
      analyzeBtn.disabled = true;
    } else {
      loading.classList.add("hidden");
      analyzeBtn.disabled = false;
    }
  }

  // ---- Report download (built client-side from the in-memory markdown) ----
  function setReport(markdown, filename) {
    if (reportBlobUrl) { URL.revokeObjectURL(reportBlobUrl); reportBlobUrl = null; }
    if (!markdown) { downloadBtn.classList.add("hidden"); return; }
    const blob = new Blob([markdown], { type: "text/markdown;charset=utf-8" });
    reportBlobUrl = URL.createObjectURL(blob);
    downloadBtn.href = reportBlobUrl;
    downloadBtn.download = filename || "code_review_report.md";
    downloadBtn.classList.remove("hidden");
  }

  // ---- Render results ----
  function renderResults() {
    setLoading(false);
    resultTabs.innerHTML = "";
    const names = Object.keys(reviews);
    if (names.length === 0) { emptyState.classList.remove("hidden"); return; }

    names.forEach((name, idx) => {
      const tab = document.createElement("button");
      tab.className = "result-tab" + (idx === 0 ? " active" : "");
      const isError = (reviews[name] || "").startsWith("Error:");
      if (isError) tab.classList.add("error");
      tab.type = "button";
      tab.innerHTML = '<span class="tab-dot"></span><span></span>';
      tab.querySelector("span:last-child").textContent = name;
      tab.addEventListener("click", () => {
        document.querySelectorAll(".result-tab").forEach((t) => t.classList.remove("active"));
        tab.classList.add("active");
        showReview(name);
      });
      resultTabs.appendChild(tab);
    });

    showReview(names[0]);
  }

  function showReview(name) {
    const md = reviews[name] || "";
    markdownEl.innerHTML = window.marked ? marked.parse(md) : escapeHtml(md);
    if (window.hljs) {
      markdownEl.querySelectorAll("pre code").forEach((block) => {
        try { hljs.highlightElement(block); } catch (_) { /* ignore */ }
      });
    }
    markdownEl.classList.remove("hidden");
    emptyState.classList.add("hidden");
    resultBody.scrollTop = 0;
  }

  function escapeHtml(s) {
    return s.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
  }

  // ---- Clear ----
  clearBtn.addEventListener("click", () => {
    selectedFiles = [];
    reviews = {};
    renderFileList();
    codeInput.value = "";
    resultTabs.innerHTML = "";
    markdownEl.innerHTML = "";
    markdownEl.classList.add("hidden");
    setReport(null, null);
    emptyState.classList.remove("hidden");
  });

  // ---- Toast ----
  let toastEl;
  function toast(msg, isError = false) {
    if (!toastEl) {
      toastEl = document.createElement("div");
      toastEl.id = "toast";
      document.body.appendChild(toastEl);
    }
    toastEl.textContent = msg;
    toastEl.className = isError ? "error show" : "show";
    clearTimeout(toast._t);
    toast._t = setTimeout(() => toastEl.classList.remove("show"), 3000);
  }

  // ---- Init ----
  refreshBadge();
})();
