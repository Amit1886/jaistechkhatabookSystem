/* Content Studio — Canva-like canvas editor engine (vanilla JS) */
(function () {
    "use strict";

    const cfg = window.STUDIO_CONFIG || {};
    const projectId = cfg.projectId;
    const csrfToken = cfg.csrfToken || "";
    const apiBase = "/api/v1/studio/";

    const stage = document.getElementById("stage");
    const stageContent = document.getElementById("elementStage");
    const uiLayer = document.getElementById("uiLayer");
    const canvasFrame = document.getElementById("canvasFrame");
    const zoomValue = document.getElementById("zoomValue");

    const el = (id) => document.getElementById(id);

    let scene = JSON.parse(document.getElementById("scene-data").textContent || "{}");
    let elements = scene.elements || [];
    let pages = scene.pages || [];
    let brandKit = scene.brand_kit || null;
    let config = scene.project || {};
    if (cfg.width) {
        config.width = cfg.width;
        config.height = cfg.height;
        config.background_color = cfg.background_color;
        config.id = projectId;
        config.title = cfg.title;
    }

    let selectedId = null;
    let history = [];
    let historyIndex = -1;
    let zoom = 1;
    let panX = 0, panY = 0;
    let activeTool = "select";
    let saveTimer = null;
    let saveState = "idle";

    const FONTS = JSON.parse(document.getElementById("fonts-data").textContent || "[]");
    const ICONS = JSON.parse(document.getElementById("icons-data").textContent || "[]");
    const TEMPLATES = JSON.parse(document.getElementById("templates-data").textContent || "[]");

    function guid() {
        return "e_" + Date.now() + "_" + Math.random().toString(36).slice(2, 8);
    }

    function setSize(w, h) {
        stage.style.width = w + "px";
        stage.style.height = h + "px";
    }
    setSize(config.width || 1080, config.height || 1080);

    function snapshot() {
        history = history.slice(0, historyIndex + 1);
        history.push(clone(elements, pages));
        historyIndex++;
        if (history.length > 50) {
            history.shift();
            historyIndex--;
        }
    }
    function clone(elems, pgs) {
        return {
            elements: JSON.parse(JSON.stringify(elems)),
            pages: JSON.parse(JSON.stringify(pgs)),
        };
    }
    function undo() {
        if (historyIndex <= 0) return;
        const cur = clone(elements, pages);
        history[historyIndex] = cur;
        const prev = history[historyIndex - 1];
        historyIndex--;
        elements = JSON.parse(JSON.stringify(prev.elements));
        pages = JSON.parse(JSON.stringify(prev.pages));
        selectedId = null;
        render();
    }
    function redo() {
        if (historyIndex >= history.length - 1) return;
        historyIndex++;
        const next = history[historyIndex];
        elements = JSON.parse(JSON.stringify(next.elements));
        pages = JSON.parse(JSON.stringify(next.pages));
        selectedId = null;
        render();
    }
    snapshot();

    function findBy(id) {
        return elements.find((e) => e.id === id);
    }
    function bringForward(id) {
        const e = findBy(id);
        if (!e) return;
        const maxZ = elements.reduce((m, x) => Math.max(m, x.z_index || 0), 0);
        e.z_index = maxZ + 1;
        render();
    }
    function sendBackward(id) {
        const e = findBy(id);
        if (!e) return;
        const minZ = elements.reduce((m, x) => Math.min(m, x.z_index || 0), 0);
        e.z_index = minZ - 1;
        render();
    }
    function duplicate(id) {
        const e = findBy(id);
        if (!e) return;
        snapshot();
        const copy = JSON.parse(JSON.stringify(e));
        copy.id = guid();
        copy.x = (e.x || 0) + 20;
        copy.y = (e.y || 0) + 20;
        copy.z_index = (e.z_index || 0) + 1;
        elements.push(copy);
        selectedId = copy.id;
        render();
    }
    function remove(id) {
        elements = elements.filter((e) => e.id !== id);
        selectedId = null;
    }
    function deleteSelected() {
        if (!selectedId) return;
        snapshot();
        remove(selectedId);
        render();
    }

    function clearWrappers() {
        stageContent.innerHTML = "";
        uiLayer.innerHTML = "";
    }
    function createWrapper(e) {
        const wrap = document.createElement("div");
        wrap.className = "element-wrapper";
        wrap.style.left = (e.x || 0) + "px";
        wrap.style.top = (e.y || 0) + "px";
        wrap.style.width = (e.width || 100) + "px";
        wrap.style.height = (e.height || 100) + "px";
        wrap.style.zIndex = (e.z_index || 0);
        wrap.dataset.id = e.id;

        const visual = document.createElement("div");
        visual.className = "element-visual";
        visual.style.width = (e.width || 100) + "px";
        visual.style.height = (e.height || 100) + "px";
        visual.style.opacity = String(e.opacity == null ? 1 : e.opacity);
        if (e.rotation) visual.style.transform = "rotate(" + e.rotation + "deg)";
        visual.style.transformOrigin = "0 0";

        renderVisual(visual, e);
        wrap.appendChild(visual);

        if (selectedId === e.id) wrap.classList.add("selected");

        wrap.addEventListener("mousedown", (ev) => {
            ev.stopPropagation();
            selectElement(e.id, ev);
        });
        return wrap;
    }
    function renderVisual(visual, e) {
        const type = e.element_type || e.type || "text";
        const style = e.style || {};
        visual.innerHTML = "";
        visual.classList.remove("text-el", "shape-el", "icon-el");

        if (type === "text") {
            const t = document.createElement("div");
            t.className = "text-el";
            t.style.fontFamily = style.font_family || configBrandFont() || "Arial";
            const fs = style.font_size || 32;
            t.style.fontSize = fs + "px";
            t.style.color = style.color || "#111827";
            t.style.fontWeight = style.font_weight || "normal";
            t.style.textAlign = style.text_align || "center";
            if (e.content) t.textContent = e.content;
            else t.textContent = "Click to edit text";
            visual.appendChild(t);
        } else if (type === "image" || type === "sticker") {
            const img = document.createElement("img");
            img.className = "el-img";
            img.alt = "image";
            const src = e.content || (style && style.url) || "";
            if (src) img.src = src;
            else img.src = "https://via.placeholder.com/150?text=Image";
            visual.appendChild(img);
            visual.classList.add("icon-el");
        } else if (type === "icon") {
            const span = document.createElement("span");
            span.className = "icon-el";
            const svg = findIcon(e.content || style && style.icon_name);
            span.innerHTML = svg || '<i class="bi bi-star"></i>';
            visual.appendChild(span);
        } else if (type === "shape") {
            const s = document.createElement("div");
            s.className = "shape-el";
            const kind = style.shape || "rectangle";
            if (kind === "circle") {
                s.style.borderRadius = "50%";
            } else {
                s.style.borderRadius = style.border_radius ? style.border_radius + "%" : "0";
            }
            s.style.background = style.fill || configPrimary() || "#000000";
            if (style.stroke) {
                s.style.border = (style.stroke_width || 2) + "px solid " + style.stroke;
            }
            visual.appendChild(s);
        }
        const typeClass = type === "text" ? "text-el" : (type === "shape" ? "shape-el" : "icon-el");
        visual.classList.add(typeClass);
    }
    function configBrandFont() {
        return brandKit && brandKit.font_family;
    }
    function configPrimary() {
        return brandKit && brandKit.primary_color;
    }
    function findIcon(name) {
        if (!name) return null;
        const icon = ICONS.find((i) => i.name === name);
        if (icon) return icon.svg_content;
        if (name.indexOf("<svg") === 0) return name;
        return null;
    }

    function render() {
        clearWrappers();
        const sorted = [...elements].sort((a, b) => (a.z_index || 0) - (b.z_index || 0));
        sorted.forEach((e) => {
            stageContent.appendChild(createWrapper(e));
        });
        renderHandles();
        updateZoomLabel();
        bindMove();
    }
    function applyZoomPan() {
        stage.style.transform = "translate(" + panX + "px," + panY + "px) scale(" + zoom + ")";
    }

    function renderHandles() {
        if (!selectedId) return;
        const e = findBy(selectedId);
        if (!e) return;
        const wrap = stageContent.querySelector('[data-id="' + e.id + '"]');
        if (!wrap) return;
        const visual = wrap.querySelector(".element-visual");
        const rect = visual.getBoundingClientRect();
        const frame = canvasFrame.getBoundingClientRect();
        const base = {
            left: rect.left - frame.left + canvasFrame.scrollLeft,
            top: rect.top - frame.top + canvasFrame.scrollTop,
            w: rect.width,
            h: rect.height,
            cx: rect.left - frame.left + canvasFrame.scrollLeft + rect.width / 2,
            cy: rect.top - frame.top + canvasFrame.scrollTop + rect.height / 2,
        };
        const hs = 8;
        const positions = {
            nw: [base.left - hs / 2, base.top - hs / 2],
            n: [base.cx - hs / 2, base.top - hs / 2],
            ne: [base.left + base.w - hs / 2, base.top - hs / 2],
            w: [base.left - hs / 2, base.cy - hs / 2],
            e: [base.left + base.w - hs / 2, base.cy - hs / 2],
            sw: [base.left - hs / 2, base.top + base.h - hs / 2],
            s: [base.cx - hs / 2, base.top + base.h - hs / 2],
            se: [base.left + base.w - hs / 2, base.top + base.h - hs / 2],
        };
        ["nw", "n", "ne", "w", "e", "sw", "s", "se"].forEach((h) => {
            const hk = document.createElement("div");
            hk.className = "handle h-" + h;
            hk.dataset.handle = h;
            hk.style.left = positions[h][0] + "px";
            hk.style.top = positions[h][1] + "px";
            uiLayer.appendChild(hk);
        });
        const rh = document.createElement("div");
        rh.className = "handle-rotate";
        rh.dataset.handle = "rotate";
        rh.style.left = base.cx + "px";
        rh.style.top = (base.top - 24) + "px";
        uiLayer.appendChild(rh);
    }
    let dragState = null;
    function selectElement(id, mouseEvent) {
        const validTools = ["select", "text", "shape", "icon"];
        if (!validTools.includes(activeTool)) return;
        if (mouseEvent && mouseEvent.shiftKey) {
            mouseEvent.stopPropagation();
            if (selectedId !== id) selectedId = id;
        } else if (selectedId !== id) {
            selectedId = id;
        }
        render();
        updateProperties();
        bindHandles();
    }

    function bindHandles() {
        uiLayer.querySelectorAll(".handle").forEach((h) => {
            h.onmousedown = (ev) => startResize(ev, h.dataset.handle);
        });
        const rh = uiLayer.querySelector(".handle-rotate");
        if (rh) rh.onmousedown = (ev) => startRotate(ev);
    }
    function startResize(ev, handle) {
        ev.preventDefault();
        ev.stopPropagation();
        const e = findBy(selectedId);
        if (!e) return;
        const rect = canvasFrame.getBoundingClientRect();
        const origin = { x: ev.clientX - rect.left + canvasFrame.scrollLeft, y: ev.clientY - rect.top + canvasFrame.scrollTop };
        const start = {
            x: e.x || 0, y: e.y || 0, w: e.width || 100, h: e.height || 100,
            origin: origin,
        };
        function move(moveEv) {
            const cur = {
                x: moveEv.clientX - rect.left + canvasFrame.scrollLeft,
                y: moveEv.clientY - rect.top + canvasFrame.scrollTop,
            };
            const dx = (cur.x - origin.x) / zoom;
            const dy = (cur.y - origin.y) / zoom;
            let nx = start.x, ny = start.y, nw = start.w, nh = start.h;
            const lock = moveEv.shiftKey;
            if (handle.includes("e")) {
                nw = Math.max(20, start.w + dx);
                if (lock) nh = nw * (start.h / start.w);
            }
            if (handle.includes("s")) {
                nh = Math.max(20, start.h + dy);
                if (lock) nw = nh * (start.w / start.h);
            }
            if (handle.includes("w")) {
                nw = Math.max(20, start.w - dx);
                nx = start.x + (start.w - nw);
            }
            if (handle.includes("n")) {
                nh = Math.max(20, start.h - dy);
                ny = start.y + (start.h - nh);
            }
            e.x = Math.round(nx); e.y = Math.round(ny);
            e.width = Math.round(nw); e.height = Math.round(nh);
            render();
        }
        function up() {
            document.removeEventListener("mousemove", move);
            document.removeEventListener("mouseup", up);
            snapshot();
        }
        document.addEventListener("mousemove", move);
        document.addEventListener("mouseup", up);
    }
    function startRotate(ev) {
        ev.preventDefault();
        ev.stopPropagation();
        const e = findBy(selectedId);
        if (!e) return;
        const rect = canvasFrame.getBoundingClientRect();
        const centerX = (e.x || 0) + (e.width || 100) / 2;
        const centerY = (e.y || 0) + (e.height || 100) / 2;
        function move(moveEv) {
            const cx = moveEv.clientX - rect.left + canvasFrame.scrollLeft;
            const cy = moveEv.clientY - rect.top + canvasFrame.scrollTop;
            const rad = Math.atan2((cy - centerY * zoom), (cx - centerX * zoom));
            let deg = (rad * 180 / Math.PI);
            e.rotation = Math.round(((deg % 360) + 360) % 360);
            render();
        }
        function up() {
            document.removeEventListener("mousemove", move);
            document.removeEventListener("mouseup", up);
            snapshot();
        }
        document.addEventListener("mousemove", move);
        document.addEventListener("mouseup", up);
    }
    function startMove(ev) {
        ev.preventDefault();
        ev.stopPropagation();
        const e = findBy(selectedId);
        if (!e) return;
        const rect = canvasFrame.getBoundingClientRect();
        const origin = { x: ev.clientX - rect.left + canvasFrame.scrollLeft, y: ev.clientY - rect.top + canvasFrame.scrollTop };
        function move(moveEv) {
            const cur = {
                x: moveEv.clientX - rect.left + canvasFrame.scrollLeft,
                y: moveEv.clientY - rect.top + canvasFrame.scrollTop,
            };
            e.x = Math.round((e.x || 0) + (cur.x - origin.x) / zoom);
            e.y = Math.round((e.y || 0) + (cur.y - origin.y) / zoom);
            origin.x = cur.x;
            origin.y = cur.y;
            render();
        }
        function up() {
            document.removeEventListener("mousemove", move);
            document.removeEventListener("mouseup", up);
            snapshot();
        }
        document.addEventListener("mousemove", move);
        document.addEventListener("mouseup", up);
    }
    function bindMove() {
        stageContent.querySelectorAll(".element-wrapper").forEach((wrap) => {
            wrap.onmousedown = (ev) => {
                if (activeTool === "select") startMove(ev);
            };
        });
    }

    function bindToolbox() {
        document.querySelectorAll("[data-tool]").forEach((btn) => {
            btn.addEventListener("click", () => {
                document.querySelectorAll("[data-tool]").forEach((b) => b.classList.remove("active"));
                btn.classList.add("active");
                activeTool = btn.dataset.tool;
                if (activeTool === "select") {
                    selectedId = null;
                    render();
                    updateProperties();
                }
            });
        });
    }

    function addElement(type, defaults) {
        const e = Object.assign({
            id: guid(),
            element_type: type,
            x: 40, y: 40,
            width: 200, height: 100,
            rotation: 0, opacity: 1,
            content: "", style: {}, z_index: 0,
        }, defaults);
        if (type === "text") {
            e.content = "Add a heading";
            e.style = { color: "#111827", font_size: 32, text_align: "center", font_weight: "normal" };
            e.z_index = nextZ();
        } else if (type === "shape") {
            e.style = { shape: "rectangle", fill: configPrimary() || "#000000" };
            e.z_index = nextZ();
            e.width = 160; e.height = 100;
        } else if (type === "icon") {
            const icon = ICONS[0];
            e.content = icon ? icon.name : "star";
            e.z_index = nextZ();
            e.width = 80; e.height = 80;
        }
        snapshot();
        elements.push(e);
        selectedId = e.id;
        render();
        updateProperties();
    }
    function nextZ() {
        return elements.reduce((m, x) => Math.max(m, x.z_index || 0), 0) + 1;
    }

    const propBox = document.getElementById("rightPanelContent");
    function updateProperties() {
        if (!propBox) return;
        const e = selectedId ? findBy(selectedId) : config;
        let html = "";
        if (selectedId && e) {
            const type = e.element_type || e.type || "text";
            html += panelHeading(type, e);
            html += propNumber("X", e.x, (v) => { e.x = +v; render(); });
            html += propNumber("Y", e.y, (v) => { e.y = +v; render(); });
            html += propNumber("Width", e.width, (v) => { e.width = +v; render(); });
            html += propNumber("Height", e.height, (v) => { e.height = +v; render(); });
            html += propNumber("Rotation", e.rotation || 0, (v) => { e.rotation = +v; render(); });
            html += propRange("Opacity", e.opacity == null ? 1 : e.opacity, (v) => { e.opacity = +v; render(); });
            if (type === "text") {
                html += propText("Text", e.content || "", (v) => { e.content = v; render(); });
                html += propColor("Color", e.style.color || "#111827", (v) => { e.style.color = v; render(); });
                html += propNumber("Size", e.style.font_size || 32, (v) => { e.style.font_size = +v; render(); });
                html += propText("Font", e.style.font_family || "", (v) => { e.style.font_family = v; render(); });
            } else if (type === "shape") {
                html += propColor("Fill", e.style.fill || configPrimary() || "#000000", (v) => { e.style.fill = v; render(); });
                html += propText("Shape", e.style.shape || "rectangle", (v) => { e.style.shape = v; render(); });
            } else if (type === "image" || type === "sticker") {
                html += propText("Image URL", e.content || "", (v) => { e.content = v; render(); });
            } else if (type === "icon") {
                html += propText("Icon", e.content || "", (v) => { e.content = v; render(); });
            }
            html += propCheckbox("Lock aspect", false, null);
        } else {
            html += panelHeading("Project", config);
            html += propText("Title", config.title || "", (v) => { config.title = v; el("editorTitle").textContent = v || cfg.title; });
        }
        propBox.innerHTML = html;
    }
    function panelHeading(type, e) {
        const t = e.element_type || e.type || "element";
        return '<h6 class="mb-2">' + type.toUpperCase() + " " + t + ' <span class="float-end text-muted small">ID: ' + (e.id || "—") + '</span></h6>';
    }
    function propText(label, value, onChange) {
        return propWrap(label, '<input type="text" class="form-control form-control-sm" value="' + esc(value) + '" onchange="window.__studioFn.call(null,\'' + wrapFn(onChange) + '\',this.value)">');
    }
    function propNumber(label, value, onChange) {
        return propWrap(label, '<input type="number" class="form-control form-control-sm" value="' + (value == null ? 0 : value) + '" onchange="window.__studioFn.call(null,\'' + wrapFn(onChange) + '\',this.value)">');
    }
    function propRange(label, value, onChange) {
        return propWrap(label, '<input type="range" class="form-range" min="0" max="1" step="0.05" value="' + (value == null ? 1 : value) + '" onchange="window.__studioFn.call(null,\'' + wrapFn(onChange) + '\',this.value)">');
    }
    function propColor(label, value, onChange) {
        return propWrap(label, '<input type="color" class="form-control form-control-color form-control-sm" value="' + esc(value) + '" onchange="window.__studioFn.call(null,\'' + wrapFn(onChange) + '\',this.value)">');
    }
    function propCheckbox(label, value, onChange) {
        return propWrap(label, '<label class="form-check"><input type="checkbox" class="form-check-input" ' + (value ? "checked" : "") + '></label>');
    }
    function propWrap(label, input) {
        return '<div class="prop-row"><label class="form-label">' + label + "</label>" + input + "</div>";
    }
    let __fnId = 0;
    const __fns = {};
    function wrapFn(fn) {
        const id = "__p" + (++__fnId);
        __fns[id] = fn;
        return id;
    }
    window.__studioFn = function (id, val) { __fns[id](val); };
    function esc(s) {
        return String(s == null ? "" : s).replace(/['"&<>]/g, (c) => ({ "'": "&#39;", '"': "&#34;", "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
    }

    function updateZoomLabel() { if (zoomValue) zoomValue.textContent = Math.round(zoom * 100) + "%"; }
    function setZoom(z) { zoom = Math.max(0.2, Math.min(3, z)); applyZoomPan(); updateZoomLabel(); }
    function zoomFit() {
        const area = canvasFrame;
        const maxW = area.clientWidth;
        const maxH = area.clientHeight - 44;
        const s = config.width || 1080;
        const t = config.height || 1080;
        setZoom(Math.min(maxW / s, maxH / t));
        panX = 0; panY = 0;
        applyZoomPan();
    }

    function setSaveState(state) {
        saveState = state;
        const badge = el("saveStatus");
        if (!badge) return;
        const labels = { idle: "Saved", saving: "Saving...", saved: "Saved", error: "Error" };
        const colors = { idle: "bg-success", saving: "bg-info", saved: "bg-success", error: "bg-danger" };
        badge.textContent = labels[state] || "Saved";
        badge.className = "badge " + (colors[state] || "bg-success");
    }
    function save() {
        setSaveState("saving");
        const payload = {
            metadata: { width: config.width, height: config.height, background_color: config.background_color },
            elements: elements.map((e) => ({
                element_type: e.element_type, type: e.element_type,
                x: e.x, y: e.y, width: e.width, height: e.height,
                rotation: e.rotation, opacity: e.opacity,
                content: e.content, style: e.style, z_index: e.z_index,
            })),
            pages: pages,
            width: config.width,
            height: config.height,
            background_color: config.background_color,
        };
        fetch(apiBase + "projects/" + projectId + "/save-design/", {
            method: "POST",
            headers: { "X-CSRFToken": csrfToken, "Content-Type": "application/json" },
            credentials: "same-origin",
            body: JSON.stringify(payload),
        }).then((r) => {
            if (!r.ok) throw new Error(r.statusText);
            setSaveState("saved");
            setTimeout(() => setSaveState("idle"), 2000);
        }).catch(() => setSaveState("error"));
    }
    function scheduleSave() {
        if (saveTimer) clearTimeout(saveTimer);
        saveTimer = setTimeout(save, 1500);
    }
    function exportJson() {
        const data = {
            title: config.title,
            width: config.width,
            height: config.height,
            background_color: config.background_color,
            brand_kit: brandKit,
            elements: elements,
            pages: pages,
        };
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = (config.title || "design") + ".json";
        a.click();
        URL.revokeObjectURL(url);
    }
    function exportPng() {
        const w = config.width || 1080, h = config.height || 1080;
        const canvas = document.createElement("canvas");
        canvas.width = w;
        canvas.height = h;
        const ctx = canvas.getContext("2d");
        ctx.fillStyle = config.background_color || "#ffffff";
        ctx.fillRect(0, 0, w, h);
        const sorted = [...elements].sort((a, b) => (a.z_index || 0) - (b.z_index || 0));
        const pendingImages = [];
        sorted.forEach((e) => {
            const type = e.element_type;
            ctx.save();
            ctx.translate(e.x || 0, e.y || 0);
            ctx.globalAlpha = e.opacity == null ? 1 : e.opacity;
            if (e.rotation) ctx.rotate((e.rotation * Math.PI) / 180);
            const style = e.style || {};
            if (type === "shape") {
                ctx.fillStyle = style.fill || "#000000";
                if ((style.shape || "rectangle") === "circle") {
                    ctx.beginPath();
                    ctx.arc((e.width || 100) / 2, (e.height || 100) / 2, Math.min(e.width, e.height) / 2, 0, Math.PI * 2);
                    ctx.fill();
                } else {
                    ctx.fillRect(0, 0, e.width || 100, e.height || 100);
                }
            } else if (type === "text") {
                ctx.fillStyle = style.color || "#111827";
                const fs = style.font_size || 32;
                const fam = style.font_family || "Arial";
                ctx.textAlign = style.text_align || "center";
                ctx.textBaseline = "middle";
                ctx.font = (style.font_weight || "normal") + " " + fs + "px " + fam;
                const lines = (e.content || "").split("\n");
                const lineHeight = fs * 1.2;
                lines.forEach((ln, i) => {
                    ctx.fillText(ln, (e.width || 100) / 2, (e.height || 100) / 2 + i * lineHeight - (lines.length - 1) * lineHeight / 2);
                });
            } else if (type === "image" || type === "sticker") {
                const src = e.content || (style && style.url) || "";
                if (src) pendingImages.push({ ctx, src, x: 0, y: 0, w: e.width || 100, h: e.height || 100 });
            }
            ctx.restore();
        });
        function finishDraw() {
            pendingImages.forEach((pi) => {
                try {
                    pi.ctx.save();
                    pi.ctx.globalAlpha = 1;
                    pi.ctx.drawImage(pi.img, pi.x, pi.y, pi.w, pi.h);
                    pi.ctx.restore();
                } catch (err) { /* img not parsed */ }
            });
            const url = canvas.toDataURL("image/png");
            const a = document.createElement("a");
            a.href = url;
            a.download = (config.title || "design") + ".png";
            a.click();
        }
        if (pendingImages.length === 0) { finishDraw(); return; }
        let done = 0;
        pendingImages.forEach((pi) => {
            const img = new Image();
            img.onload = () => { pi.img = img; if (++done === pendingImages.length) finishDraw(); };
            img.onerror = () => { if (++done === pendingImages.length) finishDraw(); };
            img.crossOrigin = "anonymous";
            img.src = pi.src;
        });
    }

    function bindEvents() {
        const area = document.getElementById("editorCanvasArea");
        area.addEventListener("mousedown", (ev) => {
            if (["select", "text", "shape", "icon"].includes(activeTool)) {
                if (ev.target === area || ev.target === canvasFrame || ev.target === stageContent) {
                    selectedId = null;
                    render();
                    updateProperties();
                }
            }
        });
        bindToolbox();

        el("undoBtn").addEventListener("click", undo);
        el("redoBtn").addEventListener("click", redo);
        el("deleteBtn").addEventListener("click", deleteSelected);
        el("saveBtn").addEventListener("click", save);
        el("exportJsonBtn").addEventListener("click", exportJson);
        el("exportPngBtn").addEventListener("click", exportPng);
        el("zoomInBtn").addEventListener("click", () => setZoom(zoom + 0.1));
        el("zoomOutBtn").addEventListener("click", () => setZoom(zoom - 0.1));
        el("zoomFitBtn").addEventListener("click", zoomFit);
        el("zoomResetBtn").addEventListener("click", () => { setZoom(1); panX = 0; panY = 0; applyZoomPan(); });

        document.getElementById("addTextBtn").addEventListener("click", () => { activeTool = "text"; addElement("text"); });
        document.getElementById("addShapeBtn").addEventListener("click", () => { activeTool = "shape"; addElement("shape"); });
        document.getElementById("addIconBtn").addEventListener("click", () => { activeTool = "icon"; addElement("icon"); });
    }

    function buildLeftPanel() {
        const box = document.getElementById("leftPanelContent");
        if (!box) return;
        box.innerHTML =
            '<h6>Elements</h6>' +
            '<div class="d-grid gap-2">' +
            tb("Text", "addTextBtn", "bi-type") +
            tb("Shape", "addShapeBtn", "bi-square") +
            tb("Icon", "addIconBtn", "bi-star") +
            tb("Upload image", "addImageBtn", "bi-image") +
            "</div>";
    }

    function tb(label, id, icon) {
        return '<button class="toolbox-item" id="' + id + '"><i class="bi ' + icon + '"></i> ' + label + "</button>";
    }
    function init() {
        setSaveState("idle");
        buildLeftPanel();
        el("zoomValue").textContent = "100%";
        applyZoomPan();
        render();
        updateProperties();
        bindEvents();
        document.addEventListener("keydown", (ev) => {
            if (ev.target.tagName === "INPUT" || ev.target.tagName === "TEXTAREA") return;
            if ((ev.ctrlKey || ev.metaKey) && ev.key === "s") { ev.preventDefault(); save(); }
            if ((ev.ctrlKey || ev.metaKey) && ev.key === "z") { ev.preventDefault(); undo(); }
            if ((ev.ctrlKey || ev.metaKey) && ev.key === "Z") { ev.preventDefault(); redo(); }
            if (ev.key === "Delete" || ev.key === "Backspace") { ev.preventDefault(); deleteSelected(); }
            if (ev.key === "ArrowUp") { moveSel(0, -1); }
            if (ev.key === "ArrowDown") { moveSel(0, 1); }
            if (ev.key === "ArrowLeft") { moveSel(-1, 0); }
            if (ev.key === "ArrowRight") { moveSel(1, 0); }
        });
    }
    function moveSel(dx, dy) {
        if (!selectedId) return;
        const e = findBy(selectedId);
        if (!e) return;
        e.x = (e.x || 0) + dx;
        e.y = (e.y || 0) + dy;
        snapshot();
        render();
        updateProperties();
    }

    window.__addElement = addElement;

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
