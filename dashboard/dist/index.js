/**
 * WikiMe — Hermes Dashboard Plugin
 *
 * Three-pane knowledge wiki: navigator, workspace, and context panel.
 * Uses window.__HERMES_PLUGIN_SDK__ for React + shadcn components.
 * Fetches vault data from /api/plugins/wikime/
 */
(function () {
  "use strict";

  const SDK = window.__HERMES_PLUGIN_SDK__;
  if (!SDK) return;

  const { React } = SDK;
  const h = React.createElement;
  const { useState, useEffect, useRef } = SDK.hooks;

  // ---------------------------------------------------------------------------
  // API helpers
  // ---------------------------------------------------------------------------

  const API = "/api/plugins/wikime";

  async function fetchJSON(url) {
    const token = window.__HERMES_SESSION_TOKEN__ || "";
    const headers = {};
    if (token) {
      headers["X-Hermes-Session-Token"] = token;
      headers["Authorization"] = "Bearer " + token;
    }
    const res = await fetch(url, { headers });
    if (!res.ok) throw new Error("HTTP " + res.status);
    return res.json();
  }

  // ---------------------------------------------------------------------------
  // Minimal markdown renderer (no deps)
  // ---------------------------------------------------------------------------

  function renderMarkdown(md) {
    if (!md) return "";
    var html = md
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
    html = html.replace(/```(\w*)\n([\s\S]*?)```/g, "<pre><code>$2</code></pre>");
    html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
    html = html.replace(/^### (.+)$/gm, "<h3>$1</h3>");
    html = html.replace(/^## (.+)$/gm, "<h2>$1</h2>");
    html = html.replace(/^# (.+)$/gm, "<h1>$1</h1>");
    html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
    html = html.replace(/\*(.+?)\*/g, "<em>$1</em>");
    html = html.replace(/^- (.+)$/gm, "<li>$1</li>");
    html = html.replace(/^---$/gm, "<hr>");
    html = html.replace(/\n\n/g, "</p><p>");
    html = html.replace(/\n/g, "<br>");
    return "<p>" + html + "</p>";
  }

  // ---------------------------------------------------------------------------
  // Graph canvas
  // ---------------------------------------------------------------------------

  function GraphCanvas(props) {
    var pages = props.pages;
    var activePage = props.activePage;
    var onSelect = props.onSelect;
    var canvasRef = useRef(null);

    useEffect(function() {
      var canvas = canvasRef.current;
      if (!canvas || !pages.length) return;
      var ctx = canvas.getContext("2d");
      var W = canvas.width = canvas.offsetWidth;
      var H = canvas.height = canvas.offsetHeight;
      ctx.clearRect(0, 0, W, H);
      var nodes = pages.map(function(p, i) {
        var angle = (2 * Math.PI * i) / pages.length - Math.PI / 2;
        var r = Math.min(W, H) * 0.32;
        return {
          x: W / 2 + r * Math.cos(angle),
          y: H / 2 + r * Math.sin(angle),
          label: p.title.length > 10 ? p.title.slice(0, 10) + "…" : p.title,
          active: p.title === activePage,
          title: p.title,
        };
      });
      ctx.strokeStyle = "#30363d";
      ctx.lineWidth = 1;
      for (var i = 0; i < nodes.length; i++) {
        for (var j = i + 1; j < nodes.length; j++) {
          ctx.beginPath();
          ctx.moveTo(nodes[i].x, nodes[i].y);
          ctx.lineTo(nodes[j].x, nodes[j].y);
          ctx.stroke();
        }
      }
      nodes.forEach(function(n) {
        ctx.fillStyle = n.active ? "#58a6ff" : "#238636";
        ctx.beginPath();
        ctx.arc(n.x, n.y, n.active ? 8 : 6, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = "#c9d1d9";
        ctx.font = "9px system-ui, sans-serif";
        ctx.textAlign = "center";
        ctx.fillText(n.label, n.x, n.y + 18);
      });
      canvas._nodes = nodes;
    }, [pages, activePage]);

    return h("canvas", {
      ref: canvasRef,
      style: {
        width: "100%", height: "160px", background: "#0d1117",
        borderRadius: "8px", border: "1px solid #30363d", cursor: "pointer",
      },
      onClick: function(e) {
        var canvas = canvasRef.current;
        if (!canvas || !canvas._nodes) return;
        var rect = canvas.getBoundingClientRect();
        var x = e.clientX - rect.left;
        var y = e.clientY - rect.top;
        canvas._nodes.forEach(function(n) {
          if (Math.abs(x - n.x) < 15 && Math.abs(y - n.y) < 15) {
            onSelect(n.title);
          }
        });
      },
    });
  }

  // ---------------------------------------------------------------------------
  // Main WikiMe Page Component
  // ---------------------------------------------------------------------------

  function WikiMePage() {
    var _useState = useState([]);
    var pages = _useState[0], setPages = _useState[1];
    var _useState2 = useState(null);
    var activePage = _useState2[0], setActivePage = _useState2[1];
    var _useState3 = useState(null);
    var pageContent = _useState3[0], setPageContent = _useState3[1];
    var _useState4 = useState({ pages: 0, total_revisions: 0 });
    var stats = _useState4[0], setStats = _useState4[1];
    var _useState5 = useState("");
    var search = _useState5[0], setSearch = _useState5[1];
    var _useState6 = useState(true);
    var loading = _useState6[0], setLoading = _useState6[1];
    var _useState7 = useState(null);
    var error = _useState7[0], setError = _useState7[1];

    useEffect(function() {
      loadPages();
      loadStats();
    }, []);

    function loadPages() {
      setLoading(true);
      fetchJSON(API + "/pages")
        .then(function(data) { setPages(data.pages || []); setError(null); })
        .catch(function(e) { setError(e.message); })
        .finally(function() { setLoading(false); });
    }

    function loadStats() {
      fetchJSON(API + "/stats")
        .then(function(data) { setStats(data); })
        .catch(function() {});
    }

    function openPage(title) {
      setActivePage(title);
      fetchJSON(API + "/page?title=" + encodeURIComponent(title))
        .then(function(data) { setPageContent(data.markdown); })
        .catch(function(e) {
          setPageContent("# " + title + "\n\nCould not load: " + e.message);
        });
    }

    var filteredPages = search
      ? pages.filter(function(p) { return p.title.toLowerCase().indexOf(search.toLowerCase()) !== -1; })
      : pages;

    var categories = {};
    filteredPages.forEach(function(p) {
      var cat = p.title.indexOf("-") !== -1 ? p.title.split("-")[0] : "General";
      if (!categories[cat]) categories[cat] = [];
      categories[cat].push(p);
    });

    // ---- Styles (plain objects, no TypeScript) ----
    var S = {
      container: { display: "flex", height: "100%", background: "#0d1117", color: "#c9d1d9", fontFamily: "system-ui, -apple-system, sans-serif", overflow: "hidden" },
      nav: { width: "240px", minWidth: "180px", borderRight: "1px solid #30363d", background: "#161b22", display: "flex", flexDirection: "column", overflow: "hidden" },
      navHeader: { padding: "14px", borderBottom: "1px solid #30363d" },
      search: { width: "100%", padding: "6px 10px", background: "#0d1117", border: "1px solid #30363d", borderRadius: "6px", color: "#c9d1d9", fontSize: "0.85em", outline: "none" },
      navList: { flex: 1, overflowY: "auto", paddingBottom: "12px" },
      catTitle: { padding: "10px 14px 2px", fontSize: "0.65em", textTransform: "uppercase", color: "#8b949e", letterSpacing: "0.06em" },
      navItem: function(active) { return { padding: "5px 14px", cursor: "pointer", fontSize: "0.85em", color: active ? "#58a6ff" : "#c9d1d9", background: active ? "#1f2937" : "transparent", borderRadius: "4px", margin: "1px 6px", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }; },
      main: { flex: 1, overflowY: "auto", padding: "24px 32px", background: "#0d1117" },
      context: { width: "260px", minWidth: "200px", borderLeft: "1px solid #30363d", background: "#161b22", padding: "14px", display: "flex", flexDirection: "column", gap: "16px", overflowY: "auto" },
      sectionTitle: { fontSize: "0.75em", color: "#8b949e", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "8px" },
      statRow: { display: "flex", justifyContent: "space-between", padding: "3px 0", fontSize: "0.82em" },
      welcome: { display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: "100%", color: "#8b949e", textAlign: "center", padding: "40px" },
    };

    return h("div", { style: S.container },
      // Pane 1: Navigator
      h("div", { style: S.nav },
        h("div", { style: S.navHeader },
          h("div", { style: { fontSize: "0.95em", fontWeight: 600, marginBottom: "8px" } }, "🧠 WikiMe"),
          h("input", { style: S.search, placeholder: "🔍 Search pages...", value: search, onChange: function(e) { setSearch(e.target.value); } })
        ),
        h("div", { style: S.navList },
          loading
            ? h("div", { style: { padding: "14px", color: "#8b949e", fontSize: "0.82em" } }, "Loading…")
            : error
            ? h("div", { style: { padding: "14px", color: "#f85149", fontSize: "0.82em" } }, "⚠️ " + error)
            : pages.length === 0
            ? h("div", { style: { padding: "14px", color: "#8b949e", fontSize: "0.82em" } }, "No pages yet. Run the bulk loader!")
            : Object.keys(categories).map(function(cat) {
                return h("div", { key: cat },
                  h("div", { style: S.catTitle }, cat),
                  categories[cat].map(function(p) {
                    return h("div", { key: p.title, style: S.navItem(p.title === activePage), onClick: function() { openPage(p.title); } },
                      "📄 " + p.title);
                  })
                );
              })
        )
      ),
      // Pane 2: Workspace
      h("div", { style: S.main },
        pageContent
          ? h("div", { dangerouslySetInnerHTML: { __html: renderMarkdown(pageContent) }, style: { lineHeight: 1.6 } })
          : h("div", { style: S.welcome },
              h("div", { style: { fontSize: "1.3em", marginBottom: "10px", color: "#c9d1d9" } }, "🧠 WikiMe"),
              h("div", { style: { maxWidth: "380px" } },
                "Your personal knowledge wiki. Pages are auto-generated from conversations. Select a page from the sidebar to view its active configuration and evolution history."
              )
            )
      ),
      // Pane 3: Context Panel
      h("div", { style: S.context },
        h("div", null,
          h("div", { style: S.sectionTitle }, "🗺️ Knowledge Graph"),
          h(GraphCanvas, { pages: pages, activePage: activePage, onSelect: openPage })
        ),
        h("div", null,
          h("div", { style: S.sectionTitle }, "📊 Stats"),
          h("div", { style: S.statRow },
            h("span", { style: { color: "#8b949e" } }, "Pages"),
            h("span", { style: { fontWeight: 600 } }, String(stats.pages || pages.length))
          ),
          h("div", { style: S.statRow },
            h("span", { style: { color: "#8b949e" } }, "Revisions"),
            h("span", { style: { fontWeight: 600 } }, String(stats.total_revisions || 0))
          )
        )
      )
    );
  }

  // ---------------------------------------------------------------------------
  // Register
  // ---------------------------------------------------------------------------

  if (window.__HERMES_PLUGINS__ && typeof window.__HERMES_PLUGINS__.register === "function") {
    window.__HERMES_PLUGINS__.register("wikime", WikiMePage);
  }
})();
