(function () {
  const stack = document.getElementById("ls-shortcut-stack");
  const openBtn = document.getElementById("ls-shortcut-picker-open");
  const closeBtn = document.getElementById("ls-shortcut-picker-close");
  const cancelBtn = document.getElementById("ls-shortcut-picker-cancel");
  const saveBtn = document.getElementById("ls-shortcut-picker-save");
  const modal = document.getElementById("ls-shortcut-modal");
  const pickerList = document.getElementById("ls-shortcut-picker-list");

  if (!stack || !modal || !pickerList) return;

  const configUrl = "/accounts/admin-shortcuts/config/";
  const saveUrl = "/accounts/admin-shortcuts/save/";
  const FIXED_COUNT = 8;

  let selected = [];
  let available = [];
  let draftKeys = [];

  function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(";").shift();
    return "";
  }

  async function saveSelection() {
    const formData = new FormData();
    selected.forEach((item) => formData.append("keys[]", item.key));

    const resp = await fetch(saveUrl, {
      method: "POST",
      headers: {
        "X-CSRFToken": getCookie("csrftoken"),
        "X-Requested-With": "XMLHttpRequest",
      },
      body: formData,
      credentials: "same-origin",
    });
    if (!resp.ok) throw new Error("save failed");
  }

  function byKey(key) {
    return available.find((x) => x.key === key);
  }

  function itemTemplate(item) {
    const a = document.createElement("a");
    a.className = "ls-shortcut-item";
    a.href = item.href;
    a.dataset.key = item.key;
    a.draggable = true;
    a.innerHTML =
      '<span class="ls-shortcut-item__left">' +
      '<span class="ls-shortcut-item__drag" title="拖拽排序">⋮⋮</span>' +
      '<span class="ls-shortcut-item__text">' +
      `<strong>${item.title}</strong>` +
      `<small>${item.desc}</small>` +
      "</span></span>" +
      '<span class="ls-shortcut-item__arrow">›</span>';

    a.addEventListener("dragstart", function (e) {
      e.dataTransfer.setData("text/plain", item.key);
      a.classList.add("is-dragging");
    });

    a.addEventListener("dragend", function () {
      a.classList.remove("is-dragging");
      stack.querySelectorAll(".is-drop-target").forEach((el) => el.classList.remove("is-drop-target"));
    });

    a.addEventListener("dragover", function (e) {
      e.preventDefault();
      a.classList.add("is-drop-target");
    });

    a.addEventListener("dragleave", function () {
      a.classList.remove("is-drop-target");
    });

    a.addEventListener("drop", async function (e) {
      e.preventDefault();
      a.classList.remove("is-drop-target");

      const fromKey = e.dataTransfer.getData("text/plain");
      const toKey = item.key;
      if (!fromKey || !toKey || fromKey === toKey) return;

      const fromIdx = selected.findIndex((x) => x.key === fromKey);
      const toIdx = selected.findIndex((x) => x.key === toKey);
      if (fromIdx < 0 || toIdx < 0) return;

      const moving = selected.splice(fromIdx, 1)[0];
      selected.splice(toIdx, 0, moving);
      render();

      try {
        await saveSelection();
      } catch (_) {}
    });

    return a;
  }

  function render() {
    stack.innerHTML = "";
    selected.slice(0, FIXED_COUNT).forEach((item) => stack.appendChild(itemTemplate(item)));
  }

  function openModal() {
    draftKeys = selected.map((x) => x.key);
    renderPicker();
    modal.classList.add("is-open");
    modal.setAttribute("aria-hidden", "false");
  }

  function closeModal() {
    modal.classList.remove("is-open");
    modal.setAttribute("aria-hidden", "true");
  }

  function renderPicker() {
    pickerList.innerHTML = "";
    const selectedSet = new Set(draftKeys);

    available.forEach((item) => {
      const row = document.createElement("label");
      row.className = "ls-picker-row";

      const input = document.createElement("input");
      input.type = "checkbox";
      input.checked = selectedSet.has(item.key);
      input.addEventListener("change", function () {
        if (input.checked) {
          if (draftKeys.length >= FIXED_COUNT) {
            input.checked = false;
            return;
          }
          draftKeys.push(item.key);
        } else {
          draftKeys = draftKeys.filter((k) => k !== item.key);
        }
        renderPicker();
      });

      const text = document.createElement("span");
      text.className = "ls-picker-row__text";
      text.innerHTML = `<strong>${item.title}</strong><small>${item.desc}</small>`;

      row.appendChild(input);
      row.appendChild(text);

      if (!input.checked && draftKeys.length >= FIXED_COUNT) {
        input.disabled = true;
      }
      pickerList.appendChild(row);
    });
  }

  async function commitDraft() {
    if (draftKeys.length !== FIXED_COUNT) return;
    const next = draftKeys.map((k) => byKey(k)).filter(Boolean);
    if (next.length !== FIXED_COUNT) return;
    selected = next;
    render();
    await saveSelection();
  }

  openBtn?.addEventListener("click", openModal);
  closeBtn?.addEventListener("click", closeModal);
  cancelBtn?.addEventListener("click", closeModal);
  modal.addEventListener("click", function (e) {
    if (e.target && e.target.dataset && e.target.dataset.close === "1") closeModal();
  });
  saveBtn?.addEventListener("click", async function () {
    try {
      await commitDraft();
      closeModal();
    } catch (_) {}
  });

  (async function init() {
    try {
      const resp = await fetch(configUrl, { credentials: "same-origin" });
      if (!resp.ok) return;
      const data = await resp.json();

      available = Array.isArray(data.available) ? data.available : [];
      selected = Array.isArray(data.selected) ? data.selected : [];

      const selectedKeys = new Set(selected.map((x) => x.key));
      const normalized = selected.filter((x) => x && x.key).slice(0, FIXED_COUNT);
      if (normalized.length < FIXED_COUNT) {
        for (const item of available) {
          if (normalized.length >= FIXED_COUNT) break;
          if (!selectedKeys.has(item.key)) {
            normalized.push(item);
            selectedKeys.add(item.key);
          }
        }
      }
      selected = normalized.slice(0, FIXED_COUNT);
      render();
    } catch (_) {}
  })();
})();
