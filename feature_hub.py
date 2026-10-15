
"""
EcoTwin AI — simulation, energy calculations, and AI recommendations.

This file is standalone and does not modify or depend on twin.py.
All equipment ratings, savings assumptions, tariffs, and grid factors are
illustrative. Replace them with verified facility data before real-world use.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any


DEFAULT_ELECTRICITY_PRICE_PER_KWH = 8.0
DEFAULT_GRID_KG_CO2_PER_KWH = 0.70
DEFAULT_AI_MODEL = "gpt-4o-mini"

ENVIRONMENTS: dict[str, dict[str, Any]] = {
    "Home": {
        "description": "Residential energy management",
        "savings_fraction": 0.12,
        "devices": [
            {"name": "Lights", "watts": 40, "kind": "lighting", "critical": False},
            {"name": "Air Conditioner", "watts": 1200, "kind": "hvac", "critical": False},
            {"name": "Refrigerator", "watts": 150, "kind": "critical", "critical": True},
            {"name": "Computer", "watts": 100, "kind": "plug", "critical": False},
            {"name": "Television", "watts": 90, "kind": "plug", "critical": False},
        ],
        "strategies": [
            "Switch off lights in unoccupied rooms.",
            "Use an efficient AC setpoint and clean filters regularly.",
            "Reduce standby power for non-critical electronics.",
            "Keep the refrigerator running and maintain its door seals.",
        ],
    },
    "Campus/Classroom": {
        "description": "Classroom and campus facilities",
        "savings_fraction": 0.18,
        "devices": [
            {"name": "Lights", "watts": 400, "kind": "lighting", "critical": False},
            {"name": "Projector", "watts": 250, "kind": "plug", "critical": False},
            {"name": "Computers", "watts": 600, "kind": "plug", "critical": False},
            {"name": "Air Conditioning", "watts": 2500, "kind": "hvac", "critical": False},
        ],
        "strategies": [
            "Switch off classroom lighting when rooms are vacant.",
            "Schedule cooling around teaching hours and occupancy.",
            "Enable sleep mode on computers and projectors.",
            "Review classroom schedules to avoid conditioning empty rooms.",
        ],
    },
    "Data Center": {
        "description": "Server room and data-center operations",
        "savings_fraction": 0.10,
        "devices": [
            {"name": "Servers", "watts": 8000, "kind": "critical", "critical": True},
            {"name": "Cooling", "watts": 4000, "kind": "hvac", "critical": True},
            {"name": "UPS Losses", "watts": 800, "kind": "critical", "critical": True},
            {"name": "Lighting", "watts": 200, "kind": "lighting", "critical": False},
        ],
        "strategies": [
            "Review cooling airflow and hot/cold aisle separation.",
            "Audit server utilization before considering consolidation.",
            "Measure UPS efficiency and investigate avoidable conversion losses.",
            "Turn off nonessential lighting only where safe.",
        ],
    },
    "Industry/Factory": {
        "description": "Industrial production and factory utilities",
        "savings_fraction": 0.14,
        "devices": [
            {"name": "Production Motors", "watts": 5000, "kind": "critical", "critical": True},
            {"name": "Compressed Air", "watts": 2000, "kind": "process", "critical": True},
            {"name": "HVAC", "watts": 1200, "kind": "hvac", "critical": False},
            {"name": "Lighting", "watts": 400, "kind": "lighting", "critical": False},
        ],
        "strategies": [
            "Inspect compressed-air leaks and unloaded running time.",
            "Schedule HVAC around occupancy and production shifts.",
            "Review motor loading and maintenance with qualified engineers.",
            "Use efficient lighting in suitable areas.",
        ],
    },
}


@dataclass
class EcoTwinController:
    """Small in-memory controller for interactive what-if simulations."""

    environment: str = "Home"
    electricity_price_per_kwh: float = DEFAULT_ELECTRICITY_PRICE_PER_KWH
    grid_kg_co2_per_kwh: float = DEFAULT_GRID_KG_CO2_PER_KWH
    occupancy: int = 1
    vacancy_delay_seconds: int = 30
    devices_on: dict[str, bool] = field(default_factory=dict)
    elapsed_seconds: float = 0.0
    vacant_seconds: float = 0.0
    energy_used_kwh: float = 0.0
    energy_saved_kwh: float = 0.0
    events: list[str] = field(default_factory=list)
    auto_off_devices: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        self.set_environment(self.environment, log_event=False)

    @property
    def available_devices(self) -> list[dict[str, Any]]:
        return ENVIRONMENTS[self.environment]["devices"]

    def log(self, message: str) -> None:
        self.events.insert(0, message)
        self.events = self.events[:100]

    def set_environment(self, environment: str, log_event: bool = True) -> None:
        if environment not in ENVIRONMENTS:
            raise ValueError(f"Unknown environment: {environment}")
        self.environment = environment
        self.devices_on = {d["name"]: True for d in self.available_devices}
        self.auto_off_devices.clear()
        if log_event:
            self.log(f"Environment changed to {environment}.")

    def set_occupancy(self, count: int) -> None:
        count = max(0, int(count))
        was_vacant = self.occupancy == 0
        self.occupancy = count
        self.vacant_seconds = 0.0
        if count > 0:
            for device in self.available_devices:
                name = device["name"]
                if name in self.auto_off_devices:
                    self.devices_on[name] = True
                    self.auto_off_devices.discard(name)
            self.log(f"Occupancy detected: {count}.")
        elif not was_vacant:
            self.log("Space is now vacant.")

    def set_device(self, name: str, enabled: bool) -> None:
        valid = {d["name"] for d in self.available_devices}
        if name not in valid:
            raise ValueError(f"Unknown device: {name}")
        self.devices_on[name] = bool(enabled)
        self.auto_off_devices.discard(name)
        self.log(f"{name}: {'ON' if enabled else 'OFF'} (manual control).")

    def current_power_watts(self) -> float:
        return sum(
            float(device["watts"])
            for device in self.available_devices
            if self.devices_on.get(device["name"], True)
        )

    def tick(self, seconds: float = 1.0) -> dict[str, float]:
        """Advance the simulated clock. This is not a real sensor reading."""
        seconds = max(0.0, float(seconds))
        self.elapsed_seconds += seconds

        if self.occupancy == 0:
            self.vacant_seconds += seconds
            if self.vacant_seconds >= self.vacancy_delay_seconds:
                for device in self.available_devices:
                    name = device["name"]
                    if device["kind"] == "lighting" and self.devices_on.get(name, True):
                        self.devices_on[name] = False
                        self.auto_off_devices.add(name)
                        self.log(f"{name} automatically switched off after vacancy.")
        else:
            self.vacant_seconds = 0.0

        power_w = self.current_power_watts()
        energy_kwh = power_w * seconds / 3_600_000
        self.energy_used_kwh += energy_kwh

        # Estimated avoidable energy for auto-off lighting during vacancy.
        saved_w = sum(
            float(d["watts"])
            for d in self.available_devices
            if d["kind"] == "lighting" and d["name"] in self.auto_off_devices
        )
        self.energy_saved_kwh += saved_w * seconds / 3_600_000

        return {
            "power_w": power_w,
            "energy_kwh": self.energy_used_kwh,
            "estimated_saved_kwh": self.energy_saved_kwh,
        }

    def reset(self) -> None:
        self.devices_on = {d["name"]: True for d in self.available_devices}
        self.elapsed_seconds = 0.0
        self.vacant_seconds = 0.0
        self.energy_used_kwh = 0.0
        self.energy_saved_kwh = 0.0
        self.events.clear()
        self.auto_off_devices.clear()
        self.log("Simulation reset.")

    def get_device_status(self) -> list[dict[str, Any]]:
        return [
            {
                "Device": d["name"],
                "Rated power (W)": d["watts"],
                "Status": "ON" if self.devices_on.get(d["name"], True) else "OFF",
                "Critical": d["critical"],
            }
            for d in self.available_devices
        ]


def scenario_comparison(
    environment: str,
    occupancy_hours_per_day: float = 8.0,
    operating_hours_per_day: float = 12.0,
    days: int = 30,
    grid_kg_co2_per_kwh: float = DEFAULT_GRID_KG_CO2_PER_KWH,
    electricity_price_per_kwh: float = DEFAULT_ELECTRICITY_PRICE_PER_KWH,
    savings_fraction_override: float | None = None,
) -> dict[str, Any]:
    """
    Estimate baseline vs optimized energy from rated power and assumed schedules.
    Outputs are planning estimates, not calibrated meter measurements.
    """
    if environment not in ENVIRONMENTS:
        raise ValueError(f"Unknown environment: {environment}")

    occupancy_hours = max(0.0, min(24.0, float(occupancy_hours_per_day)))
    operating_hours = max(0.0, min(24.0, float(operating_hours_per_day)))
    days = max(1, int(days))
    if grid_kg_co2_per_kwh < 0 or electricity_price_per_kwh < 0:
        raise ValueError("Price and grid emissions factor must be non-negative.")

    devices = ENVIRONMENTS[environment]["devices"]
    baseline_daily_kwh = sum(
        float(d["watts"]) * operating_hours / 1000 for d in devices
    )

    # The optimization is a planning estimate. It does not disable critical equipment.
    fraction = (
        float(savings_fraction_override)
        if savings_fraction_override is not None
        else float(ENVIRONMENTS[environment]["savings_fraction"])
    )
    fraction = max(0.0, min(0.60, fraction))

    # Occupancy-sensitive settings affect the estimated opportunity for lighting.
    lighting_kw = sum(
        float(d["watts"]) / 1000 for d in devices if d["kind"] == "lighting"
    )
    vacancy_hours = max(0.0, operating_hours - occupancy_hours)
    if lighting_kw > 0 and operating_hours > 0:
        vacancy_share = min(1.0, vacancy_hours / operating_hours)
        fraction = min(0.60, fraction + vacancy_share * 0.03)

    baseline_kwh = baseline_daily_kwh * days
    optimized_kwh = baseline_kwh * (1.0 - fraction)
    saved_kwh = baseline_kwh - optimized_kwh

    baseline_cost = baseline_kwh * electricity_price_per_kwh
    optimized_cost = optimized_kwh * electricity_price_per_kwh
    baseline_co2 = baseline_kwh * grid_kg_co2_per_kwh
    optimized_co2 = optimized_kwh * grid_kg_co2_per_kwh

    return {
        "environment": environment,
        "period_days": days,
        "baseline_kwh": round(baseline_kwh, 3),
        "optimized_kwh": round(optimized_kwh, 3),
        "saved_kwh": round(saved_kwh, 3),
        "savings_fraction": round(fraction, 4),
        "baseline_cost": round(baseline_cost, 2),
        "optimized_cost": round(optimized_cost, 2),
        "saved_cost": round(baseline_cost - optimized_cost, 2),
        "baseline_co2_kg": round(baseline_co2, 3),
        "optimized_co2_kg": round(optimized_co2, 3),
        "co2_avoided_kg": round(baseline_co2 - optimized_co2, 3),
        "strategies": list(ENVIRONMENTS[environment]["strategies"]),
        "assumptions": [
            "Equipment ratings are illustrative nameplate values.",
            "Operating schedules and savings fraction are planning assumptions.",
            "Savings are not measured or guaranteed.",
            "Critical data-center and production equipment is not automatically shut down.",
        ],
    }


def generate_ai_recommendations(
    scenario: dict[str, Any],
    occupancy_count: int | None = None,
    vacancy_detected: bool | None = None,
    api_key: str | None = None,
    model: str = DEFAULT_AI_MODEL,
) -> dict[str, Any]:
    """
    Return an OpenAI recommendation when configured; otherwise return a safe
    deterministic fallback. Never treat the model's text as verified metering.
    """
    key = api_key or os.getenv("OPENAI_API_KEY")
    context = {
        "scenario": scenario,
        "occupancy_count": occupancy_count,
        "vacancy_detected": vacancy_detected,
    }

    if key:
        try:
            from openai import OpenAI  # Optional dependency; import only when needed.

            client = OpenAI(api_key=key)
            response = client.chat.completions.create(
                model=model,
                temperature=0.2,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are EcoTwin AI, an energy efficiency advisor. "
                            "Use only supplied figures for numerical claims. Do not "
                            "invent measured results or promise savings. Treat the "
                            "scenario as an illustrative estimate. Never recommend "
                            "turning off critical servers, cooling, refrigeration, "
                            "safety systems, or production equipment without qualified "
                            "engineering review. Return concise Markdown with prioritized "
                            "actions, rationale, risks, and a clear note that estimates "
                            "are not measured values."
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(context, ensure_ascii=False),
                    },
                ],
            )
            content = response.choices[0].message.content or ""
            if content.strip():
                return {
                    "provider": "OpenAI",
                    "model": model,
                    "fallback": False,
                    "recommendations": content.strip(),
                }
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
    else:
        error = "OPENAI_API_KEY is not configured."

    env = str(scenario.get("environment", "the selected facility"))
    strategies = scenario.get("strategies", [])
    if occupancy_count == 0 or vacancy_detected is True:
        strategies = [
            "Check that lighting in vacant areas is switched off.",
            *strategies,
        ]

    fallback_lines = [
        f"### Rule-based recommendations for {env}",
        "",
        "These actions are suggestions; validate them against real equipment and safety requirements.",
    ]
    for index, item in enumerate(strategies[:5], start=1):
        fallback_lines.append(f"{index}. {item}")
    fallback_lines.extend(
        [
            "",
            f"- Estimated energy saved over the selected period: {scenario.get('saved_kwh', 'not available')} kWh.",
            f"- Estimated cost reduction: {scenario.get('saved_cost', 'not available')} currency units.",
            f"- Estimated CO₂ avoided: {scenario.get('co2_avoided_kg', 'not available')} kg.",
            "",
            "Keep critical equipment and safety systems operating. Review changes with the responsible facility engineer.",
        ]
    )
    return {
        "provider": "Rule-based fallback",
        "model": None,
        "fallback": True,
        "error": error,
        "recommendations": "\n".join(fallback_lines),
    }
