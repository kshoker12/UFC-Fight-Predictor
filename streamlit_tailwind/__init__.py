from pathlib import Path
from typing import Optional

import streamlit.components.v1 as components

# Tell Streamlit that there is a component called streamlit_tailwind,
# and that the code to display that component is in the "frontend" folder.
frontend_dir = (Path(__file__).parent / "frontend").absolute()
_component_func = components.declare_component("st_tw", path=str(frontend_dir))


def st_tw(
    text: str,
    height: Optional[int] = 100,
    key: Optional[str] = None,
):
    """
    Render the provided Tailwind HTML (passed as `text`) inside a Streamlit component.
    """

    return _component_func(text=text, height=height, key=key)

