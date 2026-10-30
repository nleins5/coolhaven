"""Interactive planning studio. Run with: streamlit run app.py"""

from __future__ import annotations

import json
from dataclasses import asdict, replace
from html import escape

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from coolhaven.cli import candidate_dict
from coolhaven.data import synthetic_city
from coolhaven.engine import Config, evolve, greedy, random_search
from coolhaven.model import City, Demand, Problem, Scenario, Site
from coolhaven.pareto import compromise, hypervolume

st.set_page_config(page_title="CoolHaven · Planning studio", page_icon="◒", layout="wide")
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@400;500;600;700;800&display=swap');
html, body, [data-testid="stApp"] {font-family:'DM Sans',sans-serif;}
h1,h2,h3 {font-family:'Manrope',sans-serif!important;letter-spacing:-.04em;}
.block-container {padding-top:4rem;padding-bottom:3rem;max-width:1500px;}
[data-testid="stSidebar"] {border-right:1px solid #e0e7dd;}
[data-testid="stMetric"] {background:#fff;border:1px solid #dfe6dc;border-radius:14px;padding:18px;}
[data-testid="stMetricValue"] {font-family:'Manrope',sans-serif;font-size:2rem;}
.eyebrow {font-size:11px;font-weight:700;letter-spacing:.18em;color:#137b67;margin-bottom:14px;}
.hero {font-family:'Manrope',sans-serif;font-size:clamp(36px,4.3vw,64px);line-height:1.06;
font-weight:800;letter-spacing:-.055em;margin:8px 0 20px;color:#20392f;}
.hero em {font-style:normal;color:#137b67;}
.intro {font-size:15px;line-height:1.7;color:#607268;max-width:630px;}
.context {background:#e9efdf;border:1px solid #d7e1cb;border-radius:16px;
padding:23px;margin:10px 0 16px;}
.context .big {font-family:'Manrope',sans-serif;font-size:30px;font-weight:700;margin:8px 0;}
.pill {display:inline-block;font-size:11px;padding:5px 10px;border-radius:20px;
background:#e4eee7;color:#17674f;font-weight:600;margin:4px 4px 4px 0;}
.footnote {color:#65766c;font-size:12px;line-height:1.65;margin-top:20px;}
.gene {display:inline-block;min-width:38px;text-align:center;border-radius:8px;margin:3px;
padding:8px 5px;font-size:11px;background:#e9ede7;color:#617167;}
.gene.on {background:#137b67;color:#fff;}
</style>
""",
    unsafe_allow_html=True,
)

GREEN, GOLD, DARK, MUTED = "#137b67", "#e4ac4b", "#20392f", "#708074"


def style(fig, height=350):
    fig.update_layout(
        height=height,
        margin=dict(l=15, r=15, t=20, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="DM Sans, sans-serif", color=DARK, size=12),
        legend=dict(orientation="h", y=-0.12, x=0),
        xaxis=dict(gridcolor="#e4e9e0", zeroline=False),
        yaxis=dict(gridcolor="#e4e9e0", zeroline=False),
    )
    return fig


@st.cache_data(show_spinner=False, max_entries=12)
def solve(city, hubs, budget, radius, population, generations, seed):
    problem = Problem(city, hubs, budget, radius)
    run = evolve(problem, Config(population, generations, seed=seed))
    baseline, calls = greedy(problem)
    return run, baseline, calls


@st.cache_data(show_spinner=False, max_entries=12)
def sample_random(city, hubs, budget, radius, evaluations, seed):
    return random_search(Problem(city, hubs, budget, radius), evaluations, seed)


with st.sidebar:
    st.markdown("### ◒ CoolHaven")
    st.caption("EVOLUTION FOR URBAN RESILIENCE")
    st.divider()
    st.markdown("**01 / Define the city**")
    upload = st.file_uploader(
        "Custom city JSON", type="json", help="See data/README.md for the schema."
    )
    city = synthetic_city()
    if upload:
        try:
            raw = json.loads(upload.getvalue())
            city = City(
                raw["name"],
                raw["provenance"],
                tuple(Demand(**d) for d in raw["demand"]),
                tuple(Site(**s) for s in raw["sites"]),
                tuple(
                    Scenario(s["id"], s["walking_multiplier"], tuple(s.get("unavailable", [])))
                    for s in raw["scenarios"]
                ),
            )
            city.validate()
            if len(city.sites) > 60 or len(city.demand) > 500 or len(city.scenarios) > 80:
                raise ValueError("Interactive limit: 60 sites, 500 demand points, 80 scenarios.")
        except (KeyError, ValueError, TypeError, OverflowError) as exc:
            st.error(f"Invalid scenario: {exc}")
            st.stop()
    stress = st.toggle("Include closure scenarios", value=True)
    if not stress:
        retained = tuple(s for s in city.scenarios if not s.unavailable)
        if not retained:
            st.error("This dataset has no scenarios without closures.")
            st.stop()
        city = replace(city, scenarios=retained)
    hubs = st.slider("Number of hubs", 1, min(10, len(city.sites)), min(5, len(city.sites)))
    minimum_budget = int(np.ceil(sum(sorted(s.cost for s in city.sites)[:hubs])))
    budget = st.number_input(
        "Budget · planning units", min_value=minimum_budget, value=max(210, minimum_budget), step=10
    )
    radius = st.slider("Walking range · km", 0.4, 3.0, 2.4, 0.1)
    st.caption("Range is reduced by each scenario's walking multiplier.")
    st.markdown("**02 / Evolve the plans**")
    with st.expander("Solver settings"):
        population = st.select_slider("Population", [24, 48, 64, 96], value=48)
        generations = st.slider("Generations", 10, 100, 35, 5)
        seed = st.number_input("Random seed", min_value=0, max_value=999999, value=42)
    st.button(
        "Recompute plan",
        type="primary",
        use_container_width=True,
        help="Changes above also recompute automatically; identical runs are cached.",
    )
    st.divider()
    st.caption("Synthetic city · schematic distances\n\nNSGA-II / 3 objectives / hard constraints")

left, right = st.columns([2.1, 1], gap="large")
with left:
    st.markdown(
        '<div class="eyebrow">PLANNING STUDIO / EXPERIMENT 01</div>', unsafe_allow_html=True
    )
    st.markdown(
        '<div class="hero">A cooler city.<br><em>A fairer plan.</em></div>', unsafe_allow_html=True
    )
    st.markdown(
        '<div class="intro">Where should the next cooling hubs go? Explore plans that '
        "balance heat-weighted access, neighbourhood equity and cost, then test what "
        "happens when a hub closes.</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        '<span class="pill">BINARY GENOME</span><span class="pill">PARETO OPTIMIZATION</span>'
        '<span class="pill">OUTAGE STRESS TEST</span>',
        unsafe_allow_html=True,
    )
with right:
    st.markdown(
        f'<div class="context"><div class="eyebrow">THE PLANNING CANVAS</div>'
        f'<div class="big">{len(city.sites)} possible places.</div>'
        f"<div>{len(city.demand)} demand clusters · {len(set(d.group for d in city.demand))} "
        f"neighbourhoods<br>{len(city.scenarios)} explicit scenarios</div></div>",
        unsafe_allow_html=True,
    )
    st.caption(
        "A teaching model for exploring trade-offs. Scores are accessibility proxies; "
        "they do not estimate medical protection or facility capacity."
    )

with st.spinner("Evolving feasible plans and preserving the Pareto frontier…"):
    try:
        run, baseline, greedy_calls = solve(
            city, hubs, budget, radius, population, generations, seed
        )
        problem = Problem(city, hubs, budget, radius)
    except ValueError as exc:
        st.error(str(exc))
        st.stop()

st.divider()
pref_col, plan_col = st.columns([1, 2])
preferences = {
    "Balanced": (0.45, 0.4, 0.15),
    "Access first": (0.75, 0.2, 0.05),
    "Equity first": (0.2, 0.75, 0.05),
    "Lower cost": (0.2, 0.15, 0.65),
}
with pref_col:
    preference = st.selectbox("Decision preference", list(preferences))
recommended = compromise(run.archive, preferences[preference])
with plan_col:
    index = st.selectbox(
        "Explore the frontier",
        range(len(run.archive)),
        index=run.archive.index(recommended),
        format_func=lambda i: (
            f"Plan {i + 1:02} · {run.archive[i].metrics.cost:.0f} units · "
            f"access {run.archive[i].metrics.robust_access:.1%} · equity "
            f"{run.archive[i].metrics.equitable_access:.1%}"
        ),
        key=f"plan_{preference}_{hubs}_{budget}_{radius}_{stress}_{population}_{generations}_{seed}",
    )
chosen = run.archive[index]
metrics = chosen.metrics
st.caption(
    f"{len(run.archive)} non-dominated plans found. Preferences select a plan after evolution "
    f"using weights {preferences[preference]}; they do not change NSGA-II's objectives."
)
a, b, c, d = st.columns(4)
a.metric("Worst-scenario access", f"{metrics.robust_access:.1%}")
b.metric("Worst-neighbourhood access", f"{metrics.equitable_access:.1%}")
c.metric(
    "Plan cost",
    f"{metrics.cost:.0f}",
    f"{budget - metrics.cost:.0f} units remaining",
    delta_color="off",
)
d.metric("Feasible hubs", f"{sum(chosen.genome)} / {hubs}")

studio, tradeoffs, lab, exports = st.tabs(
    ["Planning studio", "Trade-off explorer", "Inside the algorithm", "Data & exports"]
)

with studio:
    map_col, group_col = st.columns([1.8, 1], gap="large")
    with map_col:
        st.subheader("The neighbourhood canvas")
        worst_scenario = int(np.argmin(metrics.scenario_access))
        scene_index = st.selectbox(
            "Inspect a scenario",
            range(len(city.scenarios)),
            index=worst_scenario,
            format_func=lambda i: city.scenarios[i].id.replace("_", " "),
            key=f"scene_{stress}_{len(city.scenarios)}",
        )
        scene = city.scenarios[scene_index]
        selected = np.flatnonzero(chosen.genome)
        access = problem.access[scene_index, :, selected].max(axis=0)
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=[d.x for d in city.demand],
                y=[d.y for d in city.demand],
                mode="markers",
                name="Demand cluster",
                marker=dict(
                    size=[7 + np.sqrt(d.population) * 0.42 for d in city.demand],
                    color=access,
                    cmin=0,
                    cmax=1,
                    colorscale=[[0, "#eccf93"], [0.5, "#9bc7a4"], [1, GREEN]],
                    opacity=0.8,
                    line=dict(width=1, color="white"),
                    colorbar=dict(title="Access", thickness=9, len=0.5, tickformat=".0%"),
                ),
                text=[
                    f"{d.id} · {d.group}<br>Population {d.population:,}<br>Access {v:.1%}"
                    for d, v in zip(city.demand, access, strict=True)
                ],
                hovertemplate="%{text}<extra></extra>",
            )
        )
        absent = [s for s, bit in zip(city.sites, chosen.genome, strict=True) if not bit]
        fig.add_trace(
            go.Scatter(
                x=[s.x for s in absent],
                y=[s.y for s in absent],
                mode="markers",
                name="Unselected site",
                marker=dict(size=9, symbol="x", color="#a0afa2"),
                text=[s.name for s in absent],
                hovertemplate="%{text}<extra></extra>",
            )
        )
        for closed, name, color, symbol in [
            (False, "Active hub", GREEN, "diamond"),
            (True, "Closed hub", "#a95346", "x"),
        ]:
            items = [
                s
                for s, bit in zip(city.sites, chosen.genome, strict=True)
                if bit and (s.id in scene.unavailable) == closed
            ]
            fig.add_trace(
                go.Scatter(
                    x=[s.x for s in items],
                    y=[s.y for s in items],
                    mode="markers+text",
                    name=name,
                    marker=dict(
                        size=19, color=color, symbol=symbol, line=dict(width=2, color="white")
                    ),
                    text=[s.id for s in items],
                    textposition="top center",
                    customdata=[[s.name, s.cost] for s in items],
                    hovertemplate="%{customdata[0]}<br>%{customdata[1]} cost units<extra></extra>",
                )
            )
        style(fig, 440)
        fig.update_xaxes(title="Schematic east-west distance · km")
        fig.update_yaxes(title="North-south · km", scaleanchor="x", scaleratio=1)
        st.plotly_chart(fig, use_container_width=True, key="city_map")
        st.caption(
            f"Scenario access: {metrics.scenario_access[scene_index]:.1%}. "
            "Bubble size represents population. Coordinates describe a fictional city."
        )
    with group_col:
        st.subheader("No neighbourhood left out")
        st.caption(
            "Minimum group access across all modeled scenarios; each group's worst "
            "case can occur in a different scenario."
        )
        fig = go.Figure(
            go.Bar(
                x=list(metrics.group_access),
                y=problem.groups,
                orientation="h",
                marker_color=[
                    GOLD if v == min(metrics.group_access) else GREEN for v in metrics.group_access
                ],
                text=[f"{v:.1%}" for v in metrics.group_access],
                textposition="outside",
                hovertemplate="%{y}: %{x:.1%}<extra></extra>",
            )
        )
        style(fig, 285)
        fig.update_xaxes(
            range=[0, min(1, max(metrics.group_access) * 1.3 + 0.03)], tickformat=".0%"
        )
        fig.update_yaxes(autorange="reversed")
        st.plotly_chart(fig, use_container_width=True, key="groups")
        st.markdown("**The resilience gap**")
        st.write(
            f"Nominal access is **{metrics.nominal_access:.1%}**. Under the hardest modeled "
            f"scenario it falls to **{metrics.robust_access:.1%}**. The optimizer evaluates "
            "that harder case when comparing plans."
        )
        st.caption(
            "100% would mean every demand cluster has an available hub at zero walking "
            "distance. Access declines linearly to zero at the walking-range limit."
        )

with tradeoffs:
    st.subheader("Better is a choice, not a single number")
    st.write(
        "Each dot is a plan the search could not improve in all objectives at once. "
        "A higher, darker dot improves access and equity; a dot further left costs less."
    )
    fig = go.Figure(
        go.Scatter(
            x=[c.metrics.cost for c in run.archive],
            y=[c.metrics.robust_access for c in run.archive],
            mode="markers",
            name="Pareto plan",
            marker=dict(
                size=11,
                color=[c.metrics.equitable_access for c in run.archive],
                colorscale=[[0, "#e0c78d"], [1, GREEN]],
                showscale=True,
                colorbar=dict(title="Equity", tickformat=".0%"),
            ),
            text=[
                f"Plan {i + 1:02}<br>Equity {c.metrics.equitable_access:.1%}"
                for i, c in enumerate(run.archive)
            ],
            hovertemplate="%{text}<br>Cost %{x:.0f}<br>Robust access %{y:.1%}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[metrics.cost],
            y=[metrics.robust_access],
            mode="markers",
            name="Selected plan",
            marker=dict(size=23, symbol="circle-open", color=DARK, line=dict(width=3)),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[baseline.metrics.cost],
            y=[baseline.metrics.robust_access],
            mode="markers",
            name="Greedy baseline",
            marker=dict(size=14, symbol="x", color="#b36148"),
        )
    )
    style(fig, 420)
    fig.update_xaxes(title="Cost · planning units")
    fig.update_yaxes(title="Worst-scenario heat-weighted access", tickformat=".0%")
    st.plotly_chart(fig, use_container_width=True, key="pareto")
    if st.button("Compare with equal-budget random search"):
        with st.spinner("Sampling random feasible plans…"):
            random_run = sample_random(city, hubs, budget, radius, run.evaluation_calls, seed)
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Method": "NSGA-II",
                        "Hypervolume": hypervolume([c.objectives for c in run.archive]),
                        "Scoring calls": run.evaluation_calls,
                        "Unique plans": run.unique_evaluations,
                    },
                    {
                        "Method": "Random search",
                        "Hypervolume": hypervolume([c.objectives for c in random_run.archive]),
                        "Scoring calls": random_run.evaluation_calls,
                        "Unique plans": random_run.unique_evaluations,
                    },
                    {
                        "Method": "Greedy",
                        "Hypervolume": hypervolume([baseline.objectives]),
                        "Scoring calls": greedy_calls,
                        "Unique plans": greedy_calls,
                    },
                ]
            ),
            hide_index=True,
            use_container_width=True,
        )
        st.caption(
            "Higher hypervolume is better. Fixed reference (1,1,1); objectives are "
            "(1 − robust access, 1 − worst-group access, cost / budget). Duplicate "
            "scoring calls count toward the search budget. Greedy includes partial sets."
        )

with lab:
    st.subheader("From a bit string to a city plan")
    st.markdown(
        "".join(
            f'<span class="gene {"on" if bit else ""}">{escape(s.id)}<br><b>{bit}</b></span>'
            for s, bit in zip(city.sites, chosen.genome, strict=True)
        ),
        unsafe_allow_html=True,
    )
    st.caption("1 = open a hub · 0 = leave this site unselected")
    first, second = st.columns(2, gap="large")
    with first:
        st.markdown("**Evolution, with hard constraints**")
        st.markdown(
            "1. Initialize random binary plans and repair count and budget.\n"
            "2. Rank plans by Pareto dominance and crowding distance.\n"
            "3. Select parents by binary tournament.\n"
            "4. Apply uniform crossover and swap mutation; repair again.\n"
            "5. Keep an elite population and archive every non-dominated discovery."
        )
        st.caption(
            f"{run.evaluation_calls:,} scoring calls · {run.unique_evaluations:,} unique "
            f"plans · mutation probability 0.35 per child · seed {seed}"
        )
    with second:
        fig = go.Figure(
            go.Scatter(
                x=[h["generation"] for h in run.history],
                y=[h["hypervolume"] for h in run.history],
                mode="lines",
                line=dict(color=GREEN, width=3),
                fill="tozeroy",
                fillcolor="rgba(19,123,103,.08)",
                name="Archive hypervolume",
            )
        )
        style(fig, 270)
        fig.update_xaxes(title="Generation")
        fig.update_yaxes(title="Archive hypervolume")
        st.plotly_chart(fig, use_container_width=True, key="convergence")
    st.info(
        "The frontier is the best found within a finite search budget. Global optimality "
        "is only verified by exhaustive enumeration on small test instances."
    )

with exports:
    st.subheader("Take the experiment with you")
    st.caption(city.provenance)
    export = {
        "city": city.to_dict(),
        "hubs": hubs,
        "budget": budget,
        "radius": radius,
        "config": asdict(Config(population, generations, seed=seed)),
        "preferences": preferences[preference],
        "selected_plan": candidate_dict(chosen, problem),
        "history": run.history,
    }
    one, two, three = st.columns(3)
    one.download_button(
        "Download selected plan · JSON",
        json.dumps(export, indent=2),
        file_name="coolhaven-plan.json",
        mime="application/json",
    )
    frame = pd.DataFrame(
        [
            {
                "plan": i + 1,
                "robust_access": c.metrics.robust_access,
                "worst_group_access": c.metrics.equitable_access,
                "cost": c.metrics.cost,
                "sites": ", ".join(
                    s.id for s, bit in zip(city.sites, c.genome, strict=True) if bit
                ),
            }
            for i, c in enumerate(run.archive)
        ]
    )
    two.download_button(
        "Download frontier · CSV",
        frame.to_csv(index=False),
        file_name="coolhaven-frontier.csv",
        mime="text/csv",
    )
    three.download_button(
        "Download city · JSON",
        json.dumps(city.to_dict(), indent=2),
        file_name="coolhaven-city.json",
        mime="application/json",
    )
    st.dataframe(frame, hide_index=True, use_container_width=True)
    st.markdown("**What the model leaves out**")
    st.write(
        "No capacities, opening hours, street networks, measured temperatures, travel safety "
        "or empirical outage probabilities. Costs are abstract planning units. Every demand "
        "cluster uses its most accessible available hub; people are not assigned to finite "
        "seats. Group labels are synthetic and are not demographic classifications."
    )

st.markdown(
    '<div class="footnote">COOLHAVEN / A transparent optimization experiment. '
    "Built around binary genomes, explicit assumptions and reproducible search budgets.</div>",
    unsafe_allow_html=True,
)
