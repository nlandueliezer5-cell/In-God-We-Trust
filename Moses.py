"""
IN GOD WE TRUST — Internet Starlink
Wi-Fi Access Pass Portal (Streamlit)

Single-file, production-ready app.
- Client tab: buy a pass, track approval status live.
- Admin tab: approve/reject orders, assign codes, view logs, track sales.
"""

import base64
import datetime
import json
import os
import random
import string
import threading
import uuid

import pandas as pd
import requests
import streamlit as st

# ---------------------------------------------------------------------------
# 1. Page Configuration & Constants
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="IN GOD WE TRUST — Internet Starlink",
    page_icon="📡",
    layout="centered",
)

APP_URL = (
    st.secrets.get("APP_URL", "in-god-we-trust-6er82udqjawfqbkyzmohgl.streamlit.app")
    if hasattr(st, "secrets")
    else "https://igwt-wifi.streamlit.app"
)

NTFY_TOPIC = "igwt_wifi_moise_2026"
NTFY_PUBLISH_URL = "https://ntfy.sh"

DATA_DIR = "igwt_data"
ORDERS_FILE = os.path.join(DATA_DIR, "orders.json")
SALES_FILE = os.path.join(DATA_DIR, "sales.json")
VAULT_FILE = os.path.join(DATA_DIR, "vault.json")
LOG_FILE = os.path.join(DATA_DIR, "notif_log.json")

os.makedirs(DATA_DIR, exist_ok=True)

PLANS = [
    {"key": "12H", "label": "⏳ 12 Heures — 1 500 FC", "price": 1500},
    {"key": "24H", "label": "🚀 24 Heures — 2 500 FC", "price": 2500},
    {"key": "48H", "label": "⚡ 48 Heures — 5 000 FC", "price": 5000},
]


def fmt_fc(n):
    try:
        return f"{int(n):,}".replace(",", " ")
    except (TypeError, ValueError):
        return str(n)


# ---------------------------------------------------------------------------
# 2. Persistence Helpers & Shared Store
# ---------------------------------------------------------------------------
def _load(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default


def _save(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def generate_test_passwords(n=10):
    return [
        "PASS-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=5))
        for _ in range(n)
    ]


def _ensure_order_ids(orders):
    """Backward compatibility: give every legacy order a stable string id."""
    changed = False
    for o in orders:
        if not o.get("id"):
            o["id"] = uuid.uuid4().hex
            changed = True
    return changed


@st.cache_resource
def get_store():
    orders = _load(ORDERS_FILE, [])
    if _ensure_order_ids(orders):
        _save(ORDERS_FILE, orders)
    return {
        "lock": threading.Lock(),
        "orders": orders,
        "sales": _load(SALES_FILE, []),
        "vault": _load(VAULT_FILE, None) or generate_test_passwords(20),
        "notif_log": _load(LOG_FILE, []),
    }


store = get_store()


def save_orders():
    _save(ORDERS_FILE, store["orders"])


def save_sales():
    _save(SALES_FILE, store["sales"])


def save_vault():
    _save(VAULT_FILE, store["vault"])


def save_log():
    store["notif_log"] = store["notif_log"][-50:]
    _save(LOG_FILE, store["notif_log"])


def get_order_by_id(order_id):
    for o in store["orders"]:
        if o.get("id") == order_id:
            return o
    return None


# ---------------------------------------------------------------------------
# 3. Notifications with Web Link
# ---------------------------------------------------------------------------
def send_ntfy_push(client_name, plan, total, ref_id, pay_method):
    message = (
        f"Client: {client_name}\n"
        f"Pass: {plan} ({fmt_fc(total)} FC)\n"
        f"Paiement: {pay_method}\n"
        f"Ref: {ref_id}\n\n"
        f"Lien: {APP_URL}"
    )

    payload = {
        "topic": NTFY_TOPIC,
        "message": message,
        "title": "IGWT — Nouvelle Commande !",
        "priority": 5,
        "tags": ["moneybag", "wifi"],
        "click": APP_URL,
    }
    entry = {
        "time": datetime.datetime.now().strftime("%H:%M:%S"),
        "client": client_name,
        "channel": "ntfy",
    }
    ok = False
    try:
        res = requests.post(NTFY_PUBLISH_URL, json=payload, timeout=8)
        if res.status_code == 200:
            entry["status"] = "sent"
            ok = True
        else:
            entry["status"] = f"http_{res.status_code}: {res.text[:200]}"
    except Exception as e:
        entry["status"] = f"error: {e}"

    with store["lock"]:
        store["notif_log"].append(entry)
        save_log()

    if ok:
        st.toast("🔔 Notification transmise à Moïse !", icon="✅")
    else:
        st.toast(f"⚠️ Ntfy: {entry['status']}", icon="❌")

    return ok


def send_telegram_push(client_name, plan, total, ref_id, pay_method):
    token = st.secrets.get("TELEGRAM_BOT_TOKEN") if hasattr(st, "secrets") else None
    chat_id = st.secrets.get("TELEGRAM_CHAT_ID") if hasattr(st, "secrets") else None
    if not token or not chat_id:
        return None

    text = (
        f"📡 IGWT — Nouvelle Commande !\n"
        f"Client: {client_name}\n"
        f"Pass: {plan} ({fmt_fc(total)} FC)\n"
        f"Mode: {pay_method}\n"
        f"Ref: {ref_id}\n\n"
        f"🔗 Ouvrir le portail: {APP_URL}"
    )

    entry = {
        "time": datetime.datetime.now().strftime("%H:%M:%S"),
        "client": client_name,
        "channel": "telegram",
    }
    ok = False
    try:
        res = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=8,
        )
        entry["status"] = "sent" if res.status_code == 200 else f"http_{res.status_code}"
        ok = res.status_code == 200
    except Exception as e:
        entry["status"] = f"error: {e}"

    with store["lock"]:
        store["notif_log"].append(entry)
        save_log()
    return ok


def notify_new_order(client_name, plan, total, ref_id, pay_method):
    send_ntfy_push(client_name, plan, total, ref_id, pay_method)
    send_telegram_push(client_name, plan, total, ref_id, pay_method)


@st.cache_data(show_spinner=False)
def get_base64_image(image_path):
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except Exception:
        return None


logo_b64 = get_base64_image("IGWT_logo.png")

# ---------------------------------------------------------------------------
# 4. Custom Styling (High-Contrast Dark Theme)
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    .stApp { background-color: #0b132b !important; color: #ffffff !important; }

    p, span, label, div, h1, h2, h3, h4, h5, h6 {
        color: #ffffff !important;
        opacity: 1 !important;
    }

    .stCaption, [data-testid="stCaptionContainer"] p {
        color: #cbd5e1 !important;
    }

    .header-card {
        background: linear-gradient(135deg, #0a1128 0%, #1c2541 100%);
        border: 2px solid #00b4d8;
        border-radius: 18px;
        padding: 20px;
        text-align: center;
        box-shadow: 0 8px 32px 0 rgba(0, 180, 216, 0.25);
        margin-bottom: 20px;
    }
    .status-badge {
        background-color: #10b981;
        color: #ffffff !important;
        padding: 6px 16px;
        border-radius: 20px;
        font-weight: bold;
        font-size: 13px;
        display: inline-block;
    }
    .info-card {
        background: #1c2541;
        border-left: 5px solid #00b4d8;
        border-radius: 10px;
        padding: 14px 18px;
        margin-bottom: 20px;
        color: #ffffff !important;
    }
    .number-display-box {
        background-color: #0a1128 !important;
        border: 2px dashed #00b4d8 !important;
        border-radius: 10px !important;
        padding: 14px !important;
        text-align: center !important;
        font-family: monospace !important;
        font-size: 24px !important;
        font-weight: bold !important;
        color: #ffd700 !important;
        letter-spacing: 2px !important;
        margin: 10px 0 !important;
    }
    .code-box {
        background: #10b981;
        color: #000000 !important;
        font-size: 26px;
        font-weight: bold;
        text-align: center;
        padding: 15px;
        border-radius: 12px;
        letter-spacing: 2px;
        margin: 15px 0;
    }
    div.stButton > button {
        background: linear-gradient(90deg, #00b4d8 0%, #0077b6 100%) !important;
        color: #ffffff !important;
        font-weight: bold !important;
        font-size: 16px !important;
        border-radius: 10px !important;
        border: none !important;
        padding: 12px 20px !important;
        width: 100% !important;
        box-shadow: 0 4px 12px rgba(0, 180, 216, 0.3) !important;
    }
    div.stButton > button:hover { filter: brightness(1.1); }

    [data-testid="stTextInput"] input,
    [data-testid="stSelectbox"] > div > div {
        background-color: #1c2541 !important;
        color: #ffffff !important;
        border: 1px solid #00b4d8 !important;
        caret-color: #ffffff !important;
    }
    [data-testid="stTextInput"] input::placeholder { color: #94a3b8 !important; }
    [data-testid="stWidgetLabel"] p,
    [data-testid="stMarkdownContainer"] p,
    label { color: #f8fafc !important; font-weight: 500; }
    [data-testid="stRadio"] label { color: #f8fafc !important; }
    [data-testid="stDataFrame"] { color: #0b132b !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# 5. Header Component
# ---------------------------------------------------------------------------
logo_html = (
    f'<img src="data:image/png;base64,{logo_b64}" style="max-width: 130px;'
    ' margin-bottom: 10px;" /><br>'
    if logo_b64
    else "📡 "
)

st.markdown(
    f"""
    <div class="header-card">
        {logo_html}
        <h1 style="margin:0; font-size: 26px; color:#ffffff;">IN GOD WE TRUST</h1>
        <p style="font-weight: 600; margin-top: 5px; margin-bottom: 12px; color:#00b4d8;">
            ⚡ Service Internet Satellite Starlink Haute Vitesse
        </p>
        <span class="status-badge">🟢 RÉSEAU EN LIGNE • ACTIF</span>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="info-card">
        <p style="margin: 0; font-size: 13px; font-weight: bold; color: #00b4d8;">👤 GÉRANT & PROPRIÉTAIRE</p>
        <p style="margin: 2px 0; font-size: 16px; font-weight: bold; color:#ffffff;">Mugisa Bakebuga Moïse</p>
        <p style="margin: 0; font-size: 13px; color:#cbd5e1;">
            📍 <b>Adresse :</b> Près de la station Andama (sur la route principale), Ghiro, Haut-Uele.<br>
            📞 <b>M-Pesa :</b> 0833890033
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

tab_client, tab_admin = st.tabs(["🛒 Acheter un Pass", "🔒 Espace Administrateur"])

# ---------------------------------------------------------------------------
# 6. Client Tab View
# ---------------------------------------------------------------------------


@st.fragment(run_every=5)
def render_pending_order(order_id):
    """Isolated auto-refreshing fragment — polls order status without a
    full-page reload, so the rest of the UI/state stays stable."""
    order = get_order_by_id(order_id)

    if order is None:
        st.error("Commande introuvable. Veuillez passer une nouvelle commande.")
        if st.button("🛒 Nouvelle commande", key="frag_missing_order_btn"):
            st.session_state.pop("current_order_id", None)
            st.rerun()
        return

    status = order.get("Status", "Pending")

    st.write(f"**Client :** {order.get('Client', '-')}")
    st.write(f"**Forfait :** {order.get('Forfait', '-')}")
    st.write(f"**Mode de Paiement :** {order.get('Mode', 'M-Pesa')}")
    st.write(f"**Référence :** `{order.get('Ref', '-')}`")

    if status == "Pending":
        st.warning("⏳ **En attente de confirmation par Moïse...**")
        st.info(
            "Dès que Moïse aura validé votre demande, votre code d'accès "
            "apparaîtra automatiquement ici (actualisation automatique)."
        )
    elif status == "Approved":
        st.success("✅ **Demande confirmée ! Voici votre code d'accès Wi-Fi :**")
        st.markdown(
            f'<div class="code-box">{order.get("Code", "")}</div>',
            unsafe_allow_html=True,
        )
        st.caption("💡 *Saisissez ce code sur la page de connexion Wi-Fi Starlink.*")
        if st.button("🛒 Passer une autre commande", key="frag_new_order_btn"):
            st.session_state.pop("current_order_id", None)
            st.rerun()
    else:
        st.error("❌ Cette commande a été refusée. Veuillez contacter Moïse.")
        if st.button("🛒 Passer une nouvelle commande", key="frag_retry_order_btn"):
            st.session_state.pop("current_order_id", None)
            st.rerun()


with tab_client:
    current_order_id = st.session_state.get("current_order_id")

    if current_order_id:
        with st.container(border=True):
            st.write("### 🧾 Statut de votre commande")
            render_pending_order(current_order_id)
    else:
        with st.container(border=True):
            st.write("### 1. 🎫 Choisir un Pass Wi-Fi")
            plan_choice = st.radio(
                "Sélectionnez la durée d'accès :",
                [p["label"] for p in PLANS],
                key="plan_choice",
            )
            selected_plan = next(p for p in PLANS if p["label"] == plan_choice)
            unit_price = selected_plan["price"]
            st.markdown(f"#### 💵 Total à payer : **{fmt_fc(unit_price)} FC**")

        with st.container(border=True):
            st.write("### 2. 💳 Mode de Paiement")
            payment_mode = st.radio(
                "Choisissez comment vous allez payer :",
                [
                    "📱 Mobile Money (M-Pesa)",
                    "💵 Espèces (Paiement Cash en main)",
                ],
                key="payment_mode",
            )
            is_mpesa = "M-Pesa" in payment_mode

            if is_mpesa:
                st.write("Envoyez le montant exact au numéro M-Pesa ci-dessous :")
                st.markdown(
                    '<div class="number-display-box">0833890033</div>',
                    unsafe_allow_html=True,
                )
                st.caption("💡 *Saisissez ce numéro dans votre menu M-Pesa (*112#).*")
            else:
                st.info(
                    "💵 **Option Cash :** Cliquez simplement sur le bouton ci-dessous pour "
                    "envoyer la demande. Moïse validera dès qu'il recevra les espèces."
                )

        with st.container(border=True):
            st.write("### 3. 📝 Valider la Commande")
            c_name = st.text_input("Votre Nom & Prénom :", placeholder="Ex: Jean Marc")
            c_phone = st.text_input("Votre N° de Téléphone :", placeholder="Ex: 0812345678")

            if is_mpesa:
                c_ref = st.text_input(
                    "Numéro / ID de Référence du SMS M-Pesa :",
                    placeholder="Ex: PP260807.1345.H12345",
                )
            else:
                c_ref = "CASH"
                st.caption("✅ Référence automatiquement définie sur `CASH`.")

            btn_label = (
                "🚀 Soumettre mon Paiement M-Pesa"
                if is_mpesa
                else "🚀 Demander le Pass (Paiement Cash)"
            )

            if st.button(btn_label):
                ref_ok = bool(c_ref) if is_mpesa else True
                if c_name and c_phone and ref_ok:
                    pay_type = "M-Pesa" if is_mpesa else "Cash"
                    new_order = {
                        "id": uuid.uuid4().hex,
                        "Heure": datetime.datetime.now().strftime("%H:%M:%S"),
                        "Client": c_name,
                        "Phone": c_phone,
                        "Forfait": selected_plan["key"],
                        "Total": unit_price,
                        "Mode": pay_type,
                        "Ref": c_ref,
                        "Status": "Pending",
                        "Code": "",
                    }
                    with store["lock"]:
                        store["orders"].append(new_order)
                        save_orders()

                    st.session_state.current_order_id = new_order["id"]
                    notify_new_order(
                        c_name, selected_plan["key"], unit_price, c_ref, pay_type
                    )
                    st.rerun()
                else:
                    st.warning("⚠️ Veuillez remplir tous les champs du formulaire.")

# ---------------------------------------------------------------------------
# 7. Admin Tab View
# ---------------------------------------------------------------------------
with tab_admin:
    st.write("### 🔒 Espace Administrateur")
    admin_password = (
        st.secrets.get("ADMIN_PASSWORD", "moise2026")
        if hasattr(st, "secrets")
        else "moise2026"
    )

    if not st.session_state.get("admin_authed", False):
        pwd = st.text_input("Mot de passe de Moïse :", type="password", key="admin_pwd_input")
        if st.button("🔓 Se connecter"):
            if pwd and pwd.lower() == admin_password.lower():
                st.session_state.admin_authed = True
                st.rerun()
            else:
                st.error("❌ Mot de passe incorrect.")
    else:
        st.success("🔓 Accès autorisé. Bienvenue, Moïse !")
        col_refresh, col_logout = st.columns(2)
        if col_refresh.button("🔄 Actualiser"):
            st.rerun()
        if col_logout.button("🚪 Se déconnecter"):
            st.session_state.admin_authed = False
            st.rerun()

        st.write("---")
        st.write("### 📩 Demandes en attente")
        with store["lock"]:
            pending_list = [
                o for o in store["orders"] if o.get("Status", "Pending") == "Pending"
            ]

        if pending_list:
            for order in pending_list:
                oid = order["id"]
                with st.container(border=True):
                    st.warning(
                        f"👤 **Client :** {order.get('Client', '-')} ({order.get('Phone', '-')})  \n"
                        f"🎫 **Forfait :** {order.get('Forfait', '-')} — **{fmt_fc(order.get('Total', 0))} FC**  \n"
                        f"💳 **Mode :** {order.get('Mode', 'M-Pesa')}  \n"
                        f"🧾 **Référence :** `{order.get('Ref', '-')}`  \n"
                        f"🕒 **Heure :** {order.get('Heure', '-')}"
                    )

                    default_code = store["vault"][0] if store["vault"] else "STAR-1234"
                    assigned_code = st.text_input(
                        "Code Wi-Fi à assigner :",
                        value=default_code,
                        key=f"code_in_{oid}",
                    )

                    col_a, col_b = st.columns(2)
                    if col_a.button("✅ Valider", key=f"btn_val_{oid}"):
                        with store["lock"]:
                            live_order = get_order_by_id(oid)
                            if live_order is not None:
                                live_order["Status"] = "Approved"
                                live_order["Code"] = assigned_code
                                if assigned_code in store["vault"]:
                                    store["vault"].remove(assigned_code)
                                store["sales"].append(
                                    {
                                        "Heure": live_order.get("Heure", "-"),
                                        "Date": datetime.date.today().strftime("%d/%m/%Y"),
                                        "Forfait": live_order.get("Forfait", "-"),
                                        "Mode": live_order.get("Mode", "M-Pesa"),
                                        "Total (FC)": live_order.get("Total", 0),
                                    }
                                )
                                save_orders()
                                save_vault()
                                save_sales()
                        st.toast("✅ Code validé et transmis au client !")
                        st.rerun()

                    if col_b.button("❌ Refuser", key=f"btn_del_{oid}"):
                        with store["lock"]:
                            live_order = get_order_by_id(oid)
                            if live_order is not None:
                                live_order["Status"] = "Rejected"
                                save_orders()
                        st.rerun()
        else:
            st.info("Aucune commande en attente.")

        st.write("---")
        st.write("### 🔔 Journal des notifications (débogage)")
        if store["notif_log"]:
            st.dataframe(
                pd.DataFrame(list(reversed(store["notif_log"]))),
                use_container_width=True,
            )
        else:
            st.caption("Aucune notification envoyée pour le moment.")
        if st.button("📨 Envoyer une notification de test"):
            notify_new_order("TEST", "12H", 1500, "TEST-REF", "Cash")
            st.rerun()

        st.write("---")
        st.write("### 🔑 Réserve de mots de passe de test")
        st.write(store["vault"])
        if st.button("🔄 Générer 10 nouveaux codes de test"):
            with store["lock"]:
                store["vault"] = generate_test_passwords(10)
                save_vault()
            st.rerun()

        st.write("---")
        st.write("### 📈 Bilan des Revenus")
        if store["sales"]:
            df = pd.DataFrame(store["sales"])
            total_revenue = sum(s.get("Total (FC)", 0) for s in store["sales"])

            m1, m2 = st.columns(2)
            m1.metric("💰 Total Encaissé", f"{fmt_fc(total_revenue)} FC")
            m2.metric("🧾 Nombre de Ventes", len(store["sales"]))

            st.dataframe(df.iloc[::-1], use_container_width=True)

            csv_data = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                "⬇️ Exporter en CSV",
                data=csv_data,
                file_name=f"igwt_ventes_{datetime.date.today().isoformat()}.csv",
                mime="text/csv",
            )

            st.write("")
            confirm_clear = st.checkbox(
                "Je confirme vouloir effacer définitivement l'historique des ventes."
            )
            if st.button("🗑️ Effacer l'historique", disabled=not confirm_clear):
                with store["lock"]:
                    store["sales"] = []
                    save_sales()
                st.toast("🗑️ Historique des ventes effacé.")
                st.rerun()
        else:
            st.info("Aucune vente enregistrée pour le moment.")
