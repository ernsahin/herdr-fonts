"""Optional iTerm2 API integration, isolated so the picker has a bounded timeout."""
import json
import sys


async def perform(connection):
    app = await iterm2.async_get_app(connection)
    operation = sys.argv[1]
    if operation == "capture":
        window = app.current_terminal_window
        session = window.current_tab.current_session if window and window.current_tab else None
    else:
        session = app.get_session_by_id(sys.argv[2])
    if session is None:
        raise RuntimeError("No matching iTerm2 session. Open/select the intended session first.")
    profile = await session.async_get_profile()
    if operation == "write":
        await profile.async_set_normal_font(sys.argv[3])
        profile = await session.async_get_profile()
    print(json.dumps({"target": session.session_id, "font": profile.normal_font}))


if __name__ == "__main__":
    try:
        import iterm2
    except ImportError:
        sys.exit("iTerm2 needs the optional iterm2 package in this Python environment. "
                 "See README.md for virtualenv setup; enable iTerm2 Settings > General > Magic > Python API.")
    try:
        iterm2.run_until_complete(perform)
    except Exception as exc:
        sys.exit(f"iTerm2 API: {exc}")
