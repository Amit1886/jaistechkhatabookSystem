// sidebar.js
document.addEventListener("DOMContentLoaded", function () {

    const sidebar = document.getElementById("sidebar");
    const toggleBtn = document.getElementById("togglePin");

    if (!sidebar || !toggleBtn) return;

    const STORAGE_KEY = "kp_sidebar_collapsed";
    const mobileMql = window.matchMedia("(max-width: 768px)");
    const hoverCapableMql = window.matchMedia("(hover: hover) and (pointer: fine)");

    function setToggleIcon(isCollapsed) {
        const icon = toggleBtn.querySelector("i");
        if (!icon) return;
        icon.classList.toggle("bi-layout-sidebar-inset", !isCollapsed);
        icon.classList.toggle("bi-layout-sidebar-inset-reverse", isCollapsed);
    }

    function setCollapsed(isCollapsed, { persist = true } = {}) {
        sidebar.classList.toggle("collapsed", !!isCollapsed);
        sidebar.classList.remove("hover-open");
        document.body.classList.toggle("sidebar-collapsed", !!isCollapsed);
        document.body.classList.toggle("sidebar-expanded", !isCollapsed);
        toggleBtn.setAttribute("aria-expanded", String(!isCollapsed));
        setToggleIcon(!!isCollapsed);

        if (!persist) return;
        try {
            localStorage.setItem(STORAGE_KEY, isCollapsed ? "1" : "0");
        } catch (e) { }
    }

    function getStoredCollapsed() {
        try {
            return localStorage.getItem(STORAGE_KEY) === "1";
        } catch (e) {
            return false;
        }
    }

    function applyInitialState() {
        if (mobileMql.matches) {
            setCollapsed(true, { persist: false });
            return;
        }
        setCollapsed(getStoredCollapsed(), { persist: false });
    }

    applyInitialState();

    toggleBtn.addEventListener("click", function () {
        const nextCollapsed = !sidebar.classList.contains("collapsed");
        // On mobile we always default to collapsed, but still let users expand temporarily.
        setCollapsed(nextCollapsed, { persist: !mobileMql.matches });
    });

    /* ====
       HOVER OPEN WHEN COLLAPSED
    ===== */
    if (hoverCapableMql.matches) {
        sidebar.addEventListener("mouseenter", function () {
            if (mobileMql.matches) return;
            if (sidebar.classList.contains("collapsed")) {
                sidebar.classList.add("hover-open");
            }
        });

        sidebar.addEventListener("mouseleave", function () {
            sidebar.classList.remove("hover-open");
        });
    }

    // When switching between mobile/desktop widths, re-apply the correct default state.
    try {
        mobileMql.addEventListener("change", applyInitialState);
    } catch (e) {
        // Safari fallback not needed on this project, but keep safe.
        window.addEventListener("resize", applyInitialState);
    }

    /* ====
       SUBMENU TOGGLE
    ===== */
    document.querySelectorAll(".submenu-toggle").forEach(btn => {
        btn.addEventListener("click", function (e) {
            e.preventDefault();
            const parent = this.parentElement;
            if (!parent) return;
            parent.classList.toggle("open");
            try {
                this.setAttribute("aria-expanded", String(parent.classList.contains("open")));
            } catch (e) { }
        });
    });

});
