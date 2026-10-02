import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# ============================================================
# PAGE
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
    "Resistance, inventory, weighted-average price and RPG rules are based "
    "on the course mechanics. The exact Flex-generation formula is not fully "
    "published, so Flex estimates can be adjusted and calibrated using real results."
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


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.header("🎯 Round Setup")

rpg_round = st.sidebar.number_input(
    "RPG Round",
    min_value=0,
    max_value=20,
    value=0,
    step=1,
    key="rpg_round"
)

product_name = st.sidebar.text_input(
    "Product Name",
    value="Pet Feeder",
    key="product_name"
)

base_price = st.sidebar.number_input(
    "Base Price",
    min_value=0.01,
    value=320.0,
    step=1.0,
    key="base_price"
)

base_units = st.sidebar.number_input(
    "Base Units",
    min_value=1,
    value=6000,
    step=100,
    key="base_units"
)

st.sidebar.header("🎮 RPG Position")

role = st.sidebar.selectbox(
    "Role",
    ["Seller", "Buyer"],
    key="role"
)

resistance = st.sidebar.number_input(
    "Resistance Price",
    min_value=0.01,
    value=291.2 if role == "Seller" else 350.0,
    step=0.1,
    key="resistance"
)

current_flex = st.sidebar.number_input(
    "Current Flex",
    min_value=0.0,
    value=2.0,
    step=1.0,
    key="current_flex"
)

importance = st.sidebar.slider(
    "Importance",
    1,
    6,
    5,
    key="importance"
)

target_units = st.sidebar.number_input(
    "Target Units",
    min_value=1,
    value=int(base_units),
    step=100,
    key="target_units"
)

units_already_completed = st.sidebar.number_input(
    "Units Already Completed",
    min_value=0,
    value=0,
    step=100,
    key="units_completed"
)

if role == "Buyer":
    max_purchase = st.sidebar.number_input(
        "Max Purchase",
        min_value=int(target_units),
        value=max(int(target_units), int(base_units)),
        step=100,
        key="max_purchase"
    )
else:
    max_purchase = None

# ============================================================
# STARTING QUALITY / DELIVERY
# ============================================================

st.sidebar.header("⚙️ Starting Capability")

if role == "Seller":
    q_default = 2
    d_default = 2
else:
    q_default = 0
    d_default = 0

start_quality_name = st.sidebar.selectbox(
    "Starting Quality",
    list(QUALITY.keys()),
    index=q_default
)

start_delivery_name = st.sidebar.selectbox(
    "Starting Delivery",
    list(DELIVERY.keys()),
    index=d_default
)

start_quality = QUALITY[start_quality_name]
start_delivery = DELIVERY[start_delivery_name]


# ============================================================
# FLEX MODEL
# ============================================================

st.sidebar.header("🟣 Experimental Flex Model")

use_calibration = False

if st.session_state.calibrated_weights is not None:
    use_calibration = st.sidebar.checkbox(
        "Use calibrated Flex weights",
        value=True
    )

if use_calibration:
    quality_weight = st.session_state.calibrated_weights["quality"]
    delivery_weight = st.session_state.calibrated_weights["delivery"]

    st.sidebar.success(
        f"Calibrated: Quality={quality_weight:.2f}, "
        f"Delivery={delivery_weight:.2f}"
    )

else:
    quality_weight = st.sidebar.slider(
        "Flex per Quality-level gap",
        0.0,
        10.0,
        2.0,
        0.5
    )

    delivery_weight = st.sidebar.slider(
        "Flex per Delivery-level gap",
        0.0,
        10.0,
        2.0,
        0.5
    )

volume_weighting = st.sidebar.checkbox(
    "Scale Flex by deal volume",
    value=True
)


# ============================================================
# CORE FUNCTIONS
# ============================================================

def price_gap_percent(role, price, resistance):

    if role == "Seller":
        return ((price - resistance) / resistance) * 100

    return ((resistance - price) / resistance) * 100


def get_gaps(
    role,
    start_quality,
    start_delivery,
    final_quality,
    final_delivery
):

    if role == "Seller":

        q_gap = start_quality - final_quality
        d_gap = start_delivery - final_delivery

    else:

        q_gap = final_quality - start_quality
        d_gap = final_delivery - start_delivery

    return max(0, q_gap), max(0, d_gap)


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
        gain *= units / target_units

    return gain, q_gap, d_gap


def inventory_factor(
    role,
    total_units,
    target_units,
    max_purchase=None
):

    if role == "Buyer":
        if total_units > max_purchase:
            return 0.0

    return min(total_units / target_units, 1.0)


def experimental_score(
    gap_pct,
    final_flex,
    importance,
    inventory
):

    return (
        (max(0, gap_pct) + final_flex)
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

    final_flex = current_flex + fg

    total_units = units_already_completed + units

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

    price_valid = (
        price >= resistance
        if role == "Seller"
        else price <= resistance
    )

    max_valid = True

    if role == "Buyer":
        max_valid = total_units <= max_purchase

    # Strategy classification

    price_component = max(0, pg)
    flex_component = fg

    if price_component > flex_component * 1.5:
        strategy = "Price-first"

    elif flex_component > price_component * 1.5:
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
        "Valid Price": price_valid,
        "Within Max": max_valid
    }


def counterpart_proxy(
    role,
    price,
    quality,
    delivery,
    min_price,
    max_price
):
    """
    Experimental proxy only.

    Seller role:
    Counterparty = buyer.
    Buyer likes lower price + better service.

    Buyer role:
    Counterparty = seller.
    Seller likes higher price + lower service burden.
    """

    rng = max(max_price - min_price, 0.01)

    q = QUALITY[quality]
    d = DELIVERY[delivery]

    if role == "Seller":

        price_benefit = (
            (max_price - price)
            / rng
            * 100
        )

        service_benefit = (
            ((q - 1) + (d - 1))
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
            ((3 - q) + (3 - d))
            / 4
            * 100
        )

    return (
        0.5 * price_benefit
        + 0.5 * service_benefit
    )


def pareto_mask(x, y):

    n = len(x)

    keep = np.ones(n, dtype=bool)

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
# TAB 1 — OFFER A / B / C
# ============================================================

with tabs[0]:

    st.header("Offer A / B / C Comparison")

    st.write(
        "Enter several realistic offers. The model compares "
        "Price Gap, Flex potential, volume completion, and estimated score."
    )

    if role == "Seller":

        defaults = [
            (340.0, "High", "Fast"),
            (330.0, "Medium", "Medium"),
            (320.0, "Low", "Slow")
        ]

    else:

        defaults = [
            (290.0, "Low", "Slow"),
            (300.0, "Medium", "Medium"),
            (310.0, "High", "Fast")
        ]

    offers = []

    cols = st.columns(3)

    for i, col in enumerate(cols):

        letter = chr(65 + i)

        with col:

            st.subheader(f"Offer {letter}")

            p = st.number_input(
                f"Price {letter}",
                min_value=1.0,
                value=defaults[i][0],
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

            q = st.selectbox(
                f"Quality {letter}",
                list(QUALITY.keys()),
                index=list(QUALITY.keys()).index(defaults[i][1]),
                key=f"quality_{letter}"
            )

            d = st.selectbox(
                f"Delivery {letter}",
                list(DELIVERY.keys()),
                index=list(DELIVERY.keys()).index(defaults[i][2]),
                key=f"delivery_{letter}"
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

    comparison = pd.DataFrame(offers)

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
        comparison[display_cols].style.format({
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
        comparison["Experimental Score"].idxmax()
    ]

    st.success(
        f"Highest experimental value: "
        f"{best_offer['Offer']} — "
        f"{best_offer['Strategy']} strategy — "
        f"Score {best_offer['Experimental Score']:.2f}"
    )

    for row in offers:

        if not row["Valid Price"]:

            st.error(
                f"{row['Offer']}: Price violates Resistance."
            )

        if not row["Within Max"]:

            st.error(
                f"{row['Offer']}: Buyer would exceed Max Purchase."
            )


# ============================================================
# TAB 2 — BREAK EVEN
# ============================================================

with tabs[1]:

    st.header("Price ↔ Flex Break-even")

    st.write(
        "This tells you how much price advantage is equivalent "
        "to one Flex point under the experimental score model."
    )

    one_flex_value = resistance / 100

    st.metric(
        "Approximate price value of 1 Flex",
        f"{one_flex_value:.2f} NTD"
    )

    st.caption(
        "Because 1 Flex contributes approximately the same amount "
        "as 1 percentage point of Resistance in this experimental model."
    )

    offer_names = comparison["Offer"].tolist()

    c1, c2 = st.columns(2)

    with c1:
        reference_name = st.selectbox(
            "Reference Offer",
            offer_names,
            index=0
        )

    with c2:
        challenger_name = st.selectbox(
            "Challenger Offer",
            offer_names,
            index=1
        )

    reference = comparison[
        comparison["Offer"] == reference_name
    ].iloc[0]

    challenger = comparison[
        comparison["Offer"] == challenger_name
    ].iloc[0]

    ref_score = reference["Experimental Score"]

    challenger_inventory = (
        challenger["Inventory %"] / 100
    )

    if challenger_inventory > 0:

        required_total_component = (
            ref_score
            / (
                importance
                * challenger_inventory
            )
        )

        required_gap = (
            required_total_component
            - challenger["Final Flex"]
        )

        if role == "Seller":

            break_even_price = (
                resistance
                * (
                    1
                    + required_gap / 100
                )
            )

        else:

            break_even_price = (
                resistance
                * (
                    1
                    - required_gap / 100
                )
            )

        st.metric(
            f"{challenger_name} Break-even Price",
            f"{break_even_price:.2f}"
        )

        actual_extra_flex = (
            challenger["Flex Gain"]
            - reference["Flex Gain"]
        )

        price_difference = abs(
            challenger["Price"]
            - reference["Price"]
        )

        flex_needed_for_price_difference = (
            price_difference
            / one_flex_value
        )

        c1, c2, c3 = st.columns(3)

        c1.metric(
            "Price Difference",
            f"{price_difference:.2f}"
        )

        c2.metric(
            "Flex Needed to Offset It",
            f"{flex_needed_for_price_difference:.2f}"
        )

        c3.metric(
            "Actual Extra Flex",
            f"{actual_extra_flex:.2f}"
        )

        if actual_extra_flex > flex_needed_for_price_difference:

            st.success(
                "The additional Flex is experimentally worth "
                "more than the price concession."
            )

        else:

            st.warning(
                "The price advantage is experimentally worth "
                "more than the additional Flex."
            )


# ============================================================
# TAB 3 — DEAL TRACKER
# ============================================================

with tabs[2]:

    st.header("Completed Deal Tracker")

    st.write(
        "Record real deals here. The dashboard calculates "
        "weighted-average price and volume automatically."
    )

    with st.form("deal_form"):

        c1, c2, c3 = st.columns(3)

        with c1:
            counterparty = st.text_input(
                "Counterparty Group"
            )

            deal_id = st.text_input(
                "Deal ID"
            )

        with c2:
            deal_price = st.number_input(
                "Deal Price",
                min_value=1.0,
                value=float(base_price),
                step=1.0
            )

            deal_units = st.number_input(
                "Deal Units",
                min_value=1,
                value=1000,
                step=100
            )

        with c3:
            deal_quality = st.selectbox(
                "Deal Quality",
                list(QUALITY.keys())
            )

            deal_delivery = st.selectbox(
                "Deal Delivery",
                list(DELIVERY.keys())
            )

        status = st.selectbox(
            "Status",
            [
                "Completed",
                "Waiting",
                "Cancelled"
            ]
        )

        add_deal = st.form_submit_button(
            "Add Deal"
        )

        if add_deal:

            existing_ids = [
                d["Deal ID"]
                for d in st.session_state.deals
            ]

            if deal_id and deal_id in existing_ids:

                st.error(
                    "Duplicate Deal ID detected. "
                    "Each Deal ID should be unique."
                )

            else:

                st.session_state.deals.append({
                    "Counterparty": counterparty,
                    "Deal ID": deal_id,
                    "Price": deal_price,
                    "Units": deal_units,
                    "Quality": deal_quality,
                    "Delivery": deal_delivery,
                    "Status": status
                })

                st.success("Deal added.")

    if st.session_state.deals:

        deal_df = pd.DataFrame(
            st.session_state.deals
        )

        st.dataframe(
            deal_df,
            use_container_width=True
        )

        completed = deal_df[
            deal_df["Status"] == "Completed"
        ]

        if not completed.empty:

            total_volume = completed["Units"].sum()

            weighted_avg = (
                (
                    completed["Price"]
                    * completed["Units"]
                ).sum()
                / total_volume
            )

            c1, c2, c3 = st.columns(3)

            c1.metric(
                "Completed Units",
                f"{total_volume:,.0f}"
            )

            c2.metric(
                "Weighted Average Price",
                f"{weighted_avg:.2f}"
            )

            completion = min(
                total_volume / target_units,
                1
            )

            c3.metric(
                "Target Completion",
                f"{completion * 100:.1f}%"
            )

            if role == "Buyer":

                if total_volume > max_purchase:

                    st.error(
                        "Buyer has exceeded Max Purchase."
                    )

            else:

                if total_volume > target_units:

                    st.warning(
                        "Seller has sold above target Units. "
                        "Check possible overproduction Flex cost."
                    )

        if st.button(
            "Clear All Deals"
        ):

            st.session_state.deals = []
            st.rerun()

    else:

        st.info("No deals recorded yet.")


# ============================================================
# TAB 4 — PACKAGE GENERATOR
# ============================================================

with tabs[3]:

    st.header("Win-Win Package Generator")

    st.write(
        "Instead of arguing over one issue, present several "
        "packages where better service is exchanged for price."
    )

    spread = st.slider(
        "Price step between packages",
        1.0,
        30.0,
        10.0,
        1.0
    )

    if role == "Seller":

        package_data = [
            (
                "Premium",
                base_price + 2 * spread,
                "High",
                "Fast"
            ),
            (
                "Balanced",
                base_price + spread,
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
                base_price - 2 * spread,
                "Low",
                "Slow"
            ),
            (
                "Balanced",
                base_price - spread,
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

    package_units = st.number_input(
        "Package Units",
        min_value=1,
        value=2000,
        step=100
    )

    packages = []

    for (
        name,
        price,
        q,
        d
    ) in package_data:

        result = evaluate_offer(
            name,
            price,
            package_units,
            q,
            d
        )

        packages.append(result)

    package_df = pd.DataFrame(packages)

    price_min = package_df["Price"].min()
    price_max = package_df["Price"].max()

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
            "Price Gap %": "{:.2f}",
            "Flex Gain": "{:.2f}",
            "Experimental Score": "{:.2f}",
            "Counterparty Benefit Proxy": "{:.1f}"
        }),
        use_container_width=True
    )

    st.caption(
        "Counterparty Benefit Proxy is experimental. "
        "It rewards price/service combinations likely to be "
        "more attractive to the other side."
    )


# ============================================================
# TAB 5 — PARETO FRONTIER
# ============================================================

with tabs[4]:

    st.header("Win-Win Negotiation Frontier")

    st.write(
        "The frontier highlights packages where improving your "
        "own result would require reducing value for the counterparty, "
        "or vice versa."
    )

    frontier_units = st.number_input(
        "Units for Frontier Simulation",
        min_value=1,
        value=2000,
        step=100
    )

    price_values = np.linspace(
        base_price - 30,
        base_price + 30,
        13
    )

    frontier_rows = []

    for p in price_values:

        for q_name in QUALITY.keys():

            for d_name in DELIVERY.keys():

                result = evaluate_offer(
                    "Scenario",
                    p,
                    frontier_units,
                    q_name,
                    d_name
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
                    "Counterparty Benefit": cp
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

    pareto_df = frontier_df[mask]

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
        label="Frontier"
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

    st.header("Calibrate Flex Using Real RPG Data")

    st.write(
        "After real deals, enter the actual Flex gain shown "
        "by the RPG. After several observations, the app can "
        "estimate the Quality and Delivery Flex weights."
    )

    with st.form(
        "calibration_form"
    ):

        c1, c2, c3 = st.columns(3)

        with c1:

            cal_units = st.number_input(
                "Observed Deal Units",
                min_value=1,
                value=1000,
                step=100
            )

        with c2:

            cal_quality = st.selectbox(
                "Observed Deal Quality",
                list(QUALITY.keys()),
                key="cal_q"
            )

        with c3:

            cal_delivery = st.selectbox(
                "Observed Deal Delivery",
                list(DELIVERY.keys()),
                key="cal_d"
            )

        actual_flex_gain = st.number_input(
            "Actual Flex Gain from RPG",
            min_value=0.0,
            value=1.0,
            step=0.1
        )

        add_observation = st.form_submit_button(
            "Add Observation"
        )

        if add_observation:

            qg, dg = get_gaps(
                role,
                start_quality,
                start_delivery,
                QUALITY[cal_quality],
                DELIVERY[cal_delivery]
            )

            volume_factor = (
                cal_units / target_units
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
                np.ones(len(cal_df))
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

            c1, c2, c3 = st.columns(3)

            c1.metric(
                "Estimated Quality Weight",
                f"{q_est:.2f}"
            )

            c2.metric(
                "Estimated Delivery Weight",
                f"{d_est:.2f}"
            )

            c3.metric(
                "Estimated Intercept",
                f"{intercept:.2f}"
            )

            if st.button(
                "Use These Calibrated Weights"
            ):

                st.session_state.calibrated_weights = {
                    "quality": q_est,
                    "delivery": d_est
                }

                st.success(
                    "Calibrated weights activated. "
                    "The page will use them after rerun."
                )

                st.rerun()

        else:

            st.info(
                "Add at least 3 real observations "
                "before calibration."
            )

        if st.button(
            "Clear Calibration Data"
        ):

            st.session_state.calibration = []
            st.session_state.calibrated_weights = None
            st.rerun()


# ============================================================
# TAB 7 — MONTE CARLO
# ============================================================

with tabs[6]:

    st.header("Monte Carlo / Risk Analysis")

    st.write(
        "Flex gain is uncertain. This simulation asks: "
        "If the actual Flex gain is somewhat higher or lower "
        "than expected, which offer remains strong?"
    )

    sim_offer_name = st.selectbox(
        "Offer to Simulate",
        comparison["Offer"].tolist()
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
        0.5
    )

    target_score = st.number_input(
        "Target Score",
        min_value=0.0,
        value=80.0,
        step=5.0
    )

    simulations = st.slider(
        "Number of Simulations",
        1000,
        20000,
        5000,
        1000
    )

    rng = np.random.default_rng(
        42
    )

    simulated_gain = rng.normal(
        sim_offer["Flex Gain"],
        flex_uncertainty,
        simulations
    )

    simulated_gain = np.maximum(
        0,
        simulated_gain
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

    c1, c2, c3, c4 = st.columns(4)

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
    "Decision rule: do not maximize Price or Flex independently. "
    "Compare the value of the price concession with the additional "
    "Flex and the effect on volume completion."
)