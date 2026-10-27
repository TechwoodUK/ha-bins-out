/* Bins Out sidebar page: the Bins Out card on a page of its own. Vanilla ES module. */

// Same three-line icon HA uses for its own menu button.
const MENU_ICON = "M3,6H21V8H3V6M3,11H21V13H3V11M3,16H21V18H3V16Z";

class BinsOutPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; min-height: 100%; background: var(--primary-background-color); }
        .toolbar {
          display: flex; align-items: center; gap: 4px; height: var(--header-height, 56px);
          padding: 0 12px; box-sizing: border-box; font-size: 20px;
          background: var(--app-header-background-color, var(--primary-color));
          color: var(--app-header-text-color, var(--text-primary-color, #fff));
          border-bottom: var(--app-header-border-bottom, none);
        }
        button {
          display: none; width: 48px; height: 48px; padding: 12px; border: 0; border-radius: 50%;
          background: none; color: inherit; cursor: pointer;
        }
        button.show { display: block; }
        button:hover { background: rgba(127, 127, 127, 0.15); }
        svg { width: 24px; height: 24px; fill: currentColor; }
        .title { margin-left: 12px; }
        .content { max-width: 600px; margin: 0 auto; padding: 16px; }
        .error { color: var(--error-color, #db4437); }
      </style>
      <div class="toolbar">
        <button aria-label="Menu"><svg viewBox="0 0 24 24"><path d="${MENU_ICON}"></path></svg></button>
        <div class="title"></div>
      </div>
      <div class="content"></div>`;
    // HA's sidebar listens for this, same as its own menu button.
    this.shadowRoot.querySelector("button").addEventListener("click", () =>
      this.dispatchEvent(new Event("hass-toggle-menu", { bubbles: true, composed: true })),
    );
  }

  set hass(hass) {
    this._hass = hass;
    if (this._card) this._card.hass = hass;
    this._updateMenuButton();
  }

  set narrow(narrow) {
    this._narrow = narrow;
    this._updateMenuButton();
  }

  set panel(panel) {
    this._panelConfig = panel.config || {};
    this.shadowRoot.querySelector(".title").textContent = panel.title || "Bins";
    this._loadCard();
  }

  _updateMenuButton() {
    const hidden = this._hass?.dockedSidebar === "always_hidden";
    this.shadowRoot.querySelector("button").classList.toggle("show", Boolean(this._narrow || hidden));
  }

  async _loadCard() {
    if (this._loading) return;
    this._loading = true;
    const content = this.shadowRoot.querySelector(".content");
    try {
      // Same URL as the dashboard resource, so the browser loads the card only once.
      if (!customElements.get("bins-out-card")) await import(this._panelConfig.card_url);
      const card = document.createElement("bins-out-card");
      card.setConfig({ type: "custom:bins-out-card", entity: this._panelConfig.entity });
      if (this._hass) card.hass = this._hass;
      this._card = card;
      content.replaceChildren(card);
    } catch (err) {
      const msg = document.createElement("p");
      msg.className = "error";
      msg.textContent = `Couldn't load the Bins Out card: ${err.message}`;
      content.replaceChildren(msg);
    }
  }
}

if (!customElements.get("bins-out-panel")) customElements.define("bins-out-panel", BinsOutPanel);
