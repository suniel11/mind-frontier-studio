from __future__ import annotations


def compose_motion_filter(scene, frames: int, fps: int, width: int, height: int) -> str:
    motion = str(getattr(scene, "motion_type", "cinematic_push"))
    intensity = int(getattr(scene, "emotional_intensity", 6) or 6)
    hook = int(getattr(scene, "number", 0)) == 1

    speed = 0.00048 + min(10, max(1, intensity)) * 0.000035
    max_zoom = 1.12 if hook else 1.085

    if motion in {"cinematic_pull", "dolly_out"}:
        zoom = f"if(eq(on,1),{max_zoom},max(1.015,zoom-{speed:.6f}))"
        x = "iw/2-(iw/zoom/2)+3*sin(on/35)"
        y = "ih/2-(ih/zoom/2)+2*cos(on/41)"
    elif motion in {"slow_pan_left", "pan_left", "parallax_left"}:
        zoom = "1.075"
        x = f"max(0,(iw-iw/zoom)*(1-on/{max(1, frames)}))+3*sin(on/32)"
        y = "ih/2-(ih/zoom/2)+2*cos(on/45)"
    elif motion in {"slow_pan_right", "pan_right", "parallax_right"}:
        zoom = "1.075"
        x = f"min(iw-iw/zoom,(iw-iw/zoom)*(on/{max(1, frames)}))+3*sin(on/32)"
        y = "ih/2-(ih/zoom/2)+2*cos(on/45)"
    elif motion == "tilt_up":
        zoom = "1.07"
        x = "iw/2-(iw/zoom/2)"
        y = f"max(0,(ih-ih/zoom)*(1-on/{max(1, frames)}))"
    elif motion == "tilt_down":
        zoom = "1.07"
        x = "iw/2-(iw/zoom/2)"
        y = f"min(ih-ih/zoom,(ih-ih/zoom)*(on/{max(1, frames)}))"
    elif motion == "drift":
        zoom = "1.05+0.004*sin(on/36)"
        x = "iw/2-(iw/zoom/2)+9*sin(on/23)"
        y = "ih/2-(ih/zoom/2)+6*cos(on/29)"
    elif motion == "micro_push":
        zoom = "min(zoom+0.00032,1.05)"
        x = "iw/2-(iw/zoom/2)+3*sin(on/38)"
        y = "ih/2-(ih/zoom/2)"
    elif motion == "static":
        zoom = "1.025"
        x = "iw/2-(iw/zoom/2)"
        y = "ih/2-(ih/zoom/2)"
    else:
        zoom = f"min(zoom+{speed:.6f},{max_zoom})"
        x = "iw/2-(iw/zoom/2)+3*sin(on/39)"
        y = "ih/2-(ih/zoom/2)+2*cos(on/47)"

    return (
        "scale=1240:2200,"
        "zoompan="
        f"z='{zoom}':"
        f"x='{x}':"
        f"y='{y}':"
        f"d={frames}:"
        f"s={width}x{height}:"
        f"fps={fps},"
        "eq=contrast=1.055:brightness=-0.008:saturation=0.92:gamma=0.99,"
        "unsharp=5:5:0.38:5:5:0,"
        "vignette=PI/5,"
        "noise=alls=2.2:allf=t+u,"
        "format=yuv420p"
    )
