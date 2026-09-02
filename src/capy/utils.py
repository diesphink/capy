def format_time(seconds, padminutes=True):
    if seconds == 0:
        return "--:--"
    minutes, secs = divmod(int(seconds), 60)
    if padminutes:
        return f"{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes}:{secs:02d}"
