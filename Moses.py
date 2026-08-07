import base64
import datetime
import random
import string
import urllib.parse
import pandas as pd
import requests
import streamlit as st

# 1. Configuration de la page
st.set_page_config(
    page_title="IN GOD WE TRUST — Internet Starlink",
    page_icon="📡",
    layout="centered",
)

NTFY_TOPIC = "igwt_wifi_moise_2026"

# Initialisation de la session
if "pending_orders" not in st.session_state:
    st.session_state.pending_orders = []

if "sales_history" not in st.session_state:
    st.session_state.sales_history = []


def generate_test_passwords(n=10):
    return [
        "PASS-"
        + "".join(random.choices(string.ascii_uppercase + string.digits, k=5))
        for _ in range(n)
    ]


if "password_vault" not in st.session_state:
    st.session_state.password_vault = generate_test_passwords(20)


def send_ntfy_push(client_name, plan, total, ref_id):
    """Envoie une notification push via HTTP GET (plus fiable sur Streamlit Cloud)."""
    try:
        msg_text = f"Client: {client_name} | Pass: {plan} ({total:,} FC) | Ref: {ref_id}"
        encoded_msg = urllib.parse.quote(msg_text)
        url = f"https://ntfy.sh/{NTFY_TOPIC}/publish?message={encoded_msg}&title=Nouvelle+Commande&tags=moneybag,wifi"

        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            st.toast("🔔 Notification envoyée à Moïse !", icon="📲")
        else:
            st.toast(f"⚠️ Ntfy Code: {res.status_code}")
    except Exception as e:
        st.toast(f"⚠️ Erreur notification: {e}")


def get_base64_image(image_path):
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except Exception:
        return None


logo_b64 = get_base64_image("IGWT_logo.png")

# 2. Styles CSS Adaptatifs (Thème Clair & Sombre)
st.markdown(
    """
    <style>
    /* Carte d'en-tête (Fixe et élégante) */
    .header-card {
        background: linear-gradient(135deg, #0a1128 0%, #1c2541 100%);
        border: 2px solid #00b4d8;
        border-radius: 20px;
        padding: 20px;
        text-align: center;
        box-shadow: 0 8px 32px 0 rgba(0, 180, 216, 0.25);
        margin-bottom: 20px;
    }
    .header-card h1 {
        color: #ffffff !important;
    }
    .header-card p {
        color: #00b4d8 !important;
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
    
    /* Carte gérant adaptative */
    .info-card {
        background: rgba(0, 180, 216, 0.1);
        border-left: 5px solid #00b4d8;
        border-radius: 10px;
        padding: 14px 18px;
        margin-bottom: 20px;
    }
    
    /* Code d'accès Wi-Fi */
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
    
    /* Boutons universels toujours visibles */
    div.stButton > button {
        background: linear-gradient(90deg, #00b4d8 0%, #0077b6 100%) !important;
        color: #ffffff !important;
        font-weight: bold !important;
        font-size: 16px !important;
        border-radius: 10px !important;
        border: none !important;
        padding: 10px 20px !important;
        width: 100% !important;
        box-shadow: 0 4px 12px rgba(0, 180, 216, 0.3) !important;
    }
    
    div.stButton > button:hover {
        background: linear-gradient(90deg, #0077b6 0%, #03045e 100%) !important;
        color: #ffffff !important;
        box-shadow: 0 0 18px rgba(0, 180, 216, 0.6) !important;
    }
    
    .designer-footer {
        text-align: center;
        font-size: 12px;
        opacity: 0.7;
        margin-top: 40px;
        padding-top: 15px;
        border-top: 1px solid rgba(150,150,150,0.2);
        font-style: italic;
    }
    </style>
""",
    unsafe_allow_html=True,
)

# 3. En-tête Principal
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
        <h1 style="margin:0; font-size: 26px;">IN GOD WE TRUST</h1>
        <p style="font-weight: 600; margin-top: 5px; margin-bottom: 12px;">
            ⚡ Service Internet Satellite Starlink Haute Vitesse
        </p>
        <span class="status-badge">🟢 RÉSEAU EN LIGNE • ACTIF</span>
    </div>
""",
    unsafe_allow_html=True,
)

# Carte Propriétaire
st.markdown(
    """
    <div class="info-card">
        <p style="margin: 0; font-size: 13px; font-weight: bold; color: #00b4d8;">👤 GÉRANT & PROPRIÉTAIRE</p>
        <p style="margin: 2px 0; font-size: 16px; font-weight: bold;">Mugisa Bakebuga Moïse</p>
        <p style="margin: 0; font-size: 13px;">
            📍 <b>Adresse :</b> Près de la station Andama (sur la route principale), Ghiro, Haut-Uele.<br>
            📞 <b>M-Pesa :</b> 0833890033
        </p>
    </div>
""",
    unsafe_allow_html=True,
)

# 4. Navigation
tab_client, tab_admin = st.tabs(["🛒 Acheter un Pass", "🔒 Espace Administrateur"])

# --- ONGLET 1 : CLIENT ---
with tab_client:
  if "current_order_id" in st.session_state:
    order_idx = st.session_state.current_order_id
    order = st.session_state.pending_orders[order_idx]

    with st.container(border=True):
      st.write("### 🧾 Statut de votre commande")
      st.write(f"**Client :** {order['Client']}")
      st.write(f"**Forfait :** {order['Forfait']}")
      st.write(f"**Référence SMS :** `{order['Ref']}`")

      if order["Status"] == "Pending":
        st.warning("⏳ **En attente de confirmation par Moïse...**")
        st.info(
            "Dès que Moïse aura vérifié le paiement Mobile Money, votre code"
            " apparaîtra automatiquement ici."
        )
        if st.button("🔄 Rafraîchir le statut"):
          st.rerun()
      elif order["Status"] == "Approved":
        st.success(
            "✅ **Paiement confirmé ! Voici votre code d'accès Wi-Fi :**"
        )
        st.markdown(
            f'<div class="code-box">{order["Code"]}</div>',
            unsafe_allow_html=True,
        )
        st.caption(
            "💡 *Saisissez ce code sur la page de connexion Wi-Fi Starlink.*"
        )
        if st.button("🛒 Passer une autre commande"):
          del st.session_state.current_order_id
          st.rerun()

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
      st.markdown(
          f"#### 💵 Total à payer : **{unit_price:,} FC**".replace(",", " ")
      )

    with st.container(border=True):
      st.write("### 2. 📲 Effectuer le Paiement M-Pesa")
      st.write("Envoyez le montant exact au numéro M-Pesa ci-dessous :")
      st.code("0833890033", language="text")
      st.caption(
          "💡 *Cliquez sur le bouton de copie à droite dans le rectangle"
          " ci-dessus.*"
      )

    with st.container(border=True):
      st.write("### 3. 📝 Valider la Commande")
      c_name = st.text_input("Votre Nom & Prénom :", placeholder="Ex: Jean Marc")
      c_phone = st.text_input(
          "Votre N° de Téléphone :", placeholder="Ex: 0812345678"
      )
      c_ref = st.text_input(
          "Numéro / ID de Référence du SMS M-Pesa :",
          placeholder="Ex: PP260807.1345.H12345",
      )

      if st.button("🚀 Soumettre mon Paiement"):
        if c_name and c_phone and c_ref:
          clean_plan = (
              "12H"
              if "12" in plan_choice
              else ("24H" if "24" in plan_choice else "48H")
          )

          new_order = {
              "Heure": datetime.datetime.now().strftime("%H:%M:%S"),
              "Client": c_name,
              "Phone": c_phone,
              "Forfait": clean_plan,
              "Total": unit_price,
              "Ref": c_ref,
              "Status": "Pending",
              "Code": "",
          }

          st.session_state.pending_orders.append(new_order)
          st.session_state.current_order_id = (
              len(st.session_state.pending_orders) - 1
          )

          send_ntfy_push(c_name, clean_plan, unit_price, c_ref)
          st.rerun()
        else:
          st.warning("⚠️ Veuillez remplir tous les champs du formulaire.")

# --- ONGLET 2 : ADMIN ---
with tab_admin:
  st.write("### 🔒 Espace Administrateur")
  pwd = st.text_input("Mot de passe de Moïse :", type="password")

  if pwd.lower() == "moise2026":
    st.success("🔓 Accès autorisé. Bienvenue, Moïse !")
    st.write("---")
    st.write("### 📩 Demandes en attente")

    pending_list = [
        (i, o)
        for i, o in enumerate(st.session_state.pending_orders)
        if o["Status"] == "Pending"
    ]

    if pending_list:
      for idx, order in pending_list:
        with st.container(border=True):
          st.warning(f"""
                    👤 **Client :** {order['Client']} ({order['Phone']})  
                    🎫 **Forfait :** {order['Forfait']} — **{order['Total']:,} FC**  
                    🧾 **SMS Référence :** `{order['Ref']}`
                    """)

          assigned_code = st.text_input(
              f"Code Wi-Fi pour la commande #{idx+1} :",
              value=(
                  st.session_state.password_vault[0]
                  if st.session_state.password_vault
                  else "STAR-1234"
              ),
              key=f"code_in_{idx}",
          )

          col_a, col_b = st.columns(2)
          if col_a.button(f"✅ Valider #{idx+1}", key=f"btn_val_{idx}"):
            st.session_state.pending_orders[idx]["Status"] = "Approved"
            st.session_state.pending_orders[idx]["Code"] = assigned_code

            if assigned_code in st.session_state.password_vault:
              st.session_state.password_vault.remove(assigned_code)

            sale_entry = {
                "Heure": order["Heure"],
                "Date": datetime.date.today().strftime("%d/%m/%Y"),
                "Forfait": order["Forfait"],
                "Total (FC)": order["Total"],
            }
            st.session_state.sales_history.append(sale_entry)
            st.toast("✅ Code validé et transmis au client !")
            st.rerun()

          if col_b.button(f"❌ Refuser #{idx+1}", key=f"btn_del_{idx}"):
            st.session_state.pending_orders[idx]["Status"] = "Rejected"
            st.rerun()
    else:
      st.info("Aucune commande en attente.")

    st.write("---")
    st.write("### 🔑 Réserve de mots de passe de test")
    st.write(st.session_state.password_vault)
    if st.button("🔄 Générer 10 nouveaux codes de test"):
      st.session_state.password_vault = generate_test_passwords(10)
      st.rerun()

    st.write("---")
    st.write("### 📈 Bilan des Revenus")
    if st.session_state.sales_history:
      df = pd.DataFrame(st.session_state.sales_history)
      st.metric(
          "Total Encaissé", f"{df['Total (FC)'].sum():,} FC".replace(",", " ")
      )
      st.dataframe(df, use_container_width=True)

      if st.button("🗑️ Effacer l'historique"):
        st.session_state.sales_history = []
        st.rerun()

# Pied de page
st.markdown(
    """
    <div class="designer-footer">
        Designed by Eliezer Nlandu
    </div>
""",
    unsafe_allow_html=True,
)
