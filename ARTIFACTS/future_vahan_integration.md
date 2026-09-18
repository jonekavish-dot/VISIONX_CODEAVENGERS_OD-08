# IVACS V-TRACE: Production VAHAN / Parivahan Integration Architecture

**Project:** IVACS V-TRACE (Vehicle Trust, Route & Evidence Engine)  
**Problem Statement:** OD-08 — License Plate Detection and Recognition from Construction-Site CCTV Footage  
**Standard:** Ministry of Road Transport & Highways (MoRTH) — National Informatics Centre (NIC) VAHAN 4.0 API Integration  

---

## 1. Architectural Separation: Demo Registry vs. Production VAHAN

In compliance with hackathon evaluation guidelines and legal privacy mandates:
* **Current State (Hackathon MVP):** Employs `DemoVehicleRegistry` backed by local SQLite persistence. It simulates official RTO response structures without unauthorized web scraping, fake credentials, or simulated government claims.
* **Production State:** Seamlessly activates `VahanVehicleRegistry` implementing the identical abstract interface `VehicleRegistry`. Zero changes are required in the core CV, OCR, or alert engines.

```
       +-----------------------------------------------------------------+
       |               VehicleRegistry (Abstract Base Class)             |
       |             async def get_vehicle(plate_number: str)            |
       +-----------------------------------------------------------------+
                                      |
                 +--------------------+--------------------+
                 |                                         |
                 v                                         v
   +---------------------------+             +---------------------------+
   |    DemoVehicleRegistry    |             |   VahanVehicleRegistry    |
   | (Active in Hackathon MVP) |             |  (Enterprise Production)  |
   |   Local SQLite Database   |             |   NIC Gateway / MoRTH     |
   +---------------------------+             +---------------------------+
```

---

## 2. Production VAHAN 4.0 API Integration Architecture

In enterprise deployments on major infrastructure projects (e.g., National Highways Authority of India - NHAI, Smart Cities, or Airport Terminal Construction), site operators obtain authorized enterprise API credentials from the **National Informatics Centre (NIC)** under MoRTH guidelines.

```
+------------------+          +-------------------+          +------------------+
|   IVACS Edge     |  mTLS    |  Corporate Proxy  |  HTTPS   |   NIC / MoRTH    |
| V-TRACE Instance | -------->| & HSM / PKI Sign  | -------->|    VAHAN 4.0     |
| (Site CAM Gate)  |          | (Token & Caching) |          |  National Cloud  |
+------------------+          +-------------------+          +------------------+
```

### 2.1 Security & Authentication Handshake
1. **Mutual Transport Layer Security (mTLS):** Bi-directional X.509 certificate authentication between client and the NIC Parivahan gateway.
2. **Digital Signature Certificates (DSC):** Request payloads are signed using a Class 3 Organization Digital Signature Certificate (PKI) stored in a hardware security module (HSM) or encrypted keystore.
3. **OAuth 2.0 / Bearer Tokens:** Time-limited JWT access tokens (1-hour expiry) acquired through NIC's SSO/Identity Provider using authorized Client ID & Secret.

---

## 3. Data Schema & Field Mapping

The production `VahanVehicleRegistry` maps NIC VAHAN 4.0 JSON responses directly to our internal `VehicleRegistryRecord` schema:

```json
{
  "rc_regn_no": "TN01AB1234",
  "rc_vch_catg": "COMMERCIAL_TRANSPORT",
  "rc_vh_class": "Heavy Goods Vehicle (HGV) / Tipper",
  "rc_maker_model": "TATA MOTORS LTD / PRIMA 2830.K",
  "rc_color": "CANARY YELLOW",
  "rc_fuel_desc": "DIESEL",
  "rc_regn_dt": "2021-04-15",
  "rc_fit_upto": "2026-04-14",
  "rc_insurance_upto": "2025-11-30",
  "rc_pucc_upto": "2025-05-20",
  "rc_status": "ACTIVE",
  "rc_blacklist_status": "CLEAR",
  "rc_permit_no": "TN/GOODS/2021/8932",
  "rc_permit_type": "ALL INDIA GOODS PERMIT",
  "rc_permit_valid_upto": "2026-04-14"
}
```

### Internal Field Mapping:

| NIC VAHAN Field | IVACS Schema Field | Consistency Check Utility |
|---|---|---|
| `rc_regn_no` | `plate_number` | Primary key lookup & plate normalization |
| `rc_vh_class` | `vehicle_type` | Mapped to coarse class (`truck`, `bus`, `car`, `motorcycle`) |
| `rc_maker_model` | `vehicle_make` / `vehicle_model` | Secondary visual fingerprint validation |
| `rc_color` | `color` | Dominant color extraction comparison |
| `rc_fit_upto` | `fitness_valid_upto` | Automated entry denial for expired fitness certificates |
| `rc_status` | `rc_status` | Immediate security alert if `SUSPENDED` or `BLACKLISTED` |

---

## 4. Privacy, DPDP Act 2023 Compliance & Edge Caching

### 4.1 Digital Personal Data Protection (DPDP) Act Compliance
* **PII Masking at the Ingestion Boundary:** Citizen personal identification is strictly masked. Owner names are received as `K**** S****` and phone numbers as `******9812`.
* **Zero PII Storage:** IVACS V-TRACE never writes unmasked citizen personal data to local database tables or evidence logs. Only technical vehicle attributes (class, make, model, color, validity) are retained.
* **Purpose Limitation:** In accordance with Section 6 of the DPDP Act, data is accessed solely for the specified purpose of authorized construction perimeter security and workplace safety compliance.

### 4.2 Local Edge Caching Architecture
To maintain sub-50ms gate transaction times and avoid overwhelming national NIC infrastructure:
* **Cache-Aside Pattern:** When a plate is first scanned, `VahanVehicleRegistry` checks a local Redis or SQLite cache.
* **Time-to-Live (TTL):** Static attributes (make, model, color, class) are cached with a **24-hour TTL**. Dynamic statuses (e.g., active blacklist or permit revocations) are checked against a real-time invalidation webhook or an hourly sync.
* **Offline Fallback:** If site internet connectivity fails, the system smoothly falls back to cached records and emits a `TELEMETRY_OFFLINE` advisory while continuing native visual fingerprinting.

---

## 5. Seamless Switchover Guide

To switch from the demo registry to the production VAHAN connector in a live installation:

1. Update `.env` or application configuration:
   ```ini
   REGISTRY_BACKEND=vahan
   VAHAN_API_GATEWAY=https://parivahan.gov.in/api/v4/vehicle-details
   VAHAN_CLIENT_ID=SITE_NHAI_CHENNAI_08
   VAHAN_CLIENT_SECRET=YOUR_ENTERPRISE_SECRET_KEY
   VAHAN_KEYSTORE_PATH=/etc/vtrace/pki/client_cert.p12
   ```
2. In `backend/vehicle_registry/registry_service.py`:
   ```python
   # The service factory dynamically selects the configured registry
   if settings.REGISTRY_BACKEND == "vahan":
       from backend.vehicle_registry.vahan_registry import VahanVehicleRegistry
       registry = VahanVehicleRegistry(
           gateway_url=settings.VAHAN_API_GATEWAY,
           client_id=settings.VAHAN_CLIENT_ID,
           secret=settings.VAHAN_CLIENT_SECRET
       )
   else:
       from backend.vehicle_registry.demo_registry import DemoVehicleRegistry
       registry = DemoVehicleRegistry()
   ```
3. All downstream systems (`check_consistency`, `AlertService`, `Command Center Dashboard`) continue operating without any code modifications.
