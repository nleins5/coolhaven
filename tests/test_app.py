"""Exercise the actual Streamlit script without a browser or server."""

from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_dashboard_renders_and_preferences_do_not_crash():
    app = AppTest.from_file(str(Path(__file__).parents[1] / "app.py"), default_timeout=60)
    app.run()
    assert not app.exception
    assert len(app.metric) == 4
    assert app.metric[3].value == "5 / 5"
    # Selectboxes: sidebar population, preference, plan, scenario.
    preference = next(s for s in app.selectbox if s.label == "Decision preference")
    preference.select("Equity first").run()
    assert not app.exception
    app.toggle[0].set_value(False).run()
    assert not app.exception
