import time
import random
import re
from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter
from config import logger

router = APIRouter(prefix="/api/obd", tags=["obd"])

# Global dictionary keeping track of simulated Porsche vehicle telemetry state
OBD_TELEMETRY_STATE = {
    "rpm": 800.0,
    "speed": 0.0,
    "temp": 90.0,
    "tps": 0.0,
    "pasm": 30.0,
    "exhaust_valve": False,
    "dtcs": []  # List of dicts, e.g. [{"code": "P0300", "description": "Random/Multiple Cylinder Misfire Detected"}]
}

class ObdMetricsUpdate(BaseModel):
    rpm: Optional[float] = None
    speed: Optional[float] = None
    temp: Optional[float] = None
    tps: Optional[float] = None
    pasm: Optional[float] = None
    exhaust_valve: Optional[bool] = None

class DtcTriggerRequest(BaseModel):
    code: str
    description: str

@router.get("/metrics")
def get_obd_metrics():
    """Retrieve current simulated OBD-II and vehicle metrics."""
    return OBD_TELEMETRY_STATE

@router.post("/metrics")
def update_obd_metrics(metrics: ObdMetricsUpdate):
    """Update active simulated telemetry metrics."""
    global OBD_TELEMETRY_STATE
    if metrics.rpm is not None:
        OBD_TELEMETRY_STATE["rpm"] = max(0.0, min(9000.0, metrics.rpm))
    if metrics.speed is not None:
        OBD_TELEMETRY_STATE["speed"] = max(0.0, min(350.0, metrics.speed))
    if metrics.temp is not None:
        OBD_TELEMETRY_STATE["temp"] = max(0.0, min(140.0, metrics.temp))
    if metrics.tps is not None:
        OBD_TELEMETRY_STATE["tps"] = max(0.0, min(100.0, metrics.tps))
    if metrics.pasm is not None:
        OBD_TELEMETRY_STATE["pasm"] = max(0.0, min(100.0, metrics.pasm))
    if metrics.exhaust_valve is not None:
        OBD_TELEMETRY_STATE["exhaust_valve"] = metrics.exhaust_valve
    
    logger.info(f"OBD telemetry metrics updated: {OBD_TELEMETRY_STATE}")
    return {"status": "updated", "metrics": OBD_TELEMETRY_STATE}

@router.get("/dtcs")
def get_obd_dtcs():
    """Retrieve active Diagnostic Trouble Codes (DTCs)."""
    return {"dtcs": OBD_TELEMETRY_STATE["dtcs"]}

@router.post("/dtc/trigger")
def trigger_obd_dtc(request: DtcTriggerRequest):
    """Trigger/simulate a new Diagnostic Trouble Code (DTC)."""
    global OBD_TELEMETRY_STATE
    if not any(d["code"] == request.code for d in OBD_TELEMETRY_STATE["dtcs"]):
        OBD_TELEMETRY_STATE["dtcs"].append({
            "code": request.code,
            "description": request.description
        })
        logger.warning(f"DTC triggered on vehicle simulator: {request.code} - {request.description}")
        return {"status": "triggered", "code": request.code, "dtcs": OBD_TELEMETRY_STATE["dtcs"]}
    return {"status": "exists", "dtcs": OBD_TELEMETRY_STATE["dtcs"]}

@router.post("/dtc/clear")
def clear_obd_dtcs():
    """Clear all active Diagnostic Trouble Codes (DTCs) from dashboard."""
    global OBD_TELEMETRY_STATE
    OBD_TELEMETRY_STATE["dtcs"] = []
    logger.info("Cleared all active DTCs from vehicle simulator.")
    return {"status": "cleared", "dtcs": []}

@router.get("/can-stream")
def get_can_stream():
    """
    Generates a mock list of 20 raw CAN-bus and OBD-II response frames
    based on the current active telemetry state.
    """
    # RPM raw OBD payload format: (A * 256 + B) / 4
    rpm_val = OBD_TELEMETRY_STATE["rpm"]
    rpm_raw = int(rpm_val * 4)
    rpm_a, rpm_b = divmod(rpm_raw, 256)
    
    # Speed raw OBD payload format: A (in km/h)
    speed_val = OBD_TELEMETRY_STATE["speed"]
    speed_a = int(speed_val)
    
    # Engine Coolant Temp raw OBD payload format: A - 40
    temp_val = OBD_TELEMETRY_STATE["temp"]
    temp_a = max(0, min(255, int(temp_val + 40)))
    
    # Throttle Position (TPS) raw OBD payload format: A * 100 / 255
    tps_val = OBD_TELEMETRY_STATE["tps"]
    tps_a = max(0, min(255, int(tps_val * 255 / 100)))
    
    # Build standard OBD/CAN response frames
    frames = [
        {"id": "0x18DAF110", "data": f"04 41 0C {rpm_a:02X} {rpm_b:02X} 00 00 00", "description": f"Engine Speed (RPM): {rpm_val:.0f}"},
        {"id": "0x18DAF110", "data": f"03 41 0D {speed_a:02X} 00 00 00 00 00 00", "description": f"Vehicle Speed (km/h): {speed_val:.0f}"},
        {"id": "0x18DAF110", "data": f"03 41 05 {temp_a:02X} 00 00 00 00 00 00", "description": f"Engine Coolant Temperature (°C): {temp_val:.1f}"},
        {"id": "0x18DAF110", "data": f"03 41 11 {tps_a:02X} 00 00 00 00 00 00", "description": f"Throttle Position Sensor (%): {tps_val:.0f}"}
    ]
    
    # Append PASM suspension status frame (custom CAN ID 0x130)
    pasm_val = int(OBD_TELEMETRY_STATE["pasm"] * 2.55)
    frames.append({"id": "0x00000130", "data": f"08 {pasm_val:02X} 00 00 00 00 00 00 00", "description": f"PASM Damper Setting: {OBD_TELEMETRY_STATE['pasm']:.0f}%"})
    
    # Append Exhaust Valve status frame (custom CAN ID 0x240)
    valv_bit = 0x01 if OBD_TELEMETRY_STATE["exhaust_valve"] else 0x00
    frames.append({"id": "0x00000240", "data": f"02 {valv_bit:02X} 00 00 00 00 00 00 00", "description": f"Exhaust Valve Active: {'YES' if valv_bit else 'NO'}"})
    
    # Active DTC frames
    dtcs = OBD_TELEMETRY_STATE["dtcs"]
    if dtcs:
        for d in dtcs:
            code = d["code"]
            match = re.search(r'\d+', code)
            num_part = int(match.group(0)) if match else 300
            high_byte = 0x03 if code.startswith("P") else 0x13
            low_byte = num_part % 256
            frames.append({
                "id": "0x18DAF110",
                "data": f"04 43 01 {high_byte:02X} {low_byte:02X} 00 00 00",
                "description": f"Pending Trouble Code (DTC): {code} ({d['description']})"
            })
    else:
        frames.append({"id": "0x18DAF110", "data": "02 43 00 00 00 00 00 00 00 00", "description": "No Diagnostic Trouble Codes stored"})
        
    bg_ids = ["0x00000100", "0x00000120", "0x000001B0", "0x00000320", "0x00000450", "0x000005F2"]
    for i in range(13):
        cid = random.choice(bg_ids)
        bytes_data = " ".join(f"{random.randint(0, 255):02X}" for _ in range(8))
        frames.append({"id": cid, "data": f"08 {bytes_data}", "description": "Background CAN-bus Broadcast Frame"})
        
    metadata_frames = frames[:6]
    rest_frames = frames[6:]
    random.shuffle(rest_frames)
    
    all_frames = metadata_frames + rest_frames
    return {"timestamp": time.time(), "frames": all_frames[:20]}
