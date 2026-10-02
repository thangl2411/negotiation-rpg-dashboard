import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import requests


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
    "Compare offers, analyze Price vs Flex trade-offs, track deals, "
    "build win-win packages, and test negotiation strategies."
)

st.info(
    "This is an experimental decision-support model. "
    "The exact Flex-generation formula is not fully published, "
    "so Flex estimates can be adjusted and later calibrated using real RPG results."
)


# ============================================================
# SESSION STATE
# ============================================================

if "deals" not in st.session_state:
    st.session_state.deals = []

if "calibration" not in st.session_state:
    st.session_state.calibration = []

if "calibrated_weights" not in st.session_state:
    st.session_state.calibrated_weights = None


# ============================================================
# QUALITY / DELIVERY LEVELS
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
# SUPABASE CONNECTION
# ============================================================

SUPABASE_AVAILABLE = False
SUPABASE_ERROR = None

try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

    HEADERS = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

    SUPABASE_AVAILABLE = True

except Exception as e:
    SUPABASE_ERROR = str(e)


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

    if not data:
        return None

    return data[0]


def save_round_settings(settings):

    if not SUPABASE_AVAILABLE:
        raise RuntimeError(
            "Supabase secrets are not configured."
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
# LOAD SAVED SETTINGS
# ============================================================

saved = None

if SUPABASE_AVAILABLE:

    try:
        saved = load_round_settings()

    except Exception as e:
        st.warning(
            f"Could not load shared settings from Supabase: {e}"
        )

else:

    st.warning(
        "Supabase persistence is not active in this environment. "
        "The app will still work, but shared round settings will not be saved."
    )


# ============================================================
# DEFAULT VALUES
# ============================================================

default_round = int(
    saved.get("rpg_round", 0)
) if saved else 0

default_product = (
    saved.get("product_name", "Pet Feeder")
    if saved else "Pet Feeder"
)

default_base_price = float(
    saved.get("base_price", 320.0)
) if saved else 320.0

default_base_units = int(
    saved.get("base_units", 6000)
) if saved else 6000

default_role = (
    saved.get("role", "Seller")
    if saved else "Seller"
)

default_resistance = float(
    saved.get("resistance", 291.2)
) if saved else 291.2

default_flex = float(
    saved.get("current_flex", 2.0)
) if saved else 2.0

default_importance = int(
    saved.get("importance", 5)
) if saved else 5

default_target_units = int(
    saved.get("target_units", default_base_units)
) if saved else default_base_units

default_max_purchase = int(
    saved.get("max_purchase", default_target_units)
) if saved else default_target_units

default_quality = (
    saved.get("start_quality", "High")
    if saved else "High"
)

default_delivery = (
    saved.get("start_delivery", "Fast")
    if saved else "Fast"
)


# ============================================================
# SIDEBAR — SHARED ROUND SETUP
# ============================================================

st.sidebar.header("🎯 Shared Round Setup")

rpg_round = st.sidebar.number_input(
    "RPG Round",
    min_value=0,
    max_value=20,
    value=default_round,
    step=1,
    key="setup_rpg_round"
)

product_name = st.sidebar.text_input(
    "Product Name",
    value=default_product,
    key="setup_product_name"
)

base_price = st.sidebar.number_input(
    "Base Price",
    min_value=0.01,
    value=default_base_price,
    step=1.0,
    key="setup_base_price"
)

base_units = st.sidebar.number_input(
    "Base Units",
    min_value=1,
    value=default_base_units,
    step=100,
    key="setup_base_units"
)


# ============================================================
# SIDEBAR — RPG POSITION
# ============================================================

st.sidebar.header("🎮 RPG Position")

role_options = ["Seller", "Buyer"]

role = st.sidebar.selectbox(
    "Role",
    role_options,
    index=safe_index(
        role_options,
        default_role,
        0
    ),
    key="setup_role"
)

resistance = st.sidebar.number_input(
    "Resistance Price",
    min_value=0.01,
    value=default_resistance,
    step=0.1,
    key="setup_resistance"
)

current_flex = st.sidebar.number_input(
    "Current Flex",
    min_value=0.0,
    value=default_flex,
    step=1.0,
    key="setup_current_flex"
)

importance = st.sidebar.slider(
    "Importance",
    min_value=1,
    max_value=6,
    value=min(
        max(default_importance, 1),
        6
    ),
    key="setup_importance"
)

target_units = st.sidebar.number_input(
    "Target Units",
    min_value=1,
    value=default_target_units,
    step=100,
    key="setup_target_units"
)

units_already_completed = st.sidebar.number_input(
    "Units Already Completed",
    min_value=0,
    value=0,
    step=100,
    key="units_already_completed"
)

if role == "Buyer":

    safe_max_default = max(
        default_max_purchase,
        int(target_units)
    )

    max_purchase = st.sidebar.number_input(
        "Max Purchase",
        min_value=int(target_units),
        value=safe_max_default,
        step=100,
        key="setup_max_purchase"
    )

else:
    max_purchase = None


# ============================================================
# STARTING QUALITY / DELIVERY
# ============================================================

st.sidebar.header("⚙️ Starting Quality / Delivery")

quality_names = list(QUALITY.keys())
delivery_names = list(DELIVERY.keys())

start_quality_name = st.sidebar.selectbox(
    "Starting Quality",
    quality_names,
    index=safe_index(
        quality_names,
        default_quality,
        2 if role == "Seller" else 0
    ),
    key="setup_start_quality"
)

start_delivery_name = st.sidebar.selectbox(
    "Starting Delivery",
    delivery_names,
    index=safe_index(
        delivery_names,
        default_delivery,
        2 if role == "Seller" else 0
    ),
    key="setup_start_delivery"
)

start_quality = QUALITY[start_quality_name]
start_delivery = DELIVERY[start_delivery_name]


# ============================================================
# SAVE ROUND SETTINGS
# ============================================================

if st.sidebar.button(
    "💾 Save Shared Round Settings",
    use_container_width=True,
    key="save_shared_settings"
):

    settings = {
        "rpg_round": int(rpg_round),
        "product_name": product_name,
        "base_price": float(base_price),
        "base_units": int(base_units),
        "role": role,
        "resistance": float(resistance),
        "current_flex": float(current_flex),
        "importance": int(importance),
        "target_units": int(target_units),
        "max_purchase": (
            int(max_purchase)
            if max_purchase is not None
            else 0
        ),
        "start_quality": start_quality_name,
        "start_delivery": start_delivery_name
    }

    try:

        save_round_settings(settings)

        st.sidebar.success(
            "Saved! Everyone will use these settings."
        )

        st.rerun()

    except Exception as e:

        st.sidebar.error(
            f"Could not save settings: {e}"
        )


if st.sidebar.button(
    "🔄 Reload Shared Settings",
    use_container_width=True,
    key="reload_shared_settings"
):
    st.rerun()


# ============================================================
# FLEX MODEL
# ============================================================

st.sidebar.header("🟣 Experimental Flex Model")

use_calibration = False

if st.session_state.calibrated_weights is not None:

    use_calibration = st.sidebar.checkbox(
        "Use calibrated Flex weights",
        value=True,
        key="use_calibrated_weights"
    )

if use_calibration:

    quality_weight = (
        st.session_state
        .calibrated_weights["quality"]
    )

    delivery_weight = (
        st.session_state
        .calibrated_weights["delivery"]
    )

    st.sidebar.success(
        f"Quality={quality_weight:.2f}, "
        f"Delivery={delivery_weight:.2f}"
    )

else:

    quality_weight = st.sidebar.slider(
        "Flex per Quality-level gap",
        0.0,
        10.0,
        2.0,
        0.5,
        key="quality_weight"
    )

    delivery_weight = st.sidebar.slider(
        "Flex per Delivery-level gap",
        0.0,
        10.0,
        2.0,
        0.5,
        key="delivery_weight"
    )

volume_weighting = st.sidebar.checkbox(
    "Scale Flex by deal volume",
    value=True,
    key="volume_weighting"
)


# ============================================================
# CURRENT ROUND BANNER
# ============================================================

st.subheader(
    f"RPG {rpg_round} — {product_name}"
)

c1, c2, c3, c4 = st.columns(4)

c1.metric(
    "Base Price",
    f"{base_price:.2f}"
)

c2.metric(
    "Base Units",
    f"{base_units:,}"
)

c3.metric(
    "Role",
    role
)

c4.metric(
    "Resistance",
    f"{resistance:.2f}"
)


# ============================================================
# CORE FUNCTIONS
# ============================================================

def price_gap_percent(
    role,
    price,
    resistance
):

    if role == "Seller":

        return (
            (price - resistance)
            / resistance
            * 100
        )

    return (
        (resistance - price)
        / resistance
        * 100
    )


def get_gaps(
    role,
    start_quality,
    start_delivery,
    final_quality,
    final_delivery
):

    if role == "Seller":

        q_gap = (
            start_quality
            - final_quality
        )

        d_gap = (
            start_delivery
            - final_delivery
        )

    else:

        q_gap = (
            final_quality
            - start_quality
        )

        d_gap = (
            final_delivery
            - start_delivery
        )

    return (
        max(0, q_gap),
        max(0, d_gap)
    )


def flex_gain(
    role,
    start_quality,
    start_delivery,
    final_quality,
    final_delivery,
    units,
    target_units,
    quality_weight,
    delivery_weight,
    volume_weighting
):

    q_gap, d_gap = get_gaps(
        role,
        start_quality,
        start_delivery,
        final_quality,
        final_delivery
    )

    gain = (
        q_gap * quality_weight
        + d_gap * delivery_weight
    )

    if volume_weighting:

        gain *= (
            units
            / target_units
        )

    return (
        gain,
        q_gap,
        d_gap
    )


def inventory_factor(
    role,
    total_units,
    target_units,
    max_purchase=None
):

    if role == "Buyer":

        if (
            max_purchase is not None
            and total_units > max_purchase
        ):
            return 0.0

    return min(
        total_units / target_units,
        1.0
    )


def experimental_score(
    gap_pct,
    final_flex,
    importance,
    inventory
):

    return (
        (
            max(0, gap_pct)
            + final_flex
        )
        * importance
        * inventory
    )


def evaluate_offer(
    name,
    price,
    units,
    quality_name,
    delivery_name
):

    q = QUALITY[quality_name]
    d = DELIVERY[delivery_name]

    pg = price_gap_percent(
        role,
        price,
        resistance
    )

    fg, qg, dg = flex_gain(
        role,
        start_quality,
        start_delivery,
        q,
        d,
        units,
        target_units,
        quality_weight,
        delivery_weight,
        volume_weighting
    )

    final_flex = (
        current_flex
        + fg
    )

    total_units = (
        units_already_completed
        + units
    )

    inv = inventory_factor(
        role,
        total_units,
        target_units,
        max_purchase
    )

    score = experimental_score(
        pg,
        final_flex,
        importance,
        inv
    )

    if role == "Seller":

        valid_price = (
            price >= resistance
        )

    else:

        valid_price = (
            price <= resistance
        )

    within_max = True

    if role == "Buyer":

        within_max = (
            total_units
            <= max_purchase
        )

    price_component = max(
        0,
        pg
    )

    flex_component = fg

    if (
        price_component
        > flex_component * 1.5
    ):

        strategy = "Price-first"

    elif (
        flex_component
        > price_component * 1.5
    ):

        strategy = "Flex-first"

    else:

        strategy = "Balanced"

    return {
        "Offer": name,
        "Price": price,
        "Units": units,
        "Quality": quality_name,
        "Delivery": delivery_name,
        "Price Gap %": pg,
        "Flex Gain": fg,
        "Final Flex": final_flex,
        "Quality Gap": qg,
        "Delivery Gap": dg,
        "Inventory %": inv * 100,
        "Experimental Score": score,
        "Strategy": strategy,
        "Valid Price": valid_price,
        "Within Max": within_max
    }


def counterpart_proxy(
    role,
    price,
    quality,
    delivery,
    min_price,
    max_price
):

    rng = max(
        max_price - min_price,
        0.01
    )

    q = QUALITY[quality]
    d = DELIVERY[delivery]

    if role == "Seller":

        price_benefit = (
            (max_price - price)
            / rng
            * 100
        )

        service_benefit = (
            (
                (q - 1)
                + (d - 1)
            )
            / 4
            * 100
        )

    else:

        price_benefit = (
            (price - min_price)
            / rng
            * 100
        )

        service_benefit = (
            (
                (3 - q)
                + (3 - d)
            )
            / 4
            * 100
        )

    return (
        0.5 * price_benefit
        + 0.5 * service_benefit
    )


def pareto_mask(
    x,
    y
):

    n = len(x)

    keep = np.ones(
        n,
        dtype=bool
    )

    for i in range(n):

        for j in range(n):

            if i == j:
                continue

            dominates = (
                x[j] >= x[i]
                and y[j] >= y[i]
                and (
                    x[j] > x[i]
                    or y[j] > y[i]
                )
            )

            if dominates:

                keep[i] = False
                break

    return keep


# ============================================================
# TABS
# ============================================================

tabs = st.tabs([
    "⚖️ Offer Comparator",
    "💱 Break-even",
    "📦 Deal Tracker",
    "🤝 Win-Win Packages",
    "📈 Frontier",
    "🧪 Flex Calibration",
    "🎲 Risk Simulation"
])


# ============================================================
# TAB 1 — OFFER COMPARATOR
# ============================================================

with tabs[0]:

    st.header(
        "Offer A / B / C Comparison"
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
                    1,
                    base_price - 20
                ),
                "Low",
                "Slow"
            ),
            (
                max(
                    1,
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

    offers = []

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
                key=f"offer_price_{letter}"
            )

            u = st.number_input(
                f"Units {letter}",
                min_value=1,
                value=min(
                    2000,
                    int(target_units)
                ),
                step=100,
                key=f"offer_units_{letter}"
            )

            q = st.selectbox(
                f"Quality {letter}",
                quality_names,
                index=safe_index(
                    quality_names,
                    defaults[i][1]
                ),
                key=f"offer_quality_{letter}"
            )

            d = st.selectbox(
                f"Delivery {letter}",
                delivery_names,
                index=safe_index(
                    delivery_names,
                    defaults[i][2]
                ),
                key=f"offer_delivery_{letter}"
            )

            offers.append(
                evaluate_offer(
                    f"Offer {letter}",
                    p,
                    u,
                    q,
                    d
                )
            )

    comparison = pd.DataFrame(
        offers
    )

    display_cols = [
        "Offer",
        "Price",
        "Units",
        "Quality",
        "Delivery",
        "Price Gap %",
        "Flex Gain",
        "Final Flex",
        "Inventory %",
        "Experimental Score",
        "Strategy"
    ]

    st.dataframe(
        comparison[
            display_cols
        ].style.format({
            "Price": "{:.2f}",
            "Price Gap %": "{:.2f}",
            "Flex Gain": "{:.2f}",
            "Final Flex": "{:.2f}",
            "Inventory %": "{:.1f}",
            "Experimental Score": "{:.2f}"
        }),
        use_container_width=True
    )

    best_offer = comparison.loc[
        comparison[
            "Experimental Score"
        ].idxmax()
    ]

    st.success(
        f"Highest experimental value: "
        f"{best_offer['Offer']} — "
        f"{best_offer['Strategy']} — "
        f"Score "
        f"{best_offer['Experimental Score']:.2f}"
    )

    for row in offers:

        if not row[
            "Valid Price"
        ]:

            st.error(
                f"{row['Offer']}: "
                "Price violates Resistance."
            )

        if not row[
            "Within Max"
        ]:

            st.error(
                f"{row['Offer']}: "
                "Buyer exceeds Max Purchase."
            )


# ============================================================
# TAB 2 — BREAK EVEN
# ============================================================

with tabs[1]:

    st.header(
        "Price ↔ Flex Break-even"
    )

    one_flex_value = (
        resistance / 100
    )

    st.metric(
        "Approximate price value of 1 Flex",
        f"{one_flex_value:.2f} NTD"
    )

    st.caption(
        "Experimental interpretation: "
        "1 Flex contributes approximately like "
        "1 percentage point of Resistance."
    )

    offer_names = (
        comparison["Offer"]
        .tolist()
    )

    c1, c2 = st.columns(2)

    with c1:

        reference_name = (
            st.selectbox(
                "Reference Offer",
                offer_names,
                index=0,
                key="break_even_reference"
            )
        )

    with c2:

        challenger_name = (
            st.selectbox(
                "Challenger Offer",
                offer_names,
                index=1,
                key="break_even_challenger"
            )
        )

    reference = comparison[
        comparison["Offer"]
        == reference_name
    ].iloc[0]

    challenger = comparison[
        comparison["Offer"]
        == challenger_name
    ].iloc[0]

    price_difference = abs(
        challenger["Price"]
        - reference["Price"]
    )

    flex_needed = (
        price_difference
        / one_flex_value
        if one_flex_value > 0
        else 0
    )

    actual_extra_flex = (
        challenger["Flex Gain"]
        - reference["Flex Gain"]
    )

    b1, b2, b3 = (
        st.columns(3)
    )

    b1.metric(
        "Price Difference",
        f"{price_difference:.2f}"
    )

    b2.metric(
        "Flex Needed to Offset",
        f"{flex_needed:.2f}"
    )

    b3.metric(
        "Extra Flex",
        f"{actual_extra_flex:.2f}"
    )

    if (
        actual_extra_flex
        > flex_needed
    ):

        st.success(
            "Under the experimental model, "
            "the extra Flex is worth more "
            "than the price concession."
        )

    else:

        st.warning(
            "Under the experimental model, "
            "the price advantage is worth more "
            "than the extra Flex."
        )


# ============================================================
# TAB 3 — DEAL TRACKER
# ============================================================

with tabs[2]:

    st.header(
        "Completed Deal Tracker"
    )

    with st.form(
        "deal_form"
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

            deal_price = (
                st.number_input(
                    "Deal Price",
                    min_value=0.01,
                    value=float(
                        base_price
                    ),
                    step=1.0
                )
            )

            deal_units = (
                st.number_input(
                    "Deal Units",
                    min_value=1,
                    value=1000,
                    step=100
                )
            )

        with c3:

            deal_quality = (
                st.selectbox(
                    "Deal Quality",
                    quality_names
                )
            )

            deal_delivery = (
                st.selectbox(
                    "Deal Delivery",
                    delivery_names
                )
            )

        status = st.selectbox(
            "Status",
            [
                "Completed",
                "Waiting",
                "Cancelled"
            ]
        )

        add_deal = (
            st.form_submit_button(
                "Add Deal"
            )
        )

        if add_deal:

            existing_ids = [
                d["Deal ID"]
                for d
                in st.session_state.deals
            ]

            if (
                deal_id
                and deal_id
                in existing_ids
            ):

                st.error(
                    "Duplicate Deal ID."
                )

            else:

                st.session_state.deals.append({
                    "Counterparty":
                        counterparty,
                    "Deal ID":
                        deal_id,
                    "Price":
                        deal_price,
                    "Units":
                        deal_units,
                    "Quality":
                        deal_quality,
                    "Delivery":
                        deal_delivery,
                    "Status":
                        status
                })

                st.success(
                    "Deal added."
                )

    if st.session_state.deals:

        deal_df = pd.DataFrame(
            st.session_state.deals
        )

        st.dataframe(
            deal_df,
            use_container_width=True
        )

        completed = deal_df[
            deal_df["Status"]
            == "Completed"
        ]

        if not completed.empty:

            total_volume = (
                completed["Units"]
                .sum()
            )

            weighted_avg = (
                (
                    completed["Price"]
                    * completed["Units"]
                ).sum()
                / total_volume
            )

            c1, c2, c3 = (
                st.columns(3)
            )

            c1.metric(
                "Completed Units",
                f"{total_volume:,.0f}"
            )

            c2.metric(
                "Weighted Average Price",
                f"{weighted_avg:.2f}"
            )

            completion = min(
                total_volume
                / target_units,
                1
            )

            c3.metric(
                "Target Completion",
                f"{completion * 100:.1f}%"
            )

            if role == "Buyer":

                if (
                    total_volume
                    > max_purchase
                ):

                    st.error(
                        "Max Purchase exceeded."
                    )

            else:

                if (
                    total_volume
                    > target_units
                ):

                    st.warning(
                        "Seller is above target Units. "
                        "Check possible overproduction Flex cost."
                    )

        if st.button(
            "Clear All Deals",
            key="clear_all_deals"
        ):

            st.session_state.deals = []
            st.rerun()

    else:

        st.info(
            "No deals recorded yet."
        )


# ============================================================
# TAB 4 — WIN-WIN PACKAGES
# ============================================================

with tabs[3]:

    st.header(
        "Win-Win Package Generator"
    )

    spread = st.slider(
        "Price step between packages",
        1.0,
        30.0,
        10.0,
        1.0,
        key="package_spread"
    )

    package_units = st.number_input(
        "Package Units",
        min_value=1,
        value=min(
            2000,
            int(target_units)
        ),
        step=100,
        key="package_units"
    )

    if role == "Seller":

        package_data = [
            (
                "Premium",
                base_price
                + 2 * spread,
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

        package_data = [
            (
                "Economy",
                max(
                    0.01,
                    base_price
                    - 2 * spread
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

    packages = []

    for (
        name,
        price,
        q,
        d
    ) in package_data:

        packages.append(
            evaluate_offer(
                name,
                price,
                package_units,
                q,
                d
            )
        )

    package_df = pd.DataFrame(
        packages
    )

    price_min = (
        package_df["Price"]
        .min()
    )

    price_max = (
        package_df["Price"]
        .max()
    )

    package_df[
        "Counterparty Benefit Proxy"
    ] = [
        counterpart_proxy(
            role,
            row["Price"],
            row["Quality"],
            row["Delivery"],
            price_min,
            price_max
        )
        for _, row
        in package_df.iterrows()
    ]

    st.dataframe(
        package_df[
            [
                "Offer",
                "Price",
                "Quality",
                "Delivery",
                "Price Gap %",
                "Flex Gain",
                "Experimental Score",
                "Counterparty Benefit Proxy"
            ]
        ].style.format({
            "Price": "{:.2f}",
            "Price Gap %": "{:.2f}",
            "Flex Gain": "{:.2f}",
            "Experimental Score": "{:.2f}",
            "Counterparty Benefit Proxy": "{:.1f}"
        }),
        use_container_width=True
    )


# ============================================================
# TAB 5 — FRONTIER
# ============================================================

with tabs[4]:

    st.header(
        "Win-Win Negotiation Frontier"
    )

    frontier_units = (
        st.number_input(
            "Units for Frontier Simulation",
            min_value=1,
            value=min(
                2000,
                int(target_units)
            ),
            step=100,
            key="frontier_units"
        )
    )

    price_values = (
        np.linspace(
            max(
                0.01,
                base_price - 30
            ),
            base_price + 30,
            13
        )
    )

    frontier_rows = []

    for p in price_values:

        for q_name in quality_names:

            for d_name in delivery_names:

                result = (
                    evaluate_offer(
                        "Scenario",
                        p,
                        frontier_units,
                        q_name,
                        d_name
                    )
                )

                cp = counterpart_proxy(
                    role,
                    p,
                    q_name,
                    d_name,
                    price_values.min(),
                    price_values.max()
                )

                frontier_rows.append({
                    "Price": p,
                    "Quality": q_name,
                    "Delivery": d_name,
                    "Our Score":
                        result[
                            "Experimental Score"
                        ],
                    "Counterparty Benefit":
                        cp
                })

    frontier_df = pd.DataFrame(
        frontier_rows
    )

    mask = pareto_mask(
        frontier_df[
            "Counterparty Benefit"
        ].values,
        frontier_df[
            "Our Score"
        ].values
    )

    pareto_df = (
        frontier_df[mask]
    )

    fig, ax = plt.subplots(
        figsize=(9, 6)
    )

    ax.scatter(
        frontier_df[
            "Counterparty Benefit"
        ],
        frontier_df[
            "Our Score"
        ],
        alpha=0.25,
        label="All packages"
    )

    ax.scatter(
        pareto_df[
            "Counterparty Benefit"
        ],
        pareto_df[
            "Our Score"
        ],
        color="red",
        label="Pareto Frontier"
    )

    ax.set_xlabel(
        "Counterparty Benefit Proxy"
    )

    ax.set_ylabel(
        "Our Experimental Score"
    )

    ax.set_title(
        "Win-Win Package Frontier"
    )

    ax.legend()

    ax.grid(
        alpha=0.3
    )

    st.pyplot(fig)

    st.dataframe(
        pareto_df.sort_values(
            "Our Score",
            ascending=False
        ),
        use_container_width=True
    )


# ============================================================
# TAB 6 — FLEX CALIBRATION
# ============================================================

with tabs[5]:

    st.header(
        "Calibrate Flex Using Real RPG Results"
    )

    with st.form(
        "calibration_form"
    ):

        c1, c2, c3 = (
            st.columns(3)
        )

        with c1:

            cal_units = (
                st.number_input(
                    "Observed Deal Units",
                    min_value=1,
                    value=1000,
                    step=100
                )
            )

        with c2:

            cal_quality = (
                st.selectbox(
                    "Observed Deal Quality",
                    quality_names,
                    key="cal_quality"
                )
            )

        with c3:

            cal_delivery = (
                st.selectbox(
                    "Observed Deal Delivery",
                    delivery_names,
                    key="cal_delivery"
                )
            )

        actual_flex_gain = (
            st.number_input(
                "Actual Flex Gain",
                min_value=0.0,
                value=1.0,
                step=0.1
            )
        )

        add_observation = (
            st.form_submit_button(
                "Add Observation"
            )
        )

        if add_observation:

            qg, dg = get_gaps(
                role,
                start_quality,
                start_delivery,
                QUALITY[cal_quality],
                DELIVERY[
                    cal_delivery
                ]
            )

            volume_factor = (
                cal_units
                / target_units
                if volume_weighting
                else 1
            )

            st.session_state.calibration.append({
                "Units": cal_units,
                "Quality": cal_quality,
                "Delivery": cal_delivery,
                "Quality Feature":
                    qg * volume_factor,
                "Delivery Feature":
                    dg * volume_factor,
                "Actual Flex":
                    actual_flex_gain
            })

            st.success(
                "Observation added."
            )

    if st.session_state.calibration:

        cal_df = pd.DataFrame(
            st.session_state.calibration
        )

        st.dataframe(
            cal_df,
            use_container_width=True
        )

        if len(cal_df) >= 3:

            X = np.column_stack([
                cal_df[
                    "Quality Feature"
                ].values,
                cal_df[
                    "Delivery Feature"
                ].values,
                np.ones(
                    len(cal_df)
                )
            ])

            y = cal_df[
                "Actual Flex"
            ].values

            beta, _, _, _ = (
                np.linalg.lstsq(
                    X,
                    y,
                    rcond=None
                )
            )

            q_est = max(
                0,
                beta[0]
            )

            d_est = max(
                0,
                beta[1]
            )

            intercept = beta[2]

            c1, c2, c3 = (
                st.columns(3)
            )

            c1.metric(
                "Estimated Quality Weight",
                f"{q_est:.2f}"
            )

            c2.metric(
                "Estimated Delivery Weight",
                f"{d_est:.2f}"
            )

            c3.metric(
                "Intercept",
                f"{intercept:.2f}"
            )

            if st.button(
                "Use These Calibrated Weights",
                key="use_calibrated_btn"
            ):

                st.session_state.calibrated_weights = {
                    "quality": q_est,
                    "delivery": d_est
                }

                st.rerun()

        else:

            st.info(
                "Add at least 3 observations."
            )

        if st.button(
            "Clear Calibration Data",
            key="clear_calibration"
        ):

            st.session_state.calibration = []
            st.session_state.calibrated_weights = None

            st.rerun()


# ============================================================
# TAB 7 — RISK SIMULATION
# ============================================================

with tabs[6]:

    st.header(
        "Monte Carlo / Risk Analysis"
    )

    sim_offer_name = st.selectbox(
        "Offer to Simulate",
        comparison["Offer"].tolist(),
        key="sim_offer"
    )

    sim_offer = comparison[
        comparison["Offer"]
        == sim_offer_name
    ].iloc[0]

    flex_uncertainty = st.slider(
        "Flex Gain Standard Deviation",
        0.0,
        10.0,
        2.0,
        0.5,
        key="flex_uncertainty"
    )

    target_score = st.number_input(
        "Target Score",
        min_value=0.0,
        value=80.0,
        step=5.0,
        key="target_score"
    )

    simulations = st.slider(
        "Number of Simulations",
        1000,
        20000,
        5000,
        1000,
        key="simulations"
    )

    rng = (
        np.random.default_rng(
            42
        )
    )

    simulated_gain = rng.normal(
        sim_offer[
            "Flex Gain"
        ],
        flex_uncertainty,
        simulations
    )

    simulated_gain = (
        np.maximum(
            0,
            simulated_gain
        )
    )

    simulated_final_flex = (
        current_flex
        + simulated_gain
    )

    pg = max(
        0,
        sim_offer[
            "Price Gap %"
        ]
    )

    inv = (
        sim_offer[
            "Inventory %"
        ]
        / 100
    )

    simulated_scores = (
        (
            pg
            + simulated_final_flex
        )
        * importance
        * inv
    )

    mean_score = np.mean(
        simulated_scores
    )

    p10 = np.percentile(
        simulated_scores,
        10
    )

    median = np.percentile(
        simulated_scores,
        50
    )

    p90 = np.percentile(
        simulated_scores,
        90
    )

    probability_target = np.mean(
        simulated_scores
        >= target_score
    )

    c1, c2, c3, c4 = (
        st.columns(4)
    )

    c1.metric(
        "Expected Score",
        f"{mean_score:.2f}"
    )

    c2.metric(
        "10th Percentile",
        f"{p10:.2f}"
    )

    c3.metric(
        "Median",
        f"{median:.2f}"
    )

    c4.metric(
        "90th Percentile",
        f"{p90:.2f}"
    )

    st.metric(
        f"Probability Score ≥ {target_score:.0f}",
        f"{probability_target * 100:.1f}%"
    )

    fig, ax = plt.subplots(
        figsize=(9, 5)
    )

    ax.hist(
        simulated_scores,
        bins=40,
        alpha=0.75
    )

    ax.axvline(
        target_score,
        color="red",
        linestyle="--",
        label="Target"
    )

    ax.set_xlabel(
        "Experimental Score"
    )

    ax.set_ylabel(
        "Frequency"
    )

    ax.set_title(
        f"Risk Distribution — {sim_offer_name}"
    )

    ax.legend()

    st.pyplot(fig)


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "Main decision rule: do not maximize Price or Flex independently. "
    "Compare the price concession, Flex gain, service level, "
    "and progress toward your target volume together."
)