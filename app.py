import math
import requests
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt


# ============================================================
# PAGE SETUP
# ============================================================

st.set_page_config(
    page_title="Negotiation RPG Decision Support",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Negotiation RPG Decision Support System")

st.caption(
    "Live offer analysis, projected RPG scoring, shared accepted deals, "
    "weighted-average pricing, Flex analysis, and win-win package comparison."
)

st.info(
    "The score model follows the structure observed directly on the RPG dashboard. "
    "Quality/Delivery Flex uses the observed rule of 1 Flex per 100 units per gap level. "
    "Different-counterparty bonus remains an estimate until more live RPG data is collected."
)


# ============================================================
# CONSTANTS
# ============================================================

QUALITY = {
    "Low": 1,
    "Medium": 2,
    "High": 3
}

DELIVERY = {
    "Slow": 1,
    "Medium": 2,
    "Fast": 3
}


def safe_index(options, value, default=0):
    try:
        return options.index(value)
    except Exception:
        return default


# ============================================================
# SUPABASE
# ============================================================

SUPABASE_AVAILABLE = False

try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

    HEADERS = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

    SUPABASE_AVAILABLE = True

except Exception:
    SUPABASE_AVAILABLE = False


# ============================================================
# ROUND SETTINGS DATABASE
# ============================================================

def load_round_settings():

    if not SUPABASE_AVAILABLE:
        return None

    url = (
        f"{SUPABASE_URL}/rest/v1/"
        "round_settings?id=eq.1&select=*"
    )

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=10
    )

    response.raise_for_status()

    data = response.json()

    return data[0] if data else None


def save_round_settings(settings):

    if not SUPABASE_AVAILABLE:
        raise RuntimeError(
            "Supabase is not configured."
        )

    url = (
        f"{SUPABASE_URL}/rest/v1/"
        "round_settings?id=eq.1"
    )

    response = requests.patch(
        url,
        headers={
            **HEADERS,
            "Prefer": "return=minimal"
        },
        json=settings,
        timeout=10
    )

    response.raise_for_status()


# ============================================================
# ACCEPTED DEALS DATABASE
# ============================================================

def load_accepted_deals(round_number):

    if not SUPABASE_AVAILABLE:
        return []

    url = (
        f"{SUPABASE_URL}/rest/v1/"
        f"accepted_deals?"
        f"rpg_round=eq.{int(round_number)}"
        f"&order=created_at.asc"
        f"&select=*"
    )

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=10
    )

    response.raise_for_status()

    return response.json()


def add_accepted_deal(deal):

    if not SUPABASE_AVAILABLE:
        raise RuntimeError(
            "Supabase is not configured."
        )

    url = (
        f"{SUPABASE_URL}/rest/v1/"
        "accepted_deals"
    )

    response = requests.post(
        url,
        headers={
            **HEADERS,
            "Prefer": "return=representation"
        },
        json=deal,
        timeout=10
    )

    response.raise_for_status()

    return response.json()


def update_deal_status(
    database_id,
    new_status
):

    url = (
        f"{SUPABASE_URL}/rest/v1/"
        f"accepted_deals?id=eq.{database_id}"
    )

    response = requests.patch(
        url,
        headers={
            **HEADERS,
            "Prefer": "return=minimal"
        },
        json={
            "status": new_status
        },
        timeout=10
    )

    response.raise_for_status()


def delete_deal(database_id):

    url = (
        f"{SUPABASE_URL}/rest/v1/"
        f"accepted_deals?id=eq.{database_id}"
    )

    response = requests.delete(
        url,
        headers=HEADERS,
        timeout=10
    )

    response.raise_for_status()


# ============================================================
# LOAD ROUND
# ============================================================

saved = None

if SUPABASE_AVAILABLE:

    try:
        saved = load_round_settings()

    except Exception as e:
        st.warning(
            f"Could not load shared round settings: {e}"
        )

else:
    st.warning(
        "Supabase is unavailable. "
        "The calculator still works, but shared saving is disabled."
    )


# ============================================================
# DEFAULTS
# ============================================================

default_round = (
    int(saved.get("rpg_round", 0))
    if saved else 0
)

default_product = (
    saved.get("product_name", "Pet Feeder")
    if saved else "Pet Feeder"
)

default_base_price = (
    float(saved.get("base_price", 320))
    if saved else 320.0
)

default_base_units = (
    int(saved.get("base_units", 6000))
    if saved else 6000
)

default_role = (
    saved.get("role", "Seller")
    if saved else "Seller"
)

default_resistance = (
    float(saved.get("resistance", 291.2))
    if saved else 291.2
)

default_flex = (
    float(saved.get("current_flex", 13))
    if saved else 13.0
)

default_importance = (
    int(saved.get("importance", 3))
    if saved else 3
)

default_target_units = (
    int(saved.get(
        "target_units",
        default_base_units
    ))
    if saved else default_base_units
)

default_max_purchase = (
    int(saved.get(
        "max_purchase",
        default_target_units
    ))
    if saved else default_target_units
)

default_quality = (
    saved.get("start_quality", "High")
    if saved else "High"
)

default_delivery = (
    saved.get("start_delivery", "Fast")
    if saved else "Fast"
)


# ============================================================
# SIDEBAR — ROUND
# ============================================================

st.sidebar.header("🎯 Shared Round Setup")

rpg_round = st.sidebar.number_input(
    "RPG Round",
    min_value=0,
    max_value=20,
    value=default_round,
    step=1,
    key="rpg_round"
)

product_name = st.sidebar.text_input(
    "Product",
    value=default_product,
    key="product_name"
)

base_price = st.sidebar.number_input(
    "Base Price",
    min_value=0.01,
    value=default_base_price,
    step=1.0,
    key="base_price"
)

base_units = st.sidebar.number_input(
    "Base Units",
    min_value=1,
    value=default_base_units,
    step=100,
    key="base_units"
)


# ============================================================
# SIDEBAR — POSITION
# ============================================================

st.sidebar.header("🎮 Negotiation Position")

role_options = [
    "Seller",
    "Buyer"
]

role = st.sidebar.selectbox(
    "Role",
    role_options,
    index=safe_index(
        role_options,
        default_role
    ),
    key="role"
)

resistance = st.sidebar.number_input(
    "Resistance Price",
    min_value=0.01,
    value=default_resistance,
    step=0.1,
    key="resistance"
)

importance = st.sidebar.slider(
    "Importance",
    min_value=1,
    max_value=6,
    value=max(
        1,
        min(6, default_importance)
    ),
    key="importance"
)

target_units = st.sidebar.number_input(
    "Target Units",
    min_value=1,
    value=default_target_units,
    step=100,
    key="target_units"
)

if role == "Buyer":

    max_purchase = st.sidebar.number_input(
        "Max Purchase",
        min_value=int(target_units),
        value=max(
            int(target_units),
            default_max_purchase
        ),
        step=100,
        key="max_purchase"
    )

else:
    max_purchase = None


quality_names = list(
    QUALITY.keys()
)

delivery_names = list(
    DELIVERY.keys()
)

start_quality_name = st.sidebar.selectbox(
    "Starting Quality",
    quality_names,
    index=safe_index(
        quality_names,
        default_quality,
        2 if role == "Seller" else 0
    ),
    key="start_quality"
)

start_delivery_name = st.sidebar.selectbox(
    "Starting Delivery",
    delivery_names,
    index=safe_index(
        delivery_names,
        default_delivery,
        2 if role == "Seller" else 0
    ),
    key="start_delivery"
)

start_quality = QUALITY[
    start_quality_name
]

start_delivery = DELIVERY[
    start_delivery_name
]


# ============================================================
# SIDEBAR — LIVE RPG STATE
# ============================================================

st.sidebar.header("📡 Current Live RPG State")

st.sidebar.caption(
    "Copy these numbers from the real RPG dashboard."
)

current_completed_units = st.sidebar.number_input(
    "Completed Units Now",
    min_value=0,
    value=800,
    step=100,
    key="current_completed_units"
)

current_weighted_price = st.sidebar.number_input(
    "Current Weighted Avg. Price",
    min_value=0.01,
    value=float(base_price),
    step=1.0,
    key="current_weighted_price"
)

current_flex = st.sidebar.number_input(
    "Current Flex",
    value=default_flex,
    step=1.0,
    key="current_flex"
)


# ============================================================
# SAVE ROUND SETTINGS
# ============================================================

if st.sidebar.button(
    "💾 Save Shared Round Setup",
    use_container_width=True
):

    settings = {
        "rpg_round":
            int(rpg_round),

        "product_name":
            product_name,

        "base_price":
            float(base_price),

        "base_units":
            int(base_units),

        "role":
            role,

        "resistance":
            float(resistance),

        "current_flex":
            float(current_flex),

        "importance":
            int(importance),

        "target_units":
            int(target_units),

        "max_purchase":
            int(max_purchase)
            if max_purchase is not None
            else 0,

        "start_quality":
            start_quality_name,

        "start_delivery":
            start_delivery_name
    }

    try:
        save_round_settings(
            settings
        )

        st.sidebar.success(
            "Shared round setup saved."
        )

        st.rerun()

    except Exception as e:

        st.sidebar.error(
            f"Save failed: {e}"
        )


# ============================================================
# REAL RPG CALCULATION FUNCTIONS
# ============================================================

def price_gap_percent(
    role,
    weighted_price,
    resistance
):

    if role == "Seller":

        return (
            (
                weighted_price
                - resistance
            )
            / resistance
            * 100
        )

    return (
        (
            resistance
            - weighted_price
        )
        / resistance
        * 100
    )


def quality_delivery_gaps(
    role,
    start_quality,
    start_delivery,
    deal_quality,
    deal_delivery
):

    if role == "Seller":

        quality_gap = (
            start_quality
            - deal_quality
        )

        delivery_gap = (
            start_delivery
            - deal_delivery
        )

    else:

        quality_gap = (
            deal_quality
            - start_quality
        )

        delivery_gap = (
            deal_delivery
            - start_delivery
        )

    return (
        quality_gap,
        delivery_gap
    )


def deal_flex_change(
    role,
    start_quality,
    start_delivery,
    deal_quality,
    deal_delivery,
    units
):
    """
    Observed live RPG rule:
    1 gap level = 1 Flex per 100 units.

    Positive gap = gain Flex.
    Negative gap = spend Flex.
    """

    q_gap, d_gap = (
        quality_delivery_gaps(
            role,
            start_quality,
            start_delivery,
            deal_quality,
            deal_delivery
        )
    )

    total_gap = (
        q_gap + d_gap
    )

    flex_change = (
        total_gap
        * units
        / 100
    )

    return (
        flex_change,
        q_gap,
        d_gap
    )


def inventory_ratio(
    completed_units,
    target_units
):

    if target_units <= 0:
        return 0

    ratio = (
        completed_units
        / target_units
    )

    ratio = min(
        ratio,
        1.0
    )

    # Matches the observed RPG style:
    # 800 / 6000 = 0.1333 -> 0.13
    return round(
        ratio,
        2
    )


def rpg_score(
    price_gap_pct,
    flex_points,
    importance,
    inventory
):

    return (
        (
            price_gap_pct
            + flex_points
        )
        * importance
        * inventory
    )


def weighted_average_price(
    current_units,
    current_avg_price,
    new_units,
    new_price
):

    total_units = (
        current_units
        + new_units
    )

    if total_units <= 0:
        return 0

    weighted_value = (
        current_units
        * current_avg_price
        + new_units
        * new_price
    )

    return (
        weighted_value
        / total_units
    )


def seller_overproduction_cost(
    total_sold,
    target_units
):

    if total_sold <= target_units:
        return 0

    ten_percent = (
        target_units
        * 0.10
    )

    excess = (
        total_sold
        - target_units
    )

    return math.ceil(
        excess
        / ten_percent
    )


def qualifying_group_bonus(
    deals,
    target_units
):
    """
    Experimental interpretation:
    +1 per distinct counterparty whose active volume
    reaches at least 10% of target Units.

    Based on the live dashboard note.
    """

    if not deals:
        return 0

    df = pd.DataFrame(
        deals
    )

    active = df[
        df["status"].isin(
            [
                "Accepted",
                "Submitted",
                "Completed"
            ]
        )
    ]

    if active.empty:
        return 0

    threshold = (
        target_units * 0.10
    )

    grouped = (
        active
        .groupby(
            "counterparty_group"
        )["units"]
        .sum()
    )

    qualifying = (
        grouped >= threshold
    ).sum()

    return int(
        qualifying
    )


# ============================================================
# CURRENT SCORE CHECK
# ============================================================

current_inventory = (
    inventory_ratio(
        current_completed_units,
        target_units
    )
)

current_price_gap = (
    price_gap_percent(
        role,
        current_weighted_price,
        resistance
    )
)

current_score_estimate = (
    rpg_score(
        current_price_gap,
        current_flex,
        importance,
        current_inventory
    )
)


# ============================================================
# ROUND SUMMARY
# ============================================================

st.subheader(
    f"RPG {rpg_round} — {product_name}"
)

m1, m2, m3, m4, m5 = (
    st.columns(5)
)

m1.metric(
    "Base Price",
    f"{base_price:.2f}"
)

m2.metric(
    "Resistance",
    f"{resistance:.2f}"
)

m3.metric(
    "Current Flex",
    f"{current_flex:.2f}"
)

m4.metric(
    "Inventory",
    f"{current_inventory * 100:.0f}%"
)

m5.metric(
    "Calculated Current Score",
    f"{current_score_estimate:.2f}"
)

st.caption(
    "Compare 'Calculated Current Score' with the real RPG dashboard. "
    "If they match, the core model is aligned with the live game."
)


# ============================================================
# TABS
# ============================================================

tabs = st.tabs([
    "⚖️ Offer Comparator",
    "✅ Shared Accepted Deals",
    "📈 Round Projection",
    "💱 Price vs Flex",
    "🤝 Win-Win Packages"
])


# ============================================================
# TAB 1 — OFFER COMPARATOR
# ============================================================

with tabs[0]:

    st.header(
        "Offer A / B / C Comparison"
    )

    st.write(
        "Each offer is projected from your CURRENT live RPG state."
    )

    if role == "Seller":

        defaults = [
            (
                base_price + 20,
                "High",
                "Fast"
            ),
            (
                base_price + 10,
                "Medium",
                "Medium"
            ),
            (
                base_price,
                "Low",
                "Slow"
            )
        ]

    else:

        defaults = [
            (
                max(
                    0.01,
                    base_price - 20
                ),
                "Low",
                "Slow"
            ),
            (
                max(
                    0.01,
                    base_price - 10
                ),
                "Medium",
                "Medium"
            ),
            (
                base_price,
                "High",
                "Fast"
            )
        ]

    offer_results = []

    cols = st.columns(3)

    for i, col in enumerate(cols):

        letter = chr(
            65 + i
        )

        with col:

            st.subheader(
                f"Offer {letter}"
            )

            p = st.number_input(
                f"Price {letter}",
                min_value=0.01,
                value=float(
                    defaults[i][0]
                ),
                step=1.0,
                key=f"price_{letter}"
            )

            u = st.number_input(
                f"Units {letter}",
                min_value=1,
                value=2000,
                step=100,
                key=f"units_{letter}"
            )

            q_name = st.selectbox(
                f"Quality {letter}",
                quality_names,
                index=safe_index(
                    quality_names,
                    defaults[i][1]
                ),
                key=f"quality_{letter}"
            )

            d_name = st.selectbox(
                f"Delivery {letter}",
                delivery_names,
                index=safe_index(
                    delivery_names,
                    defaults[i][2]
                ),
                key=f"delivery_{letter}"
            )

            new_weighted_price = (
                weighted_average_price(
                    current_completed_units,
                    current_weighted_price,
                    u,
                    p
                )
            )

            flex_change, q_gap, d_gap = (
                deal_flex_change(
                    role,
                    start_quality,
                    start_delivery,
                    QUALITY[q_name],
                    DELIVERY[d_name],
                    u
                )
            )

            projected_flex = (
                current_flex
                + flex_change
            )

            projected_units = (
                current_completed_units
                + u
            )

            overproduction = 0

            if role == "Seller":

                overproduction = (
                    seller_overproduction_cost(
                        projected_units,
                        target_units
                    )
                )

                projected_flex -= (
                    overproduction
                )

            projected_inventory = (
                inventory_ratio(
                    projected_units,
                    target_units
                )
            )

            projected_gap = (
                price_gap_percent(
                    role,
                    new_weighted_price,
                    resistance
                )
            )

            projected_score = (
                rpg_score(
                    projected_gap,
                    projected_flex,
                    importance,
                    projected_inventory
                )
            )

            buyer_invalid = (
                role == "Buyer"
                and projected_units
                > max_purchase
            )

            if buyer_invalid:
                projected_score = 0

            offer_results.append({
                "Offer":
                    f"Offer {letter}",

                "Price":
                    p,

                "Units":
                    u,

                "Quality":
                    q_name,

                "Delivery":
                    d_name,

                "Q Gap":
                    q_gap,

                "D Gap":
                    d_gap,

                "Flex Δ":
                    flex_change,

                "Projected Flex":
                    projected_flex,

                "Weighted Price":
                    new_weighted_price,

                "Projected Units":
                    projected_units,

                "Inventory %":
                    projected_inventory * 100,

                "Price Gap %":
                    projected_gap,

                "Projected Score":
                    projected_score
            })

    offer_df = pd.DataFrame(
        offer_results
    )

    st.dataframe(
        offer_df.style.format({
            "Price":
                "{:.2f}",

            "Flex Δ":
                "{:.2f}",

            "Projected Flex":
                "{:.2f}",

            "Weighted Price":
                "{:.2f}",

            "Inventory %":
                "{:.0f}",

            "Price Gap %":
                "{:.2f}",

            "Projected Score":
                "{:.2f}"
        }),
        use_container_width=True,
        hide_index=True
    )

    best = offer_df.loc[
        offer_df[
            "Projected Score"
        ].idxmax()
    ]

    st.success(
        f"Highest projected score: "
        f"{best['Offer']} — "
        f"{best['Projected Score']:.2f}"
    )


# ============================================================
# TAB 2 — SHARED ACCEPTED DEALS
# ============================================================

with tabs[1]:

    st.header(
        "✅ Shared Accepted Deals"
    )

    st.caption(
        "This is your team's coordination record. "
        "The official deal still needs to be submitted correctly in the RPG."
    )

    with st.form(
        "accepted_form",
        clear_on_submit=True
    ):

        c1, c2, c3 = (
            st.columns(3)
        )

        with c1:

            counterparty = (
                st.text_input(
                    "Counterparty Group"
                )
            )

            deal_id = (
                st.text_input(
                    "Deal ID"
                )
            )

        with c2:

            agreed_price = (
                st.number_input(
                    "Agreed Price",
                    min_value=0.01,
                    value=float(
                        base_price
                    ),
                    step=1.0
                )
            )

            agreed_units = (
                st.number_input(
                    "Agreed Units",
                    min_value=1,
                    value=1000,
                    step=100
                )
            )

        with c3:

            agreed_quality = (
                st.selectbox(
                    "Agreed Quality",
                    quality_names
                )
            )

            agreed_delivery = (
                st.selectbox(
                    "Agreed Delivery",
                    delivery_names
                )
            )

        accepted_by = st.text_input(
            "Accepted By"
        )

        status = st.selectbox(
            "Status",
            [
                "Accepted",
                "Submitted",
                "Completed",
                "Cancelled"
            ]
        )

        notes = st.text_area(
            "Notes"
        )

        submit_deal = (
            st.form_submit_button(
                "✅ Save Accepted Deal",
                use_container_width=True
            )
        )

        if submit_deal:

            if not counterparty:

                st.error(
                    "Enter the counterparty group."
                )

            elif not deal_id:

                st.error(
                    "Enter the Deal ID."
                )

            else:

                flex_delta, q_gap, d_gap = (
                    deal_flex_change(
                        role,
                        start_quality,
                        start_delivery,
                        QUALITY[
                            agreed_quality
                        ],
                        DELIVERY[
                            agreed_delivery
                        ],
                        agreed_units
                    )
                )

                deal = {
                    "rpg_round":
                        int(rpg_round),

                    "product_name":
                        product_name,

                    "counterparty_group":
                        counterparty,

                    "deal_id":
                        deal_id,

                    "our_role":
                        role,

                    "price":
                        float(
                            agreed_price
                        ),

                    "units":
                        int(
                            agreed_units
                        ),

                    "quality":
                        agreed_quality,

                    "delivery":
                        agreed_delivery,

                    "status":
                        status,

                    "accepted_by":
                        accepted_by,

                    "notes":
                        notes
                }

                try:

                    add_accepted_deal(
                        deal
                    )

                    st.success(
                        f"Saved. "
                        f"Estimated Flex change: "
                        f"{flex_delta:+.2f}"
                    )

                    st.rerun()

                except requests.HTTPError as e:

                    if (
                        e.response is not None
                        and
                        e.response.status_code
                        == 409
                    ):

                        st.error(
                            "Deal ID already exists."
                        )

                    else:

                        st.error(
                            f"Save failed: {e}"
                        )

                except Exception as e:

                    st.error(
                        f"Save failed: {e}"
                    )


    # LOAD DEALS

    try:

        shared_deals = (
            load_accepted_deals(
                rpg_round
            )
        )

    except Exception as e:

        shared_deals = []

        st.error(
            f"Could not load deals: {e}"
        )


    if shared_deals:

        deal_df = pd.DataFrame(
            shared_deals
        )

        # calculate Flex effect per deal

        flex_changes = []

        for _, row in deal_df.iterrows():

            flex_delta, _, _ = (
                deal_flex_change(
                    row["our_role"],
                    start_quality,
                    start_delivery,
                    QUALITY[
                        row["quality"]
                    ],
                    DELIVERY[
                        row["delivery"]
                    ],
                    row["units"]
                )
            )

            flex_changes.append(
                flex_delta
            )

        deal_df[
            "estimated_flex_change"
        ] = flex_changes

        visible_cols = [
            "counterparty_group",
            "deal_id",
            "our_role",
            "price",
            "units",
            "quality",
            "delivery",
            "estimated_flex_change",
            "status",
            "accepted_by"
        ]

        st.dataframe(
            deal_df[
                visible_cols
            ],
            use_container_width=True,
            hide_index=True
        )


        # STATUS UPDATE

        st.subheader(
            "Update Deal"
        )

        selected_id = st.selectbox(
            "Deal ID",
            deal_df[
                "deal_id"
            ].tolist(),
            key="selected_status_id"
        )

        selected_row = deal_df[
            deal_df["deal_id"]
            == selected_id
        ].iloc[0]

        new_status = st.selectbox(
            "New Status",
            [
                "Accepted",
                "Submitted",
                "Completed",
                "Cancelled"
            ],
            index=safe_index(
                [
                    "Accepted",
                    "Submitted",
                    "Completed",
                    "Cancelled"
                ],
                selected_row[
                    "status"
                ]
            ),
            key="new_status"
        )

        c1, c2 = st.columns(2)

        with c1:

            if st.button(
                "Update Status",
                use_container_width=True
            ):

                try:

                    update_deal_status(
                        int(
                            selected_row[
                                "id"
                            ]
                        ),
                        new_status
                    )

                    st.success(
                        "Status updated."
                    )

                    st.rerun()

                except Exception as e:

                    st.error(
                        f"Update failed: {e}"
                    )

        with c2:

            if st.button(
                "Delete Deal",
                use_container_width=True
            ):

                try:

                    delete_deal(
                        int(
                            selected_row[
                                "id"
                            ]
                        )
                    )

                    st.success(
                        "Deal deleted."
                    )

                    st.rerun()

                except Exception as e:

                    st.error(
                        f"Delete failed: {e}"
                    )

    else:

        st.info(
            "No shared accepted deals yet."
        )


# ============================================================
# TAB 3 — ROUND PROJECTION
# ============================================================

with tabs[2]:

    st.header(
        "📈 Full Round Projection"
    )

    st.write(
        "Uses your live completed state plus deals that are "
        "Accepted or Submitted but not yet reflected in the live dashboard."
    )

    pending_deals = []

    try:

        all_shared = (
            load_accepted_deals(
                rpg_round
            )
        )

        pending_deals = [
            d
            for d in all_shared
            if d["status"]
            in [
                "Accepted",
                "Submitted"
            ]
        ]

    except Exception:
        pending_deals = []


    projected_units = (
        current_completed_units
    )

    weighted_value = (
        current_completed_units
        * current_weighted_price
    )

    projected_flex = (
        current_flex
    )


    for deal in pending_deals:

        projected_units += (
            deal["units"]
        )

        weighted_value += (
            deal["units"]
            * deal["price"]
        )

        flex_delta, _, _ = (
            deal_flex_change(
                role,
                start_quality,
                start_delivery,
                QUALITY[
                    deal["quality"]
                ],
                DELIVERY[
                    deal["delivery"]
                ],
                deal["units"]
            )
        )

        projected_flex += (
            flex_delta
        )


    if projected_units > 0:

        projected_avg = (
            weighted_value
            / projected_units
        )

    else:
        projected_avg = 0


    bonus = (
        qualifying_group_bonus(
            pending_deals,
            target_units
        )
    )

    projected_flex += bonus


    overproduction_cost = 0

    if role == "Seller":

        overproduction_cost = (
            seller_overproduction_cost(
                projected_units,
                target_units
            )
        )

        projected_flex -= (
            overproduction_cost
        )


    projected_inventory = (
        inventory_ratio(
            projected_units,
            target_units
        )
    )


    projected_gap = (
        price_gap_percent(
            role,
            projected_avg,
            resistance
        )
        if projected_avg > 0
        else 0
    )


    projected_score = (
        rpg_score(
            projected_gap,
            projected_flex,
            importance,
            projected_inventory
        )
    )


    if (
        role == "Buyer"
        and projected_units
        > max_purchase
    ):

        projected_score = 0


    a, b, c, d = (
        st.columns(4)
    )

    a.metric(
        "Projected Units",
        f"{projected_units:,}"
    )

    b.metric(
        "Projected Avg. Price",
        f"{projected_avg:.2f}"
    )

    c.metric(
        "Projected Flex",
        f"{projected_flex:.2f}"
    )

    d.metric(
        "Projected Score",
        f"{projected_score:.2f}"
    )


    st.write(
        f"Inventory completion: "
        f"**{projected_inventory * 100:.0f}%**"
    )

    st.write(
        f"Price Gap: "
        f"**{projected_gap:.2f}%**"
    )

    st.write(
        f"Estimated different-group bonus: "
        f"**+{bonus} Flex**"
    )

    if role == "Seller":

        st.write(
            f"Estimated overproduction cost: "
            f"**-{overproduction_cost} Flex**"
        )

    if (
        role == "Buyer"
        and projected_units
        > max_purchase
    ):

        st.error(
            "⚠️ Projected units exceed Max Purchase. "
            "Projected score set to 0."
        )


# ============================================================
# TAB 4 — PRICE VS FLEX
# ============================================================

with tabs[3]:

    st.header(
        "💱 Price vs Flex Trade-off"
    )

    one_flex_price_value = (
        resistance
        / 100
    )

    st.metric(
        "Approx. Price Equivalent of 1 Flex",
        f"{one_flex_price_value:.2f}"
    )

    st.caption(
        "Because 1 Flex contributes approximately like "
        "1 percentage point in the score equation."
    )

    flex_amount = st.slider(
        "Flex Difference",
        min_value=1,
        max_value=50,
        value=5
    )

    equivalent_price = (
        flex_amount
        * one_flex_price_value
    )

    st.metric(
        f"{flex_amount} Flex ≈ price difference",
        f"{equivalent_price:.2f}"
    )

    st.write(
        "Example: if giving Medium instead of High quality "
        "creates 10 extra Flex, you can compare that with the "
        "price concession required by the buyer."
    )


# ============================================================
# TAB 5 — WIN-WIN PACKAGES
# ============================================================

with tabs[4]:

    st.header(
        "🤝 Win-Win Package Generator"
    )

    spread = st.slider(
        "Price Difference Between Packages",
        1.0,
        50.0,
        10.0,
        1.0
    )

    units = st.number_input(
        "Units per Package",
        min_value=100,
        value=2000,
        step=100
    )


    if role == "Seller":

        package_specs = [
            (
                "Premium",
                base_price
                + spread * 2,
                "High",
                "Fast"
            ),
            (
                "Balanced",
                base_price
                + spread,
                "Medium",
                "Medium"
            ),
            (
                "Economy",
                base_price,
                "Low",
                "Slow"
            )
        ]

    else:

        package_specs = [
            (
                "Economy",
                max(
                    0.01,
                    base_price
                    - spread * 2
                ),
                "Low",
                "Slow"
            ),
            (
                "Balanced",
                max(
                    0.01,
                    base_price
                    - spread
                ),
                "Medium",
                "Medium"
            ),
            (
                "Premium Service",
                base_price,
                "High",
                "Fast"
            )
        ]


    package_results = []

    for (
        name,
        price,
        q_name,
        d_name
    ) in package_specs:

        flex_delta, q_gap, d_gap = (
            deal_flex_change(
                role,
                start_quality,
                start_delivery,
                QUALITY[q_name],
                DELIVERY[d_name],
                units
            )
        )

        new_avg = (
            weighted_average_price(
                current_completed_units,
                current_weighted_price,
                units,
                price
            )
        )

        new_units = (
            current_completed_units
            + units
        )

        new_flex = (
            current_flex
            + flex_delta
        )

        new_inventory = (
            inventory_ratio(
                new_units,
                target_units
            )
        )

        new_gap = (
            price_gap_percent(
                role,
                new_avg,
                resistance
            )
        )

        score = (
            rpg_score(
                new_gap,
                new_flex,
                importance,
                new_inventory
            )
        )

        package_results.append({
            "Package":
                name,

            "Price":
                price,

            "Quality":
                q_name,

            "Delivery":
                d_name,

            "Flex Δ":
                flex_delta,

            "Projected Avg Price":
                new_avg,

            "Projected Score":
                score
        })


    package_df = pd.DataFrame(
        package_results
    )

    st.dataframe(
        package_df.style.format({
            "Price":
                "{:.2f}",

            "Flex Δ":
                "{:+.2f}",

            "Projected Avg Price":
                "{:.2f}",

            "Projected Score":
                "{:.2f}"
        }),
        use_container_width=True,
        hide_index=True
    )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "Important: Always compare this calculator with the live RPG dashboard. "
    "If the calculated current score differs from the RPG score, record the "
    "difference so the model can be refined."
)