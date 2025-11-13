import time
import hashlib
import numpy as np
from alpaca.camera import Camera

ADDRESS = "127.0.0.1:11113"
CAM_ID = 0

NUM_EXPOSURES = 5
EXPOSURE_TIME = 1.0      # seconds for each quick test exposure
POLL_INTERVAL = 0.08     # seconds between polls of CameraState/ImageReady
TIMEOUT_FACTOR = 3.0     # timeout = max(60s, exposure_time * TIMEOUT_FACTOR)
READ_RETRIES = 3
READ_RETRY_BACKOFF = 0.5

def fingerprint_image(arr):
    """Return small fingerprint: shape, mean, and md5 of a downsampled byte view."""
    try:
        a = np.asarray(arr)
        shape = a.shape
        mean = float(a.mean()) if a.size else None
        # create tiny digest: downsample to at most 256 values to avoid huge md5s
        flat = a.ravel()
        if flat.size == 0:
            digest = None
        else:
            # sample evenly up to 256 elements
            step = max(1, flat.size // 256)
            sample = flat[::step].astype(np.int64).tobytes()
            digest = hashlib.md5(sample).hexdigest()
        return {"shape": shape, "mean": mean, "md5": digest}
    except Exception as e:
        return {"error": str(e)}

def safe_get(obj, attr, default=None):
    try:
        return getattr(obj, attr)
    except Exception:
        return default

def probe_camera(address=ADDRESS, cam_id=CAM_ID,
                 exposures=NUM_EXPOSURES, exposure_time=EXPOSURE_TIME,
                 poll_interval=POLL_INTERVAL):
    logs = []
    try:
        cam = Camera(address, cam_id)
    except Exception as e:
        print(f"[ERROR] Creating Camera object: {e}")
        return

    # connect if needed
    try:
        if not cam.Connected:
            cam.Connected = True
            time.sleep(0.2)
    except Exception as e:
        print(f"[ERROR] Connecting camera: {e}")
        return

    # check optional capabilities once
    supports_percent = True
    try:
        _ = cam.PercentCompleted
    except Exception:
        supports_percent = False

    # fetch camera geometry if available
    numx = safe_get(cam, "NumX", None)
    numy = safe_get(cam, "NumY", None)
    print(f"[INFO] Connected: {cam.Connected}, NumX={numx}, NumY={numy}, supports_percent={supports_percent}")

    for i in range(1, exposures + 1):
        exposure_log = {
            "exp_index": i,
            "events": []
        }
        try:
            # attempt to clear any stale ImageReady by reading ImageArray only if ready
            try:
                if safe_get(cam, "ImageReady", False):
                    # capture a fingerprint so we can compare later
                    arr = None
                    try:
                        arr = cam.ImageArray
                    except Exception:
                        arr = None
                    exposure_log["events"].append(("preprobe_image_ready", time.time(), fingerprint_image(arr)))
            except Exception:
                pass

            # Start exposure
            t_start = time.time()
            exposure_log["events"].append(("StartExposure", t_start, {"exposure_time": exposure_time}))
            try:
                cam.StartExposure(exposure_time, True)
            except Exception as e:
                exposure_log["events"].append(("StartExposure_error", time.time(), str(e)))
                logs.append(exposure_log)
                print(f"[ERROR] StartExposure failed on attempt {i}: {e}")
                continue

            # watch/poll loop
            timeout = max(60.0, exposure_time * TIMEOUT_FACTOR)
            last_state = None
            last_image_ready = None
            percent_logged_once = False

            while True:
                t_now = time.time()
                elapsed = t_now - t_start

                # CameraState
                try:
                    cs = cam.CameraState
                    cs_name = cs.name if hasattr(cs, "name") else str(cs)
                except Exception as e:
                    cs_name = f"<err:{e}>"

                # PercentCompleted optional
                pct = None
                if supports_percent:
                    try:
                        pct = cam.PercentCompleted
                    except Exception:
                        # mark unsupported to avoid spamming
                        supports_percent = False
                        pct = None

                # ImageReady
                try:
                    ir = bool(cam.ImageReady)
                except Exception:
                    ir = None

                # record state changes only
                if cs_name != last_state:
                    exposure_log["events"].append(("CameraState", t_now, cs_name))
                    last_state = cs_name
                if ir != last_image_ready:
                    exposure_log["events"].append(("ImageReady", t_now, bool(ir)))
                    last_image_ready = ir

                # log percent once per exposure if available
                if pct is not None and not percent_logged_once:
                    exposure_log["events"].append(("PercentCompleted_initial", t_now, float(pct)))
                    percent_logged_once = True

                # Break conditions:
                # 1) ImageReady True -> proceed to read
                if ir is True:
                    exposure_log["events"].append(("ImageReady_true_at", t_now, {"elapsed": elapsed}))
                    break

                # 2) CameraState indicates idle/reading/download -> attempt to read
                if cs_name and any(k in cs_name.lower() for k in ("idle", "download", "reading")):
                    exposure_log["events"].append(("State_indicates_ready", t_now, cs_name))
                    break

                # 3) Timeout
                if elapsed > timeout:
                    exposure_log["events"].append(("timeout", t_now, {"elapsed": elapsed, "timeout": timeout}))
                    try:
                        cam.AbortExposure()
                        exposure_log["events"].append(("AbortExposure_called", time.time(), None))
                    except Exception as e:
                        exposure_log["events"].append(("AbortExposure_failed", time.time(), str(e)))
                    raise RuntimeError(f"Exposure timeout after {elapsed:.1f}s")

                time.sleep(poll_interval)

            # try reading the image with retries
            read_exc = None
            img = None
            for attempt in range(1, READ_RETRIES + 1):
                try:
                    arr = cam.ImageArray
                    if arr is None:
                        raise RuntimeError("Driver returned None for ImageArray")
                    img = np.array(arr)
                    # transpose if 2D (driver-specific)
                    if img.ndim == 2:
                        img = img.transpose()
                    exposure_log["events"].append(("ImageRead_success", time.time(), fingerprint_image(img)))
                    break
                except Exception as e:
                    read_exc = e
                    exposure_log["events"].append(("ImageRead_failed", time.time(), {"attempt": attempt, "error": str(e)}))
                    if attempt < READ_RETRIES:
                        time.sleep(READ_RETRY_BACKOFF * attempt)
                    else:
                        raise

        except Exception as overall_e:
            exposure_log["events"].append(("exposure_exception", time.time(), str(overall_e)))
            print(f"[ERROR] Exposure {i} raised exception: {overall_e}")

        logs.append(exposure_log)
        # short pause between exposures to let driver settle
        time.sleep(0.25)

    # Print compact summary
    for e in logs:
        idx = e["exp_index"]
        print(f"\n=== Exposure {idx} summary ===")
        for ev in e["events"]:
            name, ts, info = ev
            tstr = time.strftime("%H:%M:%S", time.localtime(ts)) + f".{int((ts%1)*1000):03d}"
            print(f"{tstr} | {name} | {info}")
    return logs


if __name__ == "__main__":
    probe_camera()

