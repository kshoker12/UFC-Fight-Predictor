// The `Streamlit` object exists because our html file includes
// `streamlit-component-lib.js`.
//
// If you get an error about "Streamlit" not being defined, that
// means you're missing that file.

function sendValue(value) {
  Streamlit.setComponentValue(value)
}

/**
 * The component's render function. This will be called immediately after
 * the component is initially loaded, and then again every time the
 * component gets new data from Python.
 */
function onRender(event) {
  const { text } = event.detail.args

  const html_text = document.getElementById("html_text")
  if (!html_text) return

  html_text.innerHTML = text ?? ""

  // Auto-size: fit the component frame to the rendered DOM height.
  // We use `getBoundingClientRect().height` so CSS `max-height` behaves correctly.
  if (window.__st_tw_resizeObserver) {
    try {
      window.__st_tw_resizeObserver.disconnect()
    } catch (e) {
      // Ignore observer cleanup errors
    }
    window.__st_tw_resizeObserver = null
  }

  let lastHeight = null
  const setHeightFromDom = () => {
    const rect = html_text.getBoundingClientRect()
    const nextHeight = Math.ceil(rect.height)
    if (nextHeight && nextHeight !== lastHeight) {
      lastHeight = nextHeight
      Streamlit.setFrameHeight(nextHeight)
    }
  }

  // Initial measurement after layout.
  requestAnimationFrame(() => {
    setHeightFromDom()

    // Keep updating as the layout changes (responsive wrapping, fonts, etc.).
    if (typeof ResizeObserver !== "undefined") {
      window.__st_tw_resizeObserver = new ResizeObserver(() => {
        setHeightFromDom()
      })
      window.__st_tw_resizeObserver.observe(html_text)
    } else {
      // Fallback: at least update on resize events.
      window.addEventListener("resize", setHeightFromDom)
    }
  })
}

// Render the component whenever python send a "render event"
Streamlit.events.addEventListener(Streamlit.RENDER_EVENT, onRender)
// Tell Streamlit that the component is ready to receive events
Streamlit.setComponentReady()
// Render with the correct height, if this is a fixed-height component
// Streamlit.setFrameHeight(100)

