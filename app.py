
from __future__ import annotations

import os
import threading
import time
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from feature_hub import (
    DEFAULT_ELECTRICITY_PRICE_PER_KWH,
    DEFAULT_GRID_KG_CO2_PER_KWH,
    ENVIRONMENTS,
    EcoTwinController,
    generate_ai_recommendations,
    scenario_comparison,
)

st.set_page_config(
    page_title="EcoTwin AI",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --------------------------- Styling ----------------------------------------
st.markdown(
    """
    <style>
    .main { background-color: #f7faf8; }
    .hero {
        padding: 1.2rem 1.4rem;
        border-radius: 16px;
        background: linear-gradient(115deg, #123d32, #23765a);
        color: white;
        margin-bottom: 1rem;
    }
    .hero h1 { color: white; margin-bottom: 0.3rem; }
    .hero p { color: #e1f5e9; margin-bottom: 0; }
    .small-note { font-size: 0.85rem; color: #53655d; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="hero">
      <h1>🌱 EcoTwin AI</h1>
      <p>Observe energy use · Simulate improvements · Prioritize decarbonization</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# --------------------------- Session state ----------------------------------
if "environment" not in st.session_state:
    st.session_state.environment = "Home"
if "cv_count" not in st.session_state:
    st.session_state.cv_count = 0
if "cv_active" not in st.session_state:
    st.session_state.cv_active = False
if "cv_error" not in st.session_state:
    st.session_state.cv_error = ""
if "controller" not in st.session_state:
    st.session_state.controller = EcoTwinController()
if "applied_savings" not in st.session_state:
    st.session_state.applied_savings = {}
if "last_recommendation" not in st.session_state:
    st.session_state.last_recommendation = None

# --------------------------- Sidebar ----------------------------------------
with st.sidebar:
    st.header("Facility controls")
    environment = st.selectbox(
        "Choose environment",
        list(ENVIRONMENTS.keys()),
        index=list(ENVIRONMENTS.keys()).index(st.session_state.environment),
    )
    if environment != st.session_state.environment:
        st.session_state.environment = environment
        st.session_state.controller.set_environment(environment)
        st.session_state.applied_savings = {}
        st.session_state.last_recommendation = None

    st.caption(ENVIRONMENTS[environment]["description"])
    st.divider()

    st.subheader("Planning assumptions")
    period_days = st.slider("Simulation period (days)", 1, 365, 30)
    occupancy_hours = st.slider("Occupied hours per day", 0.0, 24.0, 8.0, 0.5)
    operating_hours = st.slider("Equipment operating hours per day", 1.0, 24.0, 12.0, 0.5)
    electricity_price = st.number_input(
        "Electricity price (currency/kWh)",
        min_value=0.0,
        value=DEFAULT_ELECTRICITY_PRICE_PER_KWH,
        step=0.5,
    )
    grid_factor = st.number_input(
        "Grid emissions factor (kg CO₂/kWh)",
        min_value=0.0,
        value=DEFAULT_GRID_KG_CO2_PER_KWH,
        step=0.05,
        format="%.3f",
    )
    st.caption(
        "Illustrative defaults only. Replace with your local tariff and a cited, "
        "current grid emissions factor."
    )

    st.divider()
    st.subheader("Optimization assumption")
    default_fraction = ENVIRONMENTS[environment]["savings_fraction"]
    optimization_pct = st.slider(
        "Estimated optimization potential (%)",
        min_value=0,
        max_value=40,
        value=int(default_fraction * 100),
        step=1,
    )

scenario = scenario_comparison(
    environment=environment,
    occupancy_hours_per_day=occupancy_hours,
    operating_hours_per_day=operating_hours,
    days=period_days,
    grid_kg_co2_per_kwh=grid_factor,
    electricity_price_per_kwh=electricity_price,
    savings_fraction_override=optimization_pct / 100.0,
)

# --------------------------- Shared UI helpers ------------------------------
def metric_row(data: dict) -> None:
    columns = st.columns(3)
    columns[0].metric(
        "Energy saved",
        f"{data['saved_kwh']:,.1f} kWh",
        f"{data['savings_fraction'] * 100:.1f}% estimated",
    )
    columns[1].metric(
        "Cost reduction",
        f"{data['saved_cost']:,.2f}",
        "estimated",
    )
    columns[2].metric(
        "CO₂ avoided",
        f"{data['co2_avoided_kg']:,.1f} kg",
        "estimated",
    )


def make_load_chart(data: dict) -> go.Figure:
    """Illustrative daily load profile derived from the estimated total."""
    hours = list(range(24))
    base_total = data["baseline_kwh"]
    optimized_total = data["optimized_kwh"]

    # A normalized profile to illustrate time-of-day variation, not real telemetry.
    profile = [
        0.68, 0.62, 0.58, 0.56, 0.57, 0.65,
        0.78, 0.95, 1.08, 1.12, 1.10, 1.08,
        1.05, 1.03, 1.04, 1.08, 1.15, 1.24,
        1.22, 1.12, 1.00, 0.90, 0.80, 0.72,
    ]
    total_weight = sum(profile)
    baseline = [base_total * p / total_weight / max(1, data["period_days"]) for p in profile]
    optimized = [optimized_total * p / total_weight / max(1, data["period_days"]) for p in profile]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=hours, y=baseline, mode="lines+markers", name="Baseline",
        line={"width": 3},
    ))
    fig.add_trace(go.Scatter(
        x=hours, y=optimized, mode="lines+markers", name="Optimized estimate",
        line={"width": 3, "dash": "dash"},
    ))
    fig.update_layout(
        title="Illustrative 24-hour energy profile",
        xaxis_title="Hour of day",
        yaxis_title="Estimated energy (kWh/hour)",
        template="plotly_white",
        height=370,
        margin={"l": 20, "r": 20, "t": 60, "b": 30},
        legend={"orientation": "h", "y": 1.12},
    )
    return fig


# --------------------------- Main dashboard ---------------------------------
st.caption(
    "DEMO MODE · Equipment ratings, schedules, and savings assumptions are illustrative. "
    "Replace them with measured data before using the results for operational decisions."
)

overview_tab, twin_tab, cv_tab, ai_tab, devices_tab = st.tabs(
    [
        "📊 Overview",
        "🧩 Digital Twin",
        "📷 Live Computer Vision",
        "✨ GenAI Strategy",
        "⚙️ Device Controls",
    ]
)

# =========================== Overview =======================================
with overview_tab:
    st.subheader(f"Energy overview — {environment}")
    st.write(ENVIRONMENTS[environment]["description"])

    c1, c2, c3 = st.columns(3)
    c1.metric("Baseline energy", f"{scenario['baseline_kwh']:,.1f} kWh")
    c2.metric("Optimized estimate", f"{scenario['optimized_kwh']:,.1f} kWh")
    c3.metric("Optimization potential", f"{scenario['savings_fraction'] * 100:.1f}%")

    st.subheader("Estimated savings")
    metric_row(scenario)

    left, right = st.columns([1.5, 1])
    with left:
        st.plotly_chart(make_load_chart(scenario), use_container_width=True)
    with right:
        st.markdown("#### Facility snapshot")
        st.write(f"**Facility:** {environment}")
        st.write(f"**Period:** {period_days} day(s)")
        st.write(f"**Occupied:** {occupancy_hours:g} hours/day")
        st.write(f"**Operating:** {operating_hours:g} hours/day")
        st.write(f"**Tariff:** {electricity_price:.2f} per kWh")
        st.write(f"**Grid factor:** {grid_factor:.3f} kg CO₂/kWh")
        st.info(
            "The chart uses an illustrative load shape. It is not a live meter trace "
            "or a prediction of exact hourly demand."
        )

    st.subheader("Prioritized strategy ideas")
    for i, strategy in enumerate(ENVIRONMENTS[environment]["strategies"], start=1):
        st.markdown(f"{i}. {strategy}")

    st.subheader("Baseline vs. optimized")
    compare_df = pd.DataFrame(
        [
            {
                "Metric": "Energy (kWh)",
                "Baseline": scenario["baseline_kwh"],
                "Optimized estimate": scenario["optimized_kwh"],
                "Estimated reduction": scenario["saved_kwh"],
            },
            {
                "Metric": "Electricity cost",
                "Baseline": scenario["baseline_cost"],
                "Optimized estimate": scenario["optimized_cost"],
                "Estimated reduction": scenario["saved_cost"],
            },
            {
                "Metric": "CO₂ (kg)",
                "Baseline": scenario["baseline_co2_kg"],
                "Optimized estimate": scenario["optimized_co2_kg"],
                "Estimated reduction": scenario["co2_avoided_kg"],
            },
        ]
    )
    st.dataframe(compare_df, use_container_width=True, hide_index=True)

    st.download_button(
        "Download scenario results (CSV)",
        data=compare_df.to_csv(index=False).encode("utf-8"),
        file_name="ecotwin_scenario_results.csv",
        mime="text/csv",
    )

# =========================== Digital Twin ===================================
with twin_tab:
    st.subheader("Digital Twin simulation")
    st.write(
        "Use the controls below to explore equipment status and occupancy-triggered "
        "lighting. The controller is a local simulation, not a building-management system."
    )

    controller: EcoTwinController = st.session_state.controller
    controller.electricity_price_per_kwh = electricity_price
    controller.grid_kg_co2_per_kwh = grid_factor

    occ_col, delay_col = st.columns(2)
    with occ_col:
        simulated_occupancy = st.number_input(
            "Simulated people in facility",
            min_value=0,
            max_value=1000,
            value=int(controller.occupancy),
            step=1,
            key="simulated_occupancy",
        )
    with delay_col:
        vacancy_delay = st.number_input(
            "Vacancy delay before auto-off (seconds)",
            min_value=1,
            max_value=3600,
            value=int(controller.vacancy_delay_seconds),
            step=5,
        )

    controller.vacancy_delay_seconds = int(vacancy_delay)
    if st.button("Update simulated occupancy", key="update_occ"):
        controller.set_occupancy(int(simulated_occupancy))
        st.success("Simulation occupancy updated.")

    st.markdown("#### Equipment snapshot")
    status = pd.DataFrame(controller.get_device_status())
    st.dataframe(status, use_container_width=True, hide_index=True)

    power_col, energy_col, savings_col = st.columns(3)
    power_col.metric("Current simulated power", f"{controller.current_power_watts():,.0f} W")
    energy_col.metric("Simulated energy", f"{controller.energy_used_kwh:.5f} kWh")
    savings_col.metric("Estimated auto-off savings", f"{controller.energy_saved_kwh:.5f} kWh")

    step_col, reset_col = st.columns(2)
    with step_col:
        seconds = st.number_input(
            "Advance simulation by seconds",
            min_value=1,
            max_value=3600,
            value=60,
            step=1,
        )
        if st.button("Advance simulation", key="advance_sim"):
            controller.tick(seconds)
            st.rerun()
    with reset_col:
        st.write("")
        st.write("")
        if st.button("Reset simulation", key="reset_sim"):
            controller.reset()
            st.rerun()

    if controller.events:
        st.markdown("#### Recent events")
        st.dataframe(
            pd.DataFrame({"Event": controller.events}),
            use_container_width=True,
            hide_index=True,
        )

# =========================== Computer Vision ================================
with cv_tab:
    st.subheader("Live webcam person detection")
    st.write(
        "Optional feature. Requires a compatible browser, camera permission, "
        "`streamlit-webrtc`, `av`, OpenCV, and Ultralytics. The first YOLO model "
        "run may download model weights."
    )

    st.warning(
        "Person detection is only a rough occupancy proxy. It can miss people or count "
        "detections incorrectly. Do not use it alone for safety or access-control decisions."
    )

    # Imports are delayed so a missing optional CV dependency does not crash the app.
    try:
        import av
        import cv2
        from streamlit_webrtc import VideoProcessorBase, webrtc_streamer
        from ultralytics import YOLO

        class PersonDetectionProcessor(VideoProcessorBase):
            def __init__(self):
                self.model = YOLO("yolov8n.pt")
                self.count = 0
                self.last_error = ""
                self.lock = threading.Lock()

            def recv(self, frame):
                image = frame.to_ndarray(format="bgr24")
                try:
                    result = self.model.predict(
                        image,
                        classes=[0],  # COCO person class
                        conf=0.35,
                        verbose=False,
                    )[0]
                    count = 0 if result.boxes is None else len(result.boxes)
                    annotated = result.plot()
                    with self.lock:
                        self.count = int(count)
                    return av.VideoFrame.from_ndarray(annotated, format="bgr24")
                except Exception as exc:
                    with self.lock:
                        self.last_error = f"{type(exc).__name__}: {exc}"
                    return av.VideoFrame.from_ndarray(image, format="bgr24")

            def get_count(self):
                with self.lock:
                    return self.count

        ctx = webrtc_streamer(
            key="ecotwin-person-detection",
            video_processor_factory=PersonDetectionProcessor,
            media_stream_constraints={"video": True, "audio": False},
            async_processing=True,
        )

        if ctx.video_processor:
            detected_count = ctx.video_processor.get_count()
            st.session_state.cv_count = detected_count
            st.metric("People detected in latest frame", detected_count)

            if st.button("Use detected count as simulated occupancy"):
                st.session_state.controller.set_occupancy(detected_count)
                st.success("Occupancy copied to the Digital Twin simulation.")

            if ctx.video_processor.last_error:
                st.error(ctx.video_processor.last_error)
        else:
            st.info("Allow camera access and start the webcam stream to begin detection.")

    except Exception as exc:
        st.info(
            "Live detection is unavailable in this environment. The rest of EcoTwin AI "
            "continues to work. Install the optional CV dependencies and restart the app."
        )
        st.caption(f"Optional CV detail: {type(exc).__name__}: {exc}")

        st.markdown("#### Demo occupancy input")
        demo_count = st.slider("Simulated detected people", 0, 50, int(st.session_state.cv_count))
        st.session_state.cv_count = demo_count
        if st.button("Use demo occupancy"):
            st.session_state.controller.set_occupancy(demo_count)
            st.success("Demo occupancy copied to the Digital Twin simulation.")

# =========================== GenAI Strategy ================================
with ai_tab:
    st.subheader("EcoTwin AI energy advisor")
    st.write(
        "OpenAI generates explanations and priorities. The scenario calculations come "
        "from the local simulation assumptions, not from the language model."
    )

    api_key_present = bool(os.getenv("OPENAI_API_KEY"))
    if api_key_present:
        st.success("OPENAI_API_KEY is configured in this process.")
    else:
        st.info(
            "OPENAI_API_KEY is not configured. The advisor will use the built-in "
            "rule-based fallback instead."
        )

    model_name = st.text_input("OpenAI model", value="gpt-4o-mini")
    vacancy_detected = st.checkbox(
        "Current facility is vacant",
        value=(st.session_state.cv_count == 0),
        help="This is an optional contextual hint; it does not override facility safety.",
    )

    if st.button("Generate recommendations", type="primary"):
        with st.spinner("Preparing recommendations..."):
            result = generate_ai_recommendations(
                scenario=scenario,
                occupancy_count=int(st.session_state.cv_count),
                vacancy_detected=vacancy_detected,
                model=model_name.strip() or "gpt-4o-mini",
            )
            st.session_state.last_recommendation = result

    recommendation = st.session_state.last_recommendation
    if recommendation:
        if recommendation.get("fallback"):
            st.warning(f"Using {recommendation['provider']}.")
            st.caption(recommendation.get("error", ""))
        else:
            st.success(
                f"Generated with {recommendation.get('provider')} "
                f"({recommendation.get('model')})."
            )

        st.markdown(recommendation["recommendations"])
        st.download_button(
            "Download recommendations",
            data=recommendation["recommendations"].encode("utf-8"),
            file_name="ecotwin_recommendations.md",
            mime="text/markdown",
        )

    st.caption(
        "Do not automatically apply AI advice to physical equipment. Review all "
        "changes with the responsible operator or engineer."
    )

# =========================== Device Controls ================================
with devices_tab:
    st.subheader("Device control sandbox")
    st.warning(
        "These controls only change the in-memory simulation. They do not connect "
        "to real devices or send commands to a facility."
    )

    controller = st.session_state.controller
    for device in controller.available_devices:
        name = device["name"]
        is_on = controller.devices_on.get(name, True)
        col1, col2, col3 = st.columns([2, 1, 2])
        col1.write(f"**{name}**")
        col2.write(f"{device['watts']} W")
        if device["critical"]:
            col3.caption("Critical equipment")
        desired = col3.toggle(
            "On",
            value=is_on,
            key=f"device_{environment}_{name}",
        )
        if desired != is_on:
            controller.set_device(name, desired)

    st.markdown("#### Simulated current load")
    st.metric("Power draw", f"{controller.current_power_watts():,.0f} W")
    st.metric("Accumulated simulated energy", f"{controller.energy_used_kwh:.5f} kWh")

# --------------------------- Footer -----------------------------------------
st.divider()
st.caption(
    f"EcoTwin AI prototype · Updated {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} · "
    "Planning estimates only; not a certified energy audit."
)
