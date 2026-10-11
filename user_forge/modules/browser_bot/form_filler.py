import time
import json
import logging
import subprocess
from typing import Dict, Any, List, Optional
from playwright.sync_api import Page

from user_forge.core.models import Account

logger = logging.getLogger(__name__)

def copy_to_windows_clipboard(text: str) -> bool:
    """Copies text to the OS clipboard on Windows using PowerShell Set-Clipboard."""
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", "Set-Clipboard", "-Value", text],
            check=False,
            timeout=3,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return True
    except Exception as e:
        logger.warning(f"Could not copy text to OS clipboard: {e}")
        return False

class FormFiller:
    """
    Resilient form detector and auto-filler for web signup pages.
    Supports complex SPA forms (Twitter/X, Reddit, Instagram, Google)
    by triggering native React/Vue property setters and injecting
    an in-browser Copilot assistant bar.
    """
    def __init__(self, page: Page):
        self.page = page

    def inject_copilot_bar(self, account: Account, plain_password: str):
        """
        Injects a persistent, non-intrusive floating Copilot bar
        at the top of the browser window. Allows instant 1-click
        copying of email, username, and password, plus manual auto-fill trigger.
        """
        try:
            full_name = account.full_name or account.username
            payload = {
                "fullName": full_name,
                "username": account.username,
                "email": account.email,
                "password": plain_password,
                "projectId": account.project_id
            }

            script = f"""
            (() => {{
                if (document.getElementById('userforge-copilot-bar')) return;

                const data = {json.dumps(payload)};

                function fillReactInput(input, val) {{
                    if (!input) return false;
                    try {{
                        input.focus();
                        const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
                        if (nativeSetter) {{
                            nativeSetter.call(input, val);
                        }} else {{
                            input.value = val;
                        }}
                        input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        input.dispatchEvent(new KeyboardEvent('keydown', {{ bubbles: true }}));
                        input.dispatchEvent(new KeyboardEvent('keyup', {{ bubbles: true }}));
                        return true;
                    }} catch(e) {{
                        return false;
                    }}
                }}

                function tryFillAll() {{
                    let filled = 0;

                    // Twitter/X: If 'Use email instead' or 'Usar correo' is present, click it
                    try {{
                        const useEmailBtns = Array.from(document.querySelectorAll('button, span, div[role="button"]'))
                            .filter(el => /usar correo|use email/i.test(el.innerText || ''));
                        if (useEmailBtns.length > 0 && useEmailBtns[0].offsetParent !== null) {{
                            useEmailBtns[0].click();
                        }}
                    }} catch(e) {{}}

                    // 1. Identifiers (Email, Username, Twitter input[name='text'] / input[name='email'])
                    const idSelectors = [
                        "input[name='email']",
                        "input[name='username_or_email']",
                        "input[autocomplete='email']",
                        "input[autocomplete='username']",
                        "input[name='text']",
                        "input[data-testid='ocfEnterTextTextInput']",
                        "input[type='email']",
                        "input[name*='email' i]",
                        "input[id*='email' i]",
                        "input[placeholder*='email' i]",
                        "input[placeholder*='correo' i]",
                        "input[aria-label*='email' i]",
                        "input[aria-label*='correo' i]",
                        "input[placeholder*='usuario' i]",
                        "input[name*='username' i]"
                    ];

                    for (const sel of idSelectors) {{
                        const el = document.querySelector(sel);
                        if (el && el.offsetParent !== null && !el.value) {{
                            fillReactInput(el, data.email);
                            filled++;
                            break;
                        }}
                    }}

                    // 2. Full Name / Name
                    const nameSelectors = [
                        "input[name='name']",
                        "input[data-testid*='name' i]",
                        "input[name*='fullname' i]",
                        "input[name*='full_name' i]",
                        "input[id*='fullname' i]",
                        "input[placeholder*='nombre' i]",
                        "input[placeholder*='name' i]"
                    ];
                    for (const sel of nameSelectors) {{
                        const el = document.querySelector(sel);
                        if (el && el.offsetParent !== null && !el.value) {{
                            fillReactInput(el, data.fullName);
                            filled++;
                            break;
                        }}
                    }}

                    // 3. Password
                    const pwSelectors = [
                        "input[type='password']",
                        "input[name*='password' i]",
                        "input[autocomplete='current-password']",
                        "input[autocomplete='new-password']"
                    ];
                    const pwInputs = document.querySelectorAll(pwSelectors.join(','));
                    pwInputs.forEach(el => {{
                        if (el && el.offsetParent !== null && !el.value) {{
                            fillReactInput(el, data.password);
                            filled++;
                        }}
                    }});

                    // 4. Date of Birth selectors (Twitter / X)
                    try {{
                        const selects = document.querySelectorAll('select');
                        if (selects.length >= 3) {{
                            if (!selects[0].value) {{
                                selects[0].value = selects[0].options[5]?.value || '5';
                                selects[0].dispatchEvent(new Event('change', {{ bubbles: true }}));
                                filled++;
                            }}
                            if (!selects[1].value) {{
                                selects[1].value = selects[1].options[15]?.value || '15';
                                selects[1].dispatchEvent(new Event('change', {{ bubbles: true }}));
                                filled++;
                            }}
                            if (!selects[2].value) {{
                                const yrOpt = Array.from(selects[2].options).find(o => /^(199\\d|200[0-2])$/.test(o.value || o.text));
                                if (yrOpt) selects[2].value = yrOpt.value;
                                else selects[2].value = selects[2].options[25]?.value || '1998';
                                selects[2].dispatchEvent(new Event('change', {{ bubbles: true }}));
                                filled++;
                            }}
                        }}
                    }} catch(e) {{}}

                    return filled;
                }}

                // Create container element
                const bar = document.createElement('div');
                bar.id = 'userforge-copilot-bar';
                bar.style.cssText = `
                    position: fixed !important;
                    top: 10px !important;
                    left: 50% !important;
                    transform: translateX(-50%) !important;
                    z-index: 2147483647 !important;
                    background: #0f172a !important;
                    border: 1px solid #4f46e5 !important;
                    box-shadow: 0 10px 25px -5px rgba(0,0,0,0.7), 0 0 12px rgba(99,102,241,0.3) !important;
                    border-radius: 12px !important;
                    padding: 6px 14px !important;
                    display: flex !important;
                    align-items: center !important;
                    gap: 10px !important;
                    font-family: system-ui, -apple-system, sans-serif !important;
                    font-size: 12px !important;
                    color: #f8fafc !important;
                    user-select: none !important;
                `;

                bar.innerHTML = `
                    <div style="display:flex;align-items:center;gap:5px;font-weight:700;color:#818cf8;white-space:nowrap;">
                        <span>⚡</span> UserForge Copilot
                    </div>
                    <div style="height:14px;width:1px;background:#334155;"></div>

                    <div style="display:flex;align-items:center;gap:5px;background:#1e293b;padding:3px 7px;border-radius:6px;border:1px solid #334155;">
                        <span style="color:#94a3b8;font-size:10px;">EMAIL:</span>
                        <span style="font-family:monospace;font-size:11px;color:#e2e8f0;max-width:160px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${{data.email}}</span>
                        <button id="uf-cp-email" style="cursor:pointer;background:#4f46e5;color:#fff;border:none;border-radius:4px;padding:2px 6px;font-size:10px;font-weight:600;">Copiar</button>
                    </div>

                    <div style="display:flex;align-items:center;gap:5px;background:#1e293b;padding:3px 7px;border-radius:6px;border:1px solid #334155;">
                        <span style="color:#94a3b8;font-size:10px;">USUARIO:</span>
                        <span style="font-family:monospace;font-size:11px;color:#e2e8f0;">@${{data.username}}</span>
                        <button id="uf-cp-user" style="cursor:pointer;background:#334155;color:#cbd5e1;border:none;border-radius:4px;padding:2px 6px;font-size:10px;font-weight:600;">Copiar</button>
                    </div>

                    <div style="display:flex;align-items:center;gap:5px;background:#1e293b;padding:3px 7px;border-radius:6px;border:1px solid #334155;">
                        <span style="color:#94a3b8;font-size:10px;">CLAVE:</span>
                        <span style="font-family:monospace;font-size:11px;color:#a5b4fc;">••••••••</span>
                        <button id="uf-cp-pass" style="cursor:pointer;background:#334155;color:#cbd5e1;border:none;border-radius:4px;padding:2px 6px;font-size:10px;font-weight:600;">Copiar</button>
                    </div>

                    <button id="uf-cp-fill" style="cursor:pointer;background:#10b981;color:#fff;border:none;border-radius:6px;padding:4px 10px;font-size:11px;font-weight:700;display:flex;align-items:center;gap:3px;white-space:nowrap;">
                        ⚡ Auto-Rellenar
                    </button>
                `;

                if (document.body) {{
                    document.body.appendChild(bar);
                }} else {{
                    window.addEventListener('DOMContentLoaded', () => document.body.appendChild(bar));
                }}

                function copy(btn, text) {{
                    navigator.clipboard.writeText(text).then(() => {{
                        const prev = btn.innerText;
                        btn.innerText = '✓ Copiado';
                        btn.style.background = '#059669';
                        setTimeout(() => {{
                            btn.innerText = prev;
                            btn.style.background = btn.id === 'uf-cp-email' ? '#4f46e5' : '#334155';
                        }}, 1500);
                    }}).catch(() => {{
                        const ta = document.createElement('textarea');
                        ta.value = text;
                        document.body.appendChild(ta);
                        ta.select();
                        document.execCommand('copy');
                        document.body.removeChild(ta);
                        btn.innerText = '✓ Copiado';
                        setTimeout(() => {{ btn.innerText = 'Copiar'; }}, 1500);
                    }});
                }}

                document.getElementById('uf-cp-email').onclick = function() {{ copy(this, data.email); }};
                document.getElementById('uf-cp-user').onclick = function() {{ copy(this, data.username); }};
                document.getElementById('uf-cp-pass').onclick = function() {{ copy(this, data.password); }};

                document.getElementById('uf-cp-fill').onclick = function() {{
                    const cnt = tryFillAll();
                    const b = this;
                    b.innerText = cnt > 0 ? `✓ ${{cnt}} Rellenado(s)` : 'Buscando campos...';
                    setTimeout(() => {{ b.innerText = '⚡ Auto-Rellenar'; }}, 1800);
                }};

                // Dynamic triggers as React/Vue components finish mounting
                setTimeout(tryFillAll, 600);
                setTimeout(tryFillAll, 1500);
                setTimeout(tryFillAll, 3000);
                setTimeout(tryFillAll, 5000);
            }})();
            """
            try:
                self.page.context.add_init_script(script)
            except Exception:
                pass
            self.page.evaluate(script)
        except Exception as e:
            logger.debug(f"Copilot bar injection note: {e}")

    def fill_signup_form(self, account: Account, plain_password: str) -> Dict[str, Any]:
        """
        Scans the active page and attempts to fill standard registration input fields,
        including complex SPA selectors (Twitter/X, Reddit, Instagram).
        """
        results = {
            "email_filled": False,
            "username_filled": False,
            "password_filled": False,
            "fullname_filled": False,
            "firstname_filled": False,
            "lastname_filled": False,
            "terms_checked": False,
        }

        # 1. First copy email directly to Windows OS clipboard so user can instantly Ctrl+V
        copy_to_windows_clipboard(account.email)

        # 2. Inject the Copilot Bar immediately
        self.inject_copilot_bar(account, plain_password)

        time.sleep(1.0)

        # 3. Email & Primary Identifier field selectors (including Twitter / X name='text')
        email_selectors = [
            "input[name='username_or_email']",
            "input[name='email']",
            "input[autocomplete='username']",
            "input[autocomplete='email']",
            "input[name='text']",  # Standard Twitter/X identifier input
            "input[data-testid='ocfEnterTextTextInput']",  # Twitter/X testid
            "input[type='email']",
            "input[name*='email' i]",
            "input[id*='email' i]",
            "input[placeholder*='email' i]",
            "input[placeholder*='correo' i]",
            "input[aria-label*='email' i]",
            "input[aria-label*='correo' i]"
        ]
        for sel in email_selectors:
            try:
                loc = self.page.locator(sel)
                if loc.count() > 0 and loc.first.is_visible():
                    loc.first.fill(account.email, timeout=1200)
                    results["email_filled"] = True
                    break
            except Exception:
                pass

        # 4. Name fields
        first_name = ""
        last_name = ""
        if account.full_name:
            parts = account.full_name.split(" ", 1)
            first_name = parts[0]
            last_name = parts[1] if len(parts) > 1 else ""

        if account.full_name:
            fn_selectors = [
                "input[name='name']",  # Twitter signup full name
                "input[data-testid*='name' i]",
                "input[name*='fullname' i]",
                "input[name*='full_name' i]",
                "input[id*='fullname' i]",
                "input[placeholder*='nombre completo' i]",
                "input[placeholder*='full name' i]",
                "input[placeholder*='nombre' i]"
            ]
            for sel in fn_selectors:
                try:
                    loc = self.page.locator(sel)
                    if loc.count() > 0 and loc.first.is_visible():
                        loc.first.fill(account.full_name, timeout=1200)
                        results["fullname_filled"] = True
                        break
                except Exception:
                    pass

        # 5. Username field (if separate from email)
        username_selectors = [
            "input[name*='username' i]",
            "input[id*='username' i]",
            "input[placeholder*='usuario' i]",
            "input[placeholder*='username' i]",
            "input[aria-label*='username' i]"
        ]
        for sel in username_selectors:
            try:
                loc = self.page.locator(sel)
                if loc.count() > 0 and loc.first.is_visible():
                    loc.first.fill(account.username, timeout=1200)
                    results["username_filled"] = True
                    break
            except Exception:
                pass

        # 6. Password fields
        pwd_selectors = [
            "input[type='password']",
            "input[name*='password' i]",
            "input[name='password']",
            "input[autocomplete='current-password']",
            "input[autocomplete='new-password']"
        ]
        for sel in pwd_selectors:
            try:
                loc = self.page.locator(sel)
                if loc.count() > 0 and loc.first.is_visible():
                    loc.first.fill(plain_password, timeout=1200)
                    results["password_filled"] = True
                    break
            except Exception:
                pass

        # 7. Terms checkboxes
        terms_checkboxes = [
            "input[type='checkbox'][name*='terms' i]",
            "input[type='checkbox'][name*='agree' i]",
            "input[type='checkbox'][name*='privacy' i]",
            "input[type='checkbox'][id*='terms' i]"
        ]
        for sel in terms_checkboxes:
            try:
                loc = self.page.locator(sel)
                if loc.count() > 0 and loc.first.is_visible():
                    if not loc.first.is_checked():
                        loc.first.check(timeout=1200)
                        results["terms_checked"] = True
            except Exception:
                pass

        # Re-inject copilot bar to ensure it remains rendered on top of dynamic SPA content
        self.inject_copilot_bar(account, plain_password)

        return results
