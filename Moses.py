import base64
import datetime
import json
import os
import random
import string
import threading

import pandas as pd
import requests
import streamlit as st

# ---------------------------------------------------------------------------
# 1. Page Configuration & Global Settings
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="IN GOD WE TRUST — Internet Starlink",
    page_icon="📡",
    layout="centered",
)

# App URL sent in notifications so Moïse can tap directly to open the portal
APP_URL = st.secrets.get("APP_URL", "https://igwt-wifi.streamlit.app")

NTFY_TOPIC = "igwt_wifi_moise_2026"
NTFY_PUBLISH_URL = "https://ntfy.sh"

DATA_DIR = "igwt_data"
ORDERS_FILE = os.path.join(DATA_DIR, "orders.json")
SALES_FILE = os.path.join(DATA_DIR, "sales.json")
VAULT_FILE = os.path.join(DATA_DIR, "vault.json")
LOG_FILE = os.path.join(DATA_DIR, "notif_log.json")

os.makedirs(DATA_DIR, exist_ok=True)


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


@st.cache_resource
def get_store():
    return {
        "lock": threading.Lock(),
        "orders": _load(ORDERS_FILE, []),
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


# ---------------------------------------------------------------------------
# 3. Notifications with Web Link
# ---------------------------------------------------------------------------
def send_ntfy_push(client_name, plan, total, ref_id, pay_method):
    message = (
        f"Client: {client_name}\n"
        f"Pass: {plan} ({total:,} FC)\n"
        f"Paiement: {pay_method}\n"
        f"Ref: {ref_id}\n\n"
        f"Lien: {APP_URL}"
    ).replace(",", " ")

    payload = {
        "topic": NTFY_TOPIC,
        "message": message,
        "title": "IGWT — Nouvelle Commande !",
        "priority": 5,
        "tags": ["moneybag", "wifi"],
        "click": APP_URL,  # Tapping notification opens app URL
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
        f"Pass: {plan} ({total:,} FC)\n"
        f"Mode: {pay_method}\n"
        f"Ref: {ref_id}\n\n"
        f"🔗 Ouvrir le portail: {APP_URL}"
    ).replace(",", " ")

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


def get_base64_image(image_path):
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except Exception:
        return None


logo_b64 = get_base64_image("IGWT_logo.png")

# ---------------------------------------------------------------------------
# 4. Custom Styling (High-Contrast Text Fix)
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    /* Force overall dark background */
    .stApp { background-color: #0b132b !important; color: #ffffff !important; }

    /* High contrast text enforcement */
    p, span, label, div, h1, h2, h3, h4, h5, h6, caption {
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

    /* Input & Select Box styling */
    [data-testid="stTextInput"] input {
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
# 6. Fragment for Client Order Polling
# ---------------------------------------------------------------------------
@st.fragment(run_every="6s")
def render_order_status(order_idx):
    with store["lock"]:
        order = store["orders"][order_idx] if order_idx < len(store["orders"]) else None

    if order is None:
        if "current_order_id" in st.session_state:
            del st.session_state.current_order_id
        st.rerun()

    with st.container(border=True):
        st.write("### 🧾 Statut de votre commande")
        st.write(f"**Client :** {order['Client']}")
        st.write(f"**Forfait :** {order['Forfait']}")
        st.write(f"**Mode de Paiement :** {order.get('Mode', 'M-Pesa')}")
        st.write(f"**Référence :** `{order['Ref']}`")

        if order["Status"] == "Pending":
            st.warning("⏳ **En attente de confirmation par Moïse...**")
            st.info(
                "Dès que Moïse aura validé votre demande, votre code d'accès"
                " apparaîtra automatiquement ici."
            )
            if st.button("🔄 Rafraîchir le statut"):
                st.rerun()
        elif order["Status"] == "Approved":
            st.success("✅ **Demande confirmée ! Voici votre code d'accès Wi-Fi :**")
            st.markdown(
                f'<div class="code-box">{order["Code"]}</div>',
                unsafe_allow_html=True,
            )
            st.caption("💡 *Saisissez ce code sur la page de connexion Wi-Fi Starlink.*")
            if st.button("🛒 Passer une autre commande"):
                del st.session_state.current_order_id
                st.rerun()
        else:
            st.error("❌ Cette commande a été refusée. Veuillez contacter Moïse.")
            if st.button("🛒 Passer une nouvelle commande"):
                del st.session_state.current_order_id
                st.rerun()


# ---------------------------------------------------------------------------
# 7. Client Tab View
# ---------------------------------------------------------------------------
with tab_client:
    if "current_order_id" in st.session_state:
        render_order_status(st.session_state.current_order_id)
    else:
        with st.container(border=True):
            st.write("### 1. 🎫 Choisir un Pass Wi-Fi")
            plan_choice = st.radio(
                "Sélectionnez la durée d'accès :",
                [
                    "⏳ 12 Heures — 1 500 FC",
                    "🚀 24 Heures — 2 500 FC",
                    "⚡ 48 Heures — 5 000 FC",
                ],
            )
            unit_price = (
                1500 if "12" in plan_choice else (2500 if "24" in plan_choice else 5000)
            )
            st.markdown(f"#### 💵 Total à payer : **{unit_price:,} FC**".replace(",", " "))

        with st.container(border=True):
            st.write("### 2. 💳 Mode de Paiement")
            payment_mode = st.radio(
                "Choisissez comment vous allez payer :",
                [
                    "📱 Mobile Money (M-Pesa)",
                    "💵 Espèces (Paiement Cash en main)",
                ],
            )

            if "M-Pesa" in payment_mode:
                st.write("Envoyez le montant exact au numéro M-Pesa ci-dessous :")
                st.markdown(
                    '<div class="number-display-box">0833890033</div>',
                    unsafe_allow_html=True,
                )
                st.caption("💡 *Saisissez ce numéro dans votre menu M-Pesa (*112#).*")
            else:
                st.info(
                    "💵 **Option Cash :** Cliquez simplement sur le bouton ci-dessous pour"
                    " envoyer la demande. Moïse validera dès réception du billet."
                )

        with st.container(border=True):
            st.write("### 3. 📝 Valider la Commande")
            c_name = st.text_input("Votre Nom & Prénom :", placeholder="Ex: Jean Marc")
            c_phone = st.text_input("Votre N° de Téléphone :", placeholder="Ex: 0812345678")

            if "M-Pesa" in payment_mode:
                c_ref = st.text_input(
                    "Numéro / ID de Référence du SMS M-Pesa :",
                    placeholder="Ex: PP260807.1345.H12345",
                )
            else:
                c_ref = "CASH"

            btn_label = (
                "🚀 Soumettre mon Paiement M-Pesa"
                if "M-Pesa" in payment_mode
                else "🚀 Envoyer la demande (Paiement Cash)"
            )

            if st.button(btn_label):
                if c_name and c_phone and (c_ref if "M-Pesa" in payment_mode else True):
                    clean_plan = (
                        "12H" if "12" in plan_choice else ("24H" if "24" in plan_choice else "48H")
                    )
                    pay_type = "M-Pesa" if "M-Pesa" in payment_mode else "Cash"
                    new_order = {
                        "Heure": datetime.datetime.now().strftime("%H:%M:%S"),
                        "Client": c_name,
                        "Phone": c_phone,
                        "Forfait": clean_plan,
                        "Total": unit_price,
                        "Mode": pay_type,
                        "Ref": c_ref,
                        "Status": "Pending",
                        "Code": "",
                    }
                    with store["lock"]:
                        store["orders"].append(new_order)
                        save_orders()
                        st.session_state.current_order_id = len(store["orders"]) - 1

                    notify_new_order(c_name, clean_plan, unit_price, c_ref, pay_type)
                    st.rerun()
                else:
                    st.warning("⚠️ Veuillez remplir tous les champs du formulaire.")

# ---------------------------------------------------------------------------
# 8. Admin Tab View
# ---------------------------------------------------------------------------
with tab_admin:
    st.write("### 🔒 Espace Administrateur")
    admin_password = (
        st.secrets.get("ADMIN_PASSWORD", "moise2026")
        if hasattr(st, "secrets")
        else "moise2026"
    )
    pwd = st.text_input("Mot de passe de Moïse :", type="password")

    if pwd == admin_password:
        st.success("🔓 Accès autorisé. Bienvenue, Moïse !")
        st.write("---")
        if st.button("🔄 Actualiser"):
            st.rerun()

        st.write("### 📩 Demandes en attente")
        with store["lock"]:
            pending_list = [
                (i, o) for i, o in enumerate(store["orders"]) if o["Status"] == "Pending"
            ]

        if pending_list:
            for idx, order in pending_list:
                with st.container(border=True):
                    st.warning(
                        f"👤 **Client :** {order['Client']} ({order['Phone']})  \n"
                        f"🎫 **Forfait :** {order['Forfait']} — **{order['Total']:,} FC**  \n"
                        f"💳 **Mode :** {order.get('Mode', 'M-Pesa')}  \n"
                        f"🧾 **Référence :** `{order['Ref']}`"
                    )

                    default_code = store["vault"][0] if store["vault"] else "STAR-1234"
                    assigned_code = st.text_input(
                        f"Code Wi-Fi pour la commande #{idx + 1} :",
                        value=default_code,
                        key=f"code_in_{idx}",
                    )

                    col_a, col_b = st.columns(2)
                    if col_a.button(f"✅ Valider #{idx + 1}", key=f"btn_val_{idx}"):
                        with store["lock"]:
                            store["orders"][idx]["Status"] = "Approved"
                            store["orders"][idx]["Code"] = assigned_code
                            if assigned_code in store["vault"]:
                                store["vault"].remove(assigned_code)
                            store["sales"].append(
                                {
                                    "Heure": order["Heure"],
                                    "Date": datetime.date.today().strftime("%d/%m/%Y"),
                                    "Forfait": order["Forfait"],
                                    "Mode": order.get("Mode", "M-Pesa"),
                                    "Total (FC)": order["Total"],
                                }
                            )
                            save_orders()
                            save_vault()
                            save_sales()
                        st.toast("✅ Code validé et transmis au client !")
                        st.rerun()

                    if col_b.button(f"❌ Refuser #{idx + 1}", key=f"btn_del_{idx}"):
                        with store["lock"]:
                            store["orders"][idx]["Status"] = "Rejected"
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
            st.metric("Total Encaissé", f"{df['Tot
